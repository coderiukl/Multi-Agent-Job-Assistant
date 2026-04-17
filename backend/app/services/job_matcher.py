import json
import logging

import numpy as np
from qdrant_client.models import Filter, FieldCondition, MatchValue
from sqlalchemy import select

from app.db.models import Job
from app.db.base import AsyncSessionLocal
from app.services.qdrant_services import CV_COLLECTION_NAME, JOBS_COLLECTION_NAME, get_qdrant_client
from app.core.cache import get_redis

logger = logging.getLogger(__name__)

CACHE_TTL = 60 * 30  # 30 phút

class JobMatcherService:

    def __init__(self):
        self.qdrant = get_qdrant_client()

    async def match_from_db(self, cv_id: str, top_k: int = 5) -> list[dict]:
        redis = get_redis()
        cache_key = f"match:{cv_id}:top{top_k}"

        # 1. Kiểm tra cache
        if redis is not None:
            try:
                cached = await redis.get(cache_key)
                if cached:
                    logger.info("Cache hit: %s", cache_key)
                    return json.loads(cached)
            except Exception:
                logger.warning("Redis get failed, skip cache.")

        # 2. Lấy CV vector
        cv_vector = await self._get_cv_avg_vector(cv_id)
        if cv_vector is None:
            return []

        # 3. Search Qdrant
        response = await self.qdrant.query_points(
            collection_name=JOBS_COLLECTION_NAME,
            query=cv_vector,
            limit=top_k,
            with_payload=True,
            query_filter=Filter(must=[
                FieldCondition(key="source", match=MatchValue(value="csv"))
            ]),
        )

        # 4. Hydrate từ PostgreSQL
        results = await self._hydrate_jobs(response.points)

        # 5. Lưu cache
        if redis is not None:
            try:
                await redis.set(cache_key, json.dumps(results), ex=CACHE_TTL)
                logger.info("Cache set: %s (TTL=%ds)", cache_key, CACHE_TTL)
            except Exception:
                logger.warning("Redis set failed, bỏ qua cache.")

        return results

    async def score_web_jobs(self, cv_id: str, job_ids: list[str]) -> list[dict]:
        cv_vector = await self._get_cv_avg_vector(cv_id)
        if cv_vector is None:
            return []

        response = await self.qdrant.query_points(
            collection_name=JOBS_COLLECTION_NAME,
            query=cv_vector,
            limit=max(len(job_ids),1),
            with_payload=True,
        )

        # Filter chỉ giữ job_ids ta muốn
        job_id_set = set(job_ids)
        filtered = [point for point in response.points if point.payload.get("job_db_id") in job_id_set]
        return await self._hydrate_jobs(filtered)

    async def invalidate(self, cv_id: str, top_k: int = 5):
        redis = get_redis()
        if redis is None:
            return
        
        cache_key = f"match:{cv_id}:top{top_k}"
        try:
            await redis.delete(cache_key)
            logger.info("Cache invalidated: %s", cache_key)
        except Exception:
            logger.warning("Redis delete failed.")

    async def _get_cv_avg_vector(self, cv_id: str) -> list[float] | None:
        response = await self.qdrant.scroll(
            collection_name=CV_COLLECTION_NAME,
            scroll_filter=Filter(must=[
                FieldCondition(key="file_id", match=MatchValue(value=cv_id))
            ]),
            with_vectors=True,
            limit=200,
        )

        points, _ = response

        if not points:
            logger.warning("No CV vectors found for cv_id=%s", cv_id)
            return None

        vectors = [p.vector for p in points if p.vector]
        if not vectors:
            return None
        
        avg = np.mean(vectors, axis=0).tolist()
        return avg

    async def _hydrate_jobs(self, hits) -> list[dict]:
        if not hits:
            return []

        job_ids = list({h.payload["job_db_id"] for h in hits if h.payload.get("job_db_id")})
        score_map = {h.payload["job_db_id"]: round(h.score, 4) for h in hits if h.payload.get("job_db_id")}

        async with AsyncSessionLocal() as db:
            rows = (await db.execute(
                select(Job).where(Job.id.in_(job_ids), Job.is_active == True)
            )).scalars().all()

        return [
            {
                "id": str(job.id),
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "salary_min": job.salary_min,
                "salary_max": job.salary_max,
                "url": job.url,
                "source": job.source,
                "score": score_map.get(str(job.id), 0.0),
            }
            for job in rows
        ]