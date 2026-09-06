from app.graphs.conversation.state import ConversationState
from app.schemas.conversations_intent import ConversationIntent, IntentAnalysisResult
from app.schemas.workflow import WorkflowPlan, WorkflowStep, WorkflowType

def _collect_requested_intents(intent: IntentAnalysisResult) -> set[ConversationIntent]:
    return {
        intent.primary_intent,
        *intent.secondary_intents,
    }

def create_workflow_plan(intent: IntentAnalysisResult) -> WorkflowPlan:
    intents = _collect_requested_intents(intent)

    has_job_search = ConversationIntent.JOB_SEARCH in intents
    has_job_matching = ConversationIntent.JOB_MATCHING in intents
    has_career_advice = ConversationIntent.CAREER_ADVICE in intents

    if has_job_search and has_job_matching and has_career_advice:
        return WorkflowPlan(
            workflow_type=WorkflowType.FULL_CAREER,
            steps=[
                WorkflowStep.JOB_SEARCH,
                WorkflowStep.JOB_MATCHING,
                WorkflowStep.CAREER_ADVICE,
            ],
            current_step=WorkflowStep.JOB_SEARCH,
        )

    if has_job_search and has_job_matching:
        return WorkflowPlan(
            workflow_type=WorkflowType.JOB_RECOMMENDATION,
            steps=[
                WorkflowStep.JOB_SEARCH,
                WorkflowStep.JOB_MATCHING,
            ],
            current_step=WorkflowStep.JOB_SEARCH,
        )

    if has_job_search:
        return WorkflowPlan(
            workflow_type=WorkflowType.JOB_DISCOVERY,
            steps=[
                WorkflowStep.JOB_SEARCH,
            ],
            current_step=WorkflowStep.JOB_SEARCH
        )

    return WorkflowPlan(
        workflow_type=WorkflowType.SINGLE_AGENT,
        steps=[],
        current_step=None,
    )

def plan_workflow(state: ConversationState) -> WorkflowPlan:
    intent = state["intent"]
    return create_workflow_plan(intent)
