from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.db.models import File as FileModel
from app.db.models import FileChunk, User
from app.schemas.parse import FileListResponse, FileResponse
from app.services.cv_service import upload_and_embed_cv

router = APIRouter(prefix="/cvs", tags=["CVs"])


@router.post("/upload", response_model=FileResponse, status_code=status.HTTP_201_CREATED)
async def upload_cv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_file, chunk_count = await upload_and_embed_cv(file, db, current_user)
    return FileResponse(
        id=db_file.id,
        original_name=db_file.original_name,
        stored_name=db_file.stored_name,
        mime_type=db_file.mime_type,
        size=db_file.size,
        status=db_file.status,
        chunk_count=chunk_count,
    )


@router.get("", response_model=FileListResponse)
async def list_cvs(
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    total = await db.scalar(
        select(func.count()).select_from(FileModel).where(FileModel.user_id == current_user.id)
    )

    chunk_count_sub = (
        select(func.count())
        .where(FileChunk.file_id == FileModel.id)
        .correlate(FileModel)
        .scalar_subquery()
    )

    rows = (
        await db.execute(
            select(FileModel, chunk_count_sub.label("chunk_count"))
            .where(FileModel.user_id == current_user.id)
            .order_by(FileModel.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
    ).all()

    items = [
        FileResponse(
            id=f.id,
            original_name=f.original_name,
            stored_name=f.stored_name,
            mime_type=f.mime_type,
            size=f.size,
            status=f.status,
            chunk_count=chunk_count or 0,
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
    db_file = await _get_own_cv(db, cv_id, current_user.id)

    chunk_count = await db.scalar(
        select(func.count()).select_from(FileChunk).where(FileChunk.file_id == db_file.id)
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


@router.delete("/{cv_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cv(
    cv_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_file = await _get_own_cv(db, cv_id, current_user.id)
    await db.delete(db_file)
    await db.commit()


async def _get_own_cv(
    db: AsyncSession,
    cv_id: uuid.UUID,
    user_id: uuid.UUID,
) -> FileModel:
    db_file = await db.scalar(
        select(FileModel).where(
            FileModel.id == cv_id,
            FileModel.user_id == user_id,
        )
    )

    if not db_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CV không tồn tại hoặc bạn không có quyền truy cập",
        )

    return db_file