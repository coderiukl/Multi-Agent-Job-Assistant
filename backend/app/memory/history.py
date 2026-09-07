from collections.abc import Sequence

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage


MAX_HISTORY_MESSAGES = 6
MAX_HISTORY_CHARS = 6_000
MAX_CONTEXT_USER_MESSAGES = 3

def get_previous_message(
    messages: Sequence[BaseMessage],
    *,
    current_message: str,
) -> list[BaseMessage]:
    previous_messages = list(messages)

    if previous_messages and isinstance(previous_messages[-1], HumanMessage) and _message_text(previous_messages[-1]) == current_message:
        previous_messages.pop()

    return previous_messages

def format_conversation_history(
    messages: Sequence[BaseMessage],
    *,
    current_message: str,
) -> str:
    previous_messages = get_previous_message(messages=messages, current_message=current_message)

    recent_messages = previous_messages[-MAX_HISTORY_MESSAGES:]
    formatted_messages: list[str] = []

    for message in recent_messages:
        content = _message_text(message)

        if not content:
            continue

        if isinstance(message, HumanMessage):
            role = "User"
        elif isinstance(message, AIMessage):
            role = "Assistant"
        else:
            continue

        formatted_messages.append(f"{role}: {content}")

    if not formatted_messages:
        return "No previous conversation"

    history = "\n".join(formatted_messages)

    return history[-MAX_HISTORY_CHARS:]

def build_contextual_user_message(
    messages: Sequence[BaseMessage],
    *,
    current_message: str,
) -> str:
    previous_messages = get_previous_message(messages=messages, current_message=current_message)

    previous_user_messages = [
        _message_text(message)
        for message in previous_messages
        if isinstance(message, HumanMessage) and _message_text(message)
    ]

    previous_user_messages = previous_user_messages[-MAX_CONTEXT_USER_MESSAGES:]

    if not previous_user_messages:
        return current_message

    previous_requests = "\n".join(
        f"- {message}"
        for message in previous_user_messages
    )

    contextual_message = (
        "Previous user requests:\n"
        f"{previous_requests}\n\n"
        "Current user request:\n"
        f"{current_message}"
    )

    return contextual_message[-2000:]

def _message_text(message: BaseMessage) -> str:
    content = message.content

    if isinstance(content, str):
        return content.strip()

    return str(content).strip()