from typing import cast, Any

from langgraph.graph.state import CompiledStateGraph

from app.graphs.conversation.state import ConversationState

from app.schemas.conversation import ConversationResponseData
from app.schemas.conversations_intent import ConversationRequest, IntentAnalysisResult


class ConversationService:
    def __init__(self, *, graph: CompiledStateGraph) -> None:
        self._graph = graph

    async def process(self, request: ConversationRequest) -> ConversationResponseData:
        state = await self._invoke_graph(request)

        return ConversationResponseData(
            thread_id=request.thread_id,
            assistant_message=state["assistant_message"],
            status=state["status"],
            route=state["route"],
            intent=state["intent"],
            cv_id=request.cv_id,
            missing_inputs=state.get("missing_inputs", []),
            workflow=state.get("workflow"),
            cv_analysis_result=state.get("cv_analysis_result"),
            career_advice_result=state.get("career_advice_result"),
            cover_letter_result=state.get("cover_letter_result"),
            job_search_result=state.get("job_search_result"),
            job_matching_result=state.get("job_matching_result"),
            workflow_job_matches=state.get("workflow_job_matches", []),
        )
    
    async def analyze_intent(self, request: ConversationRequest) -> IntentAnalysisResult:
        state = await self._invoke_graph(request, stop_after_intent=True)

        return state['intent']
    
    async def _invoke_graph(self, request: ConversationRequest, stop_after_intent: bool = False) -> ConversationState:
        initial_state: ConversationState = {
            "message": request.message,
        }

        if request.cv_id is not None:
            initial_state["cv_id"] = request.cv_id

        if request.job_description is not None:
            initial_state["job_description"] = request.job_description

        config: dict[str, Any] = {
            "configurable": {
                "thread_id": str(request.thread_id),
            }
        }

        if stop_after_intent:
            result = await self._graph.ainvoke(
                initial_state,
                config=config,
                interrupt_after=["analyze_intent"]
            )
        else:
            result = await self._graph.ainvoke(initial_state, config=config)

        return cast(ConversationState, result)