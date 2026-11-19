from __future__ import annotations

from enum import StrEnum


class ProjectMode(StrEnum):
    FULLY_AUTOMATIC = "FULLY_AUTOMATIC"
    EXPERT_COPILOT = "EXPERT_COPILOT"


class ProjectStatus(StrEnum):
    ACTIVE = "ACTIVE"
    DELETING = "DELETING"
    DELETED = "DELETED"


class Stage(StrEnum):
    INTAKE = "INTAKE"
    RESEARCH = "RESEARCH"
    OUTLINE = "OUTLINE"
    PLAN = "PLAN"
    STYLE = "STYLE"
    DESIGN = "DESIGN"


STAGE_ORDER: tuple[Stage, ...] = (
    Stage.INTAKE,
    Stage.RESEARCH,
    Stage.OUTLINE,
    Stage.PLAN,
    Stage.STYLE,
    Stage.DESIGN,
)


class StageStatus(StrEnum):
    LOCKED = "LOCKED"
    AVAILABLE = "AVAILABLE"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETE = "COMPLETE"
    STALE = "STALE"
    ERROR = "ERROR"


class PageType(StrEnum):
    COVER = "COVER"
    TOC = "TOC"
    BODY = "BODY"
    END = "END"


class ArtifactKind(StrEnum):
    PLAN = "PLAN"
    DESIGN = "DESIGN"


class PageStatus(StrEnum):
    PENDING = "PENDING"
    PLANNING = "PLANNING"
    DESIGNING = "DESIGNING"
    DONE = "DONE"
    STALE = "STALE"
    ERROR = "ERROR"


class MaterialKind(StrEnum):
    PASTE = "PASTE"
    FILE = "FILE"
    URL = "URL"


class MaterialStatus(StrEnum):
    PENDING = "PENDING"
    INGESTING = "INGESTING"
    DIGESTED = "DIGESTED"
    FAILED = "FAILED"
    REMOVED = "REMOVED"


class SourceOrigin(StrEnum):
    PROVIDED = "PROVIDED"
    WEB = "WEB"


class SourceType(StrEnum):
    PASTE = "PASTE"
    FILE = "FILE"
    URL = "URL"
    WEB_RESULT = "WEB_RESULT"
    INTERVIEW_ANSWER = "INTERVIEW_ANSWER"


class GapStatus(StrEnum):
    SUGGESTED = "SUGGESTED"
    SELECTED = "SELECTED"
    REJECTED = "REJECTED"


class JobType(StrEnum):
    INGEST = "INGEST"
    DIGEST = "DIGEST"
    SEARCH = "SEARCH"
    GAP_SUGGEST = "GAP_SUGGEST"
    PROFILE = "PROFILE"
    OUTLINE = "OUTLINE"
    PLAN_PAGE = "PLAN_PAGE"
    DESIGN_PAGE = "DESIGN_PAGE"
    EXPORT = "EXPORT"
    DELETE_PROJECT = "DELETE_PROJECT"


class JobState(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class ExportFormat(StrEnum):
    PPTX = "PPTX"
    HTML = "HTML"
    PDF = "PDF"


class ExportState(StrEnum):
    QUEUED = "QUEUED"
    VALIDATING = "VALIDATING"
    COMPOSING = "COMPOSING"
    PACKAGING = "PACKAGING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class StyleScope(StrEnum):
    BUILTIN = "BUILTIN"
    ACCOUNT = "ACCOUNT"
    ORGANIZATION = "ORGANIZATION"


class LicenseStatus(StrEnum):
    CLEARED = "CLEARED"
    SUBSTITUTION_REQUIRED = "SUBSTITUTION_REQUIRED"
    UNKNOWN = "UNKNOWN"
    BLOCKED = "BLOCKED"


class HistoryReason(StrEnum):
    REGENERATE = "REGENERATE"
    TWEAK = "TWEAK"
    REPLAN = "REPLAN"
    STYLE_CHANGE = "STYLE_CHANGE"
    MANUAL = "MANUAL"


class LayoutId(StrEnum):
    SINGLE = "single"
    TWO_COL = "two_col"
    THREE_COL = "three_col"
    HERO = "hero"
    ASYNC = "async"
    MIX = "mix"


class ErrorCategory(StrEnum):
    VALIDATION = "validation"
    GATE_VIOLATION = "gate_violation"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    RATE_LIMITED = "rate_limited"
    PROVIDER_TIMEOUT = "provider_timeout"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    PARSE_FAILURE = "parse_failure"
    EXPORT_VALIDATION_FAILURE = "export_validation_failure"
    QUOTA_EXCEEDED = "quota_exceeded"
    INTERNAL = "internal"
