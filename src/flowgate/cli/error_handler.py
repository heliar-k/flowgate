"""
Unified exception handling for FlowGate CLI commands.

This module provides a decorator for consistent error handling across all CLI commands,
with standardized exit codes and error messages.
"""

from __future__ import annotations

import functools
import logging
import sys
from collections.abc import Callable

from ..core.config import ConfigError
from ..core.process import ProcessError
from .output import Output, command_id_from_args

logger = logging.getLogger(__name__)

# Exit code constants
EXIT_SUCCESS = 0
EXIT_RUNTIME_ERROR = 1
EXIT_CONFIG_ERROR = 2
# Backward-compatible aliases (FlowGate documents 0/1/2 as the public contract).
EXIT_PERMISSION_ERROR = EXIT_RUNTIME_ERROR
EXIT_INTERNAL_ERROR = EXIT_RUNTIME_ERROR


def handle_command_errors(func: Callable) -> Callable:
    """
    Decorator for unified exception handling in CLI commands.

    Catches and handles specific exceptions with appropriate exit codes:
    - ConfigError: Configuration issues (user can fix)
    - ProcessError: Process operation failures
    - PermissionError: Permission denied errors
    - Exception: Unexpected internal errors

    Args:
        func: Command function to wrap (should return int exit code)

    Returns:
        Wrapped function with error handling
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> int:
        # Extract stderr from command instance if available (for testing)
        stderr = sys.stderr
        stdout = sys.stdout
        debug = False
        output: Output | None = None
        if args and hasattr(args[0], "args"):
            stdout = getattr(args[0].args, "stdout", None) or sys.stdout
            stderr = getattr(args[0].args, "stderr", None) or sys.stderr
            debug = bool(getattr(args[0].args, "debug", False))
            try:
                output = getattr(args[0].args, "_output", None)
                if output is None:
                    output = Output.from_args(
                        args[0].args, stdout=stdout, stderr=stderr
                    )
            except Exception:
                output = None

        try:
            return func(*args, **kwargs)
        except ConfigError as exc:
            logger.error("Configuration error: %s", exc)
            if output is not None:
                output.emit_envelope(
                    {
                        "ok": False,
                        "command": command_id_from_args(getattr(args[0], "args", None)),
                        "data": {},
                        "warnings": [],
                        "errors": [{"type": "ConfigError", "message": str(exc)}],
                    }
                )
            print(f"❌ Configuration error: {exc}", file=stderr)
            return EXIT_CONFIG_ERROR
        except ProcessError as exc:
            logger.error("Process operation failed: %s", exc, exc_info=True)
            if output is not None:
                output.emit_envelope(
                    {
                        "ok": False,
                        "command": command_id_from_args(getattr(args[0], "args", None)),
                        "data": {},
                        "warnings": [],
                        "errors": [{"type": "ProcessError", "message": str(exc)}],
                    }
                )
            print(f"❌ Process operation failed: {exc}", file=stderr)
            return EXIT_RUNTIME_ERROR
        except PermissionError as exc:
            logger.error("Permission denied: %s", exc, exc_info=debug)
            if output is not None:
                output.emit_envelope(
                    {
                        "ok": False,
                        "command": command_id_from_args(getattr(args[0], "args", None)),
                        "data": {},
                        "warnings": [],
                        "errors": [{"type": "PermissionError", "message": str(exc)}],
                    }
                )
            print(f"❌ Permission denied: {exc}", file=stderr)
            return EXIT_RUNTIME_ERROR
        except Exception as exc:
            logger.exception("Internal error: %s", exc)
            if output is not None:
                output.emit_envelope(
                    {
                        "ok": False,
                        "command": command_id_from_args(getattr(args[0], "args", None)),
                        "data": {},
                        "warnings": [],
                        "errors": [{"type": type(exc).__name__, "message": str(exc)}],
                    }
                )
            print(f"❌ Internal error: {exc}", file=stderr)
            if debug:
                import traceback

                traceback.print_exc(file=stderr)
            else:
                print("Re-run with --debug for a stack trace.", file=stderr)
            return EXIT_RUNTIME_ERROR

    return wrapper
