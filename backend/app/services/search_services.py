from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FileChunk, Job
from app.services.embedding_service import _get_model
from app.services.qdrant_services import CV_COLLECTION_NAME, JOBS_COLLECTION_NAME, get_qdrant_client, search_similar

logger = logging.getLogger(__name__)

def _embed_text(text: str) -> list[float]:
    model = _get_model()
    return model.encode(text, show_progress_bar=False).tolist()

async def search_cv_vs_jd(cv_file_id: str, jd_text: str, top_k: int = 10):
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
        collection_name=CV_COLLECTION_NAME,
        ids=point_ids,
        with_vectors=True,
    )

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
    cv_vector = await get_cv_representative_vector(cv_file_id, db)
    if cv_vector is None:
        return []
    
    client = get_qdrant_client()
    try:
        results = await client.query_points(
            collection_name=JOBS_COLLECTION_NAME,
            query=cv_vector,
            limit=top_k,
            with_payload=True,
        )
    except Exception as e:
        logger.error("Qdrant search jobs failed: %s",e)
        return []
    
    results = results.points
    if not results:
        return []
    
    # 3. Lấy pg_job_id từ payload
    job_id_score_map = {
        hit.payload.get("job_db_id"): hit.score
        for hit in results
        if hit.payload.get("job_db_id")
    }

    if not job_id_score_map:
        return []
    
    # 4. Query Postgres lấy full job info
    job_ids = [uuid.UUID(jid) for jid in job_id_score_map.keys()]
    jobs = (await db.execute(
        select(Job).where(Job.id.in_(job_ids)).where(Job.is_active.is_(True)))
    ).scalars().all()

    # 5. Gắn score + sort
    output: list[dict] = []
    for job in jobs:
        score = job_id_score_map.get(str(job.id), 0.0)
        output.append({
            "id": str(job.id),
            "title": job.title,
            "location": job.location,
            "country": job.country,           
            "category": job.category,         
            "contract_type": job.contract_type, 
            "salary_min": job.salary_min,
            "salary_max": job.salary_max,
            "salary_avg": job.salary_avg,     
            "salary_raw": job.salary_raw,     
            "technical_skills": job.technical_skills,   
            "experience_required": job.experience_required, 
            "languages_required": job.languages_required,   
            "url": job.url,
            "source": job.source,
            "score": round(score, 4),
        })

    output.sort(key=lambda x: x["score"], reverse=True)
    return output
