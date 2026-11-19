from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


def to_camel(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(part.capitalize() for part in rest)


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


class EnvelopeMeta(CamelModel):
    request_id: str
    trace_id: str
    server_time: str
    project_version: int | None = None
    sequence: int | None = None
    idempotent_replay: bool | None = None


# ---- Shared shapes ---------------------------------------------------------


class PageError(CamelModel):
    code: str
    category: str
    message_key: str
    retryable: bool
    page_id: UUID | None = None


class ArtifactStatus(CamelModel):
    status: str
    artifact_version_id: UUID | None = None
    version: int | None = None
    history_depth: int | None = None
    can_undo: bool | None = None
    error: PageError | None = None


class ActiveJobRef(CamelModel):
    job_id: UUID
    type: str
    state: str
    page_id: UUID | None = None


# ---- Auth / config ---------------------------------------------------------


class UserDTO(CamelModel):
    id: UUID
    email: str
    name: str | None = None
    role: str


class AccountDTO(CamelModel):
    id: UUID
    name: str | None = None
    plan: str
    billing_status: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class SupportedFileType(CamelModel):
    extension: str
    mime_type: str
    max_bytes: int
    max_pages: int | None = None


class ClientConfigDTO(CamelModel):
    material_limit: int
    page_limit: int
    upload_max_bytes: int
    supported_file_types: list[SupportedFileType]
    search_cap_per_project: int
    export_formats: list[str]
    deck_canvas: dict[str, int]
    question_catalog_version: str
    style_catalog_version: str


class NoticeDTO(CamelModel):
    type: str
    version: str
    title: str
    body: str
    requires_consent: bool
    accepted_at: str | None = None


class NoticesDTO(CamelModel):
    notices: list[NoticeDTO]


class ConsentRequest(BaseModel):
    notice_type: str = Field(alias="noticeType")
    version: str


# ---- Project / snapshot ----------------------------------------------------


class ProjectDTO(CamelModel):
    id: UUID
    name: str
    topic: str
    mode: str
    status: str
    stage: str
    version: int
    epoch: int
    created_at: datetime
    updated_at: datetime


class StageBlockerDTO(CamelModel):
    code: str
    message_key: str
    stage: str | None = None


class StageStateDTO(CamelModel):
    stage: str
    status: str
    reachable: bool
    stale_reasons: list[str] = Field(default_factory=list)
    blockers: list[StageBlockerDTO] = Field(default_factory=list)
    advance_token: str | None = None
    advance_token_expires_at: datetime | None = None


class PointersDTO(CamelModel):
    profile_version_id: UUID | None = None
    outline_version_id: UUID | None = None
    style_selection_id: UUID | None = None


class SnapshotCountsDTO(CamelModel):
    materials: int = 0
    web_sources: int = 0
    pages: int = 0
    sections: int = 0
    plan_done: int = 0
    plan_total: int = 0
    design_done: int = 0
    design_total: int = 0
    stale_pages: int = 0
    error_pages: int = 0


class SnapshotStyleSelectionDTO(CamelModel):
    style_key: str
    style_version: int
    confirmed: bool
    confirmed_at: datetime | None = None


class ProjectSnapshotDTO(CamelModel):
    project: ProjectDTO
    stages: list[StageStateDTO]
    pointers: PointersDTO
    counts: SnapshotCountsDTO
    profile_dirty: bool
    material_limit: int
    style_selection: SnapshotStyleSelectionDTO | None = None
    active_jobs: list[ActiveJobRef] = Field(default_factory=list)
    latest_export_id: UUID | None = None
    sequence: int
    schema_version: int = 1
    server_time: datetime


class CreateProjectRequest(BaseModel):
    topic: str
    name: str | None = None
    mode: str = "FULLY_AUTOMATIC"


class PatchProjectRequest(BaseModel):
    name: str | None = None
    topic: str | None = None


class RestartRequest(BaseModel):
    confirm: bool


class StaleSummaryDTO(CamelModel):
    changed: bool
    cause: str
    affected: dict[str, list[UUID]]
    rerun: dict[str, int]
    cascade_ratio: float | None = None
    project_version: int


class AdvanceRequest(BaseModel):
    from_stage: str = Field(alias="fromStage")
    advance_token: str = Field(alias="advanceToken")


class AdvanceResultDTO(CamelModel):
    project: ProjectDTO
    stages: list[StageStateDTO]
    advanced: bool
    from_stage: str
    to_stage: str


# ---- Materials -------------------------------------------------------------


class MaterialDTO(CamelModel):
    id: UUID
    kind: str
    status: str
    display_name: str
    mime_type: str | None = None
    size_bytes: int = 0
    page_count: int | None = None
    domain: str | None = None
    error: PageError | None = None
    created_at: datetime
    updated_at: datetime
    active_job: ActiveJobRef | None = None


class MaterialListDTO(CamelModel):
    materials: list[MaterialDTO]
    limit: int
    remaining: int


class AddPasteRequest(BaseModel):
    text: str
    display_name: str | None = Field(default=None, alias="displayName")


class AddUrlRequest(BaseModel):
    url: str
    display_name: str | None = Field(default=None, alias="displayName")


class UploadUrlRequest(CamelModel):
    file_name: str
    mime_type: str
    size_bytes: int


class UploadInstruction(CamelModel):
    url: str
    method: str
    headers: dict[str, str]
    expires_at: datetime | str


class UploadUrlDTO(CamelModel):
    material_id: UUID
    upload: UploadInstruction


# ---- Research --------------------------------------------------------------


class SourceItemDTO(CamelModel):
    id: UUID
    origin: str
    source_type: str
    title: str
    summary: str
    domain: str | None = None
    rank: int = 0
    material_id: UUID | None = None
    gap_suggestion_id: UUID | None = None


class MaterialDigestDTO(CamelModel):
    material_id: UUID
    display_name: str
    status: str
    extracted_char_count: int | None = None
    length_bucket: str | None = None
    summary_preview: str | None = None


class SourceGroupDTO(CamelModel):
    count: int
    status: str
    items: list[SourceItemDTO] = Field(default_factory=list)
    digest: list[MaterialDigestDTO] | None = None


class WebSourceGroupDTO(CamelModel):
    count: int
    status: str
    items: list[SourceItemDTO] = Field(default_factory=list)
    skipped: bool = False
    cap: int = 12


class SourcePanelDTO(CamelModel):
    materials: SourceGroupDTO
    web: WebSourceGroupDTO


class QuestionOptionDTO(CamelModel):
    key: str
    label: str


class AnswerDTO(CamelModel):
    option_key: str
    revision: int
    answered_at: datetime


class QuestionDTO(CamelModel):
    key: str
    position: int
    prompt: str
    options: list[QuestionOptionDTO]
    answer: AnswerDTO | None = None


class GapSuggestionDTO(CamelModel):
    id: UUID
    label: str
    reason: str
    recommended: bool
    status: str


class GapDecisionDTO(CamelModel):
    decided_at: datetime
    selected_suggestion_ids: list[UUID]
    web_skipped: bool


class GapStateDTO(CamelModel):
    batch: int
    suggestions: list[GapSuggestionDTO]
    decision: GapDecisionDTO | None = None


class GapSearchOutcomeDTO(CamelModel):
    gap_suggestion_id: UUID
    query_index: int
    outcome: str
    result_count: int = 0
    error_code: str | None = None


class MaterialsSummaryDTO(CamelModel):
    material_ids: list[UUID]
    material_count: int
    strategy: str


class WebScopeDTO(CamelModel):
    selected_gap_suggestion_ids: list[UUID]
    web_skipped: bool
    source_count: int


class ProfileDTO(CamelModel):
    profile_version_id: UUID
    version: int
    audience: str
    goal: str
    style_mood: str
    page_count: int
    materials_summary: MaterialsSummaryDTO
    web_scope: WebScopeDTO
    content_strategy: str
    source_refs: list[UUID]
    created_at: datetime


class DigestStateDTO(CamelModel):
    status: str
    items: list[MaterialDigestDTO]


class ResearchCountsDTO(CamelModel):
    questions_total: int
    questions_answered: int
    materials_selected: int
    selected_gaps: int


class ResearchStateDTO(CamelModel):
    stage: str
    stage_status: str
    profile_dirty: bool
    questions: list[QuestionDTO]
    digest: DigestStateDTO
    gaps: GapStateDTO | None = None
    gap_searches: list[GapSearchOutcomeDTO] = Field(default_factory=list)
    sources: SourcePanelDTO
    profile: ProfileDTO | None = None
    counts: ResearchCountsDTO
    active_jobs: list[ActiveJobRef] = Field(default_factory=list)


class AnswerRequest(BaseModel):
    option_key: str = Field(alias="optionKey")


class AnswerResultDTO(CamelModel):
    question: dict[str, Any]
    profile_dirty: bool
    stale: StaleSummaryDTO | None = None


class GapDecisionRequest(CamelModel):
    selected_suggestion_ids: list[UUID] = Field(default_factory=list)
    web_skipped: bool = False


class GapDecisionResultDTO(CamelModel):
    gaps: GapStateDTO
    search_job_ids: list[UUID] = Field(default_factory=list)
    gap_searches: list[GapSearchOutcomeDTO] = Field(default_factory=list)
    web_skipped: bool


class ProfileResultDTO(CamelModel):
    profile: ProfileDTO
    profile_dirty: bool
    outline_unconfirmed: bool
    stale: StaleSummaryDTO | None = None


class ResearchStartDTO(CamelModel):
    stage: str
    stage_status: str
    job_ids: list[UUID]


# ---- Outline ---------------------------------------------------------------


class OutlineSectionDTO(CamelModel):
    section_key: str
    title: str
    position: int


class OutlinePageDTO(CamelModel):
    page_id: UUID
    position: int
    page_type: str
    section_key: str
    title: str
    key_points: list[str]
    deletable: bool


class OutlineCountsDTO(CamelModel):
    pages: int
    sections: int
    body_pages: int
    agreed_page_count: int
    deviation: int
    deviation_warning: bool


class OutlineDTO(CamelModel):
    outline_version_id: UUID
    version: int
    confirmed: bool
    confirmed_at: datetime | None = None
    pages: list[OutlinePageDTO]
    sections: list[OutlineSectionDTO]
    counts: OutlineCountsDTO
    stage_status: str


class OutlineGenerateDTO(CamelModel):
    job_id: UUID
    outline_version_id: UUID | None = None


class OutlineConfirmResultDTO(CamelModel):
    outline: OutlineDTO
    stage: StageStateDTO
    snapshot: ProjectSnapshotDTO


class OutlineEditRequest(BaseModel):
    title: str


class OutlineInsertRequest(BaseModel):
    section_key: str = Field(alias="sectionKey")
    after_page_id: UUID | None = Field(default=None, alias="afterPageId")
    title: str
    key_points: list[str] = Field(default_factory=list)


class OutlineInsertResultDTO(CamelModel):
    outline: OutlineDTO
    page_id: UUID
    stale: StaleSummaryDTO


class OutlineEditResultDTO(CamelModel):
    outline: OutlineDTO
    stale: StaleSummaryDTO


class OutlineMoveRequest(BaseModel):
    to_section_key: str = Field(alias="toSectionKey")
    before_page_id: UUID | None = Field(default=None, alias="beforePageId")
    to_position: int | None = Field(default=None, alias="toPosition")


# ---- Pages and artifacts ---------------------------------------------------


class PageSummaryDTO(CamelModel):
    page_id: UUID
    position: int
    page_type: str
    section_key: str
    section_title: str
    title: str
    plan: ArtifactStatus
    design: ArtifactStatus
    active_job: ActiveJobRef | None = None


class PageCountsDTO(CamelModel):
    total: int = 0
    plan_done: int = 0
    plan_pending: int = 0
    plan_running: int = 0
    plan_stale: int = 0
    plan_error: int = 0
    design_done: int = 0
    design_pending: int = 0
    design_running: int = 0
    design_stale: int = 0
    design_error: int = 0


class PageListDTO(CamelModel):
    outline_version_id: UUID | None = None
    project_version: int
    counts: PageCountsDTO
    pages: list[PageSummaryDTO]


class ArtifactChromeDTO(CamelModel):
    page_number: int
    deck_order: int
    title: str
    section_label: str | None = None
    chrome_version: str


class ArtifactSourceRefDTO(CamelModel):
    source_item_id: UUID
    title: str
    origin: str
    role: str


class PlanBlockV1(CamelModel):
    id: str
    slot: str
    role: str
    text: str | None = None
    items: list[str] | None = None
    asset_ref: str | None = None
    emphasis: str | None = None
    span: dict[str, int] | None = None


class PlanBodyV1(CamelModel):
    schema_version: Literal[1] = 1
    canvas: dict[str, int]
    layout_id: str
    density: str = "medium"
    blocks: list[PlanBlockV1]
    meta: dict[str, Any]


class DesignBlockV1(PlanBlockV1):
    style: dict[str, Any]


class DesignAssetV1(CamelModel):
    asset_id: str
    kind: str
    width: int
    height: int
    license_status: str


class DesignStyleRefV1(CamelModel):
    style_key: str
    style_version: int
    tokens: dict[str, str | int | float]


class DesignBodyV1(CamelModel):
    schema_version: Literal[1] = 1
    canvas: dict[str, int]
    layout_id: str
    density: str = "medium"
    style: DesignStyleRefV1
    blocks: list[DesignBlockV1]
    assets: list[DesignAssetV1] = Field(default_factory=list)
    meta: dict[str, Any]


class ArtifactHistoryDTO(CamelModel):
    depth: int
    can_undo: bool
    current_pointer_version: int


class ArtifactDTO(CamelModel):
    artifact_version_id: UUID
    page_id: UUID
    kind: str
    version: int
    content_digest: str
    input_fingerprint: str
    schema_version: int
    body: dict[str, Any]
    chrome: ArtifactChromeDTO
    source_refs: list[ArtifactSourceRefDTO]
    history: ArtifactHistoryDTO
    status: str
    created_at: datetime


class HistoryEntryDTO(CamelModel):
    artifact_version_id: UUID
    version: int
    reason: str
    created_at: datetime
    is_current: bool
    undone: bool


class PageHistoryDTO(CamelModel):
    page_id: UUID
    kind: str
    depth: int
    can_undo: bool
    entries: list[HistoryEntryDTO]


class GeneratePagesResultDTO(CamelModel):
    jobs: list[dict[str, UUID]]
    skipped_page_ids: list[UUID]
    counts: dict[str, int]


class PageJobResultDTO(CamelModel):
    job_id: UUID
    page_id: UUID


class PageActionRequest(BaseModel):
    kind: Literal["plan", "design"]


class TweakRequest(BaseModel):
    instruction: str


class UndoResultDTO(CamelModel):
    artifact: ArtifactDTO
    history: PageHistoryDTO
    stale: StaleSummaryDTO | None = None


# ---- Style -----------------------------------------------------------------


class StylePaletteDTO(CamelModel):
    primary: str
    secondary: str
    accent: str
    background: str
    surface: str
    text: str


class StyleDTO(CamelModel):
    style_key: str
    name: str
    version: int
    scope: str
    description: str
    palette: StylePaletteDTO
    preview_url: str
    license_status: str
    use_case: str


class StyleSelectionDTO(CamelModel):
    style_selection_id: UUID
    style_key: str
    style_version: int
    confirmed: bool
    confirmed_at: datetime | None = None
    remember_preference: bool
    created_at: datetime


class StyleSelectRequest(BaseModel):
    style_key: str = Field(alias="styleKey")
    style_version: int = Field(alias="styleVersion")
    remember_preference: bool = Field(default=False, alias="rememberPreference")


class StyleConfirmResultDTO(CamelModel):
    style_selection: StyleSelectionDTO
    stage: StageStateDTO
    stale: StaleSummaryDTO | None = None


# ---- Jobs / export ---------------------------------------------------------


class JobProgressDTO(CamelModel):
    phase: str
    current: int
    total: int


class JobDTO(CamelModel):
    job_id: UUID
    project_id: UUID
    type: str
    state: str
    stage: str
    page_id: UUID | None = None
    attempt_count: int
    max_attempts: int
    cancel_requested: bool
    queued_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    deadline_at: datetime | None = None
    error: PageError | None = None
    progress: JobProgressDTO | None = None


class ExportValidationCheckDTO(CamelModel):
    code: str
    status: str
    page_ids: list[UUID] = Field(default_factory=list)


class ExportArtifactDTO(CamelModel):
    artifact_id: UUID
    file_name: str
    mime_type: str
    byte_size: int
    checksum: str
    created_at: datetime
    expires_at: datetime | None = None
    download_path: str


class DeckSnapshotDTO(CamelModel):
    page_count: int
    style_key: str
    rendered_count: int
    excluded_page_ids: list[UUID] = Field(default_factory=list)


class ExportProgressDTO(CamelModel):
    phase: str
    pages_total: int
    pages_rendered: int
    percent: float


class ExportValidationDTO(CamelModel):
    passed: bool
    checks: list[ExportValidationCheckDTO]
    failed_checks: list[ExportValidationCheckDTO]


class SubstitutionReportDTO(CamelModel):
    substitutions: list[dict[str, str]]


class ExportDTO(CamelModel):
    export_id: UUID
    project_id: UUID
    format: str
    state: str
    deck_snapshot: DeckSnapshotDTO
    progress: ExportProgressDTO
    validation: ExportValidationDTO | None = None
    artifact: ExportArtifactDTO | None = None
    substitution_report: SubstitutionReportDTO | None = None
    error: PageError | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ExportCreateRequest(BaseModel):
    format: str
