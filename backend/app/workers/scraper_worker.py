import logging
import uuid

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.base import AsyncSessionLocal
from app.db.models import Job
from app.services.embedding_service import _get_model
from app.services.qdrant_services import upsert_job_chunks
from app.services.scrapers.base import JobItem

logger = logging.getLogger(__name__)

async def embed_and_upsert_jobs(jobs: list[JobItem], limit: int = 20) -> list[dict]:
    results: list[dict] = []
    model = _get_model()

    async with AsyncSessionLocal() as db:
        for job in jobs[:limit]:
            try:
                # 1. Upsert PostgreSQL — ON CONFLICT url DO UPDATE
                stmt = (
                    pg_insert(Job)
                    .values(
                        title=job.title,
                        company=job.company,
                        location=job.location,
                        description=job.description,
                        salary_min=job.salary_min,
                        salary_max=job.salary_max,
                        url=job.url,
                        source=job.source,
                        is_active=True,
                    )
                    .on_conflict_do_update(
                        index_elements=["url"],
                        set_={
                            "description": job.description,
                            "is_active": True,
                        },
                    )
                    .returning(Job.id)
                )
                result = await db.execute(stmt)
                job_id: uuid.UUID = result.scalar_one()
                await db.commit()

                # 2. Embed description (hoặc title nếu không có description)
                text_to_embed = job.description or job.title
                vector: list[float] = model.encode(
                    text_to_embed, show_progress_bar=False
                ).tolist()

                # 3. Upsert Qdrant
                await upsert_job_chunks([{
                    "job_db_id": str(job_id),
                    "title": job.title,
                    "company": job.company,
                    "location": job.location,
                    "source": job.source,
                    "url": job.url,
                    "vector": vector,
                }])

                results.append({
                    "id": str(job_id),
                    "title": job.title,
                    "company": job.company,
                    "location": job.location,
                    "salary_min": job.salary_min,
                    "salary_max": job.salary_max,
                    "url": job.url,
                    "source": job.source,
                    "score": None,  # sẽ được tính ở matcher
                })

            except Exception as e:
                logger.error("embed_and_upsert_jobs error for url=%s: %s", job.url, e)
                await db.rollback()
                continue

    return results