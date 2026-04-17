import json
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.state import AgentState
from app.agents.workflow import agent_graph
from app.core.dependencies import get_current_user, get_db
from app.db.models import Conversation, Message, User
from app.services.cv_service import upload_and_embed_cv

router = APIRouter(prefix="/conversations", tags=["conversations"])


class ConversationCreate(BaseModel):
    title: Optional[str] = "Cuộc trò chuyện mới"


class ConversationUpdate(BaseModel):
    title: str


class ConversationResponse(BaseModel):
    id: uuid.UUID
    title: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    message_type: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("", response_model=list[ConversationResponse])
async def list_conversations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc(), Conversation.created_at.desc())
    )
    return result.scalars().all()


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    body: ConversationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conv = Conversation(
        user_id=current_user.id,
        title=(body.title or "Cuộc trò chuyện mới").strip(),
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await _get_own_conv(db, conversation_id, current_user.id)


@router.patch("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: uuid.UUID,
    body: ConversationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conv = await _get_own_conv(db, conversation_id, current_user.id)
    conv.title = body.title.strip() or "Cuộc trò chuyện mới"
    await db.commit()
    await db.refresh(conv)
    return conv


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conv = await _get_own_conv(db, conversation_id, current_user.id)
    await db.delete(conv)
    await db.commit()


@router.get("/{conversation_id}/messages", response_model=list[MessageResponse])
async def list_messages(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_own_conv(db, conversation_id, current_user.id)

    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    return result.scalars().all()


@router.post("/{conversation_id}/chat")
async def chat(
    conversation_id: uuid.UUID,
    message: str = Form(...),
    cv_id: Optional[uuid.UUID] = Form(None),
    file: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conv = await _get_own_conv(db, conversation_id, current_user.id)

    content = message.strip()
    if not content and not file:
        raise HTTPException(status_code=422, detail="Message hoặc file không được để trống")

    if file:
        db_file, _ = await upload_and_embed_cv(file=file, db=db, current_user=current_user)
        cv_id = db_file.id

    user_msg = Message(
        conversation_id=conversation_id,
        role="user",
        content=content if content else f"Đã upload file: {file.filename}",
        message_type="chat",
    )
    db.add(user_msg)

    if conv.title == "Cuộc trò chuyện mới" and content:
        conv.title = content[:60]

    await db.commit()

    initial_state: AgentState = {
        "messages": [HumanMessage(content=content if content else "Hãy phân tích file CV vừa tải lên")],
        "user_id": str(current_user.id),
        "cv_id": cv_id,
        "intent": None,
        "matched_jobs": None,
        "response_type": None,
    }

    return StreamingResponse(
        _stream_and_save(
            state=initial_state,
            conversation_id=conversation_id,
            db=db,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _get_own_conv(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Conversation:
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation không tồn tại")
    return conv


async def _stream_and_save(
    state: AgentState,
    conversation_id: uuid.UUID,
    db: AsyncSession,
):
    full_response = ""
    response_type = "general"
    matched_jobs = None

    try:
        async for event in agent_graph.astream_events(state, version="v2"):
            kind = event.get("event")

            if kind == "on_chat_model_stream":
                token = event["data"]["chunk"].content
                if token:
                    full_response += token
                    yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"

            elif kind == "on_chain_end" and event.get("name") == "LangGraph":
                output = event["data"].get("output", {}) or {}
                response_type = output.get("response_type", "general")
                matched_jobs = output.get("matched_jobs")

        if full_response:
            ai_msg = Message(
                conversation_id=conversation_id,
                role="assistant",
                content=full_response,
                message_type=response_type,
            )
            db.add(ai_msg)
            await db.commit()

        payload: dict = {"done": True, "response_type": response_type}
        if matched_jobs:
            payload["matched_jobs"] = matched_jobs

        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    except Exception as e:
        error_msg = f"Đã xảy ra lỗi khi xử lý hội thoại: {str(e)}"

        ai_msg = Message(
            conversation_id=conversation_id,
            role="assistant",
            content=error_msg,
            message_type="error",
        )
        db.add(ai_msg)
        await db.commit()

        yield f"data: {json.dumps({'error': error_msg, 'done': True}, ensure_ascii=False)}\n\n"