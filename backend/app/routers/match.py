from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.services.search_services import search_cv_vs_jd, find_matching_jobs
from app.schemas.cv_jd import ChunkResult, CvVsJdRequest, CvVsJdResponse, JobMatchResult

router = APIRouter(prefix="/match", tags=["match"])

@router.post("/cv-vs-jd", response_model=CvVsJdResponse)
async def match_cv_vs_jd(body: CvVsJdRequest, db: AsyncSession = Depends(get_db)):
    """
    So sánh CV với 1 JD.
    Trả về similarity score + các đoạn CV liên quan nhất.
    """
    if not body.jd_text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="jd_text không được để trống"
        )
    
    result = await search_cv_vs_jd(
        cv_file_id=str(body.cv_file_id),
        jd_text=body.jd_text,
        top_k=body.top_k
    )

    return result

@router.get("/jobs/{cv_file_id}", response_model=list[JobMatchResult])
async def match_jobs_for_cv(cv_file_id: uuid.UUID, top_k: int = 20, db: AsyncSession = Depends(get_db)):
    """
    Tìm danh sách jobs phù hợp nhất với CV.
    """
    jobs = await find_matching_jobs(
        cv_file_id=str(cv_file_id),
        db=db,
        top_k=top_k
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
