"""
Tests for BaseCommand abstract base class.
"""
import sys
import unittest
from argparse import Namespace
from pathlib import Path

# Direct import to avoid triggering flowgate.__init__ during transition
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Import the module directly without going through flowgate package
import importlib.util
spec = importlib.util.spec_from_file_location(
    "base",
    Path(__file__).parent.parent / "src" / "flowgate" / "cli" / "commands" / "base.py"
)
base_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base_module)
BaseCommand = base_module.BaseCommand


class ConcreteCommand(BaseCommand):
    """Concrete implementation for testing."""

    def execute(self) -> int:
        """Execute the command."""
        return 0


class TestBaseCommand(unittest.TestCase):
    """Test suite for BaseCommand base class."""

    def test_base_command_instantiation(self):
        """Test that BaseCommand can be instantiated with args and config."""
        args = Namespace(command="test")
        config = {"test": "value"}

        cmd = ConcreteCommand(args, config)

        self.assertEqual(cmd.args, args)
        self.assertEqual(cmd.config, config)

    def test_execute_not_implemented(self):
        """Test that BaseCommand.execute raises NotImplementedError."""
        args = Namespace(command="test")
        config = {}

        cmd = BaseCommand(args, config)

        with self.assertRaises(NotImplementedError):
            cmd.execute()

    def test_validate_config_default_implementation(self):
        """Test that validate_config has a default no-op implementation."""
        args = Namespace(command="test")
        config = {}

        cmd = ConcreteCommand(args, config)

        # Should not raise any exception
        result = cmd.validate_config()
        self.assertIsNone(result)

    def test_concrete_command_execute(self):
        """Test that concrete command can override execute."""
        args = Namespace(command="test")
        config = {}

        cmd = ConcreteCommand(args, config)
        exit_code = cmd.execute()

        self.assertEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
