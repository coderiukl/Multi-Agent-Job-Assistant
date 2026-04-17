from __future__ import annotations

import logging
from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams
)

from app.core.config import settings

logger = logging.getLogger(__name__)

CV_COLLECTION_NAME = "cv_chunks"
JOBS_COLLECTION_NAME = "jobs"
VECTOR_SIZE = 1024

def get_qdrant_client() -> AsyncQdrantClient:
    if not hasattr(get_qdrant_client, "_instance"):
        get_qdrant_client._instance = AsyncQdrantClient(
            host = settings.QDRANT_HOST,
            port = settings.QDRANT_PORT,
        )
    return get_qdrant_client._instance

async def ensure_collection() -> None:

    client = get_qdrant_client()
    existing = await client.get_collections()
    names = [c.name for c in existing.collections]

    for collection_name in (CV_COLLECTION_NAME, JOBS_COLLECTION_NAME):
        if collection_name in names:
            logger.info("Qdrant collection already exists: %s", collection_name)
            continue

        await client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )
        logger.info("Created Qdrant collection: %s", collection_name)

async def upsert_job_chunks(jobs: list[dict]) -> list[str]:
    client = get_qdrant_client()
    points = [
        PointStruct(
            id=str(job["job_db_id"]),
            vector=job["vector"],
            payload={
                "job_db_id": str(job["job_db_id"]),
                "title":     job["title"],
                "company":   job.get("company"),
                "location":  job.get("location"),
                "source":    job.get("source"),
                "url":       job["url"],
            },
        )
        for job in jobs
    ]
    await client.upsert(collection_name=JOBS_COLLECTION_NAME, points=points)
    return [job["job_db_id"] for job in jobs]


async def upsert_cv_chunks(chunks: list[dict[str, Any]]) -> list[str]:
    client = get_qdrant_client()
    points = [
        PointStruct(
            id=str(chunk["chunk_db_id"]),
            vector=chunk["vector"],
            payload={
                "file_id":     chunk["file_id"],
                "chunk_index": chunk["chunk_index"],
                "content":     chunk["content"],
            },
        )
        for chunk in chunks
    ]
    await client.upsert(collection_name=CV_COLLECTION_NAME, points=points)
    return [chunk["chunk_db_id"] for chunk in chunks]

async def search_similar(vector: list[float], top_k: int = 10, file_id_filter: str | None = None) -> list[dict]:
    from qdrant_client.models import Filter, FieldCondition, MatchValue

    client = get_qdrant_client()

    query_filter = None
    if file_id_filter:
        query_filter = Filter(
            must=[FieldCondition(
                key = "file_id",
                match=MatchValue(value=file_id_filter),
            )]
        )
    
    response = await client.query_points(
        collection_name = CV_COLLECTION_NAME,
        query=vector,
        limit=top_k,
        query_filter=query_filter,
        with_payload=True,
    )

    return [
        {
            "chunk_db_id": str(hit.id),
            "score": hit.score,
            "content": hit.payload.get("content", ""),
            "file_id": hit.payload.get("file_id", ""),
            "chunk_index": hit.payload.get("chunk_index", 0),
        }
        for hit in response.points
    ]