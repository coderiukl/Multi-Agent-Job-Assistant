
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
    company: Optional[str]
    location: Optional[str]
    country: Optional[str]
    category: Optional[str]
    contract_type: Optional[str]
    salary_min: Optional[int]
    salary_max: Optional[int]
    salary_avg: Optional[float]
    salary_raw: Optional[str]
    technical_skills: Optional[str]
    experience_required: Optional[str]
    languages_required: Optional[str]
    url: str
    source: Optional[str]
    score: float