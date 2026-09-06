from typing import TypedDict

from app.schemas.conversation import (
    ConversationRoute,
    ConversationStatus,
    RequiredInput,
)
from app.schemas.conversations_intent import IntentAnalysisResult
from app.schemas.cv_profile import CVProfile
from app.schemas.cv_analysis import CVAnalysisResult
from app.schemas.career_advice import CareerAdviceResult
from app.schemas.job_search import JobSearchResult
from app.schemas.job_matching import JobMatchingResult
from app.schemas.cover_letter import CoverLetterResult
from app.schemas.workflow import WorkflowPlan, WorkflowJobMatch

class ConversationState(TypedDict, total=False):
    # Dữ liệu từ request
    message: str
    cv_id: str | None
    job_description: str | None

    # Context được backend xác thực
    cv_profile: CVProfile | None
    has_cv: bool
    has_jd: bool

    # Kết quả Intent Analysis
    intent: IntentAnalysisResult

    # Workflow
    workflow: WorkflowPlan | None

    # Kết quả điều phối
    route: ConversationRoute
    status: ConversationStatus
    missing_inputs: list[RequiredInput]

    # Kết quả của các business agent
    cv_analysis_result: CVAnalysisResult | None
    career_advice_result: CareerAdviceResult | None
    job_search_result: JobSearchResult | None
    job_matching_result: JobMatchingResult | None
    workflow_job_matches: list[WorkflowJobMatch]
    cover_letter_result: CoverLetterResult | None

    # Nội dung trả về người dùng
    assistant_message: str