"""
Output helpers for FlowGate CLI.

This module centralizes CLI output formatting so commands can support both
human-friendly ("legacy") and machine-friendly ("json"/"kv") modes without
duplicating logic.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, TextIO

_FORMAT_CHOICES = ("auto", "legacy", "kv", "json")


def _is_tty(stream: TextIO) -> bool:
    isatty = getattr(stream, "isatty", None)
    return bool(callable(isatty) and isatty())


def resolve_output_format(requested: str, *, stdout: TextIO) -> str:
    """Resolve the effective output format for this invocation."""
    requested = (requested or "legacy").strip().lower()
    if requested not in _FORMAT_CHOICES:
        return "legacy"
    if requested != "auto":
        return requested
    return "legacy" if _is_tty(stdout) else "kv"


def command_id_from_args(args: Any) -> str:
    """Derive a stable command id from parsed argparse args."""
    command = str(getattr(args, "command", "unknown") or "unknown")
    if command == "service":
        sub = getattr(args, "service_cmd", None)
        if sub:
            return f"service.{sub}"
    if command == "auth":
        sub = getattr(args, "provider", None)
        if sub:
            return f"auth.{sub}"
    if command == "bootstrap":
        sub = getattr(args, "bootstrap_cmd", None)
        if sub:
            return f"bootstrap.{sub}"
    if command == "integration":
        sub = getattr(args, "integration_cmd", None)
        if sub:
            return f"integration.{sub}"
    return command


def _flatten_kv(obj: Any, *, prefix: str = "") -> Iterable[tuple[str, Any]]:
    if isinstance(obj, dict):
        for key in sorted(obj.keys(), key=lambda k: str(k)):
            value = obj[key]
            next_prefix = f"{prefix}.{key}" if prefix else str(key)
            yield from _flatten_kv(value, prefix=next_prefix)
        return
    if isinstance(obj, list):
        for idx, value in enumerate(obj):
            next_prefix = f"{prefix}.{idx}" if prefix else str(idx)
            yield from _flatten_kv(value, prefix=next_prefix)
        return
    yield prefix, obj


def _kv_value(value: Any) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return str(value)
    # For strings and other scalars, emit JSON to preserve whitespace safely.
    try:
        return json.dumps(value, ensure_ascii=False)
    except TypeError:
        return json.dumps(str(value), ensure_ascii=False)


@dataclass(frozen=True)
class Output:
    """CLI output emitter for legacy/json/kv modes."""

    format: str
    stdout: TextIO
    stderr: TextIO
    quiet: bool = False
    plain: bool = False
    interactive: bool = False

    @classmethod
    def from_args(
        cls, args: Any, *, stdout: TextIO | None = None, stderr: TextIO | None = None
    ) -> Output:
        out = stdout or getattr(args, "stdout", None) or sys.stdout
        err = stderr or getattr(args, "stderr", None) or sys.stderr
        requested = str(getattr(args, "format", "legacy") or "legacy")
        effective = resolve_output_format(requested, stdout=out)
        quiet = bool(getattr(args, "quiet", False))
        plain = bool(getattr(args, "plain", False))
        # Interactive means we can reasonably prompt a user.
        interactive = bool(_is_tty(out) and _is_tty(sys.stdin))
        return cls(
            format=effective,
            stdout=out,
            stderr=err,
            quiet=quiet,
            plain=plain,
            interactive=interactive,
        )

    def progress(self, message: str) -> None:
        """Emit progress to stderr (TTY only) unless quiet."""
        if self.quiet:
            return
        if not _is_tty(self.stderr):
            return
        print(message, file=self.stderr, flush=True)

    def emit_envelope(self, envelope: dict[str, Any]) -> None:
        """Emit an envelope in json/kv mode. No-op in legacy mode."""
        if self.format == "legacy":
            return
        if self.format == "json":
            print(
                json.dumps(envelope, ensure_ascii=False, sort_keys=True),
                file=self.stdout,
            )
            return
        if self.format == "kv":
            for key, value in _flatten_kv(envelope):
                if not key:
                    continue
                print(f"{key}={_kv_value(value)}", file=self.stdout)
            return
