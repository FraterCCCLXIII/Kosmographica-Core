from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping

from app.tools.errors import AdminDisabled, ConfigError

DEFAULT_API_URL = "http://127.0.0.1:8000/api/v1"
CONFIG_FILENAME = ".kosmo"


@dataclass(frozen=True)
class ToolConfig:
    api_url: str = DEFAULT_API_URL
    workspace_id: str | None = None
    project_id: str | None = None
    timeout_seconds: float = 30.0
    auth_token: str | None = None
    admin_enabled: bool = False
    database_url: str | None = None

    def require_project(self, project_id: str | None = None) -> str:
        resolved = project_id or self.project_id
        if not resolved:
            raise ConfigError("No project id provided. Run `kosmo config set-project <project-id>` or pass --project.")
        return resolved

    def require_workspace(self, workspace_id: str | None = None) -> str:
        resolved = workspace_id or self.workspace_id
        if not resolved:
            raise ConfigError("No workspace id provided. Run `kosmo config set-workspace <workspace-id>` or pass --workspace.")
        return resolved

    def require_admin_database_url(self) -> str:
        if not self.admin_enabled:
            raise AdminDisabled("Admin diagnostics are disabled. Set KOSMO_ADMIN_ENABLED=true to opt in.")
        if not self.database_url:
            raise ConfigError("No database URL configured for admin diagnostics.")
        return _readonly_url(self.database_url)


def load_config(cwd: Path | None = None, env: Mapping[str, str] | None = None) -> ToolConfig:
    env = env or os.environ
    file_values = _read_config_file(_discover_config_path(cwd or Path.cwd()))
    merged = {
        "api_url": file_values.get("api_url", DEFAULT_API_URL),
        "workspace_id": file_values.get("workspace_id"),
        "project_id": file_values.get("project_id"),
        "timeout_seconds": file_values.get("timeout_seconds", 30.0),
        "auth_token": file_values.get("auth_token"),
        "admin_enabled": file_values.get("admin_enabled", False),
        "database_url": file_values.get("database_url"),
    }
    env_map = {
        "KOSMO_API_URL": "api_url",
        "KOSMO_WORKSPACE_ID": "workspace_id",
        "KOSMO_PROJECT_ID": "project_id",
        "KOSMO_TIMEOUT_SECONDS": "timeout_seconds",
        "KOSMO_AUTH_TOKEN": "auth_token",
        "KOSMO_ADMIN_ENABLED": "admin_enabled",
        "KOSMO_DATABASE_URL": "database_url",
        "DATABASE_URL": "database_url",
    }
    for env_key, config_key in env_map.items():
        if env.get(env_key):
            merged[config_key] = env[env_key]
    return ToolConfig(
        api_url=str(merged["api_url"]).rstrip("/"),
        workspace_id=_none_if_empty(merged.get("workspace_id")),
        project_id=_none_if_empty(merged.get("project_id")),
        timeout_seconds=float(merged["timeout_seconds"]),
        auth_token=_none_if_empty(merged.get("auth_token")),
        admin_enabled=_to_bool(merged["admin_enabled"]),
        database_url=_none_if_empty(merged.get("database_url")),
    )


def config_file_path(cwd: Path | None = None, *, global_config: bool = False) -> Path:
    if global_config:
        return Path.home() / CONFIG_FILENAME
    return (cwd or Path.cwd()) / CONFIG_FILENAME


def read_config_values(cwd: Path | None = None) -> dict[str, object]:
    return _read_config_file(_discover_config_path(cwd or Path.cwd()))


def set_config_value(key: str, value: object, cwd: Path | None = None, *, global_config: bool = False) -> Path:
    allowed = {"api_url", "workspace_id", "project_id", "timeout_seconds", "auth_token", "admin_enabled", "database_url"}
    if key not in allowed:
        raise ConfigError(f"Unsupported config key: {key}")
    path = config_file_path(cwd, global_config=global_config)
    values = _read_config_file(path)
    values[key] = value
    path.write_text(json.dumps(values, indent=2, sort_keys=True) + "\n")
    return path


def serialize_config(config: ToolConfig) -> dict[str, object]:
    values = asdict(config)
    if values["auth_token"]:
        values["auth_token"] = "***"
    if values["database_url"]:
        values["database_url"] = "***"
    return values


def _discover_config_path(cwd: Path) -> Path:
    for path in [cwd, *cwd.parents]:
        candidate = path / CONFIG_FILENAME
        if candidate.exists():
            return candidate
    home_candidate = Path.home() / CONFIG_FILENAME
    if home_candidate.exists():
        return home_candidate
    return cwd / CONFIG_FILENAME


def _read_config_file(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid Kosmographica config file: {path}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"Kosmographica config file must contain a JSON object: {path}")
    return data


def _none_if_empty(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _readonly_url(database_url: str) -> str:
    if database_url.startswith("postgresql+asyncpg://"):
        return database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return database_url
