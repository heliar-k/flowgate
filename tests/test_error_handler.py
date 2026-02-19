"""
Tests for unified exception handling decorator.
"""
from __future__ import annotations

import io
import sys
import unittest
from unittest.mock import patch

from flowgate.cli.error_handler import (
    EXIT_CONFIG_ERROR,
    EXIT_INTERNAL_ERROR,
    EXIT_PERMISSION_ERROR,
    EXIT_RUNTIME_ERROR,
    EXIT_SUCCESS,
    ProcessError,
    handle_command_errors,
)
from flowgate.config import ConfigError


class TestErrorHandler(unittest.TestCase):
    """Test cases for error handler decorator."""

    def test_success_case(self):
        """Test that successful execution returns EXIT_SUCCESS."""
        @handle_command_errors
        def successful_command():
            return EXIT_SUCCESS

        result = successful_command()
        self.assertEqual(result, EXIT_SUCCESS)

    def test_config_error_handling(self):
        """Test that ConfigError returns EXIT_CONFIG_ERROR."""
        @handle_command_errors
        def command_with_config_error():
            raise ConfigError("Invalid configuration")

        with patch("sys.stderr", new_callable=io.StringIO) as mock_stderr:
            result = command_with_config_error()

        self.assertEqual(result, EXIT_CONFIG_ERROR)
        stderr_output = mock_stderr.getvalue()
        self.assertIn("❌ Configuration error:", stderr_output)
        self.assertIn("Invalid configuration", stderr_output)

    def test_process_error_handling(self):
        """Test that ProcessError returns EXIT_RUNTIME_ERROR."""
        @handle_command_errors
        def command_with_process_error():
            raise ProcessError("Failed to start service")

        with patch("sys.stderr", new_callable=io.StringIO) as mock_stderr:
            result = command_with_process_error()

        self.assertEqual(result, EXIT_RUNTIME_ERROR)
        stderr_output = mock_stderr.getvalue()
        self.assertIn("❌ Process operation failed:", stderr_output)
        self.assertIn("Failed to start service", stderr_output)

    def test_permission_error_handling(self):
        """Test that PermissionError returns EXIT_PERMISSION_ERROR."""
        @handle_command_errors
        def command_with_permission_error():
            raise PermissionError("Access denied to file")

        with patch("sys.stderr", new_callable=io.StringIO) as mock_stderr:
            result = command_with_permission_error()

        self.assertEqual(result, EXIT_PERMISSION_ERROR)
        stderr_output = mock_stderr.getvalue()
        self.assertIn("❌ Permission denied:", stderr_output)
        self.assertIn("Access denied to file", stderr_output)

    def test_generic_exception_handling(self):
        """Test that generic Exception returns EXIT_INTERNAL_ERROR."""
        @handle_command_errors
        def command_with_generic_error():
            raise ValueError("Unexpected error")

        with patch("sys.stderr", new_callable=io.StringIO) as mock_stderr:
            result = command_with_generic_error()

        self.assertEqual(result, EXIT_INTERNAL_ERROR)
        stderr_output = mock_stderr.getvalue()
        self.assertIn("❌ Internal error:", stderr_output)
        self.assertIn("Unexpected error", stderr_output)
        self.assertIn("Please use --debug for more details", stderr_output)

    def test_decorator_preserves_function_metadata(self):
        """Test that decorator preserves original function metadata."""
        @handle_command_errors
        def example_command():
            """Example command docstring."""
            return EXIT_SUCCESS

        self.assertEqual(example_command.__name__, "example_command")
        self.assertEqual(example_command.__doc__, "Example command docstring.")

    def test_decorator_with_arguments(self):
        """Test that decorator works with functions that take arguments."""
        @handle_command_errors
        def command_with_args(value: int, flag: bool = False):
            if flag:
                raise ConfigError("Flag was set")
            return value

        # Test successful case
        result = command_with_args(42, flag=False)
        self.assertEqual(result, 42)

        # Test error case
        with patch("sys.stderr", new_callable=io.StringIO):
            result = command_with_args(42, flag=True)
        self.assertEqual(result, EXIT_CONFIG_ERROR)


if __name__ == "__main__":
    unittest.main()
