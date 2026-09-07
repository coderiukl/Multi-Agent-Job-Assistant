from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator, field_validator

class ConversationIntent(StrEnum):
    CV_ANALYSIS = "cv_analysis"
    JOB_SEARCH = "job_search"
    JOB_MATCHING = "job_matching"
    CAREER_ADVICE = "career_advice"
    COVER_LETTER = "cover_letter"
    GENERAL_QUESTION = "general_question"
    SMALL_TALK = "small_talk"
    OUT_OF_SCOPE = "out_of_scope"
    CLARIFICATION = "clarification"

class ConversationRequest(BaseModel):
    thread_id: UUID = Field(default_factory=uuid4)
    message: str = Field(min_length=1, max_length=2000)
    cv_id: str | None = Field(default=None, max_length=100)
    job_description: str | None = Field(default=None, max_length=20_000)

    @field_validator("message")
    @classmethod
    def normalize_message(cls, value: str) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError("Message must not be empty.")

        return normalized

    @field_validator("cv_id", "job_description")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None

        normalized = value.strip()
        return normalized or None

class IntentAnalysisInput(BaseModel):
    message: str = Field(min_length=1, max_length=2000, description="Message sent by the user.")
    has_cv: bool = Field(default=False, description="Whether the request contains a CV.")
    has_jd: bool = Field(default=False, description="Whether the request contains a job description.")

class IntentAnalysisResult(BaseModel):
    primary_intent: ConversationIntent
    secondary_intents: list[ConversationIntent] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    requires_cv: bool = False
    requires_jd: bool = False

    needs_clarification: bool = False
    clarification_question: str | None = None

    @model_validator(mode="after")
    def validate_clarification(self) -> "IntentAnalysisResult":
        if self.needs_clarification and not self.clarification_question:
            raise ValueError(
                "clarification_question is required when "
                "needs_clarification is true."
            )

        if not self.needs_clarification and self.clarification_question is not None:
            raise ValueError(
                "clarification_question must be null when "
                "needs_clarification is false."
            )

        return self

