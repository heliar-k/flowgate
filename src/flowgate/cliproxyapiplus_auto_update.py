from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .bootstrap import (
    DEFAULT_CLIPROXY_REPO,
    _http_get_json,
    download_cliproxyapi_plus,
    validate_cliproxy_binary,
)
from .cliproxyapiplus_release import fetch_latest_release
from .cliproxyapiplus_update_check import write_cliproxyapiplus_installed_version
from .cliproxyapiplus_version import build_update_info
from .constants import CLIPROXYAPI_PLUS_SERVICE
from .process import ProcessSupervisor


def check_latest_version(
    current_version: str, repo: str = DEFAULT_CLIPROXY_REPO
) -> dict[str, str] | None:
    """Check latest release from GitHub and return update info when newer exists."""
    latest, release_url = fetch_latest_release(repo=repo, http_get_json=_http_get_json)
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

    write_cliproxyapiplus_installed_version(runtime_dir, latest_version)

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
