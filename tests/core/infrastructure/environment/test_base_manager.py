"""
Tests for BaseEnvironmentManager abstract class.

This module tests the BaseEnvironmentManager to verify common functionality
and proper abstract class behavior.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from pytest_analyzer.core.infrastructure.environment.base_manager import (
    BaseEnvironmentManager,
)


class ConcreteEnvironmentManager(BaseEnvironmentManager):
    """Concrete implementation for testing purposes."""

    def build_command(self, base_command):
        return ["test", "run"] + base_command

    @classmethod
    def detect(cls, project_path):
        return True


class TestBaseEnvironmentManager:
    """Test cases for BaseEnvironmentManager abstract class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.project_path = Path("/test/project")
        self.manager = ConcreteEnvironmentManager(self.project_path)

    def test_constructor_properly_initializes_project_path(self):
        """Test that constructor properly initializes project_path."""
        assert self.manager.project_path == self.project_path

    def test_constructor_initializes_logger(self):
        """Test that constructor initializes logger with class name."""
        assert self.manager.logger.name == "ConcreteEnvironmentManager"

    @patch("subprocess.call")
    def test_execute_command_calls_subprocess_with_correct_arguments(self, mock_call):
        """Test that execute_command correctly calls subprocess.call with the right arguments."""
        mock_call.return_value = 0
        command = ["pytest", "tests/"]

        result = self.manager.execute_command(command)

        mock_call.assert_called_once_with(command, cwd=self.project_path)
        assert result == 0

    @patch("subprocess.call")
    def test_execute_command_returns_subprocess_exit_code(self, mock_call):
        """Test that execute_command returns the exit code from subprocess.call."""
        mock_call.return_value = 1
        command = ["pytest", "tests/"]

        result = self.manager.execute_command(command)

        assert result == 1

    @patch("subprocess.call")
    def test_execute_command_logs_debug_message(self, mock_call):
        """Test that execute_command logs debug message with command details."""
        mock_call.return_value = 0
        command = ["pytest", "tests/"]

        with patch.object(self.manager.logger, "debug") as mock_debug:
            self.manager.execute_command(command)

            mock_debug.assert_called_once_with("Executing command: pytest tests/")

    def test_activate_does_not_raise_exception(self):
        """Test that default activate method doesn't raise exceptions."""
        # Should not raise any exception
        self.manager.activate()

    def test_activate_logs_debug_message(self):
        """Test that activate logs appropriate debug message."""
        with patch.object(self.manager.logger, "debug") as mock_debug:
            self.manager.activate()

            mock_debug.assert_called_once_with("Environment activation not required")

    def test_deactivate_does_not_raise_exception(self):
        """Test that default deactivate method doesn't raise exceptions."""
        # Should not raise any exception
        self.manager.deactivate()

    def test_deactivate_logs_debug_message(self):
        """Test that deactivate logs appropriate debug message."""
        with patch.object(self.manager.logger, "debug") as mock_debug:
            self.manager.deactivate()

            mock_debug.assert_called_once_with("Environment deactivation not required")

    def test_cannot_instantiate_abstract_class_directly(self):
        """Test that attempting to instantiate the abstract class directly raises TypeError."""
        with pytest.raises(
            TypeError, match="Can't instantiate abstract class BaseEnvironmentManager"
        ):
            BaseEnvironmentManager(self.project_path)

    def test_subclass_without_build_command_raises_type_error(self):
        """Test that subclassing without implementing build_command raises TypeError."""

        class IncompleteManager(BaseEnvironmentManager):
            @classmethod
            def detect(cls, project_path):
                return True

        with pytest.raises(
            TypeError, match="Can't instantiate abstract class IncompleteManager"
        ):
            IncompleteManager(self.project_path)

    def test_subclass_without_detect_raises_type_error(self):
        """Test that subclassing without implementing detect raises TypeError."""

        class IncompleteManager(BaseEnvironmentManager):
            def build_command(self, base_command):
                return base_command

        with pytest.raises(
            TypeError, match="Can't instantiate abstract class IncompleteManager"
        ):
            IncompleteManager(self.project_path)

    def test_concrete_implementation_works_correctly(self):
        """Test that a complete concrete implementation works correctly."""
        # Should not raise any exceptions
        manager = ConcreteEnvironmentManager(self.project_path)

        # Test abstract methods work
        assert manager.build_command(["test"]) == ["test", "run", "test"]
        assert ConcreteEnvironmentManager.detect(self.project_path) is True

    @patch("subprocess.call")
    def test_execute_command_handles_subprocess_exceptions(self, mock_call):
        """Test that execute_command handles subprocess exceptions gracefully."""
        mock_call.side_effect = FileNotFoundError("Command not found")
        command = ["nonexistent", "command"]

        with pytest.raises(FileNotFoundError):
            self.manager.execute_command(command)

    def test_logger_is_properly_configured(self):
        """Test that logger is properly configured and accessible."""
        assert hasattr(self.manager, "logger")
        assert self.manager.logger is not None
        assert isinstance(self.manager.logger, type(self.manager.logger))

    def test_project_path_is_immutable_reference(self):
        """Test that project_path maintains its reference correctly."""
        original_path = self.manager.project_path

        # Verify it's the same reference
        assert self.manager.project_path is original_path
        assert self.manager.project_path == self.project_path
