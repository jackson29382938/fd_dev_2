"""Credential path resolution for Google Sheets integrations."""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional


def _env_path(name: str) -> Optional[Path]:
    value = os.environ.get(name)
    if not value:
        return None
    return Path(value).expanduser()


def candidate_credentials_paths(base_dir: Path) -> List[Path]:
    """Return credential locations in priority order."""
    paths: List[Path] = []

    for env_name in ("FTID_CREDENTIALS_PATH", "GOOGLE_APPLICATION_CREDENTIALS"):
        path = _env_path(env_name)
        if path is not None:
            paths.append(path)

    state_dir = os.environ.get("FTID_STATE_DIR")
    if state_dir:
        paths.append(Path(state_dir).expanduser() / "credentials.json")

    paths.extend(
        [
            Path(base_dir) / "requirements" / "credentials.json",
            Path.home() / ".ftid" / "credentials.json",
            Path.home() / "Documents" / "FTID_Generator" / "credentials.json",
        ]
    )

    unique_paths: List[Path] = []
    seen = set()
    for path in paths:
        resolved = path.expanduser()
        key = str(resolved)
        if key not in seen:
            unique_paths.append(resolved)
            seen.add(key)
    return unique_paths


def resolve_credentials_path(base_dir: Path) -> Path:
    for path in candidate_credentials_paths(base_dir):
        if path.exists():
            return path
    return Path(base_dir) / "requirements" / "credentials.json"


def credentials_error_message(base_dir: Path) -> str:
    candidates = "\n".join(f"- {path}" for path in candidate_credentials_paths(base_dir))
    return "credentials.json not found. Checked:\n" + candidates
