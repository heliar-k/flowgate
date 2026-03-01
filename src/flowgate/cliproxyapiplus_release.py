from __future__ import annotations

from collections.abc import Callable
from typing import Any


def build_latest_release_url(repo: str) -> str:
    """Build GitHub API URL for the latest release of a repository."""
    return f"https://api.github.com/repos/{repo}/releases/latest"


def parse_latest_release_payload(payload: dict[str, Any]) -> tuple[str, str]:
    """Extract latest version and release URL from GitHub release payload."""
    latest = str(payload.get("tag_name", "")).strip()
    release_url = str(payload.get("html_url", "")).strip()
    return latest, release_url


def fetch_latest_release(
    *, repo: str, http_get_json: Callable[[str], dict[str, Any]]
) -> tuple[str, str]:
    """Fetch latest release metadata and return (latest_version, release_url)."""
    data = http_get_json(build_latest_release_url(repo))
    return parse_latest_release_payload(data)
