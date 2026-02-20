"""Performance monitoring and observability utilities.

This module provides decorators and utilities for tracking operation performance
and logging metrics to the events log. Performance data helps identify bottlenecks
and optimize critical paths.

Example usage:
    @measure_time("config_load")
    def load_config(path: str) -> dict:
        # Function implementation
        return config
"""

import functools
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


def measure_time(operation: str) -> Callable[[F], F]:
    """Decorator to measure and log function execution time.

    Measures the wall-clock time for a function call and logs it to the
    events log. Does not affect the function's behavior - exceptions and
    return values pass through unchanged.

    Args:
        operation: Name of the operation being measured (e.g., "config_load")

    Returns:
        Decorated function that logs performance metrics

    Example:
        @measure_time("profile_switch")
        def switch_profile(name: str) -> None:
            # Implementation
            pass
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                # Always log metrics, even if function raised exception
                duration_ms = (time.perf_counter() - start_time) * 1000
                log_performance_metric(
                    operation=operation,
                    duration_ms=duration_ms,
                    function_name=func.__name__,
                )

        return wrapper  # type: ignore[return-value]

    return decorator


def log_performance_metric(
    operation: str,
    duration_ms: float,
    function_name: Optional[str] = None,
    context: Optional[dict[str, Any]] = None,
) -> None:
    """Log a performance metric to the events log.

    Writes a JSON line to .router/runtime/events.log with performance data.
    If the events log doesn't exist yet (e.g., during tests or first run),
    this function silently succeeds without creating directories.

    Args:
        operation: High-level operation name (e.g., "config_load")
        duration_ms: Execution time in milliseconds
        function_name: Name of the function measured (optional)
        context: Additional context data (optional)

    Example:
        log_performance_metric(
            operation="profile_switch",
            duration_ms=1234.56,
            function_name="switch_profile",
            context={"profile": "balanced"}
        )
    """
    # Build metric record
    metric: dict[str, Any] = {
        "event": "performance_metric",
        "operation": operation,
        "duration_ms": round(duration_ms, 2),
        "timestamp": datetime.now(UTC).isoformat(),
    }

    if function_name:
        metric["function"] = function_name

    if context:
        metric["context"] = context

    # Try to append to events log
    # Use well-known path relative to project root
    events_log = Path(".router/runtime/events.log")

    try:
        # Create parent directories if they don't exist
        events_log.parent.mkdir(parents=True, exist_ok=True)

        # Append JSON line to events log
        with events_log.open("a", encoding="utf-8") as f:
            f.write(json.dumps(metric) + "\n")
    except (OSError, IOError):
        # Silently fail if we can't write (e.g., permissions, disk full)
        # Don't break the application for observability failures
        pass


def get_recent_metrics(
    operation: Optional[str] = None, limit: int = 100
) -> list[dict[str, Any]]:
    """Retrieve recent performance metrics from the events log.

    Reads the events log and returns performance_metric events, optionally
    filtered by operation name. Most recent events are returned first.

    Args:
        operation: Filter by operation name (None = return all)
        limit: Maximum number of metrics to return

    Returns:
        List of metric dictionaries, most recent first

    Example:
        # Get last 50 config_load metrics
        metrics = get_recent_metrics("config_load", limit=50)
        avg_ms = sum(m["duration_ms"] for m in metrics) / len(metrics)
    """
    events_log = Path(".router/runtime/events.log")

    if not events_log.exists():
        return []

    metrics: list[dict[str, Any]] = []

    try:
        with events_log.open("r", encoding="utf-8") as f:
            # Read all lines (could optimize with tail for large files)
            for line in f:
                try:
                    event = json.loads(line.strip())
                    if event.get("event") == "performance_metric":
                        if operation is None or event.get("operation") == operation:
                            metrics.append(event)
                except json.JSONDecodeError:
                    # Skip malformed lines
                    continue
    except (OSError, IOError):
        # Return empty list if we can't read the file
        return []

    # Return most recent first, limited
    return list(reversed(metrics[-limit:]))
