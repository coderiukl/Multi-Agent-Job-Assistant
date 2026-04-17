import asyncio
import logging

from langchain_core.messages import SystemMessage, HumanMessage

from app.agents.state import AgentState
from app.core.llm import get_llm, get_llm_no_stream
from app.services.scrapers.topcv import TopCVScraper
from app.services.scrapers.itviec import ITviecScraper
from app.services.job_matcher import JobMatcherService
from app.workers.scraper_worker import embed_and_upsert_jobs

logger = logging.getLogger(__name__)

KEYWORD_EXTRACT_PROMPT = """
Trích xuất từ khóa tìm việc từ câu của user.
Chỉ trả về tên vị trí / ngành nghề (VD: "python developer", "marketing manager", "kế toán").
KHÔNG trả về các từ: "cv", "việc", "tìm việc", "job".
Nếu không xác định được vị trí cụ thể, trả về "software engineer".
Không giải thích, không thêm ký tự thừa.
"""


async def _extract_keyword(message: str) -> str:
    """Dùng LLM extract keyword tìm việc từ message của user."""
    llm = get_llm_no_stream()
    res = await llm.ainvoke([
        SystemMessage(content=KEYWORD_EXTRACT_PROMPT),
        HumanMessage(content=message),
    ])
    print(f"[keyword] raw response: {res!r}")
    print(f"[keyword] content: '{res.content}'")
    return res.content.strip()


async def matcher_node(state: AgentState) -> AgentState:
    cv_id = state.get("cv_id", "")
    if not cv_id:
        return {**state, "matched_jobs": [], "match_error": "Không tìm thấy CV"}

    # ── Extract keyword nếu chưa có trong state ──────────────
    keyword = state.get("search_keyword", "")
    if not keyword:
        last_message = state["messages"][-1].content
        try:
            keyword = await _extract_keyword(last_message)
            logger.info("[matcher] extracted keyword='%s'", keyword)
        except Exception as e:
            logger.warning("[matcher] keyword extraction failed: %s", e)
            keyword = ""

    if not keyword:
        logger.warning("[matcher] keyword is empty, cannot search jobs")
        return {**state, "matched_jobs": [], "match_error": "Không thể xác định từ khóa tìm việc"}

    location = state.get("search_location", "hcm")
    matcher  = JobMatcherService()

    # ── Chạy song song: web scrape + DB search ───────────────
    web_jobs, db_jobs = await asyncio.gather(
        _search_web(keyword, location, cv_id, matcher),
        matcher.match_from_db(str(cv_id), top_k=5),
    )

    # ── Merge + deduplicate theo URL ─────────────────────────
    seen_urls: set[str] = set()
    merged: list[dict] = []
    for job in web_jobs + db_jobs:
        url = job.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            merged.append(job)

    # ── Re-rank theo score giảm dần ──────────────────────────
    merged.sort(key=lambda x: x.get("score") or 0.0, reverse=True)

    logger.info(
        "[matcher] keyword='%s' → web=%d, db=%d, merged=%d",
        keyword, len(web_jobs), len(db_jobs), len(merged),
    )

    return {
        **state,
        "search_keyword": keyword,   # lưu lại vào state để dùng sau nếu cần
        "matched_jobs":   merged,
        "web_count":      len(web_jobs),
        "db_count":       len(db_jobs),
    }


async def _search_web(
    keyword: str,
    location: str,
    cv_id: str,
    matcher: JobMatcherService,
) -> list[dict]:
    # ── Scrape TopCV + ITviec song song ──────────────────────
    topcv_result, itviec_result = await asyncio.gather(
        TopCVScraper().search(keyword, location, limit=10),
        ITviecScraper().search(keyword, location, limit=10),
        return_exceptions=True,
    )

    raw_jobs = []
    if isinstance(topcv_result, list):  raw_jobs.extend(topcv_result)
    if isinstance(itviec_result, list): raw_jobs.extend(itviec_result)

    if not raw_jobs:
        logger.warning("[matcher] web scrape returned 0 jobs for keyword='%s'", keyword)
        return []

    # ── Embed + upsert vào Qdrant ────────────────────────────
    upserted = await embed_and_upsert_jobs(raw_jobs, limit=20)

    # ── Tính score so với CV ─────────────────────────────────
    job_ids   = [j["id"] for j in upserted]
    scored    = await matcher.score_web_jobs(str(cv_id), job_ids)
    score_map = {j["id"]: j["score"] for j in scored}

    for job in upserted:
        job["score"] = score_map.get(job["id"], 0.0)

    return upserted