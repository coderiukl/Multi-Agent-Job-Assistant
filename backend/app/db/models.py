import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, Text, String, ForeignKey, Integer, BigInteger, JSON, Float, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relationships
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    files: Mapped[list["File"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    analysis_results: Mapped[list["AnalysisResult"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(100), nullable=True)

    user: Mapped["User"] = relationship(back_populates="refresh_tokens")

class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(back_populates="conversation", cascade="all, delete-orphan")
    files: Mapped[list["File"]] = relationship(back_populates="conversation")
    analysis_results: Mapped[list["AnalysisResult"]] = relationship(back_populates="conversation", cascade="all, delete-orphan")
    agent_runs: Mapped[list["AgentRun"]] = relationship(back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(50))
    # "user" | "assistant" | "system" | "tool"
    sender_name: Mapped[str | None] = mapped_column(String(255))
    # tên agent nếu role="tool", tên user nếu role="user"
    content: Mapped[str] = mapped_column(Text)
    message_type: Mapped[str | None] = mapped_column(String(50))
    # "text" | "cv_upload" | "analysis" | "job_match" | "error"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relationships
    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
    agent_runs: Mapped[list["AgentRun"]] = relationship(back_populates="message", cascade="all, delete-orphan")

class File(Base):
    """
    CV hoặc JD được upload trong 1 conversation.

    status flow:
        uploaded -> parsing -> embedded -> done
                            -> failed
    """
    __tablename__ = "files"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True
    )

    # Metadata file
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)   # "NguyenVanA_CV.pdf"
    stored_name: Mapped[str] = mapped_column(String(255), nullable=False)     # tên file sau khi rename trên disk
    file_path: Mapped[str] = mapped_column(Text, nullable=False)              # path trên disk / S3
    mime_type: Mapped[str | None] = mapped_column(String(100))                # "application/pdf" | "application/vnd..."
    size: Mapped[int | None] = mapped_column(BigInteger)                      # bytes

    # Trạng thái xử lý pipeline
    status: Mapped[str] = mapped_column(String(20), default="uploaded")
    # uploaded -> parsing -> embedded -> done | failed

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="files")
    conversation: Mapped["Conversation | None"] = relationship(back_populates="files")
    chunks: Mapped[list["FileChunk"]] = relationship(back_populates="file", cascade="all, delete-orphan")
    analysis_results: Mapped[list["AnalysisResult"]] = relationship(back_populates="file")
    match_results: Mapped[list["MatchResult"]] = relationship("MatchResult", back_populates="file", cascade="all, delete-orphan")


class FileChunk(Base):
    """
    CV được chia thành nhiều chunk để embed và search vector.
    Mỗi chunk có 1 point riêng trong Qdrant collection "cv_chunks".
    """
    __tablename__ = "file_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("files.id"), nullable=False
    )

    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)         # thứ tự chunk: 0, 1, 2, ...
    content: Mapped[str] = mapped_column(Text, nullable=False)                # text của chunk
    page_number: Mapped[int | None] = mapped_column(Integer)                  # trang trong PDF gốc
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)

    # Qdrant
    qdrant_point_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # "BAAI/bge-m3" lúc dev, "text-embedding-3-small" lúc prod
    embedded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relationships
    file: Mapped["File"] = relationship(back_populates="chunks")


class AnalysisResult(Base):
    """
    Kết quả phân tích từ một agent (CV analyzer, JD matcher, v.v.)
    Gắn với conversation + file cụ thể để dễ truy vấn lại.
    """
    __tablename__ = "analysis_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False
    )
    file_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("files.id"), nullable=True
    )

    agent_name: Mapped[str] = mapped_column(String(255))
    # "cv_analyzer" | "jd_matcher" | "job_searcher" | "improvement_advisor"

    result_type: Mapped[str] = mapped_column(String(50))
    # "summary" | "extraction" | "classification" | "matching"

    result_text: Mapped[str | None] = mapped_column(Text)       # nội dung trả lời dạng text
    result_json: Mapped[dict | None] = mapped_column(JSONB)     # structured output (skills[], matches[], v.v.)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="analysis_results")
    conversation: Mapped["Conversation"] = relationship(back_populates="analysis_results")
    file: Mapped["File | None"] = relationship(back_populates="analysis_results")


class AgentRun(Base):
    """
    Log chi tiết từng lần agent chạy — dùng để debug, trace, và analytics.
    Gắn với message cụ thể đã trigger agent đó.
    """
    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id"), nullable=True
    )

    agent_name: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="running")
    # "running" | "success" | "failed"

    input_json: Mapped[dict | None] = mapped_column(JSONB)      # input truyền vào agent
    output_json: Mapped[dict | None] = mapped_column(JSONB)     # output agent trả về
    error_message: Mapped[str | None] = mapped_column(Text)     # traceback nếu failed

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    conversation: Mapped["Conversation"] = relationship(back_populates="agent_runs")
    message: Mapped["Message | None"] = relationship(back_populates="agent_runs")

class MatchResult(Base):
    __tablename__ = "match_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    file: Mapped["File"] = relationship("File", back_populates="match_results")
    job: Mapped["Job"] = relationship("Job", back_populates="match_results")
    
    __table_args__ = (
        UniqueConstraint("file_id", "job_id", name="uq_match_file_job"),
    )

class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # ── Core fields ──
    title: Mapped[str] = mapped_column(String, nullable=False)
    company: Mapped[str | None] = mapped_column(String, nullable=True)
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    country: Mapped[str | None] = mapped_column(String, nullable=True)
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    contract_type: Mapped[str | None] = mapped_column(String, nullable=True)
    working_hours: Mapped[str | None] = mapped_column(String, nullable=True)

    # ── Salary ──
    salary_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_avg: Mapped[float | None] = mapped_column(Float, nullable=True)
    salary_raw: Mapped[str | None] = mapped_column(String, nullable=True)  # fix: float → str

    # ── Skills / Requirements ──
    technical_skills: Mapped[str | None] = mapped_column(Text, nullable=True)
    soft_skills: Mapped[str | None] = mapped_column(Text, nullable=True)
    qualifications: Mapped[str | None] = mapped_column(Text, nullable=True)
    experience_required: Mapped[str | None] = mapped_column(String, nullable=True)
    languages_required: Mapped[str | None] = mapped_column(String, nullable=True)  # fix: language_ → languages_
    benefits: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Full text ──
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    requirements_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Meta ──
    url: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    source: Mapped[str | None] = mapped_column(String, default="csv")
    qdrant_point_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)  # fix: server_default → default
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # ── Relationships ──
    match_results: Mapped[list["MatchResult"]] = relationship("MatchResult", back_populates="job")