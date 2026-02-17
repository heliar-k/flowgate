from __future__ import annotations

from typing import Any

from .constants import DEFAULT_SERVICE_HOST


def _litellm_base_url(config: dict[str, Any]) -> str:
    services = config.get("services", {})
    if not isinstance(services, dict):
        raise ValueError("services must be a mapping/object")

    litellm = services.get("litellm", {})
    if not isinstance(litellm, dict):
        raise ValueError("services.litellm must be a mapping/object")

    host = litellm.get("host", DEFAULT_SERVICE_HOST)
    port = litellm.get("port")
    if not isinstance(port, int):
        raise ValueError("services.litellm.port must be an integer")
    return f"http://{host}:{port}"


def build_integration_specs(config: dict[str, Any]) -> dict[str, Any]:
    base_url = _litellm_base_url(config)

    integration = config.get("integration", {})
    if not isinstance(integration, dict):
        integration = {}

    default_model = str(integration.get("default_model", "router-default")).strip()
    if not default_model:
        default_model = "router-default"

    fast_model = str(integration.get("fast_model", default_model)).strip()
    if not fast_model:
        fast_model = default_model

    return {
        "codex": {
            "base_url": f"{base_url}/v1",
            "model": default_model,
        },
        "claude_code": {
            "base_url": base_url,
            "env": {
                "ANTHROPIC_MODEL": default_model,
                "ANTHROPIC_DEFAULT_OPUS_MODEL": default_model,
                "ANTHROPIC_DEFAULT_SONNET_MODEL": default_model,
                "ANTHROPIC_DEFAULT_HAIKU_MODEL": fast_model,
            },
        },
    }
