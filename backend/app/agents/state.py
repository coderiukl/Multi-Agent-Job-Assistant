from typing import TypedDict, Any, Optional
import uuid

class AgentState(TypedDict, total=False):
    # User & context
    user_id: Optional[uuid.UUID]
    cv_id: Optional[uuid.UUID]
    conversation_id: Optional[uuid.UUID]
    messages: list[dict]

    # Intent
    intent: Optional[str]                  # "job_search" | "cv_advice" | "general"
    search_keyword: Optional[str] 
    search_location: Optional[str] 

    # Results
    matched_jobs: list[dict]
    web_count: int               # số job từ web
    db_count: int                # số job từ DB/CSV
    match_error: str | None

    # Response
    response: str
    response_type: str