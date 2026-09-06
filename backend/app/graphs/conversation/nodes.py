import logging
from typing import Any
import asyncio

from app.core.exceptions import ResourceNotFoundException

from app.graphs.conversation.state import ConversationState
from app.graphs.conversation.routing import collect_missing_inputs
from app.graphs.conversation.planning import plan_workflow
from app.graphs.conversation.workflow import advance_workflow

from app.repositories.cv import CVRepository

from app.schemas.conversations_intent import IntentAnalysisInput
from app.schemas.conversation import ConversationRoute, ConversationStatus, RequiredInput
from app.schemas.job_search import JobSearchResult, JobSearchRequest
from app.schemas.job_matching import JobMatchingInput, JobMatchingResult, JobMatchTarget, MatchRecommendation
from app.schemas.cv_analysis import CVAnalysisInput, CVAnalysisResult, CVQualityLevel
from app.schemas.career_advice import CareerAdviceInput, CareerAdviceResult
from app.schemas.cover_letter import CoverLetterInput, CoverLetterResult
from app.schemas.workflow import WorkflowStep, WorkflowJobMatch

from app.services.conversation.intent_analyzer import ConversationIntentAnalyzer
from app.services.job_search import HybridJobSearchService
from app.services.job_search_context import build_job_search_context
from app.services.job_matching import JobMatchingService
from app.services.cv_analysis import CVAnalysisService
from app.services.career_advice import CareerAdviceService
from app.services.cover_letter import CoverLetterService


logger = logging.getLogger(__name__)


MATCH_RECOMMENDATION_LABELS: dict[MatchRecommendation, str] = {
    MatchRecommendation.STRONG_MATCH: "rất phù hợp",
    MatchRecommendation.GOOD_MATCH: "phù hợp",
    MatchRecommendation.PARTIAL_MATCH: "phù hợp một phần",
    MatchRecommendation.LOW_MATCH: "mức độ phù hợp thấp",
}

CV_QUALITY_LABELS: dict[CVQualityLevel, str] = {
    CVQualityLevel.EXCELLENT: "rất tốt",
    CVQualityLevel.GOOD: "tốt",
    CVQualityLevel.NEEDS_IMPROVEMENT: "cần cải thiện",
    CVQualityLevel.WEAK: "còn yếu",
}

WORKFLOW_MATCH_LIMIT = 5

class ConversationNodes:
    def __init__(
        self,
        *,
        analyzer: ConversationIntentAnalyzer,
        cv_repository: CVRepository,
        cv_analysis_service: CVAnalysisService,
        career_advice_service: CareerAdviceService,
        cover_letter_service: CoverLetterService,
        job_search_service: HybridJobSearchService,
        job_matching_service: JobMatchingService,
    ) -> None:
        self._analyzer = analyzer
        self._cv_repository = cv_repository
        self._cv_analysis_service = cv_analysis_service
        self._career_advice_service = career_advice_service
        self._cover_letter_service = cover_letter_service
        self._job_search_service = job_search_service
        self._job_matching_service = job_matching_service

    async def resolve_context(self, state: ConversationState) -> dict[str, Any]:
        cv_id = state.get("cv_id")
        job_description = state.get("job_description")

        cv_profile = None

        if cv_id is not None:
            cv_profile = await self._cv_repository.get(cv_id)

            if cv_profile is None:
                raise ResourceNotFoundException(
                    resource="CV",
                    identifier=cv_id,
                )

        has_cv = cv_profile is not None
        has_jd = bool(job_description)

        logger.info(
            "Conversation context resolved",
            extra = {
                "cv_id": cv_id,
                "has_cv": has_cv,
                "has_jd": has_jd,
            }
        )

        return {
            "cv_profile": cv_profile,
            "has_cv": has_cv,
            "has_jd": has_jd,
        }

    async def analyze_intent(self, state: ConversationState) -> dict[str, Any]:
        analyzer_input = IntentAnalysisInput(
            message=state["message"],
            has_cv=state.get("has_cv", False),
            has_jd=state.get("has_jd", False)
        )

        intent = await self._analyzer.analyze(analyzer_input)

        logger.info(
            "Conversation intent analyzed",
            extra={
                "primary_intent": intent.primary_intent.value,
                "confidence": intent.confidence,
                "needs_clarification": intent.needs_clarification,
            },
        )

        return {"intent": intent}

    async def execute_cv_analysis(self, state: ConversationState) -> dict[str, Any]:
        cv_profile = state.get("cv_profile")

        if cv_profile is None:
            missing_inputs = [RequiredInput.CV]

            return {
                "route": ConversationRoute.CLARIFICATION,
                "status": ConversationStatus.NEEDS_CLARIFICATION,
                "missing_inputs": missing_inputs,
                "assistant_message": self._build_clarification_message(
                    missing_inputs=missing_inputs,
                    generated_question=None
                ),
            }

        analysis_input = CVAnalysisInput(
            cv_profile=cv_profile,
            user_request=state["message"],
        )

        result = await self._cv_analysis_service.analyze(analysis_input)

        assistant_message = self._build_cv_analysis_message(result)

        logger.info(
            "Conversation CV analysis completed",
            extra={
                "cv_id": state.get("cv_id"),
                "overall_score": result.overall_score,
                "quality_level": result.quality_level.value,
                "confidence": result.confidence,
            },
        )

        return {
            "route": ConversationRoute.CV_ANALYSIS,
            "status": ConversationStatus.COMPLETED,
            "missing_inputs": [],
            "assistant_message": assistant_message,
            "cv_analysis_result": result,
        }

    async def execute_career_advice(self, state: ConversationState) -> dict[str, Any]:
        advice_input = CareerAdviceInput(
            user_request=state["message"],
            cv_profile=state.get("cv_profile"),
        )

        result = await self._career_advice_service.advise(advice_input)
        assistant_message = self._build_career_advice_message(result)

        logger.info(
            "Conversation career advice completed",
            extra={
                "cv_id": state.get("cv_id"),
                "is_personalized": result.is_personalized,
                "recommended_role_count": len(result.recommended_roles),
                "confidence": result.confidence,
            },
        )

        return {
            "route": ConversationRoute.CAREER_ADVICE,
            "status": ConversationStatus.COMPLETED,
            "missing_inputs": [],
            "assistant_message": assistant_message,
            "career_advice_result": result,
        }

    async def execute_job_search(self, state: ConversationState) -> dict[str, Any]:
        request = JobSearchRequest(
            query=state["message"],
            page=1,
            page_size=10
        )
        search_context = build_job_search_context(state.get("cv_profile"))

        result = await self._job_search_service.search(request, context=search_context)

        assistant_message = self._build_job_search_message(result, used_cv=search_context is not None)

        logger.info(
            "Conversation job search completed",
            extra={
                "query": request.query,
                "strategy": result.strategy.value,
                "total": result.total,
                "returned_items": len(result.items),
            },
        )

        return {
            "route": ConversationRoute.JOB_SEARCH,
            "status": ConversationStatus.COMPLETED,
            "missing_inputs": [],
            "assistant_message": assistant_message,
            "job_search_result": result,
        }

    async def execute_cover_letter(self, state: ConversationState) -> dict[str, Any]:
        cv_profile = state.get("cv_profile")
        job_description = state.get("job_description")
        missing_inputs: list[RequiredInput] = []

        if cv_profile is None:
            missing_inputs.append(RequiredInput.CV)

        if not job_description:
            missing_inputs.append(RequiredInput.JOB_DESCRIPTION)

        if missing_inputs:
            return {
                "route": ConversationRoute.CLARIFICATION,
                "status": ConversationStatus.NEEDS_CLARIFICATION,
                "missing_inputs": missing_inputs,
                "assistant_message": (
                    self._build_clarification_message(
                        missing_inputs=missing_inputs,
                        generated_question=None,
                    )
                ),
            }

        letter_input = CoverLetterInput(
            user_request=state["message"],
            cv_profile=cv_profile,
            job=JobMatchTarget(description=job_description),
        )

        result = await self._cover_letter_service.generate(letter_input)

        logger.info(
            "Conversation cover letter completed",
            extra={
                "cv_id": state.get("cv_id"),
                "language": result.language.value,
                "word_count": result.word_count,
                "confidence": result.confidence,
            },
        )

        return {
            "route": ConversationRoute.COVER_LETTER,
            "status": ConversationStatus.COMPLETED,
            "missing_inputs": [],
            "assistant_message": self._build_cover_letter_message(result),
            "cover_letter_result": result,
        }

    async def execute_job_matching(self, state: ConversationState) -> dict[str, Any]:
        cv_profile = state.get("cv_profile")
        job_description = state.get("job_description")
        missing_inputs: list[RequiredInput] = []

        if cv_profile is None:
            missing_inputs.append(RequiredInput.CV)

        if not job_description:
            missing_inputs.append(RequiredInput.JOB_DESCRIPTION)

        if missing_inputs:
            return {
                "route": ConversationRoute.CLARIFICATION,
                "status": ConversationStatus.NEEDS_CLARIFICATION,
                "missing_inputs": missing_inputs,
                "assistant_message": self._build_clarification_message(missing_inputs, generated_question=None),
            }

        matching_input = JobMatchingInput(cv_profile=cv_profile, job=JobMatchTarget(description=job_description))

        result = await self._job_matching_service.match(matching_input)

        assistant_message = self._build_job_matching_message(result)

        logger.info(
            "Conversation job matching completed",
            extra={
                "cv_id": state.get("cv_id"),
                "job_id": result.job_id,
                "overall_score": result.overall_score,
                "recommendation": result.recommendation.value,
            },
        )

        return {
            "route": ConversationRoute.JOB_MATCHING,
            "status": ConversationStatus.COMPLETED,
            "missing_inputs": [],
            "assistant_message": assistant_message,
            "job_matching_result": result,
        }
    
    async def respond_clarification(self, state: ConversationState) -> dict[str, Any]:
        intent = state['intent']
        missing_inputs = collect_missing_inputs(state)

        assistant_message = self._build_clarification_message(
            missing_inputs=missing_inputs,
            generated_question=intent.clarification_question,
        )

        return {
            "route": ConversationRoute.CLARIFICATION,
            "status": ConversationStatus.NEEDS_CLARIFICATION,
            "missing_inputs": missing_inputs,
            "assistant_message": assistant_message
        }

    async def respond_small_talk(
        self,
        state: ConversationState,
    ) -> dict[str, Any]:
        return {
            "route": ConversationRoute.SMALL_TALK,
            "status": ConversationStatus.COMPLETED,
            "missing_inputs": [],
            "assistant_message": (
                "Xin chào! Tôi có thể hỗ trợ bạn phân tích CV, "
                "tìm kiếm công việc, đánh giá mức độ phù hợp với JD "
                "và tư vấn định hướng nghề nghiệp."
            ),
        }

    async def respond_out_out_scope(self, state: ConversationState) -> dict[str, Any]:
        return {
            "route": ConversationRoute.OUT_OF_SCOPE,
            "status": ConversationStatus.COMPLETED,
            "missing_inputs": [],
            "assistant_message": (
                "Yêu cầu này nằm ngoài phạm vi hỗ trợ của hệ thống. "
                "Tôi có thể giúp bạn về CV, việc làm, JD và "
                "định hướng nghề nghiệp."
            ),
        }

    async def respond_general_question(self, state: ConversationState) -> dict[str, Any] :
        return {
            "route": ConversationRoute.GENERAL_QUESTION,
            "status": ConversationStatus.COMPLETED,
            "missing_inputs": [],
            "assistant_message": (
                "Tôi là trợ lý hỗ trợ tìm việc. Bạn có thể gửi CV, "
                "mô tả công việc hoặc đặt câu hỏi về quá trình "
                "ứng tuyển và phát triển nghề nghiệp."
            ),
        }

    async def create_workflow(self, state: ConversationState) -> dict[str, Any]:
        workflow = plan_workflow(state)

        logger.info(
            "Conversation workflow planned",
            extra={
                "workflow_type": workflow.workflow_type.value,
                "steps": [
                    step.value
                    for step in workflow.steps
                ],
                "current_step": (
                    workflow.current_step.value
                    if workflow.current_step
                    else None
                ),
            },
        )

        return {"workflow": workflow}

    async def execute_workflow_job_matching(self, state: ConversationState) -> dict[str, Any]:
        workflow = state.get("workflow")
        cv_profile = state.get("cv_profile")
        search_result = state.get("job_search_result")

        if workflow is None:
            raise ValueError("Workflow plan is required for workflow job matching. ")

        if cv_profile is None:
            missing_inputs = [RequiredInput.CV]

            return {
                "route": ConversationRoute.CLARIFICATION,
                "status": ConversationStatus.NEEDS_CLARIFICATION,
                "missing_inputs": missing_inputs,
                "assistant_message": self._build_clarification_message(
                    missing_inputs=missing_inputs,
                    generated_question=None,
                ),
            }

        if search_result is None:
            raise ValueError("Job search result is required before workflow matching.")

        candidates = search_result.items[:WORKFLOW_MATCH_LIMIT]

        if not candidates:
            updated_workflow = workflow.model_copy(
                update={"current_step": WorkflowStep.COMPLETED}
            )

            return {
                "workflow": updated_workflow,
                "workflow_job_matches": [],
                "status": ConversationStatus.COMPLETED,
                "assistant_message": (
                    "Tôi chưa tìm thấy công việc phù hợp để "
                    "thực hiện bước đánh giá CV."
                ),
            }

        tasks = [self._match_workflow_job(cv_profile=cv_profile, job=hit.job) for hit in candidates]

        matches = await asyncio.gather(*tasks)

        ranked_matches = sorted(matches, key=lambda item: item.match.overall_score, reverse=True)

        updated_workflow = advance_workflow(
            workflow,
            WorkflowStep.JOB_MATCHING,
        )

        logger.info(
            "Workflow job matching completed",
            extra={
                "candidate_count": len(candidates),
                "matched_count": len(ranked_matches),
                "best_score": (
                    ranked_matches[0].match.overall_score
                    if ranked_matches
                    else None
                ),
                "next_step": updated_workflow.current_step.value,
            },
        )

        return {
            "workflow_job_matches": ranked_matches,
            "workflow": updated_workflow,
        }

    async def execute_workflow_job_search(self, state: ConversationState) -> dict[str, Any]:
            workflow = state.get("workflow")
    
            if workflow is None:
                raise ValueError("Workflow plan is required for workflow job search.")
    
            request = JobSearchRequest(
                query=state['message'],
                page=1,
                page_size=10,
            )
    
            search_context = build_job_search_context(state.get("cv_profile"))
    
            result = await self._job_search_service(request, context=search_context)
    
            updated_workflow = advance_workflow(workflow, WorkflowStep.JOB_SEARCH,)
    
            logger.info(
                "Workflow job search completed",
                extra={
                    "query": request.query,
                    "returned_items": len(result.items),
                    "next_step": updated_workflow.current_step.value,
                },
            )
    
            return {
                "job_search_resultl": result,
                "workflow": updated_workflow,
            }

    async def execute_workflow_career_advice(self, state: ConversationState) -> dict[str, Any]:
        workflow = state.get("workflow")

        if workflow is None:
            raise ValueError("Workflow plan is required for workflow career advice.")

        advice_input = CareerAdviceInput(
            user_request=state['message'],
            cv_profile=state.get("cv_profile"),
        )

        result = await self._career_advice_service.advise(advice_input)

        updated_workflow = advance_workflow(
            workflow,
            WorkflowStep.CAREER_ADVICE,
        )

        logger.info(
            "Workflow career advice completed",
            extra={
                "is_personalized": result.is_personalized,
                "recommended_role_count": len(
                    result.recommended_roles
                ),
                "next_step": updated_workflow.current_step.value,
            },
        )

        return {
            "career_advice_result": result,
            "workflow": updated_workflow,
        }

    async def build_workflow_response(self, state: ConversationState) -> dict[str, Any]:
        matches = state.get("workflow_job_matches", [])
        career_advice = state.get("career_advice_result")
        search_result = state.get("job_search_result")

        if matches:
            lines = ["Tôi đã tìm và đánh giá các công việc phù hợp nhất với CV của bạn:"]

            for index, item in enumerate(matches, start=1):
                job = item.job
                match = item.match

                company = job.company or "Không rõ công ty"

                lines.append(
                    f"{index}. {job.title} - {company}: "
                    f"{match.overall_score:.1f}/100"
                )

            if career_advice is None:
                advice_message = self._build_career_advice_message(career_advice)

                lines.extend(["", advice_message])

            assistant_message = "\n".join(lines)

        elif search_result is not None:
            assistant_message = self._build_job_search_message(
                search_result,
                used_cv=state.get("cv_profile") is not None,
            )

        else:
            assistant_message = "Workflow đã hoàn thành nhưng chưa có kết quả phù hợp."

        logger.info(
            "Workflow response built",
            extra={
                "matched_jobs": len(matches),
                "has_career_advice": career_advice is not None,
            },
        )

        return {
            "status": ConversationStatus.COMPLETED,
            "missing_inputs": [],
            "assistant_message": assistant_message,
        }
   
    @staticmethod
    def _build_clarification_message(*, missing_inputs: list[RequiredInput], generated_question: str | None) -> str:
        missing_cv = RequiredInput.CV in missing_inputs
        missing_jd = RequiredInput.JOB_DESCRIPTION in missing_inputs

        if missing_cv and missing_jd:
            return (
                "Vui lòng tải lên CV và cung cấp mô tả công việc "
                "để tôi thực hiện yêu cầu này."
            )

        if missing_cv:
            return (
                "Vui lòng tải lên CV để tôi có thể thực hiện "
                "yêu cầu này."
            )

        if missing_jd:
            return (
                "Vui lòng cung cấp mô tả công việc (JD) để tôi "
                "có thể thực hiện yêu cầu này."
            )

        if generated_question:
            return generated_question

        return "Bạn có thể cung cấp thêm thông tin về yêu cầu không?"

    @staticmethod 
    def _build_job_search_message(result: JobSearchResult, *, used_cv: bool) -> str:
        returned_count = len(result.items)

        if returned_count == 0:
            return (
                "Tôi chưa tìm thấy công việc phù hợp với tiêu chí hiện tại. "
                "Bạn có thể thử mở rộng địa điểm, kỹ năng hoặc cấp độ kinh nghiệm."
            )

        if used_cv:
            return (
                f"Tôi đã chọn ra {returned_count} công việc có mức độ liên quan "
                "cao nhất dựa trên yêu cầu và thông tin nghề nghiệp trong CV của bạn."
            )

        return (
            f"Tôi đã chọn ra {returned_count} công việc có mức độ liên quan "
            "cao nhất với yêu cầu tìm kiếm của bạn."
        )

    @staticmethod 
    def _build_job_matching_message(result: JobMatchingResult) -> str:
        recommendation_label = MATCH_RECOMMENDATION_LABELS[result.recommendation]

        return (
            f"Mức độ phù hợp của CV với công việc là "
            f"{result.overall_score:.2f}/100 "
            f"({recommendation_label}). {result.summary}"
        )

    @staticmethod
    def _build_cv_analysis_message(result: CVAnalysisResult) -> str:
        quality_label = CV_QUALITY_LABELS[result.quality_level]

        return (
            f"Điểm chất lượng nội dung CV của bạn là "
            f"{result.overall_score:.2f}/100 "
            f"(mức {quality_label}). {result.summary}"
        )

    @staticmethod
    def _build_career_advice_message(result: CareerAdviceResult) -> str:
        prefix = (
            "Dựa trên thông tin trong CV của bạn, "
            if result.is_personalized
            else "Dựa trên mục tiêu bạn cung cấp, "
        )

        if result.recommended_roles:
            primary_role = result.recommended_roles[0].role_title

            return (
                f"{prefix}hướng ưu tiên là "
                f"{primary_role}. {result.summary}"
            )

        return f"{prefix}{result.summary}"

    @staticmethod
    def _build_cover_letter_message(result: CoverLetterResult) -> str:
        return (
            "Tôi đã tạo thư ứng tuyển dựa trên CV và "
            f"mô tả công việc của bạn "
            f"({result.word_count} từ)."
        )

    async def _match_workflow_job(self, *, cv_profile, job) -> WorkflowJobMatch:
        matching_input = JobMatchingInput(
            cv_profile=cv_profile,
            job=JobMatchTarget.from_normalized_job(job),
        )

        result = await self._job_matching_service.match(matching_input)

        return WorkflowJobMatch(job=job, match=result)