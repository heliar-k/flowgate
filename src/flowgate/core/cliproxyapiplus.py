"""CLIProxyAPIPlus version management, update checking, and auto-update."""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Callable

from .bootstrap import (
    DEFAULT_CLIPROXY_REPO,
    http_get_json,
    download_cliproxyapi_plus,
    validate_cliproxy_binary,
)
from .constants import CLIPROXYAPI_PLUS_SERVICE
from .process import ProcessSupervisor

CHECK_CACHE_FILE = "cliproxyapiplus_update_cache.json"
INSTALLED_VERSION_FILE = "cliproxyapiplus.version"
CHECK_TTL_SECONDS = 24 * 60 * 60
CHECK_ERROR_TTL_SECONDS = 60 * 60


# ── Version comparison ─────────────────────────────────────
def parse_version_tuple(version: str) -> tuple[int, ...] | None:
    """Convert a version string into a tuple of ints, or None if no digits."""
    parts = re.findall(r"\d+", version)
    if not parts:
        return None
    return tuple(int(part) for part in parts)


def is_newer_version(latest: str, current: str) -> bool:
    """Return True when latest is newer than current."""
    latest_tuple = parse_version_tuple(latest)
    current_tuple = parse_version_tuple(current)
    if latest_tuple is None or current_tuple is None:
        return latest.strip() != current.strip()

    width = max(len(latest_tuple), len(current_tuple))
    latest_tuple = latest_tuple + (0,) * (width - len(latest_tuple))
    current_tuple = current_tuple + (0,) * (width - len(current_tuple))
    return latest_tuple > current_tuple


def build_update_info(
    *, current_version: str, latest_version: str, release_url: str
) -> dict[str, str] | None:
    """Create update info payload when latest_version is newer than current_version."""
    current = str(current_version).strip()
    latest = str(latest_version).strip()
    release = str(release_url).strip()
    if not latest:
        return None
    if not is_newer_version(latest, current):
        return None
    return {
        "current_version": current,
        "latest_version": latest,
        "release_url": release,
    }


# ── Release fetching ────────────────────────────────────────
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


# ── Cache/file I/O ─────────────────────────────────────────
def _cache_path(runtime_dir: str | Path) -> Path:
    return Path(runtime_dir) / CHECK_CACHE_FILE


def _version_path(runtime_dir: str | Path) -> Path:
    return Path(runtime_dir) / INSTALLED_VERSION_FILE


def _read_cache(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _write_cache(path: Path, payload: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
    except Exception:  # noqa: BLE001
        return


# ── Public version management ───────────────────────────────
def read_installed_version(runtime_dir: str | Path, fallback_version: str) -> str:
    """Read the installed CLIProxyAPIPlus version from runtime directory."""
    path = _version_path(runtime_dir)
    if not path.exists():
        return fallback_version

    try:
        version = path.read_text(encoding="utf-8").strip()
    except Exception:  # noqa: BLE001
        return fallback_version

    if not version or not re.search(r"\d", version):
        return fallback_version
    return version


def write_installed_version(runtime_dir: str | Path, version: str) -> None:
    """Write the installed CLIProxyAPIPlus version to runtime directory."""
    normalized = str(version).strip()
    if not normalized:
        return
    if normalized == "latest":
        return
    if not re.search(r"\d", normalized):
        return

    path = _version_path(runtime_dir)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(normalized, encoding="utf-8")
    except Exception:  # noqa: BLE001
        return


def check_update(
    *,
    runtime_dir: str | Path,
    current_version: str,
    repo: str,
) -> dict[str, str] | None:
    """Check for CLIProxyAPIPlus update, returns update info if available."""
    now = int(time.time())
    current = str(current_version).strip()
    if not current:
        return None

    cache_file = _cache_path(runtime_dir)
    cached = _read_cache(cache_file)
    cached_checked_at = int(cached.get("checked_at", 0) or 0)
    cached_current = str(cached.get("current_version", "")).strip()
    cache_error = bool(cached.get("error", False))
    cache_ttl = CHECK_ERROR_TTL_SECONDS if cache_error else CHECK_TTL_SECONDS
    cache_valid = (
        cached_checked_at > 0
        and now - cached_checked_at < cache_ttl
        and cached_current == current
    )
    if cache_valid:
        latest = str(cached.get("latest_version", "")).strip()
        release_url = str(cached.get("release_url", "")).strip()
        return build_update_info(
            current_version=current,
            latest_version=latest,
            release_url=release_url,
        )

    try:
        latest, release_url = fetch_latest_release(
            repo=repo, http_get_json=http_get_json
        )
    except Exception:  # noqa: BLE001
        _write_cache(
            cache_file,
            {
                "checked_at": now,
                "current_version": current,
                "error": True,
            },
        )
        return None

    _write_cache(
        cache_file,
        {
            "checked_at": now,
            "current_version": current,
            "latest_version": latest,
            "release_url": release_url,
            "error": False,
        },
    )
    return build_update_info(
        current_version=current,
        latest_version=latest,
        release_url=release_url,
    )


# ── Auto-update orchestration ────────────────────────────────
def check_latest_version(
    current_version: str, repo: str = DEFAULT_CLIPROXY_REPO
) -> dict[str, str] | None:
    """Check latest release from GitHub and return update info when newer exists."""
    latest, release_url = fetch_latest_release(repo=repo, http_get_json=http_get_json)
    return build_update_info(
        current_version=current_version,
        latest_version=latest,
        release_url=release_url,
    )


def perform_update(
    *,
    config: dict[str, Any],
    latest_version: str,
    repo: str = DEFAULT_CLIPROXY_REPO,
    require_sha256: bool = False,
) -> dict[str, Path | int | None]:
    """Download/update CLIProxyAPIPlus and restart running service if needed."""
    runtime_dir = config["paths"]["runtime_dir"]
    runtime_bin_dir = Path(runtime_dir) / "bin"

    cliproxy = download_cliproxyapi_plus(
        runtime_bin_dir,
        version=latest_version,
        repo=repo,
        require_sha256=require_sha256,
    )
    if not validate_cliproxy_binary(cliproxy):
        raise RuntimeError(f"Invalid CLIProxyAPIPlus binary downloaded: {cliproxy}")

    write_installed_version(runtime_dir, latest_version)

    restarted_pid: int | None = None
    supervisor = ProcessSupervisor(
        runtime_dir,
        events_log=config["paths"]["log_file"],
    )
    if supervisor.is_running(CLIPROXYAPI_PLUS_SERVICE):
        service_cfg = config["services"].get(CLIPROXYAPI_PLUS_SERVICE, {})
        args = service_cfg.get("command", {}).get("args", [])
        cwd = service_cfg.get("command", {}).get("cwd") or os.getcwd()
        pid = supervisor.restart(CLIPROXYAPI_PLUS_SERVICE, args, cwd=cwd)
        restarted_pid = int(pid)

    return {
        "cliproxyapi_plus": cliproxy,
        "restarted_pid": restarted_pid,
    }
