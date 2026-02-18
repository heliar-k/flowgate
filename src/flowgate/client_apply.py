from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

CLAUDE_MANAGED_MODEL_ENV_KEYS: tuple[str, ...] = (
    "ANTHROPIC_MODEL",
    "ANTHROPIC_DEFAULT_OPUS_MODEL",
    "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL",
)


def _backup_file(path: Path) -> Path | None:
    if not path.exists():
        return None
    backup = path.with_name(f"{path.name}.backup.{int(time.time())}")
    backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    return backup


def apply_claude_code_settings(
    target: str | Path, spec: dict[str, Any]
) -> dict[str, str | None]:
    target_path = Path(target).expanduser()
    target_path.parent.mkdir(parents=True, exist_ok=True)

    backup = _backup_file(target_path)

    doc: dict[str, Any] = {}
    if target_path.exists():
        raw = target_path.read_text(encoding="utf-8")
        if raw.strip():
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                raise ValueError("Claude settings must be a JSON object")
            doc = parsed

    env_raw = doc.get("env", {})
    env = env_raw if isinstance(env_raw, dict) else {}
    doc["env"] = env

    base_url = str(spec.get("base_url", "")).strip()
    if not base_url:
        raise ValueError("Claude integration spec missing base_url")
    env["ANTHROPIC_BASE_URL"] = base_url

    spec_env = spec.get("env", {})
    if isinstance(spec_env, dict):
        for key in CLAUDE_MANAGED_MODEL_ENV_KEYS:
            value = str(spec_env.get(key, "")).strip()
            if value:
                env[key] = value

    # Only update token field when it already exists.
    if "ANTHROPIC_AUTH_TOKEN" in env:
        env["ANTHROPIC_AUTH_TOKEN"] = "your-gateway-token"

    target_path.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "path": str(target_path),
        "backup_path": str(backup) if backup else None,
    }


def _extract_model_provider(config_text: str) -> str | None:
    match = re.search(r'(?m)^\s*model_provider\s*=\s*"([^"]+)"\s*$', config_text)
    if not match:
        return None
    provider = match.group(1).strip()
    return provider or None


def _upsert_provider_base_url(config_text: str, provider: str, base_url: str) -> str:
    section_header = rf"(?m)^\[model_providers\.{re.escape(provider)}\]\s*$"
    header_match = re.search(section_header, config_text)

    base_line = f'base_url = "{base_url}"'

    if not header_match:
        doc = config_text.rstrip()
        if doc:
            doc += "\n\n"
        doc += "\n".join(
            [
                f"[model_providers.{provider}]",
                base_line,
            ]
        )
        return doc + "\n"

    next_section_match = re.search(
        r"(?m)^\[[^\n]+\]\s*$", config_text[header_match.end() :]
    )
    if next_section_match:
        section_end = header_match.end() + next_section_match.start()
    else:
        section_end = len(config_text)

    section = config_text[header_match.start() : section_end]
    if re.search(r"(?m)^\s*base_url\s*=", section):
        section = re.sub(
            r'(?m)^(\s*base_url\s*=\s*)".*?"\s*$',
            rf'\1"{base_url}"',
            section,
            count=1,
        )
    else:
        section = section.rstrip("\n") + "\n" + base_line + "\n"

    return config_text[: header_match.start()] + section + config_text[section_end:]


def apply_codex_config(
    target: str | Path, spec: dict[str, Any]
) -> dict[str, str | None]:
    target_path = Path(target).expanduser()
    target_path.parent.mkdir(parents=True, exist_ok=True)

    backup = _backup_file(target_path)
    config_text = (
        target_path.read_text(encoding="utf-8") if target_path.exists() else ""
    )

    base_url = str(spec.get("base_url", "")).strip()
    if not base_url:
        raise ValueError("Codex integration spec missing base_url")

    model = str(spec.get("model", "router-default")).strip() or "router-default"
    provider = _extract_model_provider(config_text) or "flowgate"

    updated = config_text
    if not _extract_model_provider(updated):
        prefix = "\n".join(
            [
                f'model_provider = "{provider}"',
                f'model = "{model}"',
            ]
        )
        suffix = updated.lstrip("\n")
        updated = prefix + ("\n\n" + suffix if suffix else "\n")

    updated = _upsert_provider_base_url(updated, provider, base_url)

    target_path.write_text(updated, encoding="utf-8")
    return {
        "path": str(target_path),
        "backup_path": str(backup) if backup else None,
    }
