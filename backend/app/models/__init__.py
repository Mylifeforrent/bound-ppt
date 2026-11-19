from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.ids import new_id, utcnow


class Base(DeclarativeBase):
    pass


def _uuid_pk() -> Mapped[UUID]:
    return mapped_column(sa.Uuid(as_uuid=True), primary_key=True, default=new_id)


def _created() -> Mapped[datetime]:
    return mapped_column(sa.DateTime(timezone=True), default=utcnow, nullable=False)


def _updated() -> Mapped[datetime]:
    return mapped_column(sa.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class BillingAccount(Base):
    __tablename__ = "billing_account"

    id: Mapped[UUID] = _uuid_pk()
    name: Mapped[str | None] = mapped_column(sa.Text)
    plan: Mapped[str] = mapped_column(sa.Text, default="pilot", nullable=False)
    billing_status: Mapped[str | None] = mapped_column(sa.Text)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()
    deleted_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))


class AppUser(Base):
    __tablename__ = "app_user"

    id: Mapped[UUID] = _uuid_pk()
    account_id: Mapped[UUID | None] = mapped_column(sa.Uuid(as_uuid=True), sa.ForeignKey("billing_account.id"))
    email: Mapped[str] = mapped_column(sa.Text, unique=True, nullable=False)
    email_verified: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    image: Mapped[str | None] = mapped_column(sa.Text)
    name: Mapped[str | None] = mapped_column(sa.Text)
    role: Mapped[str] = mapped_column(sa.Text, default="OWNER", nullable=False)
    password_hash: Mapped[str | None] = mapped_column(sa.Text)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()
    deleted_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))


class Session(Base):
    __tablename__ = "session"

    id: Mapped[UUID] = _uuid_pk()
    session_token: Mapped[str] = mapped_column(sa.Text, unique=True, nullable=False)
    user_id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), sa.ForeignKey("app_user.id", ondelete="CASCADE"))
    expires: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = _created()


class AuthAccount(Base):
    __tablename__ = "auth_account"

    id: Mapped[UUID] = _uuid_pk()
    user_id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), sa.ForeignKey("app_user.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(sa.Text, nullable=False)
    provider_account_id: Mapped[str] = mapped_column(sa.Text, nullable=False)
    __table_args__ = (sa.UniqueConstraint("provider", "provider_account_id", name="uq_auth_provider_account"),)


class Project(Base):
    __tablename__ = "project"

    id: Mapped[UUID] = _uuid_pk()
    account_id: Mapped[UUID | None] = mapped_column(sa.Uuid(as_uuid=True), sa.ForeignKey("billing_account.id"))
    owner_user_id: Mapped[UUID | None] = mapped_column(sa.Uuid(as_uuid=True), sa.ForeignKey("app_user.id"))
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    topic: Mapped[str] = mapped_column(sa.Text, nullable=False)
    mode: Mapped[str] = mapped_column(sa.Text, default="FULLY_AUTOMATIC", nullable=False)
    status: Mapped[str] = mapped_column(sa.Text, default="ACTIVE", nullable=False)
    stage: Mapped[str] = mapped_column(sa.Text, default="INTAKE", nullable=False)
    version: Mapped[int] = mapped_column(sa.Integer, default=1, nullable=False)
    epoch: Mapped[int] = mapped_column(sa.Integer, default=1, nullable=False)
    schema_version: Mapped[int] = mapped_column(sa.Integer, default=1, nullable=False)
    current_profile_version_id: Mapped[UUID | None] = mapped_column(sa.Uuid(as_uuid=True))
    current_outline_version_id: Mapped[UUID | None] = mapped_column(sa.Uuid(as_uuid=True))
    current_style_selection_id: Mapped[UUID | None] = mapped_column(sa.Uuid(as_uuid=True))
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()
    deleted_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    purge_after: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    __table_args__ = (sa.Index("ix_project_owner_updated", "owner_user_id", "updated_at"),)


class ProjectEventCounter(Base):
    __tablename__ = "project_event_counter"

    project_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True), sa.ForeignKey("project.id", ondelete="CASCADE"), primary_key=True
    )
    last_sequence: Mapped[int] = mapped_column(sa.BigInteger, default=0, nullable=False)


class Material(Base):
    __tablename__ = "material"

    id: Mapped[UUID] = _uuid_pk()
    project_id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), sa.ForeignKey("project.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(sa.Text, nullable=False)
    status: Mapped[str] = mapped_column(sa.Text, default="PENDING", nullable=False)
    display_name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    mime_type: Mapped[str | None] = mapped_column(sa.Text)
    size_bytes: Mapped[int] = mapped_column(sa.BigInteger, default=0, nullable=False)
    page_count: Mapped[int | None] = mapped_column(sa.Integer)
    content_ref: Mapped[str | None] = mapped_column(sa.Text)
    raw_ref: Mapped[str | None] = mapped_column(sa.Text)
    source_url: Mapped[str | None] = mapped_column(sa.Text)
    domain: Mapped[str | None] = mapped_column(sa.Text)
    error_code: Mapped[str | None] = mapped_column(sa.Text)
    error_message_key: Mapped[str | None] = mapped_column(sa.Text)
    version: Mapped[int] = mapped_column(sa.Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()
    removed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    __table_args__ = (sa.Index("ix_material_project_status", "project_id", "status"),)


class MaterialDigest(Base):
    __tablename__ = "material_digest"

    id: Mapped[UUID] = _uuid_pk()
    project_id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), sa.ForeignKey("project.id", ondelete="CASCADE"))
    material_id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), sa.ForeignKey("material.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(sa.Integer, default=1, nullable=False)
    is_current: Mapped[bool] = mapped_column(sa.Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(sa.Text, default="PENDING", nullable=False)
    digest_ref: Mapped[str | None] = mapped_column(sa.Text)
    summary_preview: Mapped[str | None] = mapped_column(sa.Text)
    extracted_char_count: Mapped[int | None] = mapped_column(sa.Integer)
    length_bucket: Mapped[str | None] = mapped_column(sa.Text)
    parser_profile_version: Mapped[str] = mapped_column(sa.Text, default="v1", nullable=False)
    producer_job_id: Mapped[UUID | None] = mapped_column(sa.Uuid(as_uuid=True))
    created_at: Mapped[datetime] = _created()
    __table_args__ = (sa.UniqueConstraint("material_id", "version", name="uq_digest_material_version"),)


class SourceItem(Base):
    __tablename__ = "source_item"

    id: Mapped[UUID] = _uuid_pk()
    project_id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), sa.ForeignKey("project.id", ondelete="CASCADE"))
    origin: Mapped[str] = mapped_column(sa.Text, nullable=False)
    source_type: Mapped[str] = mapped_column(sa.Text, nullable=False)
    title: Mapped[str] = mapped_column(sa.Text, nullable=False)
    summary: Mapped[str] = mapped_column(sa.Text, nullable=False)
    domain: Mapped[str | None] = mapped_column(sa.Text)
    url_hash: Mapped[str | None] = mapped_column(sa.Text)
    content_ref: Mapped[str | None] = mapped_column(sa.Text)
    material_id: Mapped[UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True), sa.ForeignKey("material.id", ondelete="SET NULL")
    )
    gap_suggestion_id: Mapped[UUID | None] = mapped_column(sa.Uuid(as_uuid=True))
    rank: Mapped[int] = mapped_column(sa.Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = _created()
    __table_args__ = (sa.Index("ix_source_project_origin", "project_id", "origin", "created_at"),)


class InterviewQuestion(Base):
    __tablename__ = "interview_question"

    id: Mapped[UUID] = _uuid_pk()
    project_id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), sa.ForeignKey("project.id", ondelete="CASCADE"))
    question_key: Mapped[str] = mapped_column(sa.Text, nullable=False)
    position: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    prompt: Mapped[str] = mapped_column(sa.Text, nullable=False)
    options: Mapped[list[dict[str, Any]]] = mapped_column(sa.JSON, nullable=False)
    catalog_version: Mapped[str] = mapped_column(sa.Text, nullable=False)
    created_at: Mapped[datetime] = _created()
    __table_args__ = (
        sa.UniqueConstraint("project_id", "question_key", name="uq_question_project_key"),
        sa.UniqueConstraint("project_id", "position", name="uq_question_project_position"),
    )


class InterviewAnswer(Base):
    __tablename__ = "interview_answer"

    id: Mapped[UUID] = _uuid_pk()
    project_id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), sa.ForeignKey("project.id", ondelete="CASCADE"))
    question_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True), sa.ForeignKey("interview_question.id", ondelete="CASCADE"), unique=True
    )
    option_key: Mapped[str] = mapped_column(sa.Text, nullable=False)
    revision: Mapped[int] = mapped_column(sa.Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class GapSuggestion(Base):
    __tablename__ = "gap_suggestion"

    id: Mapped[UUID] = _uuid_pk()
    project_id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), sa.ForeignKey("project.id", ondelete="CASCADE"))
    batch: Mapped[int] = mapped_column(sa.Integer, default=1, nullable=False)
    label: Mapped[str] = mapped_column(sa.Text, nullable=False)
    reason: Mapped[str] = mapped_column(sa.Text, nullable=False)
    recommended: Mapped[bool] = mapped_column(sa.Boolean, default=False, nullable=False)
    position: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    status: Mapped[str] = mapped_column(sa.Text, default="SUGGESTED", nullable=False)
    producer_job_id: Mapped[UUID | None] = mapped_column(sa.Uuid(as_uuid=True))
    created_at: Mapped[datetime] = _created()
    __table_args__ = (sa.Index("ix_gap_project_batch", "project_id", "batch", "position"),)


class GapDecision(Base):
    __tablename__ = "gap_decision"

    id: Mapped[UUID] = _uuid_pk()
    project_id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), sa.ForeignKey("project.id", ondelete="CASCADE"))
    gap_suggestion_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True), sa.ForeignKey("gap_suggestion.id", ondelete="CASCADE"), unique=True
    )
    selected: Mapped[bool] = mapped_column(sa.Boolean, nullable=False)
    decided_at: Mapped[datetime] = _created()
    __table_args__ = (sa.Index("ix_gap_decision_project", "project_id", "decided_at"),)


class RequirementsProfile(Base):
    __tablename__ = "requirements_profile"

    id: Mapped[UUID] = _uuid_pk()
    project_id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), sa.ForeignKey("project.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    audience: Mapped[str] = mapped_column(sa.Text, nullable=False)
    goal: Mapped[str] = mapped_column(sa.Text, nullable=False)
    style_mood: Mapped[str] = mapped_column(sa.Text, nullable=False)
    page_count: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    materials_summary: Mapped[dict[str, Any]] = mapped_column(sa.JSON, nullable=False)
    web_scope: Mapped[dict[str, Any]] = mapped_column(sa.JSON, nullable=False)
    web_skipped: Mapped[bool] = mapped_column(sa.Boolean, default=False, nullable=False)
    content_strategy: Mapped[str] = mapped_column(sa.Text, nullable=False)
    source_refs: Mapped[list[str]] = mapped_column(sa.JSON, nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(sa.Text, nullable=False)
    producer_job_id: Mapped[UUID | None] = mapped_column(sa.Uuid(as_uuid=True))
    created_at: Mapped[datetime] = _created()
    __table_args__ = (sa.UniqueConstraint("project_id", "version", name="uq_profile_project_version"),)


class Page(Base):
    __tablename__ = "page"

    id: Mapped[UUID] = _uuid_pk()
    project_id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), sa.ForeignKey("project.id", ondelete="CASCADE"))
    page_type: Mapped[str] = mapped_column(sa.Text, nullable=False)
    created_at: Mapped[datetime] = _created()
    retired_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    __table_args__ = (sa.Index("ix_page_project_retired", "project_id", "retired_at"),)


class OutlineVersion(Base):
    __tablename__ = "outline_version"

    id: Mapped[UUID] = _uuid_pk()
    project_id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), sa.ForeignKey("project.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    confirmed_by_user_id: Mapped[UUID | None] = mapped_column(sa.Uuid(as_uuid=True))
    input_fingerprint: Mapped[str] = mapped_column(sa.Text, nullable=False)
    producer_job_id: Mapped[UUID | None] = mapped_column(sa.Uuid(as_uuid=True))
    schema_version: Mapped[int] = mapped_column(sa.Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = _created()
    __table_args__ = (sa.UniqueConstraint("project_id", "version", name="uq_outline_project_version"),)


class OutlineSectionVersion(Base):
    __tablename__ = "outline_section_version"

    id: Mapped[UUID] = _uuid_pk()
    outline_version_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True), sa.ForeignKey("outline_version.id", ondelete="CASCADE")
    )
    section_key: Mapped[str] = mapped_column(sa.Text, nullable=False)
    title: Mapped[str] = mapped_column(sa.Text, nullable=False)
    position: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    __table_args__ = (
        sa.UniqueConstraint("outline_version_id", "section_key", name="uq_outline_section_key"),
        sa.UniqueConstraint("outline_version_id", "position", name="uq_outline_section_position"),
    )


class OutlinePageVersion(Base):
    __tablename__ = "outline_page_version"

    id: Mapped[UUID] = _uuid_pk()
    outline_version_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True), sa.ForeignKey("outline_version.id", ondelete="CASCADE")
    )
    page_id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), sa.ForeignKey("page.id"))
    position: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    section_key: Mapped[str] = mapped_column(sa.Text, nullable=False)
    title: Mapped[str] = mapped_column(sa.Text, nullable=False)
    page_type: Mapped[str] = mapped_column(sa.Text, nullable=False)
    key_points: Mapped[list[str]] = mapped_column(sa.JSON, nullable=False)
    created_at: Mapped[datetime] = _created()
    __table_args__ = (
        sa.UniqueConstraint("outline_version_id", "page_id", name="uq_outline_page_page"),
        sa.UniqueConstraint("outline_version_id", "position", name="uq_outline_page_position"),
    )


class StyleDefinition(Base):
    __tablename__ = "style_definition"

    id: Mapped[UUID] = _uuid_pk()
    key: Mapped[str] = mapped_column(sa.Text, nullable=False)
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    version: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    scope: Mapped[str] = mapped_column(sa.Text, default="BUILTIN", nullable=False)
    palette: Mapped[dict[str, Any]] = mapped_column(sa.JSON, nullable=False)
    tokens: Mapped[dict[str, Any]] = mapped_column(sa.JSON, nullable=False)
    preview_ref: Mapped[str | None] = mapped_column(sa.Text)
    description: Mapped[str] = mapped_column(sa.Text, nullable=False)
    use_case: Mapped[str] = mapped_column(sa.Text, nullable=False, default="")
    license_status: Mapped[str] = mapped_column(sa.Text, default="CLEARED", nullable=False)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = _created()
    __table_args__ = (sa.UniqueConstraint("key", "version", name="uq_style_key_version"),)


class StyleSelection(Base):
    __tablename__ = "style_selection"

    id: Mapped[UUID] = _uuid_pk()
    project_id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), sa.ForeignKey("project.id", ondelete="CASCADE"))
    style_definition_id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), sa.ForeignKey("style_definition.id"))
    style_version: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    remember_preference: Mapped[bool] = mapped_column(sa.Boolean, default=False, nullable=False)
    version: Mapped[int] = mapped_column(sa.Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = _created()
    __table_args__ = (sa.Index("ix_style_selection_project", "project_id", "created_at"),)


class ArtifactVersion(Base):
    __tablename__ = "artifact_version"

    id: Mapped[UUID] = _uuid_pk()
    project_id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), sa.ForeignKey("project.id", ondelete="CASCADE"))
    page_id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), sa.ForeignKey("page.id"))
    kind: Mapped[str] = mapped_column(sa.Text, nullable=False)
    version: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    content_ref: Mapped[str] = mapped_column(sa.Text, nullable=False)
    content_digest: Mapped[str] = mapped_column(sa.Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(sa.Text, default="application/json", nullable=False)
    byte_size: Mapped[int] = mapped_column(sa.BigInteger, default=0, nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(sa.Text, nullable=False)
    upstream_refs: Mapped[dict[str, Any]] = mapped_column(sa.JSON, nullable=False)
    source_refs: Mapped[list[str]] = mapped_column(sa.JSON, nullable=False)
    producer_job_id: Mapped[UUID | None] = mapped_column(sa.Uuid(as_uuid=True))
    producer_attempt_id: Mapped[UUID | None] = mapped_column(sa.Uuid(as_uuid=True))
    producer_model: Mapped[str | None] = mapped_column(sa.Text)
    prompt_version: Mapped[str | None] = mapped_column(sa.Text)
    schema_version: Mapped[int] = mapped_column(sa.Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = _created()
    __table_args__ = (
        sa.UniqueConstraint("project_id", "page_id", "kind", "version", name="uq_artifact_version"),
        sa.Index("ix_artifact_fingerprint", "project_id", "input_fingerprint"),
    )


class ArtifactPointer(Base):
    __tablename__ = "artifact_pointer"

    id: Mapped[UUID] = _uuid_pk()
    project_id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), sa.ForeignKey("project.id", ondelete="CASCADE"))
    page_id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), sa.ForeignKey("page.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(sa.Text, nullable=False)
    artifact_version_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True), sa.ForeignKey("artifact_version.id", ondelete="CASCADE")
    )
    updated_at: Mapped[datetime] = _updated()
    __table_args__ = (sa.UniqueConstraint("project_id", "page_id", "kind", name="uq_pointer_page_kind"),)


class PageHistoryEntry(Base):
    __tablename__ = "page_history_entry"

    id: Mapped[UUID] = _uuid_pk()
    project_id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), sa.ForeignKey("project.id", ondelete="CASCADE"))
    page_id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), sa.ForeignKey("page.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(sa.Text, nullable=False)
    artifact_version_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True), sa.ForeignKey("artifact_version.id", ondelete="CASCADE")
    )
    stack_sequence: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    reason: Mapped[str] = mapped_column(sa.Text, nullable=False)
    created_at: Mapped[datetime] = _created()
    popped_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    __table_args__ = (
        sa.Index("ix_history_page_kind", "project_id", "page_id", "kind", "stack_sequence"),
    )


class ArtifactLineage(Base):
    __tablename__ = "artifact_lineage"

    id: Mapped[UUID] = _uuid_pk()
    project_id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), sa.ForeignKey("project.id", ondelete="CASCADE"))
    downstream_artifact_version_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True), sa.ForeignKey("artifact_version.id", ondelete="CASCADE")
    )
    upstream_type: Mapped[str] = mapped_column(sa.Text, nullable=False)
    upstream_id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), nullable=False)
    relation: Mapped[str] = mapped_column(sa.Text, nullable=False)
    created_at: Mapped[datetime] = _created()
    __table_args__ = (
        sa.UniqueConstraint(
            "downstream_artifact_version_id", "upstream_type", "upstream_id", name="uq_lineage_edge"
        ),
    )


class ArtifactSourceRef(Base):
    __tablename__ = "artifact_source_ref"

    id: Mapped[UUID] = _uuid_pk()
    project_id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), sa.ForeignKey("project.id", ondelete="CASCADE"))
    artifact_version_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True), sa.ForeignKey("artifact_version.id", ondelete="CASCADE")
    )
    source_item_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True), sa.ForeignKey("source_item.id", ondelete="CASCADE")
    )
    role: Mapped[str] = mapped_column(sa.Text, default="supporting", nullable=False)
    created_at: Mapped[datetime] = _created()
    __table_args__ = (
        sa.UniqueConstraint("artifact_version_id", "source_item_id", "role", name="uq_artifact_source_ref"),
    )


class Job(Base):
    __tablename__ = "job"

    id: Mapped[UUID] = _uuid_pk()
    project_id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), sa.ForeignKey("project.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(sa.Text, nullable=False)
    operation_key: Mapped[str] = mapped_column(sa.Text, nullable=False)
    active_operation_key: Mapped[str | None] = mapped_column(sa.Text, unique=True)
    state: Mapped[str] = mapped_column(sa.Text, default="QUEUED", nullable=False)
    priority: Mapped[int] = mapped_column(sa.Integer, default=0, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(sa.JSON, nullable=False, default=dict)
    instruction_ref: Mapped[str | None] = mapped_column(sa.Text)
    deadline_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    cancel_requested_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    attempt_count: Mapped[int] = mapped_column(sa.Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(sa.Integer, default=3, nullable=False)
    lease_owner: Mapped[str | None] = mapped_column(sa.Text)
    lease_expires_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    fencing_token: Mapped[int] = mapped_column(sa.BigInteger, default=0, nullable=False)
    last_error_code: Mapped[str | None] = mapped_column(sa.Text)
    last_error_class: Mapped[str | None] = mapped_column(sa.Text)
    progress: Mapped[dict[str, Any] | None] = mapped_column(sa.JSON)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()
    completed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    __table_args__ = (
        sa.Index("ix_job_project_state", "project_id", "state", "created_at"),
        sa.Index("ix_job_state_priority", "state", "priority", "created_at"),
    )


class JobAttempt(Base):
    __tablename__ = "job_attempt"

    id: Mapped[UUID] = _uuid_pk()
    job_id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), sa.ForeignKey("job.id", ondelete="CASCADE"))
    attempt_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    state: Mapped[str] = mapped_column(sa.Text, default="RUNNING", nullable=False)
    worker_id: Mapped[str | None] = mapped_column(sa.Text)
    fencing_token: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    started_at: Mapped[datetime] = _created()
    ended_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(sa.Text)
    error_class: Mapped[str | None] = mapped_column(sa.Text)
    provider: Mapped[str | None] = mapped_column(sa.Text)
    model_id: Mapped[str | None] = mapped_column(sa.Text)
    input_tokens: Mapped[int | None] = mapped_column(sa.Integer)
    output_tokens: Mapped[int | None] = mapped_column(sa.Integer)
    latency_ms: Mapped[int | None] = mapped_column(sa.Integer)
    estimated_cost: Mapped[float | None] = mapped_column(sa.Numeric(18, 6))
    __table_args__ = (sa.UniqueConstraint("job_id", "attempt_no", name="uq_job_attempt_no"),)


class ExportJob(Base):
    __tablename__ = "export_job"

    id: Mapped[UUID] = _uuid_pk()
    project_id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), sa.ForeignKey("project.id", ondelete="CASCADE"))
    format: Mapped[str] = mapped_column(sa.Text, nullable=False)
    state: Mapped[str] = mapped_column(sa.Text, default="QUEUED", nullable=False)
    deck_snapshot: Mapped[dict[str, Any]] = mapped_column(sa.JSON, nullable=False)
    validation_report: Mapped[dict[str, Any] | None] = mapped_column(sa.JSON)
    error_code: Mapped[str | None] = mapped_column(sa.Text)
    error_message_key: Mapped[str | None] = mapped_column(sa.Text)
    progress: Mapped[dict[str, Any] | None] = mapped_column(sa.JSON)
    created_at: Mapped[datetime] = _created()
    started_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    __table_args__ = (sa.Index("ix_export_project_created", "project_id", "created_at"),)


class ExportArtifact(Base):
    __tablename__ = "export_artifact"

    id: Mapped[UUID] = _uuid_pk()
    export_job_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True), sa.ForeignKey("export_job.id", ondelete="CASCADE"), unique=True
    )
    project_id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), nullable=False)
    object_key: Mapped[str] = mapped_column(sa.Text, nullable=False)
    checksum: Mapped[str] = mapped_column(sa.Text, nullable=False)
    byte_size: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    mime_type: Mapped[str] = mapped_column(sa.Text, nullable=False)
    file_name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    substitution_report: Mapped[dict[str, Any] | None] = mapped_column(sa.JSON)
    created_at: Mapped[datetime] = _created()
    expires_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))


class DomainEvent(Base):
    __tablename__ = "domain_event"

    id: Mapped[UUID] = _uuid_pk()
    project_id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), sa.ForeignKey("project.id", ondelete="CASCADE"))
    sequence: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    type: Mapped[str] = mapped_column(sa.Text, nullable=False)
    schema_version: Mapped[int] = mapped_column(sa.Integer, default=1, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(sa.JSON, nullable=False)
    request_id: Mapped[str | None] = mapped_column(sa.Text)
    trace_id: Mapped[str | None] = mapped_column(sa.Text)
    created_at: Mapped[datetime] = _created()
    __table_args__ = (sa.UniqueConstraint("project_id", "sequence", name="uq_event_project_sequence"),)


class UsageRecord(Base):
    __tablename__ = "usage_record"

    id: Mapped[UUID] = _uuid_pk()
    unique_key: Mapped[str | None] = mapped_column(sa.Text, unique=True)
    operation_key: Mapped[str] = mapped_column(sa.Text, nullable=False)
    adjustment_of: Mapped[UUID | None] = mapped_column(sa.Uuid(as_uuid=True))
    project_id: Mapped[UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True), sa.ForeignKey("project.id", ondelete="SET NULL")
    )
    account_id: Mapped[UUID | None] = mapped_column(sa.Uuid(as_uuid=True))
    stage: Mapped[str | None] = mapped_column(sa.Text)
    page_id: Mapped[UUID | None] = mapped_column(sa.Uuid(as_uuid=True))
    job_id: Mapped[UUID | None] = mapped_column(sa.Uuid(as_uuid=True))
    attempt_id: Mapped[UUID | None] = mapped_column(sa.Uuid(as_uuid=True))
    provider: Mapped[str | None] = mapped_column(sa.Text)
    capability: Mapped[str] = mapped_column(sa.Text, nullable=False)
    unit_type: Mapped[str] = mapped_column(sa.Text, nullable=False)
    quantity: Mapped[float] = mapped_column(sa.Numeric(18, 6), nullable=False)
    unit_price_version: Mapped[str | None] = mapped_column(sa.Text)
    estimated_cost: Mapped[float | None] = mapped_column(sa.Numeric(18, 6))
    actual_cost: Mapped[float | None] = mapped_column(sa.Numeric(18, 6))
    currency: Mapped[str] = mapped_column(sa.Text, default="USD", nullable=False)
    occurred_at: Mapped[datetime] = _created()
    __table_args__ = (sa.Index("ix_usage_project_time", "project_id", "occurred_at"),)


class PolicyRecord(Base):
    __tablename__ = "policy_record"

    id: Mapped[UUID] = _uuid_pk()
    scope_type: Mapped[str] = mapped_column(sa.Text, nullable=False)
    scope_id: Mapped[UUID | None] = mapped_column(sa.Uuid(as_uuid=True))
    project_id: Mapped[UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True), sa.ForeignKey("project.id", ondelete="CASCADE")
    )
    type: Mapped[str] = mapped_column(sa.Text, nullable=False)
    version: Mapped[str] = mapped_column(sa.Text, nullable=False)
    accepted_by_user_id: Mapped[UUID | None] = mapped_column(sa.Uuid(as_uuid=True))
    accepted_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    evidence_ref: Mapped[str | None] = mapped_column(sa.Text)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column("metadata", sa.JSON)
    __table_args__ = (sa.Index("ix_policy_scope_type", "scope_type", "scope_id", "type"),)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_record"

    id: Mapped[UUID] = _uuid_pk()
    project_id: Mapped[UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True), sa.ForeignKey("project.id", ondelete="CASCADE")
    )
    scope_key: Mapped[str] = mapped_column(sa.Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(sa.Text, nullable=False)
    request_hash: Mapped[str] = mapped_column(sa.Text, nullable=False)
    state: Mapped[str] = mapped_column(sa.Text, default="IN_PROGRESS", nullable=False)
    response_json: Mapped[dict[str, Any] | None] = mapped_column(sa.JSON)
    status_code: Mapped[int | None] = mapped_column(sa.Integer)
    resource_type: Mapped[str | None] = mapped_column(sa.Text)
    resource_id: Mapped[UUID | None] = mapped_column(sa.Uuid(as_uuid=True))
    created_at: Mapped[datetime] = _created()
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    __table_args__ = (
        sa.UniqueConstraint("scope_key", "idempotency_key", name="uq_idempotency_scope_key"),
    )


class ConfigVersion(Base):
    __tablename__ = "config_version"

    id: Mapped[UUID] = _uuid_pk()
    key: Mapped[str] = mapped_column(sa.Text, nullable=False)
    version: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    value: Mapped[dict[str, Any]] = mapped_column(sa.JSON, nullable=False)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = _created()
    __table_args__ = (sa.UniqueConstraint("key", "version", name="uq_config_key_version"),)


class GenerationProfile(Base):
    __tablename__ = "generation_profile"

    id: Mapped[UUID] = _uuid_pk()
    key: Mapped[str] = mapped_column(sa.Text, nullable=False)
    version: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    stage: Mapped[str] = mapped_column(sa.Text, nullable=False)
    provider: Mapped[str] = mapped_column(sa.Text, nullable=False)
    model_id: Mapped[str] = mapped_column(sa.Text, nullable=False)
    params: Mapped[dict[str, Any]] = mapped_column(sa.JSON, nullable=False)
    prompt_version: Mapped[str] = mapped_column(sa.Text, nullable=False)
    output_schema_version: Mapped[str] = mapped_column(sa.Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = _created()
    __table_args__ = (sa.UniqueConstraint("key", "version", name="uq_generation_profile_key_version"),)


class ProjectSnapshotCache(Base):
    __tablename__ = "project_snapshot_cache"

    project_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True), sa.ForeignKey("project.id", ondelete="CASCADE"), primary_key=True
    )
    sequence: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(sa.JSON, nullable=False)
    updated_at: Mapped[datetime] = _created()
