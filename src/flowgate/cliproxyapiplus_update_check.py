from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from .cliproxyapiplus_release import fetch_latest_release
from .cliproxyapiplus_version import (
    build_update_info,
    is_newer_version,
    parse_version_tuple,
)

CHECK_CACHE_FILE = "cliproxyapiplus_update_cache.json"
INSTALLED_VERSION_FILE = "cliproxyapiplus.version"
CHECK_TTL_SECONDS = 24 * 60 * 60
CHECK_ERROR_TTL_SECONDS = 60 * 60


def _parse_version_tuple(version: str) -> tuple[int, ...] | None:
    # Backward-compatible private wrapper used by existing tests/call sites.
    return parse_version_tuple(version)


def _is_newer_version(latest: str, current: str) -> bool:
    # Backward-compatible private wrapper used by existing tests/call sites.
    return is_newer_version(latest, current)


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


def _http_get_json(url: str) -> dict[str, Any]:
    req = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "flowgate-update-check",
        },
    )
    with urlopen(req, timeout=5) as resp:  # nosec B310
        payload = resp.read().decode("utf-8")
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise RuntimeError("invalid latest release payload")
    return data


def read_cliproxyapiplus_installed_version(
    runtime_dir: str | Path, fallback_version: str
) -> str:
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


def write_cliproxyapiplus_installed_version(
    runtime_dir: str | Path, version: str
) -> None:
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


def check_cliproxyapiplus_update(
    *,
    runtime_dir: str | Path,
    current_version: str,
    repo: str,
) -> dict[str, str] | None:
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
            repo=repo, http_get_json=_http_get_json
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
