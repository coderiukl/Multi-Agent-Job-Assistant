from app.agents.state import AgentState
from app.core.llm import get_llm
from langchain_core.messages import SystemMessage, HumanMessage

RESPONDER_SYSTEM_PROMPT = """
Bạn là trợ lý tư vấn nghề nghiệp thông minh, thân thiện.
Nhiệm vụ: trả lời các câu hỏi chung về nghề nghiệp, tìm việc, phỏng vấn, thị trường lao động Việt Nam.

Nếu user hỏi ngoài phạm vi nghề nghiệp, hãy nhẹ nhàng hướng họ trở lại chủ đề chính.
Trả lời bằng tiếng Việt, ngắn gọn, thực tế.
"""


async def responder_node(state: AgentState) -> AgentState:
    llm = get_llm()

    response = await llm.ainvoke([
        SystemMessage(content=RESPONDER_SYSTEM_PROMPT),
        *state["messages"],
    ])

    return {
        **state,
        "messages": [*state["messages"], response],
        "response_type": "general",
    }