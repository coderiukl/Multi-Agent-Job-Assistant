from functools import lru_cache
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import OpenAI
from app.core.config import settings

DEFAULT_TEMPERATURE = 0.3

@lru_cache(maxsize=1)
def get_llm() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=settings.GEMINI_MODEL,          # ví dụ: "gemini-2.0-flash"
        google_api_key=settings.GEMINI_API_KEY,
        temperature=DEFAULT_TEMPERATURE,
        streaming=True,
    )


@lru_cache(maxsize=1)
def get_llm_no_stream() -> ChatGoogleGenerativeAI:
    """LLM streaming=False — dùng cho intent, keyword extraction."""
    return ChatGoogleGenerativeAI(
        model=settings.GEMINI_MODEL,
        google_api_key=settings.GEMINI_API_KEY,
        temperature=DEFAULT_TEMPERATURE,
        streaming=False,
        thinking_budget=0,
    )