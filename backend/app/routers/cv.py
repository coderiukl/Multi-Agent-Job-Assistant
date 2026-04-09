"""
routers/cv.py

Endpoints:
    POST /cvs/upload    — Upload CV (PDF/DOCX), lưu disk, parse, chunk, lưu DB
    GET  /cvs           — Danh sách CV của user hiện tại
    GET  /cvs/{id}      — Chi tiết 1 CV
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import File as FileModel, FileChunk
from app.parsers.utils import ParseError
from app.db.models import User
from app.services.cv_parser import CVParser, chunk_text
from app.core.dependencies import get_current_user, get_db
from app.schemas.parse import FileListResponse, FileResponse
from app.parsers.text_cleaner import clean_text
from app.services.embedding_service import embed_file

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cvs", tags=["CVs"])

# ─────────────────────────────────────────
# Constants
# ─────────────────────────────────────────

MAX_FILE_SIZE = 10 * 1024 * 1024        # 10 MB
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc"}

# Thư mục lưu file upload — đặt trong settings thật sau
UPLOAD_DIR = Path("uploads/cvs")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────
# POST /cvs/upload
# ─────────────────────────────────────────

@router.post("/upload", response_model=FileResponse, status_code=status.HTTP_201_CREATED)
async def upload_cv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Flow:
        1. Validate extension + size
        2. Lưu file lên disk → lấy file_path
        3. CVParser.parse(file_path) — tự chọn PDFParser / DOCXParser / OCR fallback
        4. chunk_text() → lưu FileChunk records
        5. Cập nhật File.status = "embedded" (sẵn sàng cho embedding pipeline)
    """
    # 1. Validate extension
    original_name = file.filename or "unknown"
    ext = Path(original_name).suffix.lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Chi chap nhan file .pdf hoac .docx. Nhan duoc: '{ext}'",
        )

    # 2. Validate size
    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File qua lon. Toi da {MAX_FILE_SIZE // (1024 * 1024)} MB.",
        )

    # 3. Lưu file lên disk
    stored_name = f"{uuid.uuid4().hex}{ext}"
    file_path = UPLOAD_DIR / stored_name
    file_path.write_bytes(file_bytes)

    # 4. Tạo File record (status = "parsing")
    mime_type = file.content_type
    db_file = FileModel(
        user_id=current_user.id,
        original_name=original_name,
        stored_name=stored_name,
        file_path=str(file_path),
        mime_type=mime_type,
        size=len(file_bytes),
        status="parsing",
    )
    db.add(db_file)
    await db.flush()  # lấy id trước khi commit

    # 5. Parse text + chunk
    try:
        parser = CVParser()
        raw_text = parser.parse(str(file_path))
        raw_text = clean_text(raw_text)  # Clean text before saving

        chunks_data = chunk_text(raw_text, chunk_size=300, overlap=50)

        for chunk in chunks_data:
            db.add(FileChunk(
                file_id=db_file.id,
                chunk_index=chunk["chunk_index"],
                content=clean_text(chunk["content"]),  # Clean each chunk
                metadata_json={"token_count": chunk.get("token_count", 0)},
            ))

        db_file.status = "embedded"
        await embed_file(file_id=db_file.id, db=db)
        await db.commit()
        await db.refresh(db_file)

        logger.info(
            "CV uploaded: file_id=%s, chunks=%d, size=%d bytes",
            db_file.id, len(chunks_data), len(file_bytes),
        )

    except ParseError as exc:
        db_file.status = "failed"
        await db.commit()
        logger.error("CV parse failed: file_id=%s, code=%s, detail=%s",
                     db_file.id, exc.code, exc.detail)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.to_dict(),
        )
    except Exception as exc:
        db_file.status = "failed"
        await db.commit()
        logger.exception("CV parse unexpected error: file_id=%s", db_file.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "UNEXPECTED_ERROR", "message": str(exc)},
        )

    return FileResponse(
        id=db_file.id,
        original_name=db_file.original_name,
        stored_name=db_file.stored_name,
        mime_type=db_file.mime_type,
        size=db_file.size,
        status=db_file.status,
        chunk_count=len(chunks_data),
    )

@router.get("", response_model=FileListResponse)
async def list_cvs(
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Total count
    total = await db.scalar(
        select(func.count()).select_from(FileModel)
        .where(FileModel.user_id == current_user.id)
    )

    # Files + chunk count trong 1 query (subquery)
    chunk_count_sub = (
        select(func.count())
        .where(FileChunk.file_id == FileModel.id)
        .correlate(FileModel)
        .scalar_subquery()
    )

    rows = (await db.execute(
        select(FileModel, chunk_count_sub.label("chunk_count"))
        .where(FileModel.user_id == current_user.id)
        .order_by(FileModel.created_at.desc())
        .offset(skip)
        .limit(limit)
    )).all()

    items = [
        FileResponse(
            id=f.id,
            original_name=f.original_name,
            stored_name=f.stored_name,
            mime_type=f.mime_type,
            size=f.size,
            status=f.status,
            chunk_count=chunk_count,
        )
        for f, chunk_count in rows
    ]

    return FileListResponse(items=items, total=total or 0)

@router.get("/{cv_id}", response_model=FileResponse)
async def get_cv(
    cv_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_file = await db.scalar(
        select(FileModel).where(
            FileModel.id == cv_id,
            FileModel.user_id == current_user.id,   # authorization check
        )
    )

    if not db_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CV khong ton tai hoac ban khong co quyen truy cap.",
        )

    chunk_count = await db.scalar(
        select(func.count()).select_from(FileChunk)
        .where(FileChunk.file_id == db_file.id)
    )

    return FileResponse(
        id=db_file.id,
        original_name=db_file.original_name,
        stored_name=db_file.stored_name,
        mime_type=db_file.mime_type,
        size=db_file.size,
        status=db_file.status,
        chunk_count=chunk_count or 0,
    )