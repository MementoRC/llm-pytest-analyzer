"""Tests for the backward compatibility module."""

import warnings
from unittest.mock import patch

import pytest

from pytest_analyzer.core.analyzer_facade import PytestAnalyzerFacade
from pytest_analyzer.core.backward_compat import PytestAnalyzerService
from pytest_analyzer.utils.settings import Settings


class TestBackwardCompat:
    """Tests for the backward compatibility module."""

    def test_deprecation_warning(self):
        """Test that initializing the legacy class name shows a deprecation warning."""
        # Use pytest's warning recorder to check for the warning
        with pytest.warns(DeprecationWarning) as recorded_warnings:
            service = PytestAnalyzerService(settings=Settings())

        # Verify the warning was issued
        assert len(recorded_warnings) == 1
        assert "deprecated" in str(recorded_warnings[0].message).lower()
        assert "Use PytestAnalyzerFacade instead" in str(recorded_warnings[0].message)

        # Verify that it's still a fully functional facade
        assert isinstance(service, PytestAnalyzerFacade)

    @patch("pytest_analyzer.core.analyzer_state_machine.AnalyzerStateMachine")
    def test_facade_functions_work_through_legacy_class(self, mock_state_machine_class):
        """Test that all the facade methods work through the legacy class."""
        # Setup mock state machine
        mock_state_machine = mock_state_machine_class.return_value
        mock_state_machine.run.return_value = {
            "suggestions": ["mock_suggestion"],
            "extraction_results": {"failures": ["mock_failure"]},
        }

        # Create the legacy service and suppress the warning
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            service = PytestAnalyzerService(settings=Settings())

        # Mock the path existence check
        with patch("pathlib.Path.exists", return_value=True):
            # Call all the methods to ensure they work through the legacy class
            suggestions = service.analyze_pytest_output("fake_output.json")
            assert suggestions == ["mock_suggestion"]

            failures = service.run_pytest_only("test_path")
            assert failures == ["mock_failure"]

            suggestions = service.run_and_analyze("test_path")
            assert suggestions == ["mock_suggestion"]
