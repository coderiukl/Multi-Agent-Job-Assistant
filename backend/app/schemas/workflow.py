from enum import StrEnum

from pydantic import BaseModel, Field

class WorkflowType(StrEnum):
    SINGLE_AGENT = "single_agent"
    JOB_DISCOVERY = "job_discovery"
    JOB_RECOMMENDATION = "job_recommendation"
    FULL_CAREER = "full_career"

class WorkflowStep(StrEnum):
    RESOLVE_CONTEXT = "resolve_context"
    INTENT_ANALYSIS = "intent_analysis"
    JOB_SEARCH = "job_search"
    JOB_MATCHING = "job_matching"
    CAREER_ADVICE = "career_advice"
    COVER_LETTER = "cover_letter"
    COMPLETED = "completed"

class WorkflowPlan(BaseModel):
    workflow_type: WorkflowType = WorkflowType.SINGLE_AGENT
    steps: list[WorkflowStep] = Field(default_factory=list)
    current_step: WorkflowStep | None = None
    completed_steps: list[WorkflowStep] = Field(default_factory=list)