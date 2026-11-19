from __future__ import annotations

from typing import Any

from app.domain.enums import ErrorCategory


class AppError(Exception):
    """Typed domain error mapped to the API error envelope."""

    def __init__(
        self,
        category: ErrorCategory | str,
        message_key: str,
        *,
        http_status: int | None = None,
        details: dict[str, Any] | None = None,
        retryable: bool | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message_key)
        self.category = str(category)
        self.message_key = message_key
        self.http_status = http_status or _default_status(self.category)
        self.details = details or {}
        self.retryable = retryable if retryable is not None else self.category in {
            "conflict",
            "rate_limited",
            "provider_timeout",
            "provider_unavailable",
            "internal",
        }
        self.headers = headers or {}


def _default_status(category: str) -> int:
    return {
        "validation": 422,
        "gate_violation": 409,
        "forbidden": 403,
        "not_found": 404,
        "conflict": 409,
        "rate_limited": 429,
        "provider_timeout": 504,
        "provider_unavailable": 503,
        "parse_failure": 422,
        "export_validation_failure": 422,
        "quota_exceeded": 402,
        "internal": 500,
    }.get(category, 500)


def validation(key: str, details: dict[str, Any] | None = None) -> AppError:
    return AppError("validation", key, details=details)


def gate(key: str, details: dict[str, Any] | None = None) -> AppError:
    return AppError("gate_violation", key, details=details)


def not_found(key: str) -> AppError:
    return AppError("not_found", key)


def conflict(key: str, details: dict[str, Any] | None = None) -> AppError:
    return AppError("conflict", key, details=details)


def forbidden(key: str = "error.auth.forbidden") -> AppError:
    return AppError("forbidden", key)
