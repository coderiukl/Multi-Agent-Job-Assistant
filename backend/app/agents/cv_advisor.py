from app.agents.state import AgentState
from app.core.llm import get_llm
from app.services.qdrant_services import search_similar
from app.services.embedding_service import _get_model
from langchain_core.messages import SystemMessage, HumanMessage
import asyncio 

CV_ADVISOR_SYSTEM_PROMPT = """
Bạn là chuyên gia tư vấn CV với nhiều năm kinh nghiệm tuyển dụng tại Việt Nam.
Nhiệm vụ của bạn là phân tích CV của ứng viên và đưa ra lời khuyên cụ thể, thực tế.

Khi tư vấn, hãy:
1. Chỉ ra điểm mạnh của CV
2. Chỉ ra điểm yếu / thiếu sót cụ thể
3. Gợi ý cải thiện theo từng mục (Summary, Experience, Skills, Education)
4. Nếu user hỏi về vị trí cụ thể, so sánh CV với yêu cầu của vị trí đó

Trả lời bằng tiếng Việt, rõ ràng, có cấu trúc.
"""

async def cv_advisor_node(state: AgentState) -> AgentState:
    llm = get_llm()
    user_message = state['messages'][-1].content
    cv_id = state.get("cv_id")

    cv_context = ""
    if cv_id:
        try:
            loop = asyncio.get_running_loop()
            query_vector = await loop.run_in_executor(
                None, lambda: _get_model().encode(user_message).tolist()
            )

            chunks = await search_similar(
                vector=query_vector,
                top_k=5,
                file_id_filter=str(cv_id)
            )

            cv_context = "\n\n".join(c["content"] for c in chunks if c.get("content"))
        except Exception:
            cv_context = ""

    # Build context prompt
    context_block = (
        f"\n\n---\nNội dung CV của ứng viên:\n{cv_context}\n---"
        if cv_context
        else "\n\n(Chưa có nội dung CV — hãy yêu cầu user upload CV trước.)"
    )

    response = await llm.ainvoke([
        SystemMessage(content=CV_ADVISOR_SYSTEM_PROMPT + context_block),
        *state["messages"],  # toàn bộ lịch sử hội thoại
    ])

    return {
        **state,
        "messages": [*state["messages"], response],
        "response_type": "cv_advice",
    }

    