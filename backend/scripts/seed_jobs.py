"""
Seed jobs từ VietJob.csv vào PostgreSQL + embed vào Qdrant.

Usage:
    python -m scripts.seed_jobs --file data/VietJob.csv
    python -m scripts.seed_jobs --file data/VietJob.csv --limit 50
"""
from __future__ import annotations

import argparse
import ast
import asyncio
import csv
import hashlib
import logging
import re
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AsyncSessionLocal
from app.db.models import Job

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


# ---------- Column map ----------

COLUMN_MAP = {
    "job_title":            "title",
    "location":             "location",
    "country":              "country",
    "qualifications":       "qualifications",
    "technical_skills":     "technical_skills",
    "soft_skills":          "soft_skills",
    "languages_required":   "languages_required",
    "experience_required":  "experience_required",
    "salary":               "salary_raw",
    "contract_type":        "contract_type",
    "working_hours":        "working_hours",
    "benefits":             "benefits",
    "description":          "description",
    "requirements_text":    "requirements_text",
    "category":             "category",
    "salary_min":           "salary_min",
    "salary_max":           "salary_max",
    "salary_avg":           "salary_avg",
}

REQUIRED_COLUMNS = {"title", "description"}


# ---------- Helpers ----------

def parse_list_field(value: str) -> str | None:
    """
    Chuyển chuỗi dạng "['Cao đẳng', 'Đại học']" → "Cao đẳng, Đại học"
    Nếu không phải list string thì trả về nguyên bản.
    """
    if not value or not value.strip():
        return None

    stripped = value.strip()

    # Thử parse như Python list
    if stripped.startswith("["):
        try:
            items = ast.literal_eval(stripped)
            if isinstance(items, list):
                return ", ".join(str(i).strip() for i in items if i)
        except (ValueError, SyntaxError):
            # Fallback: xóa dấu ngoặc và quotes thủ công
            cleaned = re.sub(r"[\[\]'\"']", "", stripped)
            return ", ".join(p.strip() for p in cleaned.split(",") if p.strip())

    return stripped or None


def parse_int(value: str) -> int | None:
    """'15' / '15.0' / '15,000' / '' → int hoặc None"""
    if not value or not value.strip():
        return None
    # Lấy số đầu tiên trong chuỗi
    match = re.search(r"[\d]+(?:[.,]\d+)?", value.replace(",", ""))
    if not match:
        return None
    try:
        return int(float(match.group()))
    except ValueError:
        return None


def parse_float_salary(value: str) -> float | None:
    """
    '18 triệu' / '18.5' / '18,5' / '' → float hoặc None
    Lấy số đầu tiên xuất hiện trong chuỗi.
    """
    if not value or not value.strip():
        return None
    match = re.search(r"\d+(?:[.,]\d+)?", value.replace(",", "."))
    if not match:
        return None
    try:
        return float(match.group())
    except ValueError:
        return None


def generate_url(title: str, location: str, country: str) -> str:
    unique_str = f"{title}-{location}-{country}".lower().strip()
    hash_id = hashlib.md5(unique_str.encode()).hexdigest()[:12]
    return f"csv://vietjob/{hash_id}"


def row_to_job_dict(row: dict[str, str]) -> dict | None:
    mapped: dict = {}

    for csv_col, db_field in COLUMN_MAP.items():
        mapped[db_field] = row.get(csv_col, "").strip()

    # Validate bắt buộc
    for col in REQUIRED_COLUMNS:
        if not mapped.get(col):
            logger.debug("Bỏ qua row thiếu '%s': %s", col, row)
            return None

    # Parse list fields → plain text
    mapped["qualifications"]    = parse_list_field(mapped.get("qualifications", ""))
    mapped["soft_skills"]       = parse_list_field(mapped.get("soft_skills", ""))
    mapped["benefits"]          = parse_list_field(mapped.get("benefits", ""))
    mapped["technical_skills"]  = parse_list_field(mapped.get("technical_skills", "")) or None

    # Parse numeric
    mapped["salary_min"] = parse_int(mapped.get("salary_min", ""))
    mapped["salary_max"] = parse_int(mapped.get("salary_max", ""))
    mapped["salary_avg"] = parse_float_salary(mapped.get("salary_avg", ""))  # "18 triệu" → 18.0

    # Empty string → None cho các field optional
    for field in ["languages_required", "experience_required", "contract_type",
                  "working_hours", "location", "country", "category", "salary_raw"]:
        if not mapped.get(field):
            mapped[field] = None

    # Generate url vì CSV không có
    mapped["url"] = generate_url(
        mapped.get("title", ""),
        mapped.get("location") or "",
        mapped.get("country") or "",
    )
    mapped["source"] = "vietjob_csv"

    return mapped


# ---------- DB upsert ----------

async def upsert_jobs(session: AsyncSession, job_dicts: list[dict]) -> tuple[int, int]:
    existing_urls: set[str] = set(
        (await session.execute(select(Job.url))).scalars().all()
    )

    inserted = 0
    skipped = 0

    for d in job_dicts:
        if d["url"] in existing_urls:
            skipped += 1
            continue

        job = Job(
            id=uuid.uuid4(),
            title=d["title"],
            location=d.get("location"),
            country=d.get("country"),
            category=d.get("category"),
            contract_type=d.get("contract_type"),
            working_hours=d.get("working_hours"),
            salary_min=d.get("salary_min"),
            salary_max=d.get("salary_max"),
            salary_avg=d.get("salary_avg"),
            salary_raw=d.get("salary_raw"),
            technical_skills=d.get("technical_skills"),
            soft_skills=d.get("soft_skills"),
            qualifications=d.get("qualifications"),
            experience_required=d.get("experience_required"),
            languages_required=d.get("languages_required"),
            benefits=d.get("benefits"),
            description=d.get("description"),
            requirements_text=d.get("requirements_text"),
            url=d["url"],
            source=d["source"],
            is_active=True,
        )
        session.add(job)
        existing_urls.add(d["url"])
        inserted += 1

    await session.commit()
    return inserted, skipped


# ---------- Qdrant embed ----------

async def embed_jobs(session: AsyncSession, batch_size: int = 32) -> int:
    from app.services.embedding_service import _get_model
    from app.services.qdrant_services import get_qdrant_client
    from qdrant_client.models import PointStruct, VectorParams, Distance

    JOBS_COLLECTION = "jobs"
    VECTOR_SIZE = 1024

    client = get_qdrant_client()
    existing = await client.get_collections()
    if JOBS_COLLECTION not in [c.name for c in existing.collections]:
        await client.create_collection(
            collection_name=JOBS_COLLECTION,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )
        logger.info("Đã tạo Qdrant collection: %s", JOBS_COLLECTION)

    jobs = (await session.execute(
        select(Job)
        .where(Job.qdrant_point_id.is_(None))
        .where(Job.is_active.is_True)
    )).scalars().all()

    if not jobs:
        logger.info("Không có job nào cần embed")
        return 0

    model = _get_model()
    total = 0

    for i in range(0, len(jobs), batch_size):
        batch = jobs[i: i + batch_size]

        texts = [
            " ".join(filter(None, [
                job.title,
                job.category,
                job.qualifications,
                job.technical_skills,
                job.soft_skills,
                job.experience_required,
                job.description,
                job.requirements_text,
            ]))
            for job in batch
        ]

        vectors = model.encode(texts, batch_size=batch_size, show_progress_bar=False)

        points = []
        for job, vector in zip(batch, vectors):
            point_id = str(uuid.uuid4())
            points.append(
                PointStruct(
                    id=point_id,
                    vector=vector.tolist(),
                    payload={
                        "pg_job_id":        str(job.id),
                        "title":            job.title,
                        "location":         job.location or "",
                        "country":          job.country or "",
                        "category":         job.category or "",
                        "salary_min":       job.salary_min,
                        "salary_max":       job.salary_max,
                        "salary_avg":       job.salary_avg,
                        "contract_type":    job.contract_type or "",
                        "experience_required": job.experience_required or "",
                        "url":              job.url,
                    },
                )
            )
            job.qdrant_point_id = uuid.UUID(point_id)

        await client.upsert(collection_name=JOBS_COLLECTION, points=points)
        await session.commit()

        total += len(batch)
        logger.info("Embedded %d / %d jobs...", total, len(jobs))

    return total


# ---------- Main ----------

async def main(csv_path: Path, limit: int | None) -> None:
    if not csv_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file: {csv_path}")

    with csv_path.open(encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    logger.info("Đọc được %d rows từ %s", len(rows), csv_path)

    if limit:
        rows = rows[:limit]
        logger.info("Giới hạn %d rows (--limit)", limit)

    job_dicts = []
    invalid = 0
    for row in rows:
        d = row_to_job_dict(row)
        if d:
            job_dicts.append(d)
        else:
            invalid += 1

    logger.info("Hợp lệ: %d | Bỏ qua (thiếu field): %d", len(job_dicts), invalid)

    if not job_dicts:
        logger.warning("Không có row nào hợp lệ, dừng")
        return

    async with AsyncSessionLocal() as session:
        inserted, skipped = await upsert_jobs(session, job_dicts)
        logger.info("PostgreSQL → inserted: %d | skipped: %d", inserted, skipped)

        embedded = await embed_jobs(session)
        logger.info("Qdrant → embedded: %d jobs", embedded)

    logger.info("✅ Seed hoàn tất!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True, help="Đường dẫn VietJob.csv")
    parser.add_argument("--limit", type=int, default=None, help="Giới hạn số rows để test")
    args = parser.parse_args()

    asyncio.run(main(Path(args.file), args.limit))