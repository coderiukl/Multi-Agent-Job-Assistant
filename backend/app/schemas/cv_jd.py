
from pydantic import BaseModel
from typing import Optional
import uuid

class CvVsJdRequest(BaseModel):
    cv_file_id: uuid.UUID
    jd_text: str
    top_k: int = 10


class ChunkResult(BaseModel):
    content: str
    score: float
    chunk_index: int


class CvVsJdResponse(BaseModel):
    score: float
    matching_chunks: list[ChunkResult]


class JobMatchResult(BaseModel):
    id: str
    title: str
    company: Optional[str] = None
    location: Optional[str] = None
    country: Optional[str] = None
    category: Optional[str] = None
    contract_type: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_avg: Optional[float] = None
    salary_raw: Optional[str] = None
    technical_skills: Optional[str] = None
    experience_required: Optional[str] = None
    languages_required: Optional[str] = None
    url: str 
    source: Optional[str] = None
    score: float

class MatchResponse(BaseModel):
    cv_id: uuid.UUID
    total: int
    results: list[JobMatchResult]