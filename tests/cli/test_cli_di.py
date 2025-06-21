#!/usr/bin/env python3
"""
Tests for the DI-based analyzer CLI.

These tests verify that:
1. The CLI correctly initializes the DI container
2. Settings are properly configured from arguments
3. The analyzer service is correctly resolved from the container
4. Suggestions are correctly displayed
"""

from unittest.mock import MagicMock, patch

import pytest

from pytest_analyzer.core.di import Container
from pytest_analyzer.core.models.pytest_failure import FixSuggestion, PytestFailure
from pytest_analyzer.utils.settings import Settings


@pytest.fixture
def di_container():
    """Create a clean DI container for testing."""
    return Container()


@pytest.fixture
def di_cli_invoke():
    """Helper fixture to invoke the DI-based CLI."""
    import sys

    from pytest_analyzer.cli.analyzer_cli_di import main

    def _invoke(*args, use_settings: Settings = None):
        # Save original argv
        original_argv = sys.argv.copy()

        try:
            # Set up argv for the CLI
            sys.argv = ["pytest-analyzer-di"] + list(args)

            # Run the CLI
            result = main()

            return result
        finally:
            # Restore original argv
            sys.argv = original_argv

    return _invoke


class TestAnalyzerCLIDI:
    """Test suite for the DI-based analyzer CLI."""

    @pytest.fixture
    def mock_analyzer_service(self):
        """Create a mock analyzer service for testing."""
        from pytest_analyzer.core.analyzer_service_di import DIPytestAnalyzerService

        return MagicMock(spec=DIPytestAnalyzerService)

    def test_cli_analyze_output_file(
        self, di_cli_invoke, mock_analyzer_service, sample_json_report
    ):
        """Test that the CLI correctly analyzes an output file."""
        # Mock the service response
        failure = PytestFailure(
            test_name="test_assertion.py::test_assertion_error",
            test_file="test_assertion.py",
            error_type="AssertionError",
            error_message="assert 1 == 2",
            traceback="E       assert 1 == 2",
            line_number=6,
            relevant_code="assert x == y, 'Values are not equal'",
        )
        suggestion = FixSuggestion(
            failure=failure,
            suggestion="Change the assertion to expect 1 instead of 2",
            confidence=0.9,
            explanation="The test expects 2 but the actual value is 1",
        )
        mock_analyzer_service.analyze_pytest_output.return_value = [suggestion]

        # Invoke the CLI with the sample report
        with patch("pytest_analyzer.cli.analyzer_cli_di.console"):
            with patch(
                "pytest_analyzer.cli.analyzer_cli_di.get_service",
                return_value=mock_analyzer_service,
            ):
                result = di_cli_invoke(f"--output-path={sample_json_report}")

        # Check that service was called
        mock_analyzer_service.analyze_pytest_output.assert_called_once()
        assert sample_json_report.name in str(
            mock_analyzer_service.analyze_pytest_output.call_args[0][0]
        )

        # Check result
        assert result == 0

    def test_cli_run_and_analyze(
        self, di_cli_invoke, mock_analyzer_service, sample_assertion_file
    ):
        """Test that the CLI correctly runs and analyzes tests."""
        # Mock the service response
        failure = PytestFailure(
            test_name="test_assertion.py::test_assertion_error",
            test_file="test_assertion.py",
            error_type="AssertionError",
            error_message="assert 1 == 2",
            traceback="E       assert 1 == 2",
            line_number=6,
            relevant_code="assert x == y, 'Values are not equal'",
        )
        suggestion = FixSuggestion(
            failure=failure,
            suggestion="Change the assertion to expect 1 instead of 2",
            confidence=0.9,
            explanation="The test expects 2 but the actual value is 1",
        )
        mock_analyzer_service.run_and_analyze.return_value = [suggestion]

        # Invoke the CLI with the test file
        with patch("pytest_analyzer.cli.analyzer_cli_di.console"):
            with patch(
                "pytest_analyzer.cli.analyzer_cli_di.get_service",
                return_value=mock_analyzer_service,
            ):
                result = di_cli_invoke(str(sample_assertion_file))

        # Check that service was called
        mock_analyzer_service.run_and_analyze.assert_called_once()
        assert (
            sample_assertion_file.name
            in mock_analyzer_service.run_and_analyze.call_args[0][0]
        )

        # Check result
        assert result == 0

    def test_cli_settings_configuration(self, di_cli_invoke):
        """Test that the CLI correctly configures settings from arguments."""
        # Create a Settings object that we'll capture
        captured_settings = None

        # Define a function to capture the settings
        def mock_initialize_container(settings=None):
            nonlocal captured_settings
            captured_settings = settings
            # Return a mock container
            mock_container = MagicMock()
            mock_service = MagicMock()
            mock_service.run_and_analyze.return_value = []
            mock_container.resolve.return_value = mock_service
            return mock_container

        # Invoke CLI with various settings
        with patch("pytest_analyzer.cli.analyzer_cli_di.console"):
            with patch("pytest_analyzer.cli.analyzer_cli_di.display_suggestions"):
                with patch(
                    "pytest_analyzer.cli.analyzer_cli_di.initialize_container",
                    side_effect=mock_initialize_container,
                ):
                    di_cli_invoke(
                        "test_path",
                        "--use-llm",
                        "--max-suggestions=5",
                        "--min-confidence=0.7",
                        "--auto-apply",
                        "--llm-provider=anthropic",
                        "--llm-model=claude-3-opus-20240229",
                        "--llm-timeout=120",
                        "--preferred-format=json",
                        "--debug",
                    )

        # Check that settings were captured and configured correctly
        assert captured_settings is not None
        assert captured_settings.use_llm is True
        assert captured_settings.max_suggestions == 5
        assert captured_settings.min_confidence == 0.7
        assert captured_settings.auto_apply is True
        assert captured_settings.llm_provider == "anthropic"
        assert captured_settings.llm_model == "claude-3-opus-20240229"
        assert captured_settings.llm_timeout == 120
        assert captured_settings.preferred_format == "json"
        assert captured_settings.debug is True  # debug flag sets debug mode

    def test_cli_error_handling(self, di_cli_invoke, mock_analyzer_service):
        """Test that the CLI correctly handles errors."""
        # Make the service raise an exception
        test_exception = Exception("Test error")
        mock_analyzer_service.run_and_analyze.side_effect = test_exception

        # Invoke the CLI
        with patch("pytest_analyzer.cli.analyzer_cli_di.console"):
            with patch("logging.Logger.error") as mock_error:
                with patch(
                    "pytest_analyzer.cli.analyzer_cli_di.get_service",
                    return_value=mock_analyzer_service,
                ):
                    result = di_cli_invoke("test_path")

        # Check that error was logged and non-zero exit code returned
        mock_error.assert_called_with("An error occurred: %s", test_exception)
        assert result != 0


if __name__ == "__main__":
    pytest.main(["-v", __file__])
