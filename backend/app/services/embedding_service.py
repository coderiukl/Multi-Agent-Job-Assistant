from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import FileChunk
from app.services.qdrant_services import upsert_chunks

logger = logging.getLogger(__name__)

EMBEDDING_MODEL_NAME = "BAAI/bge-m3"
VECTOR_SIZE=1024

def _get_model():
    from sentence_transformers import SentenceTransformer
    if not hasattr(_get_model, "_instance"):
        logger.info("Loading embedding model: %s", EMBEDDING_MODEL_NAME)
        _get_model._instance = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _get_model._instance

async def embed_file(file_id: uuid.UUID, db: AsyncSession) -> int:

    # 1. Lấy tất cả chunk chưa embed
    rows = (await db.execute(
        select(FileChunk).where(FileChunk.file_id == file_id)
        .where(FileChunk.qdrant_point_id.is_(None))
        .order_by(FileChunk.chunk_index)          
    )).scalars().all()

    if not rows:
        logger.info("No chunks to embed for file_id=%s", file_id)
        return 0
    
    # 2. Encode tất cả chunks 1 lần (batch) - nhanh hơn từng cái
    model = _get_model()
    texts =  [chunk.content for chunk in rows]
    vectores = model.encode(texts, batch_size=32, show_progress_bar=False)

    # 3. upsert vào Qdrant, nhận lại point_ids
    point_ids = await upsert_chunks(
        chunks=[
            {
                "chunk_db_id": str(chunk.id),
                "file_id": str(file_id),
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "vector": vectores[i].tolist(),
            }

            for i, chunk in enumerate(rows)
        ]
    )

    # 4. Cập nhật qdrant_point_id + embedded_at về DB
    now = datetime.now(timezone.utc)
    for chunk, point_id in zip(rows, point_ids):
        chunk.qdrant_point_id = uuid.UUID(point_id)
        chunk.embedded_at = now
        chunk.embedding_model = EMBEDDING_MODEL_NAME

    await db.commit()
    logger.info("Embedded %d chunks for file_id=%s", len(rows), file_id)
    return len(rows)
