from __future__ import annotations

import logging
from collections import defaultdict

from sqlalchemy import select

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.embedding_service import _get_model
from app.services.qdrant_services import search_similar

logger = logging.getLogger(__name__)

def _embed_text(text: str) -> list[float]:
    model = _get_model()
    return model.encode(text, show_progress_bar=False).tolist()

async def search_cv_vs_jd(cv_file_id: str, jd_text: str, top_k: int = 10):
    """
    So sánh CV với 1 JD cụ thể.

    Returns:
        {
            "score": float,          # 0-1, cosine similarity trung bình top chunks
            "matching_chunks": [...] # các đoạn CV liên quan nhất
        }
    """
    jd_vector = _embed_text(jd_text)

    hits = await search_similar(
        vector=jd_vector,
        top_k=top_k,
        file_id_filter=cv_file_id,
    )

    if not hits:
        return {"score": 0.0, "matching_chunks": []}
    
    avg_score = sum(h["score"] for h in hits) / len(hits)

    return {
        "score": round(avg_score, 5),
        "matching_chunks": [
            {
                "content": h['content'],
                "score": round(h['score'], 5),
                "chunk_index": h["chunk_index"],
            }
            for h in hits
        ],
    }

async def get_cv_representative_vector(cv_file_id: str, db: AsyncSession) -> list[float] | None:
    """
    Tạo vector đại diện cho toàn bộ CV bằng cách average tất cả chunk vectors.
    Dùng để search jobs phù hợp với CV.
    """

    from app.db.models import FileChunk
    from qdrant_client.models import Filter, FieldCondition, MatchValue
    from app.services.qdrant_services import get_qdrant_client, COLLECTION_NAME

    # Lấy tất cả chunk đã embed của file này
    rows = (await db.execute(
        select(FileChunk).where(FileChunk.file_id == cv_file_id)
        .where(FileChunk.qdrant_point_id.isnot(None))
        .order_by(FileChunk.chunk_index)
    )).scalars().all()

    if not rows:
        logger.warning("No embedded chunks found for file_id=%s",cv_file_id)
        return None
    
    # Lấy vectors từ Qdrant
    client = get_qdrant_client()
    point_ids = [str(chunk.qdrant_point_id) for chunk in rows]

    points = await client.retrieve(
        collection_name=COLLECTION_NAME,
        ids=point_ids,
        with_vectors=True,
    )

    if not points:
        return None
    
    # Average pooling tất cả chunk vectors → 1 vector đại diện CV
    vectors = [p.vector for p in points if p.vector]
    if not vectors:
        return None
    
    dim = len(vectors[0])
    avg_vector = [
        sum(v[i] for v in vectors) / len(vectors)
        for i in range(dim)
    ]
    return avg_vector

async def find_matching_jobs(cv_file_id:str, db: AsyncSession, top_k: int = 20) -> list[dict]:
    """
    Tìm jobs phù hợp nhất với CV.

    Returns:
        List of job dicts với score, lấy full info từ PostgreSQL.
    """

    from app.db.models import Job
    from app.services.qdrant_services import get_qdrant_client
    from qdrant_client.models import VectorParams
    import uuid

    # 1. Lấy vector đại diện của CV 
    cv_vector = await get_cv_representative_vector(cv_file_id, db)
    if cv_vector is None:
        return []
    
    # 2. Search trong collection jobs
    client = get_qdrant_client()
    try:
        results = await client.search(
            collection_name="jobs",
            query_vector=cv_vector,
            limit=top_k,
            with_payload=True,
        )
    except Exception as e:
        logger.error("Qdrant search jobs failed: %s",e)
        return []
    
    if not results:
        return []
    
    # 3. Lấy pg_job_id từ payload
    job_id_score_map = {
        hit.payload.get("pg_job_id"): hit.score
        for hit in results
        if hit.payload.get("pg_job_id")
    }

    if not job_id_score_map:
        return []
    
    # 4. Query Postgres lấy full job info
    job_ids = [uuid.UUID(jid) for jid in job_id_score_map.keys()]
    jobs = (await db.execute(
        select(Job).where(Job.id.in_(job_ids).where(Job.is_active == True))
    )).scalars().all()

    # 5. Gắn score + sort
    result = []
    for job in jobs:
        score = job_id_score_map.get(str(job.id), 0.0)
        result.append({
            "id": str(job.id),
            "title": str(job.title),
            "company": job.company,
            "location": job.location,
            "salary_min": job.salary_min,
            "salary_max": job.salary_max,
            "url": job.url,
            "source": job.source,
            "score": round(score, 4),
        })

    result.sort(key=lambda x: x["score"], reverse=True)
    return result
