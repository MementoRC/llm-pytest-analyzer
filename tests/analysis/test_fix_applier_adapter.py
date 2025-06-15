#!/usr/bin/env python3
"""
Unit tests for the FixApplierAdapter class.

These tests verify that the adapter:
1. Properly implements the Applier protocol
2. Correctly delegates to the underlying FixApplier
3. Properly handles error scenarios
4. Is correctly resolved from the DI container
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from pytest_analyzer.core.analysis.fix_applier import FixApplicationResult, FixApplier
from pytest_analyzer.core.analysis.fix_applier_adapter import FixApplierAdapter
from pytest_analyzer.core.di.container import Container
from pytest_analyzer.core.di.service_collection import ServiceCollection
from pytest_analyzer.core.errors import FixApplicationError
from pytest_analyzer.core.interfaces.protocols import Applier
from pytest_analyzer.core.models.pytest_failure import FixSuggestion, PytestFailure


class TestFixApplierAdapter:
    """Test suite for the FixApplierAdapter class."""

    def test_implements_applier_protocol(self):
        """Test that FixApplierAdapter implements the Applier protocol."""
        adapter = FixApplierAdapter(fix_applier=MagicMock(spec=FixApplier))
        assert isinstance(adapter, Applier), "Adapter should implement Applier protocol"

    def test_apply_delegates_to_fix_applier(self, tmp_path):
        """Test that apply() delegates to the underlying FixApplier."""
        # Create a mock FixApplier with a mocked apply_fix method
        mock_fix_applier = MagicMock(spec=FixApplier)
        mock_result = FixApplicationResult(
            success=True,
            message="Applied successfully",
            applied_files=[Path("/path/to/file1.py"), Path("/path/to/file2.py")],
            rolled_back_files=[],
        )
        mock_fix_applier.apply_fix.return_value = mock_result

        # Create adapter with our mock
        adapter = FixApplierAdapter(fix_applier=mock_fix_applier)

        # Call the apply method
        changes = {
            "/path/to/file1.py": "new content 1",
            "/path/to/file2.py": "new content 2",
        }
        validation_tests = ["test_module::test_func"]
        result = adapter.apply(changes, validation_tests)

        # Verify the mock was called with the right arguments
        mock_fix_applier.apply_fix.assert_called_once_with(
            code_changes=changes,
            tests_to_validate=validation_tests,
        )

        # Verify the result is the object returned by the mock
        assert result is mock_result

    def test_apply_suggestion(self, tmp_path):
        """Test that apply_suggestion correctly delegates to the FixApplier."""
        # Create a mock FixApplier with a mocked apply_fix_suggestion method
        mock_fix_applier = MagicMock(spec=FixApplier)
        mock_result = FixApplicationResult(
            success=True,
            message="Suggestion applied successfully",
            applied_files=[Path("/path/to/file.py")],
            rolled_back_files=[],
        )
        mock_fix_applier.apply_fix_suggestion.return_value = mock_result

        # Create adapter with our mock
        adapter = FixApplierAdapter(fix_applier=mock_fix_applier)

        # Create a test failure
        failure = PytestFailure(
            test_name="test_module::test_func",
            test_file="/path/to/test_file.py",
            error_type="AssertionError",
            error_message="expected 2 but got 1",
            traceback="Traceback...",
            line_number=42,
        )

        # Create a suggestion with code changes
        suggestion = FixSuggestion(
            failure=failure,
            suggestion="Change x = 1 to x = 2",
            confidence=0.9,
            code_changes={
                "/path/to/file.py": "def func():\n    x = 2  # Fixed\n    return x",
                "source": "LLM",
            },
            explanation="The function was returning 1 instead of 2",
        )

        # Call the apply_suggestion method
        result = adapter.apply_suggestion(suggestion)

        # Verify the mock was called with the right arguments
        mock_fix_applier.apply_fix_suggestion.assert_called_once_with(suggestion)

        # Verify the result is the object returned by the mock
        assert result is mock_result

    def test_apply_suggestion_no_code_changes(self):
        """Test delegation for a suggestion with no code changes."""
        # Create a mock FixApplier
        mock_fix_applier = MagicMock(spec=FixApplier)
        mock_result = FixApplicationResult(
            success=False,
            message="Cannot apply fix: No code changes provided in suggestion.",
            applied_files=[],
            rolled_back_files=[],
        )
        mock_fix_applier.apply_fix_suggestion.return_value = mock_result
        adapter = FixApplierAdapter(fix_applier=mock_fix_applier)

        # Create a suggestion with NO code changes
        suggestion = FixSuggestion(
            failure=MagicMock(),
            suggestion="I can't fix this automatically",
            confidence=0.5,
            code_changes=None,
            explanation="Manual fix needed",
        )

        # Call the apply_suggestion method
        result = adapter.apply_suggestion(suggestion)

        # Verify the result
        assert result.success is False
        assert "No code changes" in result.message

    def test_apply_suggestion_only_metadata(self):
        """Test delegation for a suggestion with only metadata in code_changes."""
        # Create a mock FixApplier
        mock_fix_applier = MagicMock(spec=FixApplier)
        mock_result = FixApplicationResult(
            success=False,
            message="Cannot apply fix: No valid file changes found in suggestion.",
            applied_files=[],
            rolled_back_files=[],
        )
        mock_fix_applier.apply_fix_suggestion.return_value = mock_result
        adapter = FixApplierAdapter(fix_applier=mock_fix_applier)

        # Create a suggestion with ONLY metadata in code_changes
        suggestion = FixSuggestion(
            failure=MagicMock(),
            suggestion="This is just metadata",
            confidence=0.5,
            code_changes={
                "source": "LLM",
                "fingerprint": "123456",
            },
            explanation="No actual file changes",
        )

        # Call the apply_suggestion method
        result = adapter.apply_suggestion(suggestion)

        # Verify the result
        assert result.success is False
        assert "No valid file changes" in result.message

    def test_error_handling(self):
        """Test that errors are properly caught and propagated."""
        # Create a mock FixApplier that raises an exception
        mock_fix_applier = MagicMock(spec=FixApplier)
        mock_fix_applier.apply_fix.side_effect = ValueError("Something went wrong")

        # Create adapter with our mock
        adapter = FixApplierAdapter(fix_applier=mock_fix_applier)

        # Call the apply method and expect a FixApplicationError
        with pytest.raises(FixApplicationError) as excinfo:
            adapter.apply({"file.py": "content"}, ["test"])

        # Verify the error message contains our original exception info
        assert "Something went wrong" in str(excinfo.value)

    def test_show_diff_delegates_to_fix_applier(self, tmp_path):
        """Test that show_diff() delegates to the underlying FixApplier."""
        # Create a test file
        test_file = tmp_path / "test.py"
        test_file.write_text("original content")

        # Create a mock FixApplier with a mocked show_diff method
        mock_fix_applier = MagicMock(spec=FixApplier)
        mock_fix_applier.show_diff.return_value = (
            "--- a/test.py\n+++ b/test.py\n@@ -1 +1 @@\n-original content\n+new content"
        )

        # Create adapter with our mock
        adapter = FixApplierAdapter(fix_applier=mock_fix_applier)

        # Call the show_diff method with both string and Path
        result_str = adapter.show_diff(str(test_file), "new content")
        result_path = adapter.show_diff(test_file, "new content")

        # Verify the mock was called correctly
        assert mock_fix_applier.show_diff.call_count == 2
        mock_fix_applier.show_diff.assert_called_with(test_file, "new content")

        # Verify the result was returned unchanged
        assert "--- a/test.py" in result_str
        assert "--- a/test.py" in result_path

    def test_di_container_registration(self):
        """Test that the adapter is correctly registered and resolved from the DI container."""
        # Create a new container
        container = Container()

        # Register both FixApplier and the adapter
        container.register_singleton(FixApplier, FixApplier)
        container.register_factory(
            Applier,
            lambda: FixApplierAdapter(fix_applier=container.resolve(FixApplier)),
        )

        # Resolve the Applier protocol
        resolved_applier = container.resolve(Applier)

        # Verify the resolved service is our adapter
        assert isinstance(resolved_applier, FixApplierAdapter)
        assert isinstance(resolved_applier, Applier)

    def test_service_collection_registration(self):
        """Test that ServiceCollection correctly sets up the adapter."""
        # Create a service collection
        services = ServiceCollection()

        # Configure services
        services.configure_core_services()

        # Build the container
        container = services.build_container()

        # Resolve the Applier protocol
        resolved_applier = container.resolve(Applier)

        # Verify the resolved service is our adapter
        assert isinstance(resolved_applier, FixApplierAdapter)
        assert isinstance(resolved_applier, Applier)


if __name__ == "__main__":
    pytest.main(["-v", __file__])
