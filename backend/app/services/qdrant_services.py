from __future__ import annotations

import logging
import uuid

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    PointStruct,
    VectorParams
)

from app.core.config import settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "cv_chunks"
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

    if COLLECTION_NAME not in names:
        await client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=VECTOR_SIZE,
                distance=Distance.COSINE
            ),
        )
        logger.info("Created Qdrant collection: %s", COLLECTION_NAME)
    else:
        logger.info("Collection already exists: %s", COLLECTION_NAME)

async def upsert_chunks(chunks: list[dict]) -> list[str]:
    client = get_qdrant_client()

    points = [
        PointStruct(
            id = chunk["chunk_db_id"],
            vector=chunk["vector"],
            payload={
                "file_id": chunk["file_id"],
                "chunk_index": chunk["chunk_index"],
                "content": chunk['content']
            },
        )
        for chunk in chunks
    ]

    await client.upsert(collection_name=COLLECTION_NAME, points=points)
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
    
    results = await client.search(
        collection_name = COLLECTION_NAME,
        query_vector=vector,
        limit=top_k,
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
        for hit in results
    ]