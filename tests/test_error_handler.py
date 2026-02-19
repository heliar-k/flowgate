"""
Tests for unified exception handling decorator.
"""
from __future__ import annotations

import io
import logging
import sys
import unittest
from argparse import Namespace
from unittest.mock import MagicMock, patch

from flowgate.cli.commands.base import BaseCommand
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

    def test_decorator_with_command_class(self):
        """Test that decorator works with BaseCommand subclass methods."""
        class TestCommand(BaseCommand):
            @handle_command_errors
            def execute(self) -> int:
                if hasattr(self.args, "fail"):
                    raise ConfigError("Command failed")
                return EXIT_SUCCESS

        # Test successful case
        args = Namespace()
        config = {}
        cmd = TestCommand(args, config)
        result = cmd.execute()
        self.assertEqual(result, EXIT_SUCCESS)

        # Test error case
        args_fail = Namespace(fail=True)
        cmd_fail = TestCommand(args_fail, config)
        with patch("sys.stderr", new_callable=io.StringIO):
            result = cmd_fail.execute()
        self.assertEqual(result, EXIT_CONFIG_ERROR)

    def test_decorator_with_instance_method(self):
        """Test that decorator works with instance methods."""
        class CommandHandler:
            def __init__(self, should_fail: bool):
                self.should_fail = should_fail

            @handle_command_errors
            def run(self) -> int:
                if self.should_fail:
                    raise ProcessError("Handler failed")
                return EXIT_SUCCESS

        # Test successful case
        handler = CommandHandler(should_fail=False)
        result = handler.run()
        self.assertEqual(result, EXIT_SUCCESS)

        # Test error case
        handler_fail = CommandHandler(should_fail=True)
        with patch("sys.stderr", new_callable=io.StringIO):
            result = handler_fail.run()
        self.assertEqual(result, EXIT_RUNTIME_ERROR)

    def test_exception_chaining_preserves_original(self):
        """Test that exception chaining preserves original exception context."""
        @handle_command_errors
        def command_with_chained_error():
            try:
                # Simulate an underlying error
                raise ValueError("Original error")
            except ValueError as e:
                raise ConfigError("Configuration failed") from e

        with patch("sys.stderr", new_callable=io.StringIO) as mock_stderr:
            result = command_with_chained_error()

        self.assertEqual(result, EXIT_CONFIG_ERROR)
        stderr_output = mock_stderr.getvalue()
        self.assertIn("Configuration failed", stderr_output)

    def test_logging_for_config_error(self):
        """Test that logger.error() is called for ConfigError."""
        @handle_command_errors
        def command_with_config_error():
            raise ConfigError("Config issue")

        with patch("flowgate.cli.error_handler.logger") as mock_logger:
            with patch("sys.stderr", new_callable=io.StringIO):
                result = command_with_config_error()

        self.assertEqual(result, EXIT_CONFIG_ERROR)
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args
        self.assertIn("Configuration error", call_args[0][0])
        self.assertIn("Config issue", str(call_args[0][1]))

    def test_logging_for_process_error_with_traceback(self):
        """Test that logger.error(exc_info=True) is called for ProcessError."""
        @handle_command_errors
        def command_with_process_error():
            raise ProcessError("Process failed")

        with patch("flowgate.cli.error_handler.logger") as mock_logger:
            with patch("sys.stderr", new_callable=io.StringIO):
                result = command_with_process_error()

        self.assertEqual(result, EXIT_RUNTIME_ERROR)
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args
        self.assertIn("Process operation failed", call_args[0][0])
        self.assertTrue(call_args[1].get("exc_info"))

    def test_logging_for_permission_error(self):
        """Test that logger.error() is called for PermissionError."""
        @handle_command_errors
        def command_with_permission_error():
            raise PermissionError("Access denied")

        with patch("flowgate.cli.error_handler.logger") as mock_logger:
            with patch("sys.stderr", new_callable=io.StringIO):
                result = command_with_permission_error()

        self.assertEqual(result, EXIT_PERMISSION_ERROR)
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args
        self.assertIn("Permission denied", call_args[0][0])

    def test_logging_for_generic_exception(self):
        """Test that logger.exception() is called for generic Exception."""
        @handle_command_errors
        def command_with_generic_error():
            raise RuntimeError("Unexpected error")

        with patch("flowgate.cli.error_handler.logger") as mock_logger:
            with patch("sys.stderr", new_callable=io.StringIO):
                result = command_with_generic_error()

        self.assertEqual(result, EXIT_INTERNAL_ERROR)
        mock_logger.exception.assert_called_once()
        call_args = mock_logger.exception.call_args
        self.assertIn("Internal error", call_args[0][0])

    def test_non_zero_return_without_exception(self):
        """Test that non-zero return codes pass through without exception."""
        @handle_command_errors
        def command_with_error_code():
            # Simulate a command that returns error code without raising
            return 5

        result = command_with_error_code()
        self.assertEqual(result, 5)

    def test_exception_with_empty_message(self):
        """Test that exceptions with empty messages are handled gracefully."""
        @handle_command_errors
        def command_with_empty_message():
            raise ConfigError("")

        with patch("sys.stderr", new_callable=io.StringIO) as mock_stderr:
            result = command_with_empty_message()

        self.assertEqual(result, EXIT_CONFIG_ERROR)
        stderr_output = mock_stderr.getvalue()
        self.assertIn("❌ Configuration error:", stderr_output)

    def test_decorator_with_multiple_arguments(self):
        """Test that decorator works with functions having multiple arguments."""
        @handle_command_errors
        def command_with_many_args(a: int, b: str, c: bool = True, d: list = None):
            if d is None:
                d = []
            if not c:
                raise ProcessError(f"Failed with {a}, {b}, {len(d)}")
            return EXIT_SUCCESS

        # Test successful case
        result = command_with_many_args(1, "test", True, [1, 2, 3])
        self.assertEqual(result, EXIT_SUCCESS)

        # Test error case
        with patch("sys.stderr", new_callable=io.StringIO):
            result = command_with_many_args(42, "error", False, [])
        self.assertEqual(result, EXIT_RUNTIME_ERROR)

    def test_integration_with_command_execution_flow(self):
        """Test decorator in realistic command execution scenario."""
        class ProfileCommand(BaseCommand):
            @handle_command_errors
            def execute(self) -> int:
                # Simulate profile validation
                profile_name = getattr(self.args, "profile", None)
                if not profile_name:
                    raise ConfigError("Profile name is required")

                # Simulate profile not found
                profiles = self.config.get("profiles", {})
                if profile_name not in profiles:
                    raise ConfigError(f"Profile '{profile_name}' not found")

                return EXIT_SUCCESS

        # Test missing profile name
        args = Namespace(profile=None)
        config = {"profiles": {"balanced": {}, "reliability": {}}}
        cmd = ProfileCommand(args, config)

        with patch("sys.stderr", new_callable=io.StringIO) as mock_stderr:
            result = cmd.execute()

        self.assertEqual(result, EXIT_CONFIG_ERROR)
        self.assertIn("Profile name is required", mock_stderr.getvalue())

        # Test profile not found
        args = Namespace(profile="nonexistent")
        cmd = ProfileCommand(args, config)

        with patch("sys.stderr", new_callable=io.StringIO) as mock_stderr:
            result = cmd.execute()

        self.assertEqual(result, EXIT_CONFIG_ERROR)
        self.assertIn("Profile 'nonexistent' not found", mock_stderr.getvalue())

        # Test successful case
        args = Namespace(profile="balanced")
        cmd = ProfileCommand(args, config)
        result = cmd.execute()
        self.assertEqual(result, EXIT_SUCCESS)


if __name__ == "__main__":
    unittest.main()
