from langgraph.graph import StateGraph, END
from app.agents.state import AgentState
from app.agents.intent import intent_node
from app.agents.matcher import matcher_node
from app.agents.cv_advisor import cv_advisor_node
from app.agents.responder import responder_node

def route_by_intent(state: AgentState) -> str:
    intent = state.get("intent", "general")
    if intent == "job_search":
        return "matcher"
    elif intent == "cv_advice":
        return "cv_advisor"
    else:
        return "responder"

def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    # Thêm nodes
    graph.add_node("intent", intent_node)
    graph.add_node("matcher", matcher_node)
    graph.add_node("cv_advisor", cv_advisor_node)
    graph.add_node("responder", responder_node)

    # Entry point
    graph.set_entry_point("intent")

    # Route sau intent
    graph.add_conditional_edges(
        "intent",
        route_by_intent,
        {
            "matcher": "matcher",
            "cv_advisor": "cv_advisor",
            "responder": "responder",
        },
    )

    # Tất cả nodes đều kết thúc tại END
    graph.add_edge("matcher", END)
    graph.add_edge("cv_advisor", END)
    graph.add_edge("responder", END)

    return graph.compile()


# Singleton — import và dùng trực tiếp
agent_graph = build_graph()