"""Integration tests for the PytestAnalyzerService with extractors and analyzers."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pytest_analyzer.core.domain.entities.fix_suggestion import FixSuggestion
from pytest_analyzer.core.domain.entities.pytest_failure import PytestFailure
from pytest_analyzer.core.factory import create_analyzer_service
from pytest_analyzer.utils.settings import Settings


@pytest.fixture
def analyzer_service(mock_llm_client):
    """Create a basic analyzer service instance with LLM mocking."""
    settings = Settings()
    # Always use LLM (but with a mock client)
    settings.use_llm = True
    return create_analyzer_service(settings=settings, llm_client=mock_llm_client)


@pytest.fixture
def analyzer_service_with_llm(mock_llm_client):
    """Create an analyzer service with LLM enabled."""
    settings = Settings()
    settings.use_llm = True
    return create_analyzer_service(settings=settings, llm_client=mock_llm_client)


def test_service_integration_json_format(analyzer_service, report_assertion_json):
    """Test PytestAnalyzerService with JSON report format."""
    # For an integration test, we'll let the service run naturally but mock at the LLM level
    # to ensure we get a deterministic response
    from unittest.mock import patch

    # Create a more flexible mock that returns suggestions for any failure ID
    def create_mock_suggestions(failures):
        """Create mock suggestions for whatever failures are passed in."""
        result = {}
        for failure in failures:
            result[failure.id] = [
                FixSuggestion.create_from_score(
                    failure_id=failure.id,
                    suggestion_text="A good suggestion",
                    confidence_score=0.9,
                    explanation="It failed.",
                )
            ]
        return result

    # Mock the batch_suggest_fixes method with a side effect that creates appropriate responses
    with patch.object(
        analyzer_service._service.orchestrator.llm_suggester,
        "batch_suggest_fixes",
        new=AsyncMock(side_effect=create_mock_suggestions),
    ):
        # Analyze the JSON report
        suggestions = analyzer_service.analyze_pytest_output(report_assertion_json)

    # Verify the results
    assert suggestions is not None
    assert len(suggestions) > 0

    # Check that the first suggestion is properly structured
    suggestion = suggestions[0]
    assert suggestion.failure_id is not None
    # We can check the suggestion content from our mock
    assert suggestion.suggestion_text == "A good suggestion"
    assert suggestion.confidence_score == 0.9


def test_service_integration_xml_format(analyzer_service, report_assertion_xml):
    """Test PytestAnalyzerService with XML report format."""
    # Mock the async part of the service
    # Get the orchestrator to access the llm_suggester
    analyzer_service._service.orchestrator.llm_suggester.batch_suggest_fixes = (
        AsyncMock(
            return_value={
                "some_id": [
                    FixSuggestion.create_from_score(
                        failure_id="some_id",
                        suggestion_text="A good suggestion for XML",
                        confidence_score=0.8,
                        explanation="It failed in XML.",
                    )
                ]
            }
        )
    )
    # Analyze the XML report
    suggestions = analyzer_service.analyze_pytest_output(report_assertion_xml)

    # Verify the results
    assert suggestions is not None
    assert len(suggestions) > 0

    # Check that the first suggestion is properly structured
    suggestion = suggestions[0]
    assert suggestion.failure_id is not None
    assert suggestion.suggestion_text == "A good suggestion for XML"
    assert suggestion.confidence_score == 0.8


@patch("pytest_analyzer.analyzer_service.collect_failures_with_plugin")
def test_service_integration_with_plugin(mock_collect, analyzer_service):
    """Test PytestAnalyzerService with direct pytest plugin integration."""
    # Set preferred format to plugin
    analyzer_service.settings.preferred_format = "plugin"

    # Create a mock PytestFailure using domain entity
    mock_failure = PytestFailure.create(
        test_name="test_file.py::test_function",
        file_path="test_file.py",
        failure_message="assert 1 == 2",
        error_type="AssertionError",
        traceback=["E       assert 1 == 2", "E       +  where 1 = func()"],
        line_number=42,
        function_name="test_function",
        class_name=None,
    )

    # Mock the plugin to return our test failure
    mock_collect.return_value = [mock_failure]

    # Mock the async part
    # Get the private orchestrator to access the llm_suggester
    private_analyzer = analyzer_service._private_analyzer
    private_analyzer.orchestrator.llm_suggester.batch_suggest_fixes = AsyncMock(
        return_value={
            mock_failure.id: [
                FixSuggestion.create_from_score(
                    failure_id=mock_failure.id,
                    suggestion_text="Plugin suggestion",
                    confidence_score=0.99,
                    explanation="From plugin",
                )
            ]
        }
    )

    # Run the analysis
    suggestions = analyzer_service.run_and_analyze("test_path")

    # Verify the results
    assert suggestions is not None
    assert len(suggestions) > 0
    assert mock_collect.called
    assert suggestions[0].failure_id == mock_failure.id


def test_service_integration_with_llm(
    analyzer_service_with_llm, report_assertion_json, mock_llm_suggester
):
    """Test PytestAnalyzerService with LLM integration."""
    # The mock_llm_suggester fixture patches the suggester at a lower level.
    # The service will use this patched suggester.
    # We need to ensure the service's suggester instance is the one being patched,
    # or that the patch is general enough. The fixture patches the class method.
    # The service now uses batch_suggest_fixes, so we need to adapt.
    with patch(
        "pytest_analyzer.core.analysis.llm_suggester.LLMSuggester.batch_suggest_fixes",
        new_callable=AsyncMock,
    ) as mock_batch_suggest:
        # The key of the return value should be the failure ID.
        # The JSON extractor will generate an ID. We can't know it beforehand,
        # so we'll mock the return value to match any ID.
        # A more robust way is to have the mock return a value for a known ID,
        # but this requires more complex mocking of the extractor.
        # For this test, we'll assume the orchestrator gets a suggestion.
        failure_id = "some_id"

        future = asyncio.Future()
        future.set_result(
            {
                failure_id: [
                    FixSuggestion.create_from_score(
                        failure_id=failure_id,
                        suggestion_text="LLM Suggestion",
                        confidence_score=0.9,
                        explanation="From LLM",
                        code_changes=["source: llm"],
                        metadata={"source": "llm_async"},
                    )
                ]
            }
        )
        # To make this mock more robust, we can make it return the value
        # regardless of the key it's called with.
        mock_batch_suggest.return_value = future.result()

        # Analyze the JSON report
        suggestions = analyzer_service_with_llm.analyze_pytest_output(
            report_assertion_json
        )

    # Verify the results
    assert suggestions is not None
    assert len(suggestions) > 0

    # Check if we get at least one suggestion with LLM as source
    assert any(
        hasattr(suggestion, "metadata")
        and suggestion.metadata
        and suggestion.metadata.get("source") == "llm_async"
        for suggestion in suggestions
    )


def test_service_integration_no_failures(analyzer_service, report_passing_json):
    """Test PytestAnalyzerService with a report that has no failures."""
    # Analyze the passing report
    suggestions = analyzer_service.analyze_pytest_output(report_passing_json)

    # Verify the results - should be an empty list
    assert suggestions is not None
    assert len(suggestions) == 0


@patch("subprocess.run")
def test_service_integration_run_pytest(mock_subprocess, analyzer_service, tmp_path):
    """Test PytestAnalyzerService running pytest and analyzing results."""
    # Create a mock subprocess result
    mock_result = MagicMock()
    mock_result.returncode = 1  # Non-zero for failures
    mock_subprocess.return_value = mock_result

    # Create a temp JSON report file that will be "created" by pytest
    report_path = tmp_path / "json-report.json"
    report_path.write_text(
        """
    {
      "created": 1712621338.818604,
      "duration": 0.01588892936706543,
      "exitcode": 1,
      "summary": {
        "failed": 1,
        "total": 1
      },
      "tests": [
        {
          "nodeid": "test_file.py::test_function",
          "lineno": 42,
          "outcome": "failed",
          "message": "AssertionError: assert 1 == 2",
          "duration": 0.00019192695617675781,
          "call": {
            "traceback": [
              {
                "path": "test_file.py",
                "lineno": 42,
                "message": "AssertionError"
              }
            ]
          }
        }
      ]
    }
    """
    )

    # Configure the service to use JSON format
    analyzer_service.settings.preferred_format = "json"

    # Mock the async part
    # Get the private orchestrator to access the llm_suggester
    private_analyzer = analyzer_service._private_analyzer
    private_analyzer.orchestrator.llm_suggester.batch_suggest_fixes = AsyncMock(
        return_value={
            "some_id": [
                FixSuggestion.create_from_score(
                    failure_id="some_id",
                    suggestion_text="Suggestion from run",
                    confidence_score=0.85,
                    explanation="It failed during a run.",
                )
            ]
        }
    )

    # Mock the temporary file creation to return our prepared path
    with patch("tempfile.NamedTemporaryFile") as mock_tmp_file:
        mock_tmp = MagicMock()
        mock_tmp.name = str(report_path)
        mock_tmp_file.return_value.__enter__.return_value = mock_tmp

        # Run the service
        suggestions = analyzer_service.run_and_analyze("test_path")

    # Verify the results
    assert suggestions is not None
    assert len(suggestions) > 0
    assert mock_subprocess.called

    # Verify that pytest was called with the correct arguments
    pytest_args = mock_subprocess.call_args[0][0]
    assert pytest_args[0] == "pytest"
    assert pytest_args[1] == "test_path"
    assert "--json-report" in pytest_args
