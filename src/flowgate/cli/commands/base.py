"""
Base command class for FlowGate CLI commands.

This module contains the BaseCommand abstract class that
all command handlers will inherit from.
"""
from __future__ import annotations

from argparse import Namespace
from typing import Any


class BaseCommand:
    """Base class for CLI commands, providing unified command interface."""

    def __init__(self, args: Namespace, config: dict[str, Any]):
        """
        Initialize the command with arguments and configuration.

        Args:
            args: Parsed command-line arguments
            config: Router configuration dictionary
        """
        self.args = args
        self.config = config

    def execute(self) -> int:
        """
        Execute the command.

        Returns:
            Exit code: 0 for success, non-zero for failure

        Raises:
            NotImplementedError: Must be implemented by subclasses
        """
        raise NotImplementedError

    def validate_config(self) -> None:
        """
        Validate command-specific configuration requirements.

        Subclasses can override this method to perform custom validation.
        The default implementation is a no-op.
        """
        pass
