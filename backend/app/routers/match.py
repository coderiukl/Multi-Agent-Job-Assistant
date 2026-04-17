from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.db.models import File as FileModel
from app.db.models import User
from app.schemas.cv_jd import CvVsJdRequest, CvVsJdResponse, JobMatchResult
from app.services.search_services import find_matching_jobs, search_cv_vs_jd

router = APIRouter(prefix="/match", tags=["match"])


@router.post("/cv-vs-jd", response_model=CvVsJdResponse)
async def match_cv_vs_jd(
    body: CvVsJdRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not body.jd_text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="jd_text không được để trống",
        )

    await _ensure_own_cv(db, body.cv_file_id, current_user.id)

    result = await search_cv_vs_jd(
        cv_file_id=str(body.cv_file_id),
        jd_text=body.jd_text,
        top_k=body.top_k,
    )
    return result


@router.get("/jobs/{cv_file_id}", response_model=list[JobMatchResult])
async def match_jobs_for_cv(
    cv_file_id: uuid.UUID,
    top_k: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _ensure_own_cv(db, cv_file_id, current_user.id)

    jobs = await find_matching_jobs(
        cv_file_id=str(cv_file_id),
        db=db,
        top_k=top_k,
    )

    if not jobs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy job phù hợp hoặc CV chưa được embed",
        )

    return [
        JobMatchResult(
            id=job["id"],
            title=job["title"],
            company=job.get("company"),
            location=job.get("location"),
            country=job.get("country"),
            category=job.get("category"),
            contract_type=job.get("contract_type"),
            salary_min=job.get("salary_min"),
            salary_max=job.get("salary_max"),
            salary_avg=job.get("salary_avg"),
            salary_raw=job.get("salary_raw"),
            technical_skills=job.get("technical_skills"),
            experience_required=job.get("experience_required"),
            languages_required=job.get("languages_required"),
            url=job["url"],
            source=job.get("source"),
            score=job["score"],
        )
        for job in jobs
    ]


async def _ensure_own_cv(
    db: AsyncSession,
    cv_file_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    db_file = await db.scalar(
        select(FileModel).where(
            FileModel.id == cv_file_id,
            FileModel.user_id == user_id,
        )
    )

    if not db_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CV không tồn tại hoặc bạn không có quyền truy cập",
        )