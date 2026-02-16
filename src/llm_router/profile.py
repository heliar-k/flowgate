from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import merge_dicts


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def activate_profile(
    config: dict[str, Any],
    profile_name: str,
    *,
    now_iso: str | None = None,
) -> tuple[Path, Path]:
    profiles = config.get("profiles", {})
    if profile_name not in profiles:
        raise KeyError(f"Unknown profile: {profile_name}")

    litellm_base = config.get("litellm_base", {})
    profile_overlay = profiles[profile_name]

    merged = merge_dicts(litellm_base, profile_overlay)

    paths = config["paths"]
    runtime_dir = Path(paths["runtime_dir"])
    runtime_dir.mkdir(parents=True, exist_ok=True)

    active_path = Path(paths["active_config"])
    state_path = Path(paths["state_file"])

    _atomic_write(active_path, json.dumps(merged, indent=2, sort_keys=True))

    timestamp = now_iso or datetime.now(UTC).isoformat()
    state_doc = {
        "current_profile": profile_name,
        "updated_at": timestamp,
    }
    _atomic_write(state_path, json.dumps(state_doc, indent=2, sort_keys=True))

    return active_path, state_path
