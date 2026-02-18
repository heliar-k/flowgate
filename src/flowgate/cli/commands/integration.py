"""
Integration command handlers for FlowGate CLI.

This module contains command handlers for generating and applying
client integration configurations (Codex, Claude Code).
"""
from __future__ import annotations

import sys
from typing import Any, TextIO

from ...client_apply import apply_claude_code_settings, apply_codex_config
from ...integration import build_integration_specs
from .base import BaseCommand


def _render_codex_integration(spec: dict[str, Any]) -> str:
    """Render Codex integration configuration snippet."""
    base_url = str(spec.get("base_url", "")).strip()
    model = str(spec.get("model", "router-default")).strip() or "router-default"
    return "\n".join(
        [
            'model_provider = "flowgate"',
            f'model = "{model}"',
            "",
            "[model_providers.flowgate]",
            'name = "FlowGate Local"',
            f'base_url = "{base_url}"',
            'env_key = "OPENAI_API_KEY"',
            'wire_api = "responses"',
        ]
    )


def _render_claude_code_integration(spec: dict[str, Any]) -> str:
    """Render Claude Code integration configuration snippet."""
    base_url = str(spec.get("base_url", "")).strip()
    env = spec.get("env", {})
    if not isinstance(env, dict):
        env = {}

    lines = [
        f"ANTHROPIC_BASE_URL={base_url}",
        "ANTHROPIC_AUTH_TOKEN=your-gateway-token",
    ]
    for key in (
        "ANTHROPIC_MODEL",
        "ANTHROPIC_DEFAULT_OPUS_MODEL",
        "ANTHROPIC_DEFAULT_SONNET_MODEL",
        "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    ):
        value = str(env.get(key, "")).strip()
        if value:
            lines.append(f"{key}={value}")
    return "\n".join(lines)


class IntegrationPrintCommand(BaseCommand):
    """Print integration configuration snippet for a client."""

    def execute(self) -> int:
        """Execute integration print command."""
        stdout: TextIO = getattr(self.args, "stdout", None) or sys.stdout
        stderr: TextIO = getattr(self.args, "stderr", None) or sys.stderr

        client = self.args.client

        try:
            specs = build_integration_specs(self.config)
        except Exception as exc:  # noqa: BLE001
            print(f"integration render failed: {exc}", file=stderr)
            return 1

        if client == "codex":
            print(_render_codex_integration(specs.get("codex", {})), file=stdout)
            return 0
        if client == "claude-code":
            print(
                _render_claude_code_integration(specs.get("claude_code", {})), file=stdout
            )
            return 0

        print(f"Unknown integration client: {client}", file=stderr)
        return 2


class IntegrationApplyCommand(BaseCommand):
    """Apply integration configuration to a client config file."""

    def execute(self) -> int:
        """Execute integration apply command."""
        stdout: TextIO = getattr(self.args, "stdout", None) or sys.stdout
        stderr: TextIO = getattr(self.args, "stderr", None) or sys.stderr

        client = self.args.client
        target = self.args.target if self.args.target else None

        try:
            specs = build_integration_specs(self.config)
        except Exception as exc:  # noqa: BLE001
            print(f"integration render failed: {exc}", file=stderr)
            return 1

        if client == "codex":
            resolved_target = target or "~/.codex/config.toml"
            spec = specs.get("codex", {})
            if not isinstance(spec, dict):
                print("integration spec missing codex block", file=stderr)
                return 1
            try:
                result = apply_codex_config(resolved_target, spec)
            except Exception as exc:  # noqa: BLE001
                print(f"integration apply failed: {exc}", file=stderr)
                return 1
        elif client == "claude-code":
            resolved_target = target or "~/.claude/settings.json"
            spec = specs.get("claude_code", {})
            if not isinstance(spec, dict):
                print("integration spec missing claude_code block", file=stderr)
                return 1
            try:
                result = apply_claude_code_settings(resolved_target, spec)
            except Exception as exc:  # noqa: BLE001
                print(f"integration apply failed: {exc}", file=stderr)
                return 1
        else:
            print(f"Unknown integration client: {client}", file=stderr)
            return 2

        print(f"saved_path={result['path']}", file=stdout)
        backup_path = result.get("backup_path")
        if backup_path:
            print(f"backup_path={backup_path}", file=stdout)
        return 0
