"""
Unified exception handling for FlowGate CLI commands.

This module provides a decorator for consistent error handling across all CLI commands,
with standardized exit codes and error messages.
"""
from __future__ import annotations

import functools
import logging
import sys
from typing import Callable

from ..config import ConfigError
from ..process import ProcessError

logger = logging.getLogger(__name__)

# Exit code constants
EXIT_SUCCESS = 0
EXIT_CONFIG_ERROR = 1
EXIT_RUNTIME_ERROR = 2
EXIT_PERMISSION_ERROR = 3
EXIT_INTERNAL_ERROR = 99


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
        try:
            return func(*args, **kwargs)
        except ConfigError as exc:
            logger.error("Configuration error: %s", exc)
            print(f"❌ Configuration error: {exc}", file=sys.stderr)
            return EXIT_CONFIG_ERROR
        except ProcessError as exc:
            logger.error("Process operation failed: %s", exc, exc_info=True)
            print(f"❌ Process operation failed: {exc}", file=sys.stderr)
            return EXIT_RUNTIME_ERROR
        except PermissionError as exc:
            logger.error("Permission denied: %s", exc)
            print(f"❌ Permission denied: {exc}", file=sys.stderr)
            return EXIT_PERMISSION_ERROR
        except Exception as exc:
            logger.exception("Internal error: %s", exc)
            print(
                f"❌ Internal error: {exc}\n"
                "Please use --debug for more details",
                file=sys.stderr,
            )
            return EXIT_INTERNAL_ERROR

    return wrapper
