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


def _upstream_credentials(config: dict[str, Any]) -> dict[str, str]:
    credentials = config.get("credentials", {})
    if not isinstance(credentials, dict):
        return {}

    upstream = credentials.get("upstream", {})
    if not isinstance(upstream, dict):
        return {}

    result: dict[str, str] = {}
    for name, entry in upstream.items():
        if not isinstance(name, str):
            continue
        if not isinstance(entry, dict):
            continue
        file_path = entry.get("file")
        if isinstance(file_path, str) and file_path.strip():
            result[name] = file_path
    return result


def _read_api_key_from_file(path: str) -> str:
    key_path = Path(path)
    if not key_path.exists() or not key_path.is_file():
        raise ValueError(f"Credential file not found: {key_path}")
    api_key = key_path.read_text(encoding="utf-8").strip()
    if not api_key:
        raise ValueError(f"Credential file is empty: {key_path}")
    return api_key


def _resolve_model_api_key_refs(
    litellm_doc: dict[str, Any], *, upstream_credentials: dict[str, str]
) -> None:
    model_list = litellm_doc.get("model_list")
    if not isinstance(model_list, list):
        return

    api_key_cache: dict[str, str] = {}
    for idx, item in enumerate(model_list):
        if not isinstance(item, dict):
            continue
        params = item.get("litellm_params")
        if not isinstance(params, dict):
            continue

        ref_raw = params.get("api_key_ref")
        if ref_raw is None:
            continue

        if not isinstance(ref_raw, str) or not ref_raw.strip():
            raise ValueError(
                f"model_list[{idx}].litellm_params.api_key_ref must be a non-empty string"
            )

        ref = ref_raw.strip()
        file_path = upstream_credentials.get(ref)
        if not file_path:
            raise ValueError(f"Unknown api_key_ref: {ref}")

        api_key = api_key_cache.get(ref)
        if api_key is None:
            api_key = _read_api_key_from_file(file_path)
            api_key_cache[ref] = api_key

        params["api_key"] = api_key
        params.pop("api_key_ref", None)


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
    _resolve_model_api_key_refs(
        merged,
        upstream_credentials=_upstream_credentials(config),
    )

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
