#!/usr/bin/env python3
"""
FlowGate CLI entry point.

This file serves as the top-level entry point for the FlowGate CLI,
delegating to the flowgate package's run_cli function.
"""

from __future__ import annotations

import sys

from flowgate.cli import run_cli


def main() -> int:
    return run_cli(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
