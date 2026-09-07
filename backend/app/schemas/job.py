import re
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

def utc_now() -> datetime:
    return datetime.now(UTC)

def normalize_single_line(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()

def normalize_multiline(value: str) -> str:
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)

    return normalized.strip()

class JobSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

class EmploymentType(StrEnum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    INTERNSHIP = "internship"
    FREELANCE = "freelance"
    TEMPORARY = "temporary"
    OTHER = "other"

class WorkMode(StrEnum):
    ONSITE = "onsite"
    REMOTE = "remote"
    HYBRID = "hybrid"
    UNKNOWN = "unknown"

class SeniorityLevel(StrEnum):
    INTERN = "intern"
    FRESHER = "fresher"
    JUNIOR = "junior"
    MIDDLE = "middle"
    SENIOR = "senior"
    LEAD = "lead"
    MANAGER = "manager"
    DIRECTOR = "director"
    UNKNOWN = "unknown"

class SalaryPeriod(StrEnum):
    HOURLY = "hourly"
    WEEKLY = "weekly"
    FORTNIGHTLY = "fortnightly"
    MONTHLY = "monthly"
    ANNUAL = "annual"
    UNKNOWN = "unknown"

class RawJob(JobSchema):
    source: str = Field(min_length=1, max_length=100)
    source_job_id: str = Field(min_length=1, max_length=255)
    source_url: AnyHttpUrl
    payload: dict[str, Any]
    crawled_at: datetime = Field(default_factory=utc_now)

class CrawlPage(JobSchema):
    items: list[RawJob] = Field(default_factory=list)
    next_cursor: str | None = None

class JobCandidate(JobSchema):
    title: str = Field(min_length=1, max_length=500)
    company: str = Field(min_length=1, max_length=500)
    description: str = Field(min_length=1)
    location: str | None = Field(default=None, max_length=500)
    employment_type: EmploymentType | None = None
    work_mode: WorkMode = WorkMode.UNKNOWN
    seniority_level: SeniorityLevel = SeniorityLevel.UNKNOWN
    skills: list[str] = Field(default_factory=list)
    salary_min: Decimal | None = Field(default=None, ge=0)
    salary_max: Decimal | None = Field(default=None, ge=0)
    salary_period: SalaryPeriod = SalaryPeriod.UNKNOWN
    salary_currency: str | None = Field(default=None, min_length=3, max_length=3)
    posted_at: datetime | None = None
    expires_at: datetime | None = None
    source: str = Field(min_length=1, max_length=100)
    source_job_id: str = Field(min_length=1, max_length=255)
    source_url: AnyHttpUrl
    crawled_at: datetime = Field(default_factory=utc_now)
    source_metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("title", "company")
    @classmethod
    def normalize_required_single_line(cls, value: str) -> str:
        normalized = normalize_single_line(value)

        if not normalized:
            raise ValueError("Value must not be empty.")

        return normalized

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str) -> str:
        normalized = normalize_multiline(value)

        if not normalized:
            raise ValueError("Description must not be empty.")

        return normalized

    @field_validator("location")
    @classmethod
    def normalize_location(cls, value: str | None) -> str | None:
        if value is None:
            return None

        normalized = normalize_single_line(value)

        return normalized or None

    @field_validator("skills")
    @classmethod
    def normalize_skills(cls, values: list[str]) -> list[str]:
        normalized_skills: list[str] = []
        seen: set[str] = set()

        for value in values:
            normalized = normalize_single_line(value)

            if not normalized:
                continue

            deduplication_key = normalized.casefold()

            if deduplication_key in seen:
                continue

            seen.add(deduplication_key)
            normalized_skills.append(normalized)

        return normalized_skills

    @field_validator("salary_currency")
    @classmethod
    def normalize_currency(cls, value: str | None,) -> str | None:
        if value is None:
            return None

        return value.upper()

    @model_validator(mode="after")
    def validate_salary_range(self) -> "JobCandidate":
        if (
            self.salary_min is not None
            and self.salary_max is not None
            and self.salary_min > self.salary_max
        ):
            raise ValueError("salary_min must not be greater than salary_max.")

        has_salary = self.salary_min is not None or self.salary_max is not None

        if has_salary and self.salary_currency is None:
            raise ValueError("salary_currency is required when salary is provided.")

        return self

    @field_serializer("source_url")
    def serialize_source_url(self, value: AnyHttpUrl) -> str:
        return str(value)

class NormalizedJob(JobCandidate):
    job_id: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    salary_period: SalaryPeriod = SalaryPeriod.UNKNOWN

    content_hash: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )