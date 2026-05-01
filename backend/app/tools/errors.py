from __future__ import annotations


class KosmoToolError(Exception):
    """Base class for user-facing tool errors."""

    code = "kosmo_tool_error"

    def __init__(self, message: str, *, details: object | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class ConfigError(KosmoToolError):
    code = "config_error"


class BackendUnavailable(KosmoToolError):
    code = "backend_unavailable"


class ApiError(KosmoToolError):
    code = "api_error"

    def __init__(self, status_code: int, message: str, *, details: object | None = None) -> None:
        super().__init__(message, details=details)
        self.status_code = status_code


class ClusteringNotAvailable(KosmoToolError):
    code = "clustering_not_available"


class AdminDisabled(KosmoToolError):
    code = "admin_disabled"


def error_payload(error: Exception) -> dict[str, object]:
    if isinstance(error, ApiError):
        return {
            "ok": False,
            "error": {
                "code": error.code,
                "status_code": error.status_code,
                "message": error.message,
                "details": error.details,
            },
        }
    if isinstance(error, KosmoToolError):
        return {
            "ok": False,
            "error": {
                "code": error.code,
                "message": error.message,
                "details": error.details,
            },
        }
    return {
        "ok": False,
        "error": {
            "code": "unexpected_error",
            "message": "Unexpected tool failure. Check backend logs for details.",
        },
    }
