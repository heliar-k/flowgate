"""Backward-compat shim — moved to flowgate.core.observability."""
from .core.observability import *  # noqa: F401, F403
from .core.observability import measure_time, set_events_log_path, events_log_context, log_performance_metric, get_recent_metrics  # explicit
