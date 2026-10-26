"""AI 库 ORM 模型（Phase 0 基线）。

会话/消息的正本在客服库；本库只存 Agent 运行、工具调用、知识库与评测。
所有业务表带 tenant_id；知识库向量落在 Milvus，本库存 chunk 元数据。
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def uuid_pk():
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def created_at_col():
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def updated_at_col():
    return mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# ---------------------------------------------------------------------------
# Agent 运行
# ---------------------------------------------------------------------------
class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = uuid_pk()
    run_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    request_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    turn_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="RUNNING")
    intent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    skill_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    main_model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fast_model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decision: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    usage: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()
    heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('RUNNING','DECISION_PREPARED','COMPLETED','HANDED_OFF',"
            "'FAILED','SUPERSEDED')",
            name="ck_agent_runs_status",
        ),
        Index("ix_agent_runs_tenant_created", "tenant_id", "created_at"),
        Index("ix_agent_runs_conversation", "conversation_id", "created_at"),
    )


class AgentToolCall(Base):
    __tablename__ = "agent_tool_calls"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_pk: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False)
    arguments: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ok")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = created_at_col()

    __table_args__ = (
        UniqueConstraint("run_pk", "seq", name="uq_agent_tool_calls_run_seq"),
        CheckConstraint(
            "status IN ('ok','error','blocked')", name="ck_agent_tool_calls_status"
        ),
    )


# ---------------------------------------------------------------------------
# 知识库
# ---------------------------------------------------------------------------
class KnowledgeArticle(Base):
    __tablename__ = "knowledge_articles"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), nullable=False)
    scope: Mapped[str] = mapped_column(String(16), nullable=False, default="tenant")
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(32), nullable=False)
    product_models: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    content_md: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    effective_from: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    effective_to: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    source: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()

    __table_args__ = (
        UniqueConstraint("tenant_id", "slug", name="uq_knowledge_articles_tenant_slug"),
        CheckConstraint(
            "scope IN ('tenant','all_dealers')", name="ck_knowledge_articles_scope"
        ),
        CheckConstraint(
            "doc_type IN ('faq','policy','manual','troubleshooting','script',"
            "'course','firmware','store')",
            name="ck_knowledge_articles_doc_type",
        ),
        CheckConstraint(
            "status IN ('draft','published','archived')",
            name="ck_knowledge_articles_status",
        ),
        Index("ix_knowledge_articles_tenant_status", "tenant_id", "status", "doc_type"),
    )


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_articles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vector_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending"
    )
    indexed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = created_at_col()

    __table_args__ = (
        UniqueConstraint("article_id", "chunk_index", name="uq_knowledge_chunks_article_index"),
        CheckConstraint(
            "vector_status IN ('pending','indexed','failed')",
            name="ck_knowledge_chunks_vector_status",
        ),
        Index("ix_knowledge_chunks_tenant_vector", "tenant_id", "vector_status"),
    )


class KnowledgeFeedback(Base):
    __tablename__ = "knowledge_feedback"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    article_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_articles.id", ondelete="SET NULL"),
        nullable=True,
    )
    chunk_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    helpful: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = created_at_col()

    __table_args__ = (
        Index("ix_knowledge_feedback_tenant_created", "tenant_id", "created_at"),
    )


# ---------------------------------------------------------------------------
# 写操作 / Prompt / 评测
# ---------------------------------------------------------------------------
class ActionRequest(Base):
    __tablename__ = "action_requests"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    action_type: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="prepared")
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()

    __table_args__ = (
        CheckConstraint(
            "action_type IN ('create_repair_ticket','cancel_unshipped_order')",
            name="ck_action_requests_type",
        ),
        CheckConstraint(
            "status IN ('prepared','confirmed','cancelled','failed')",
            name="ck_action_requests_status",
        ),
        Index("ix_action_requests_tenant_status", "tenant_id", "status", "created_at"),
    )


class PromptVersion(Base):
    __tablename__ = "prompt_versions"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    created_at: Mapped[datetime] = created_at_col()

    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_prompt_versions_name_version"),
        CheckConstraint(
            "status IN ('draft','active','retired')", name="ck_prompt_versions_status"
        ),
        Index(
            "uq_prompt_versions_active",
            "name",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )


class AgentEvaluation(Base):
    __tablename__ = "agent_evaluations"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    eval_set: Mapped[str] = mapped_column(String(64), nullable=False)
    case_id: Mapped[str] = mapped_column(String(64), nullable=False)
    expected: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    actual: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    scores: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = created_at_col()

    __table_args__ = (
        Index("ix_agent_evaluations_tenant_set", "tenant_id", "eval_set", "created_at"),
    )


class BadCase(Base):
    __tablename__ = "bad_cases"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    detail: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()

    __table_args__ = (
        CheckConstraint(
            "status IN ('open','reviewing','fixed','ignored')", name="ck_bad_cases_status"
        ),
        Index("ix_bad_cases_tenant_status", "tenant_id", "status", "created_at"),
    )


class ModelUsageDaily(Base):
    __tablename__ = "model_usage_daily"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    usage_date: Mapped[date] = mapped_column(Date, nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    requests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prompt_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    cost_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "usage_date", "model", name="uq_model_usage_daily_key"
        ),
    )
