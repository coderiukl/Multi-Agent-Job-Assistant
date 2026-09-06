from enum import StrEnum

from app.graphs.conversation.state import ConversationState
from app.schemas.conversation import ConversationRoute, RequiredInput
from app.schemas.conversations_intent import ConversationIntent
from app.schemas.workflow import WorkflowStep, WorkflowType

INTENT_TO_STATE: dict[ConversationIntent, ConversationRoute] = {
    ConversationIntent.CV_ANALYSIS: ConversationRoute.CV_ANALYSIS,
    ConversationIntent.JOB_SEARCH: ConversationRoute.JOB_SEARCH,
    ConversationIntent.JOB_MATCHING: ConversationRoute.JOB_MATCHING,
    ConversationIntent.CAREER_ADVICE: ConversationRoute.CAREER_ADVICE,
    ConversationIntent.COVER_LETTER: ConversationRoute.COVER_LETTER,
    ConversationIntent.GENERAL_QUESTION: ConversationRoute.GENERAL_QUESTION,
    ConversationIntent.SMALL_TALK: ConversationRoute.SMALL_TALK,
    ConversationIntent.OUT_OF_SCOPE: ConversationRoute.OUT_OF_SCOPE,
    ConversationIntent.CLARIFICATION: ConversationRoute.CLARIFICATION,
}

class IntentGateRoute(StrEnum):
    CLARIFICATION = "clarification"
    PLAN_WORKFLOW = "plan_workflow"

class WorkflowRoute(StrEnum):
    SINGLE_AGENT = "single_agent"
    JOB_SEARCH = "job_search"
    JOB_MATCHING = "job_matching"
    CAREER_ADVICE = "career_advice"
    END = "end"

def collect_missing_inputs(state: ConversationState) -> list[RequiredInput]:
    intent = state["intent"]
    missing_inputs : list[RequiredInput] = []

    if intent.requires_cv and not state.get("has_cv", False):
        missing_inputs.append(RequiredInput.CV)

    if intent.requires_jd and not state.get('has_jd', False):
        missing_inputs.append(RequiredInput.JOB_DESCRIPTION)

    return missing_inputs

def route_after_analysis(state: ConversationState) -> IntentGateRoute:
    intent = state["intent"]
    missing_inputs = collect_missing_inputs(state)

    if intent.needs_clarification or missing_inputs:
        return IntentGateRoute.CLARIFICATION

    return IntentGateRoute.PLAN_WORKFLOW

def route_after_intent(state: ConversationState) -> ConversationRoute:
    intent = state["intent"]
    
    return INTENT_TO_STATE[intent.primary_intent]

def route_workflow_start(state: ConversationState) -> WorkflowRoute:
    workflow = state.get("workflow")

    if workflow is None:
        return WorkflowRoute.SINGLE_AGENT

    if workflow.workflow_type == WorkflowType.SINGLE_AGENT:
        return WorkflowRoute.SINGLE_AGENT

    if workflow.current_step == WorkflowStep.JOB_SEARCH:
        return WorkflowRoute.JOB_SEARCH

    if workflow.current_step == WorkflowStep.JOB_MATCHING:
        return WorkflowRoute.JOB_MATCHING

    if workflow.current_step == WorkflowStep.CAREER_ADVICE:
        return WorkflowRoute.CAREER_ADVICE

    return WorkflowRoute.END

def route_next_workflow_step(state: ConversationState) -> WorkflowRoute:
    workflow = state.get("workflow")

    if workflow is None:
        return WorkflowRoute.END

    if workflow.current_step == WorkflowStep.JOB_SEARCH:
        return WorkflowRoute.JOB_SEARCH

    if workflow.current_step == WorkflowStep.JOB_MATCHING:
        return WorkflowRoute.JOB_MATCHING

    if workflow.current_step == WorkflowStep.CAREER_ADVICE:
        return WorkflowRoute.CAREER_ADVICE

    return WorkflowRoute.END
