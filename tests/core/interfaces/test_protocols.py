from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import Mock

from pytest_analyzer.core.domain.entities.fix_suggestion import FixSuggestion
from pytest_analyzer.core.domain.entities.pytest_failure import PytestFailure
from pytest_analyzer.core.domain.value_objects.failure_type import FailureType
from pytest_analyzer.core.domain.value_objects.test_location import TestLocation
from pytest_analyzer.core.interfaces.protocols import (
    FailureAnalyzer,
    FixSuggester,
    TestResultRepository,
)


class TestFailureAnalyzerProtocol:
    """Test that FailureAnalyzer protocol can be implemented."""

    def test_protocol_implementation(self):
        """Test that a class can implement the FailureAnalyzer protocol."""

        class ConcreteFailureAnalyzer:
            def analyze(self, failure: PytestFailure) -> Dict[str, Any]:
                return {
                    "failure_type": failure.failure_type.value,
                    "analysis_result": "mock analysis",
                }

        analyzer = ConcreteFailureAnalyzer()

        # Create a test failure
        location = TestLocation(file_path=Path("test_file.py"), line_number=10)
        failure = PytestFailure(
            id="test-id",
            test_name="test_example",
            location=location,
            failure_message="Test failed",
            failure_type=FailureType.ASSERTION_ERROR,
        )

        result = analyzer.analyze(failure)

        assert isinstance(result, dict)
        assert result["failure_type"] == "assertion_error"
        assert result["analysis_result"] == "mock analysis"

    def test_protocol_typing(self):
        """Test that protocol supports type checking."""

        def use_analyzer(
            analyzer: FailureAnalyzer, failure: PytestFailure
        ) -> Dict[str, Any]:
            return analyzer.analyze(failure)

        # Create mock analyzer
        mock_analyzer = Mock()
        mock_analyzer.analyze.return_value = {"result": "test"}

        location = TestLocation(file_path=Path("test_file.py"))
        failure = PytestFailure(
            id="test-id",
            test_name="test_example",
            location=location,
            failure_message="Test failed",
            failure_type=FailureType.ASSERTION_ERROR,
        )

        result = use_analyzer(mock_analyzer, failure)

        assert result == {"result": "test"}
        mock_analyzer.analyze.assert_called_once_with(failure)


class TestFixSuggesterProtocol:
    """Test that FixSuggester protocol can be implemented."""

    def test_protocol_implementation(self):
        """Test that a class can implement the FixSuggester protocol."""

        class ConcreteFixSuggester:
            def suggest(
                self, failure: PytestFailure, analysis: Optional[Dict[str, Any]] = None
            ) -> FixSuggestion:
                return FixSuggestion.create(
                    failure_id=failure.id, suggestion_text="Mock suggestion"
                )

        suggester = ConcreteFixSuggester()

        # Create a test failure
        location = TestLocation(file_path=Path("test_file.py"), line_number=10)
        failure = PytestFailure(
            id="test-id",
            test_name="test_example",
            location=location,
            failure_message="Test failed",
            failure_type=FailureType.ASSERTION_ERROR,
        )

        suggestion = suggester.suggest(failure)

        assert isinstance(suggestion, FixSuggestion)
        assert suggestion.failure_id == failure.id
        assert suggestion.suggestion_text == "Mock suggestion"

    def test_protocol_with_analysis(self):
        """Test protocol implementation with analysis parameter."""

        class ConcreteFixSuggester:
            def suggest(
                self, failure: PytestFailure, analysis: Optional[Dict[str, Any]] = None
            ) -> FixSuggestion:
                analysis_info = (
                    analysis.get("info", "no analysis") if analysis else "no analysis"
                )
                return FixSuggestion.create(
                    failure_id=failure.id,
                    suggestion_text=f"Suggestion based on: {analysis_info}",
                )

        suggester = ConcreteFixSuggester()

        location = TestLocation(file_path=Path("test_file.py"))
        failure = PytestFailure(
            id="test-id",
            test_name="test_example",
            location=location,
            failure_message="Test failed",
            failure_type=FailureType.ASSERTION_ERROR,
        )

        analysis = {"info": "assertion error detected"}
        suggestion = suggester.suggest(failure, analysis)

        assert "assertion error detected" in suggestion.suggestion_text

    def test_protocol_typing(self):
        """Test that protocol supports type checking."""

        def use_suggester(
            suggester: FixSuggester, failure: PytestFailure
        ) -> FixSuggestion:
            return suggester.suggest(failure)

        # Create mock suggester
        mock_suggester = Mock()
        mock_suggestion = Mock(spec=FixSuggestion)
        mock_suggester.suggest.return_value = mock_suggestion

        location = TestLocation(file_path=Path("test_file.py"))
        failure = PytestFailure(
            id="test-id",
            test_name="test_example",
            location=location,
            failure_message="Test failed",
            failure_type=FailureType.ASSERTION_ERROR,
        )

        result = use_suggester(mock_suggester, failure)

        assert result == mock_suggestion
        mock_suggester.suggest.assert_called_once_with(failure)


class TestTestResultRepositoryProtocol:
    """Test that TestResultRepository protocol can be implemented."""

    def test_protocol_implementation(self):
        """Test that a class can implement the TestResultRepository protocol."""

        class ConcreteTestResultRepository:
            def get_failures(self, report_path: Path) -> List[PytestFailure]:
                # Mock implementation
                location = TestLocation(file_path=Path("test_file.py"))
                return [
                    PytestFailure(
                        id="test-id",
                        test_name="test_example",
                        location=location,
                        failure_message="Test failed",
                        failure_type=FailureType.ASSERTION_ERROR,
                    )
                ]

            def save_suggestions(
                self, suggestions: List[FixSuggestion], output_path: Path
            ) -> None:
                # Mock implementation - just verify it's callable
                pass

        repository = ConcreteTestResultRepository()

        # Test get_failures
        failures = repository.get_failures(Path("report.json"))
        assert len(failures) == 1
        assert isinstance(failures[0], PytestFailure)
        assert failures[0].test_name == "test_example"

        # Test save_suggestions
        suggestion = FixSuggestion.create(
            failure_id="test-id", suggestion_text="Mock suggestion"
        )

        # Should not raise an exception
        repository.save_suggestions([suggestion], Path("output.json"))

    def test_protocol_typing(self):
        """Test that protocol supports type checking."""

        def use_repository(
            repo: TestResultRepository, path: Path
        ) -> List[PytestFailure]:
            return repo.get_failures(path)

        # Create mock repository
        mock_repo = Mock()
        mock_failure = Mock(spec=PytestFailure)
        mock_repo.get_failures.return_value = [mock_failure]

        result = use_repository(mock_repo, Path("test.json"))

        assert result == [mock_failure]
        mock_repo.get_failures.assert_called_once_with(Path("test.json"))


class TestProtocolIntegration:
    """Test that protocols work together."""

    def test_complete_workflow(self):
        """Test a complete workflow using all protocols."""

        class MockAnalyzer:
            def analyze(self, failure: PytestFailure) -> Dict[str, Any]:
                return {"type": "assertion", "severity": "high"}

        class MockSuggester:
            def suggest(
                self, failure: PytestFailure, analysis: Optional[Dict[str, Any]] = None
            ) -> FixSuggestion:
                return FixSuggestion.create(
                    failure_id=failure.id, suggestion_text="Fix the assertion"
                )

        class MockRepository:
            def get_failures(self, report_path: Path) -> List[PytestFailure]:
                location = TestLocation(file_path=Path("test_file.py"))
                return [
                    PytestFailure(
                        id="test-id",
                        test_name="test_example",
                        location=location,
                        failure_message="Test failed",
                        failure_type=FailureType.ASSERTION_ERROR,
                    )
                ]

            def save_suggestions(
                self, suggestions: List[FixSuggestion], output_path: Path
            ) -> None:
                pass

        # Create instances
        analyzer = MockAnalyzer()
        suggester = MockSuggester()
        repository = MockRepository()

        # Simulate workflow
        failures = repository.get_failures(Path("report.json"))
        failure = failures[0]

        analysis = analyzer.analyze(failure)
        suggestion = suggester.suggest(failure, analysis)

        repository.save_suggestions([suggestion], Path("suggestions.json"))

        # Verify the workflow
        assert len(failures) == 1
        assert analysis["type"] == "assertion"
        assert suggestion.failure_id == failure.id
        assert "Fix the assertion" in suggestion.suggestion_text
