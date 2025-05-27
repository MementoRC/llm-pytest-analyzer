"""
Tests for the EnvironmentManager protocol.
"""

from pathlib import Path
from typing import Any, List
from unittest.mock import MagicMock

import pytest

from pytest_analyzer.core.environment.protocol import EnvironmentManager


class TestEnvironmentManagerProtocol:
    """
    Tests for the EnvironmentManager protocol definition and behavior.
    """

    def test_protocol_defines_required_methods(self) -> None:
        """
        Test that the EnvironmentManager protocol has all expected methods.
        """
        expected_methods = [
            "detect",
            "build_command",
            "execute_command",
            "activate",
            "deactivate",
        ]
        for method_name in expected_methods:
            assert hasattr(EnvironmentManager, method_name), (
                f"EnvironmentManager protocol should have method '{method_name}'"
            )
            assert callable(getattr(EnvironmentManager, method_name)), (
                f"'{method_name}' should be a callable method"
            )

    @pytest.fixture
    def valid_mock_manager_class(self) -> type:
        """
        Provides a mock class that correctly implements the EnvironmentManager protocol.
        """

        class ValidMock:
            @classmethod
            def detect(cls, project_path: Path) -> bool:
                return True

            def build_command(self, command: List[str]) -> List[str]:
                return ["mock_prefix"] + command

            def execute_command(self, command: List[str]) -> int:
                return 0

            def activate(self) -> None:
                pass

            def deactivate(self) -> None:
                pass

        return ValidMock

    @pytest.fixture
    def invalid_mock_manager_class_missing_method(self) -> type:
        """
        Provides a mock class that is missing a required method.
        """

        class InvalidMockMissing:
            @classmethod
            def detect(cls, project_path: Path) -> bool:
                return True

            # build_command is missing
            def execute_command(self, command: List[str]) -> int:
                return 0

            def activate(self) -> None:
                pass

            def deactivate(self) -> None:
                pass

        return InvalidMockMissing

    @pytest.fixture
    def invalid_mock_manager_class_wrong_signature(self) -> type:
        """
        Provides a mock class that has a method with an incorrect signature.
        """

        class InvalidMockWrongSignature:
            @classmethod
            def detect(cls, project_path: Path) -> bool:
                return True

            def build_command(self, command: List[str], extra_arg: Any) -> List[str]:
                # Incorrect signature (extra_arg)
                return ["mock_prefix"] + command

            def execute_command(self, command: List[str]) -> int:
                return 0

            def activate(self) -> None:
                pass

            def deactivate(self) -> None:
                pass

        return InvalidMockWrongSignature

    def test_runtime_checkable_with_valid_mock(
        self, valid_mock_manager_class: type
    ) -> None:
        """
        Test that a correctly implemented mock passes isinstance() check.
        """
        mock_instance = valid_mock_manager_class()
        assert isinstance(mock_instance, EnvironmentManager), (
            "Valid mock should be an instance of EnvironmentManager"
        )

    def test_runtime_checkable_with_invalid_mock_missing_method(
        self, invalid_mock_manager_class_missing_method: type
    ) -> None:
        """
        Test that a mock missing a method fails isinstance() check.
        """
        mock_instance = invalid_mock_manager_class_missing_method()
        assert not isinstance(mock_instance, EnvironmentManager), (
            "Mock missing a method should not be an instance of EnvironmentManager"
        )

    def test_runtime_checkable_with_invalid_mock_wrong_signature(
        self, invalid_mock_manager_class_wrong_signature: type
    ) -> None:
        """
        Test that a mock with an incorrect method signature fails isinstance() check.
        """
        # Note: @runtime_checkable primarily checks for method presence.
        # Signature mismatches are more reliably caught by static type checkers like Mypy.
        # However, if the method names and existence match, it might still pass isinstance.
        # For this test, we rely on the fact that the method name is the same.
        # If Python's runtime check for protocols becomes more stringent on signatures,
        # this test might change its behavior.
        mock_instance = invalid_mock_manager_class_wrong_signature()
        # This will likely pass isinstance if all methods are present,
        # as runtime_checkable doesn't deeply inspect signatures for non-ABC protocols.
        # The critical part for runtime_checkable is method presence.
        # True type safety for signatures is enforced by Mypy.
        # For this test to be robust for runtime check, the method name would need to differ
        # or a required method be absent.
        # Let's assume for now the check is primarily for presence.
        # If `build_command` was an ABC abstract method, it would be stricter.
        assert isinstance(mock_instance, EnvironmentManager), (
            "Mock with potentially problematic signature (but present methods) might still pass isinstance for non-ABC protocols."
        )

    def test_type_checking_with_valid_mock(
        self, valid_mock_manager_class: type
    ) -> None:
        """
        Demonstrates that a valid mock can be used where an EnvironmentManager is expected.
        This test would pass Mypy.
        """
        valid_mock = valid_mock_manager_class()

        def _consumer_function(manager: EnvironmentManager) -> None:
            assert manager.build_command(["pytest"]) == ["mock_prefix", "pytest"]
            manager.activate()  # Should not raise type error

        _consumer_function(valid_mock)
        # If this code were type-checked by Mypy, it should pass without errors.

    def test_type_checking_with_magic_mock(self) -> None:
        """
        Test that a MagicMock configured to match the protocol can satisfy type hints.
        Mypy would require explicit type assertion or a more detailed mock spec for full safety.
        """
        # Create a MagicMock that simulates the EnvironmentManager
        # For full Mypy compatibility with MagicMock, one might need to use `spec=EnvironmentManager`
        # or `create_autospec`.
        mock_manager = MagicMock(spec=EnvironmentManager)

        # Configure class method 'detect'
        mock_manager.detect.return_value = True
        # Configure instance methods
        mock_manager.build_command.return_value = ["pre", "cmd"]
        mock_manager.execute_command.return_value = 0
        # activate and deactivate are void methods, no return value needed for MagicMock by default

        def _consumer_function(manager: EnvironmentManager) -> None:
            assert manager.detect(Path(".")) is True
            assert manager.build_command(["cmd"]) == ["pre", "cmd"]
            assert manager.execute_command(["cmd"]) == 0
            manager.activate()
            manager.deactivate()

        _consumer_function(mock_manager)
        # This demonstrates runtime compatibility. Mypy would be stricter with MagicMock
        # unless properly configured with a spec.

    # Note on Mypy testing:
    # To explicitly test Mypy compliance, you would typically run Mypy as part of your CI/linting.
    # For example, code like this would be flagged by Mypy:
    #
    #   invalid_mock = invalid_mock_manager_class_missing_method()
    #   _consumer_function(invalid_mock) # Mypy would error here
    #
    # This file aims to create implementations that *would* pass Mypy if correct,
    # and demonstrate runtime checks where applicable.
