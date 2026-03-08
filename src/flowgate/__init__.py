"""FlowGate - CLIProxyAPIPlus wrapper."""

from __future__ import annotations

import sys


def main() -> int:
    """Entry point for the flowgate CLI."""
    from flowgate.cli import run_cli  # Lazy import to avoid loading CLI on package import

    return run_cli(sys.argv[1:])
