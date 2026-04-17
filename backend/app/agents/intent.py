from app.agents.state import AgentState
from app.core.llm import get_llm_no_stream
from langchain_core.messages import HumanMessage, SystemMessage

INTENT_SYSTEM_PROMPT = """
Bạn là router. Phân loại intent của user thành 1 trong 3 loại:
- "job_search": user muốn tìm việc làm phù hợp với CV
- "cv_advice": user muốn được tư vấn cải thiện CV
- "general": câu hỏi chung, chào hỏi, hoặc không liên quan

Chỉ trả về đúng 1 trong 3 từ khóa trên, không giải thích.
"""

async def intent_node(state: AgentState) -> AgentState:
    llm = get_llm_no_stream()
    last_message = state["messages"][-1].content

    response = await llm.ainvoke([
        SystemMessage(content=INTENT_SYSTEM_PROMPT),
        HumanMessage(content=last_message),
    ])

    intent = response.content.strip().lower()
    if intent not in ("job_search", "cv_advice", "general"):
        intent = "general"

    return {**state, "intent": intent}