import logging
from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from pytest_analyzer.core.application.services.analyzer_service import AnalyzerService
from pytest_analyzer.core.domain.entities.fix_suggestion import FixSuggestion
from pytest_analyzer.core.domain.entities.pytest_failure import PytestFailure
from pytest_analyzer.core.domain.value_objects.failure_type import FailureType


@pytest.fixture
def mock_repository():
    """Fixture for a mock TestResultRepository."""
    return MagicMock()


@pytest.fixture
def mock_analyzer():
    """Fixture for a mock FailureAnalyzer."""
    return MagicMock()


@pytest.fixture
def mock_suggester():
    """Fixture for a mock FixSuggester."""
    return MagicMock()


@pytest.fixture
def analyzer_service(mock_repository, mock_analyzer, mock_suggester):
    """Fixture for an AnalyzerService instance with mock dependencies."""
    return AnalyzerService(
        repository=mock_repository, analyzer=mock_analyzer, suggester=mock_suggester
    )


@pytest.fixture
def sample_failure1() -> PytestFailure:
    """A sample PytestFailure instance."""
    return PytestFailure.create(
        test_name="test_example_one",
        file_path=Path("tests/test_example.py"),
        failure_message="AssertionError: expected True but got False",
        error_type="AssertionError",
        line_number=10,
        function_name="test_example_one",
    )


@pytest.fixture
def sample_failure2() -> PytestFailure:
    """Another sample PytestFailure instance."""
    return PytestFailure.create(
        test_name="test_example_two",
        file_path=Path("tests/test_another.py"),
        failure_message="ValueError: invalid literal for int() with base 10: 'abc'",
        error_type="ValueError",
        line_number=20,
        function_name="test_example_two",
    )


@pytest.fixture
def sample_suggestion1(sample_failure1: PytestFailure) -> FixSuggestion:
    """A sample FixSuggestion instance."""
    return FixSuggestion.create(
        failure_id=sample_failure1.id,
        suggestion_text="Fix for failure 1",
        explanation="Explanation for fix 1",
    )


@pytest.fixture
def sample_suggestion2(sample_failure2: PytestFailure) -> FixSuggestion:
    """Another sample FixSuggestion instance."""
    return FixSuggestion.create(
        failure_id=sample_failure2.id,
        suggestion_text="Fix for failure 2",
        explanation="Explanation for fix 2",
    )


class TestAnalyzerService:
    """Test suite for the AnalyzerService."""

    def test_analyze_report_success(
        self,
        analyzer_service: AnalyzerService,
        mock_repository: MagicMock,
        mock_analyzer: MagicMock,
        mock_suggester: MagicMock,
        sample_failure1: PytestFailure,
        sample_suggestion1: FixSuggestion,
        caplog,
    ):
        """Test analyze_report successfully processes failures and returns suggestions."""
        mock_repository.get_failures.return_value = [sample_failure1]
        mock_analyzer.analyze.return_value = {"analysis_key": "analysis_value"}
        mock_suggester.suggest.return_value = sample_suggestion1
        report_path = Path("dummy_report.json")

        caplog.set_level(
            logging.INFO,
            logger="pytest_analyzer.core.application.services.analyzer_service",
        )
        suggestions = analyzer_service.analyze_report(report_path)

        assert len(suggestions) == 1
        assert suggestions[0] == sample_suggestion1
        mock_repository.get_failures.assert_called_once_with(report_path)
        mock_analyzer.analyze.assert_called_once_with(sample_failure1)
        mock_suggester.suggest.assert_called_once_with(
            sample_failure1, {"analysis_key": "analysis_value"}
        )
        mock_repository.save_suggestions.assert_not_called()
        assert f"Starting analysis of report: {report_path}" in caplog.text
        assert "Loaded 1 failures from report." in caplog.text
        assert (
            f"Generated suggestion for failure ID: {sample_failure1.id}" in caplog.text
        )
        assert (
            f"Analysis of report {report_path} completed. Generated 1 suggestions."
            in caplog.text
        )

    def test_analyze_report_saves_suggestions(
        self,
        analyzer_service: AnalyzerService,
        mock_repository: MagicMock,
        mock_analyzer: MagicMock,
        mock_suggester: MagicMock,
        sample_failure1: PytestFailure,
        sample_suggestion1: FixSuggestion,
        tmp_path: Path,
        caplog,
    ):
        """Test analyze_report saves suggestions when output_path is provided."""
        mock_repository.get_failures.return_value = [sample_failure1]
        mock_analyzer.analyze.return_value = {}
        mock_suggester.suggest.return_value = sample_suggestion1
        report_path = Path("dummy_report.json")
        output_path = tmp_path / "suggestions.json"

        caplog.set_level(
            logging.INFO,
            logger="pytest_analyzer.core.application.services.analyzer_service",
        )
        suggestions = analyzer_service.analyze_report(report_path, output_path)

        assert len(suggestions) == 1
        assert suggestions[0] == sample_suggestion1
        mock_repository.save_suggestions.assert_called_once_with(
            [sample_suggestion1], output_path
        )
        assert f"Successfully saved 1 suggestions to {output_path}" in caplog.text

    def test_analyze_report_no_failures(
        self,
        analyzer_service: AnalyzerService,
        mock_repository: MagicMock,
        mock_analyzer: MagicMock,
        mock_suggester: MagicMock,
        caplog,
    ):
        """Test analyze_report handles an empty failure list."""
        mock_repository.get_failures.return_value = []
        report_path = Path("empty_report.json")

        caplog.set_level(
            logging.INFO,
            logger="pytest_analyzer.core.application.services.analyzer_service",
        )
        suggestions = analyzer_service.analyze_report(report_path)

        assert len(suggestions) == 0
        mock_analyzer.analyze.assert_not_called()
        mock_suggester.suggest.assert_not_called()
        assert "No failures found in the report." in caplog.text

    def test_analyze_report_repository_file_not_found_error(
        self, analyzer_service: AnalyzerService, mock_repository: MagicMock, caplog
    ):
        """Test analyze_report handles FileNotFoundError from repository."""
        report_path = Path("non_existent_report.json")
        mock_repository.get_failures.side_effect = FileNotFoundError(
            "File not found: {report_path}"
        )

        caplog.set_level(
            logging.ERROR,
            logger="pytest_analyzer.core.application.services.analyzer_service",
        )
        with pytest.raises(FileNotFoundError):
            analyzer_service.analyze_report(report_path)

        assert f"Report file not found: {report_path}" in caplog.text

    def test_analyze_report_repository_generic_error_on_load(
        self, analyzer_service: AnalyzerService, mock_repository: MagicMock, caplog
    ):
        """Test analyze_report handles generic Exception from repository on load."""
        report_path = Path("error_report.json")
        mock_repository.get_failures.side_effect = Exception("Generic load error")

        caplog.set_level(
            logging.ERROR,
            logger="pytest_analyzer.core.application.services.analyzer_service",
        )
        with pytest.raises(Exception, match="Generic load error"):
            analyzer_service.analyze_report(report_path)

        assert (
            f"Error loading failures from report {report_path}: Generic load error"
            in caplog.text
        )

    def test_analyze_report_repository_error_on_save(
        self,
        analyzer_service: AnalyzerService,
        mock_repository: MagicMock,
        mock_analyzer: MagicMock,
        mock_suggester: MagicMock,
        sample_failure1: PytestFailure,
        sample_suggestion1: FixSuggestion,
        tmp_path: Path,
        caplog,
    ):
        """Test analyze_report handles repository errors during save_suggestions but still returns suggestions."""
        mock_repository.get_failures.return_value = [sample_failure1]
        mock_analyzer.analyze.return_value = {}
        mock_suggester.suggest.return_value = sample_suggestion1
        mock_repository.save_suggestions.side_effect = Exception("Save failed")

        report_path = Path("dummy_report.json")
        output_path = tmp_path / "suggestions.json"

        caplog.set_level(
            logging.ERROR,
            logger="pytest_analyzer.core.application.services.analyzer_service",
        )
        suggestions = analyzer_service.analyze_report(report_path, output_path)

        assert len(suggestions) == 1  # Still returns suggestions
        assert suggestions[0] == sample_suggestion1
        mock_repository.save_suggestions.assert_called_once_with(
            [sample_suggestion1], output_path
        )
        assert (
            f"Failed to save suggestions to {output_path}: Save failed" in caplog.text
        )

    def test_analyze_report_mixed_success_and_fallback(
        self,
        analyzer_service: AnalyzerService,
        mock_repository: MagicMock,
        mock_analyzer: MagicMock,
        mock_suggester: MagicMock,
        sample_failure1: PytestFailure,
        sample_failure2: PytestFailure,
        sample_suggestion1: FixSuggestion,
        caplog,
    ):
        """Test analyze_report processes multiple failures, some succeeding, some creating fallbacks."""
        mock_repository.get_failures.return_value = [sample_failure1, sample_failure2]

        # First failure succeeds
        mock_analyzer.analyze.side_effect = [
            {"analysis_key": "value"},  # For sample_failure1
            Exception("Analyzer error for failure 2"),  # For sample_failure2
        ]
        mock_suggester.suggest.return_value = (
            sample_suggestion1  # Only called for sample_failure1
        )

        report_path = Path("mixed_report.json")

        caplog.set_level(
            logging.INFO,
            logger="pytest_analyzer.core.application.services.analyzer_service",
        )  # INFO will capture WARNING too
        suggestions = analyzer_service.analyze_report(report_path)

        assert len(suggestions) == 2

        # Check first suggestion (successful)
        assert suggestions[0] == sample_suggestion1

        # Check second suggestion (fallback)
        fallback_suggestion = suggestions[1]
        assert fallback_suggestion.failure_id == sample_failure2.id
        assert "Automated suggestion failed." in fallback_suggestion.suggestion_text
        assert "An unexpected error occurred" in fallback_suggestion.explanation
        assert "Analyzer error for failure 2" in fallback_suggestion.explanation

        mock_analyzer.analyze.call_count == 2
        mock_suggester.suggest.assert_called_once_with(
            sample_failure1, {"analysis_key": "value"}
        )

        assert (
            f"Generated suggestion for failure ID: {sample_failure1.id}" in caplog.text
        )
        assert (
            f"Error during analysis or suggestion for failure ID {sample_failure2.id}"
            in caplog.text
        )
        assert (
            f"Created fallback suggestion for failure ID: {sample_failure2.id}"
            in caplog.text
        )

    def test_analyze_single_failure_success(
        self,
        analyzer_service: AnalyzerService,
        mock_analyzer: MagicMock,
        mock_suggester: MagicMock,
        sample_failure1: PytestFailure,
        sample_suggestion1: FixSuggestion,
        caplog,
    ):
        """Test analyze_single_failure successfully analyzes and suggests."""
        analysis_result = {"detail": "some analysis"}
        mock_analyzer.analyze.return_value = analysis_result
        mock_suggester.suggest.return_value = sample_suggestion1

        caplog.set_level(
            logging.INFO,
            logger="pytest_analyzer.core.application.services.analyzer_service",
        )
        suggestion = analyzer_service.analyze_single_failure(sample_failure1)

        assert suggestion == sample_suggestion1
        mock_analyzer.analyze.assert_called_once_with(sample_failure1)
        mock_suggester.suggest.assert_called_once_with(sample_failure1, analysis_result)
        assert (
            f"Generated suggestion for failure ID: {sample_failure1.id}" in caplog.text
        )

    def test_analyze_single_failure_analyzer_error_fallback(
        self,
        analyzer_service: AnalyzerService,
        mock_analyzer: MagicMock,
        mock_suggester: MagicMock,
        sample_failure1: PytestFailure,
        caplog,
    ):
        """Test analyze_single_failure creates fallback on analyzer error."""
        error_message = "Analyzer crashed"
        mock_analyzer.analyze.side_effect = Exception(error_message)

        caplog.set_level(
            logging.WARNING,
            logger="pytest_analyzer.core.application.services.analyzer_service",
        )
        suggestion = analyzer_service.analyze_single_failure(sample_failure1)

        assert suggestion.failure_id == sample_failure1.id
        assert "Automated suggestion failed." in suggestion.suggestion_text
        assert error_message in suggestion.explanation
        mock_suggester.suggest.assert_not_called()
        assert (
            f"Error during analysis or suggestion for failure ID {sample_failure1.id}"
            in caplog.text
        )
        assert (
            f"Created fallback suggestion for failure ID: {sample_failure1.id}"
            in caplog.text
        )

    def test_analyze_single_failure_suggester_error_fallback(
        self,
        analyzer_service: AnalyzerService,
        mock_analyzer: MagicMock,
        mock_suggester: MagicMock,
        sample_failure1: PytestFailure,
        caplog,
    ):
        """Test analyze_single_failure creates fallback on suggester error."""
        analysis_result = {"detail": "some analysis"}
        mock_analyzer.analyze.return_value = analysis_result
        error_message = "Suggester crashed"
        mock_suggester.suggest.side_effect = Exception(error_message)

        caplog.set_level(
            logging.WARNING,
            logger="pytest_analyzer.core.application.services.analyzer_service",
        )
        suggestion = analyzer_service.analyze_single_failure(sample_failure1)

        assert suggestion.failure_id == sample_failure1.id
        assert "Automated suggestion failed." in suggestion.suggestion_text
        assert error_message in suggestion.explanation
        assert (
            f"Error during analysis or suggestion for failure ID {sample_failure1.id}"
            in caplog.text
        )
        assert (
            f"Created fallback suggestion for failure ID: {sample_failure1.id}"
            in caplog.text
        )

    def test_get_failure_summary_success(
        self,
        analyzer_service: AnalyzerService,
        sample_failure1: PytestFailure,  # type: ASSERTION_ERROR
        sample_failure2: PytestFailure,  # type: EXCEPTION
        caplog,
    ):
        """Test get_failure_summary generates correct summary statistics."""
        # Create modified copies instead of altering fixture instances directly
        f1_assert_error = replace(
            sample_failure1, failure_type=FailureType.ASSERTION_ERROR
        )
        f2_exception = replace(sample_failure2, failure_type=FailureType.EXCEPTION)

        failures = [
            f1_assert_error,
            f2_exception,
            f1_assert_error,  # Two assertion errors, one exception
        ]

        caplog.set_level(
            logging.INFO,
            logger="pytest_analyzer.core.application.services.analyzer_service",
        )
        summary = analyzer_service.get_failure_summary(failures)

        expected_summary = {
            "total_failures": 3,
            "failures_by_type": {
                "ASSERTION_ERROR": 2,
                "EXCEPTION": 1,
            },
        }
        assert summary == expected_summary
        assert f"Generated failure summary: {expected_summary}" in caplog.text

    def test_get_failure_summary_no_failures(
        self, analyzer_service: AnalyzerService, caplog
    ):
        """Test get_failure_summary handles an empty failure list."""
        caplog.set_level(
            logging.DEBUG,
            logger="pytest_analyzer.core.application.services.analyzer_service",
        )
        summary = analyzer_service.get_failure_summary([])

        expected_summary = {"total_failures": 0, "failures_by_type": {}}
        assert summary == expected_summary
        assert (
            "Generating summary for 0 failures." not in caplog.text
        )  # Logged at DEBUG

    def test_get_failure_summary_with_unknown_type(
        self, analyzer_service: AnalyzerService, sample_failure1: PytestFailure, caplog
    ):
        """Test get_failure_summary handles failures with missing type attributes gracefully."""
        # To ensure the Counter logic for AttributeError is hit, we can mock one failure's type
        # to be problematic.
        # For this test, let's make one failure have failure_type=None
        sample_failure1_copy = PytestFailure.create(
            test_name=sample_failure1.test_name,
            file_path=sample_failure1.location.file_path,
            failure_message=sample_failure1.failure_message,
            error_type=sample_failure1.failure_type.value[0],  # error_type string
        )
        sample_failure1_copy.failure_type = None  # Explicitly set to None

        failures = [sample_failure1_copy]

        caplog.set_level(
            logging.WARNING,
            logger="pytest_analyzer.core.application.services.analyzer_service",
        )
        summary = analyzer_service.get_failure_summary(failures)

        expected_summary = {
            "total_failures": 1,
            "failures_by_type": {"UNKNOWN": 1},
        }
        assert summary == expected_summary

        # Check for the specific failure log
        assert (
            f"Could not determine failure type for failure ID {sample_failure1_copy.id} ('{sample_failure1_copy.test_name}')"
            in caplog.text
        )
        assert (
            "due to missing attribute or None type: failure_type is None or missing 'name' attribute"
            in caplog.text
        )

        # Check for the summary log about unknown types
        assert (
            "Encountered 1 failures with undetermined types during summary generation."
            in caplog.text
        )
        assert (
            "These have been categorized as UNKNOWN." in caplog.text
        )  # Part of the summary log
        assert "UNKNOWN" in summary["failures_by_type"]

    def test_get_failure_summary_with_attribute_error_on_failure_type_name(
        self, analyzer_service: AnalyzerService, sample_failure1: PytestFailure, caplog
    ):
        """Test get_failure_summary handles AttributeError when accessing failure_type.name."""

        # Create a failure where accessing failure_type.name will raise an AttributeError
        mock_failure_type = MagicMock()
        del (
            mock_failure_type.name
        )  # Ensure 'name' attribute is missing to cause AttributeError

        sample_failure1_copy = PytestFailure.create(
            test_name=sample_failure1.test_name,
            file_path=sample_failure1.location.file_path,
            failure_message=sample_failure1.failure_message,
            error_type=sample_failure1.failure_type.value[0],
        )
        # Override the failure_type with our mock that will cause an error
        sample_failure1_copy.failure_type = mock_failure_type

        failures = [sample_failure1_copy]

        caplog.set_level(
            logging.WARNING,
            logger="pytest_analyzer.core.application.services.analyzer_service",
        )
        summary = analyzer_service.get_failure_summary(failures)

        expected_summary = {
            "total_failures": 1,
            "failures_by_type": {"UNKNOWN": 1},
        }
        assert summary == expected_summary
        assert "Could not determine failure type" in caplog.text
        assert "missing attribute" in caplog.text
        assert "UNKNOWN" in summary["failures_by_type"]
