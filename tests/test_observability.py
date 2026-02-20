"""Tests for observability module (performance monitoring)."""

import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from flowgate.observability import (
    get_recent_metrics,
    log_performance_metric,
    measure_time,
)


@pytest.mark.unit
class TestMeasureTimeDecorator(unittest.TestCase):
    """Test the @measure_time decorator."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.events_log = Path(self.temp_dir) / ".router" / "runtime" / "events.log"

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_decorator_measures_execution_time(self):
        """Test that decorator measures and logs execution time."""
        with patch("flowgate.observability.log_performance_metric") as mock_log:

            @measure_time("test_operation")
            def slow_function():
                time.sleep(0.01)  # 10ms
                return "result"

            result = slow_function()

            self.assertEqual(result, "result")
            # Verify metric was logged
            mock_log.assert_called_once()
            args = mock_log.call_args[1]
            self.assertEqual(args["operation"], "test_operation")
            self.assertGreater(args["duration_ms"], 10.0)  # At least 10ms

    def test_decorator_preserves_function_metadata(self):
        """Test that decorator preserves function name and docstring."""

        @measure_time("test_op")
        def example_function():
            """Example docstring."""
            return 42

        self.assertEqual(example_function.__name__, "example_function")
        self.assertEqual(example_function.__doc__, "Example docstring.")

    def test_decorator_passes_through_return_value(self):
        """Test that decorator returns the original function's return value."""

        @measure_time("test_op")
        def return_value():
            return {"key": "value"}

        result = return_value()
        self.assertEqual(result, {"key": "value"})

    def test_decorator_passes_through_exceptions(self):
        """Test that decorator doesn't suppress exceptions."""

        @measure_time("test_op")
        def raise_error():
            raise ValueError("test error")

        with self.assertRaises(ValueError) as ctx:
            raise_error()

        self.assertEqual(str(ctx.exception), "test error")

    def test_decorator_logs_even_on_exception(self):
        """Test that decorator logs metrics even when function raises."""
        with patch("flowgate.observability.log_performance_metric") as mock_log:

            @measure_time("test_op")
            def raise_error():
                raise RuntimeError("boom")

            with self.assertRaises(RuntimeError):
                raise_error()

            # Verify metric was logged despite exception
            mock_log.assert_called_once()
            args = mock_log.call_args[1]
            self.assertEqual(args["operation"], "test_op")
            self.assertIn("duration_ms", args)

    def test_decorator_with_arguments(self):
        """Test that decorator works with functions that take arguments."""

        @measure_time("add_operation")
        def add(a, b):
            return a + b

        result = add(2, 3)
        self.assertEqual(result, 5)

    def test_decorator_with_kwargs(self):
        """Test that decorator works with keyword arguments."""

        @measure_time("greet_operation")
        def greet(name, greeting="Hello"):
            return f"{greeting}, {name}!"

        result = greet("World", greeting="Hi")
        self.assertEqual(result, "Hi, World!")

    def test_nested_decorators(self):
        """Test that nested decorated functions work correctly."""
        with patch("flowgate.observability.log_performance_metric") as mock_log:

            @measure_time("outer")
            def outer():
                return inner()

            @measure_time("inner")
            def inner():
                return "done"

            result = outer()

            self.assertEqual(result, "done")
            # Both functions should log metrics
            self.assertEqual(mock_log.call_count, 2)


@pytest.mark.unit
class TestLogPerformanceMetric(unittest.TestCase):
    """Test the log_performance_metric function."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = Path.cwd()
        import os

        os.chdir(self.temp_dir)

    def tearDown(self):
        """Clean up test fixtures."""
        import os
        import shutil

        os.chdir(self.original_cwd)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_log_creates_events_log(self):
        """Test that logging creates the events log file."""
        log_performance_metric("test_op", 123.45)

        events_log = Path(".router/runtime/events.log")
        self.assertTrue(events_log.exists())

    def test_log_format_is_valid_json(self):
        """Test that logged metrics are valid JSON."""
        log_performance_metric("test_op", 123.45, function_name="test_func")

        events_log = Path(".router/runtime/events.log")
        content = events_log.read_text()
        data = json.loads(content.strip())

        self.assertEqual(data["event"], "performance_metric")
        self.assertEqual(data["operation"], "test_op")
        self.assertEqual(data["duration_ms"], 123.45)
        self.assertEqual(data["function"], "test_func")
        self.assertIn("timestamp", data)

    def test_log_rounds_duration(self):
        """Test that duration is rounded to 2 decimal places."""
        log_performance_metric("test_op", 123.456789)

        events_log = Path(".router/runtime/events.log")
        content = events_log.read_text()
        data = json.loads(content.strip())

        self.assertEqual(data["duration_ms"], 123.46)

    def test_log_with_context(self):
        """Test logging with additional context."""
        log_performance_metric(
            "test_op", 100.0, context={"profile": "balanced", "service": "litellm"}
        )

        events_log = Path(".router/runtime/events.log")
        content = events_log.read_text()
        data = json.loads(content.strip())

        self.assertEqual(data["context"]["profile"], "balanced")
        self.assertEqual(data["context"]["service"], "litellm")

    def test_log_appends_to_existing_file(self):
        """Test that logging appends to existing events log."""
        log_performance_metric("op1", 100.0)
        log_performance_metric("op2", 200.0)

        events_log = Path(".router/runtime/events.log")
        lines = events_log.read_text().strip().split("\n")

        self.assertEqual(len(lines), 2)
        data1 = json.loads(lines[0])
        data2 = json.loads(lines[1])
        self.assertEqual(data1["operation"], "op1")
        self.assertEqual(data2["operation"], "op2")

    def test_log_handles_write_failure_gracefully(self):
        """Test that logging failures don't raise exceptions."""
        with patch("flowgate.observability.Path") as mock_path:
            mock_log = Mock()
            mock_path.return_value = mock_log
            mock_log.parent.mkdir.side_effect = OSError("Permission denied")

            # Should not raise
            log_performance_metric("test_op", 100.0)

    def test_log_without_function_name(self):
        """Test logging without function name."""
        log_performance_metric("test_op", 100.0)

        events_log = Path(".router/runtime/events.log")
        content = events_log.read_text()
        data = json.loads(content.strip())

        self.assertNotIn("function", data)

    def test_log_without_context(self):
        """Test logging without context."""
        log_performance_metric("test_op", 100.0)

        events_log = Path(".router/runtime/events.log")
        content = events_log.read_text()
        data = json.loads(content.strip())

        self.assertNotIn("context", data)


@pytest.mark.unit
class TestGetRecentMetrics(unittest.TestCase):
    """Test the get_recent_metrics function."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = Path.cwd()
        import os

        os.chdir(self.temp_dir)

    def tearDown(self):
        """Clean up test fixtures."""
        import os
        import shutil

        os.chdir(self.original_cwd)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_metrics_from_empty_log(self):
        """Test getting metrics when log doesn't exist."""
        metrics = get_recent_metrics()
        self.assertEqual(metrics, [])

    def test_get_all_metrics(self):
        """Test getting all metrics without filter."""
        log_performance_metric("op1", 100.0)
        log_performance_metric("op2", 200.0)
        log_performance_metric("op3", 300.0)

        metrics = get_recent_metrics()

        self.assertEqual(len(metrics), 3)
        # Most recent first
        self.assertEqual(metrics[0]["operation"], "op3")
        self.assertEqual(metrics[1]["operation"], "op2")
        self.assertEqual(metrics[2]["operation"], "op1")

    def test_get_filtered_metrics(self):
        """Test getting metrics filtered by operation."""
        log_performance_metric("config_load", 100.0)
        log_performance_metric("profile_switch", 200.0)
        log_performance_metric("config_load", 150.0)

        metrics = get_recent_metrics("config_load")

        self.assertEqual(len(metrics), 2)
        self.assertEqual(metrics[0]["operation"], "config_load")
        self.assertEqual(metrics[0]["duration_ms"], 150.0)
        self.assertEqual(metrics[1]["duration_ms"], 100.0)

    def test_get_metrics_with_limit(self):
        """Test getting metrics with limit."""
        for i in range(10):
            log_performance_metric("test_op", float(i))

        metrics = get_recent_metrics(limit=5)

        self.assertEqual(len(metrics), 5)
        # Most recent 5
        self.assertEqual(metrics[0]["duration_ms"], 9.0)
        self.assertEqual(metrics[4]["duration_ms"], 5.0)

    def test_get_metrics_ignores_non_performance_events(self):
        """Test that only performance_metric events are returned."""
        events_log = Path(".router/runtime/events.log")
        events_log.parent.mkdir(parents=True, exist_ok=True)

        # Write mixed events
        with events_log.open("w") as f:
            f.write(
                json.dumps(
                    {
                        "event": "service_start",
                        "service": "litellm",
                        "timestamp": "2024-01-01T00:00:00Z",
                    }
                )
                + "\n"
            )
            f.write(
                json.dumps(
                    {
                        "event": "performance_metric",
                        "operation": "test_op",
                        "duration_ms": 100.0,
                        "timestamp": "2024-01-01T00:00:01Z",
                    }
                )
                + "\n"
            )

        metrics = get_recent_metrics()

        self.assertEqual(len(metrics), 1)
        self.assertEqual(metrics[0]["operation"], "test_op")

    def test_get_metrics_handles_malformed_lines(self):
        """Test that malformed JSON lines are skipped."""
        events_log = Path(".router/runtime/events.log")
        events_log.parent.mkdir(parents=True, exist_ok=True)

        with events_log.open("w") as f:
            f.write("invalid json\n")
            f.write(
                json.dumps(
                    {
                        "event": "performance_metric",
                        "operation": "test_op",
                        "duration_ms": 100.0,
                        "timestamp": "2024-01-01T00:00:00Z",
                    }
                )
                + "\n"
            )

        metrics = get_recent_metrics()

        self.assertEqual(len(metrics), 1)
        self.assertEqual(metrics[0]["operation"], "test_op")

    def test_get_metrics_handles_read_failure(self):
        """Test that read failures return empty list."""
        with patch("flowgate.observability.Path") as mock_path:
            mock_log = Mock()
            mock_path.return_value = mock_log
            mock_log.exists.return_value = True
            mock_log.open.side_effect = OSError("Permission denied")

            metrics = get_recent_metrics()

            self.assertEqual(metrics, [])


if __name__ == "__main__":
    unittest.main()
