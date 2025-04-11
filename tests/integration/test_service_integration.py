"""Integration tests for the PytestAnalyzerService with extractors and analyzers."""
import pytest
import os
from unittest.mock import patch, MagicMock

from src.pytest_analyzer.core.analyzer_service import PytestAnalyzerService
from src.pytest_analyzer.core.analysis.failure_analyzer import FailureAnalyzer
from src.pytest_analyzer.core.analysis.llm_suggester import LLMSuggester
from src.pytest_analyzer.utils.settings import Settings
from src.pytest_analyzer.core.models.pytest_failure import PytestFailure


@pytest.fixture
def analyzer_service():
    """Create a basic analyzer service instance."""
    settings = Settings()
    # Disable LLM by default
    settings.use_llm = False
    return PytestAnalyzerService(settings=settings)


@pytest.fixture
def analyzer_service_with_llm(mock_llm_client):
    """Create an analyzer service with LLM enabled."""
    settings = Settings()
    settings.use_llm = True
    service = PytestAnalyzerService(settings=settings, llm_client=mock_llm_client)
    return service


def test_service_integration_json_format(analyzer_service, report_assertion_json):
    """Test PytestAnalyzerService with JSON report format."""
    # Analyze the JSON report
    suggestions = analyzer_service.analyze_pytest_output(report_assertion_json)
    
    # Verify the results
    assert suggestions is not None
    assert len(suggestions) > 0
    
    # Check that the first suggestion is properly structured
    suggestion = suggestions[0]
    assert suggestion.failure is not None
    assert suggestion.failure.test_name == "test_assertion_fail.py::test_simple_fail"
    assert suggestion.failure.error_type == "AssertionError"
    assert "Values are not equal" in suggestion.failure.error_message
    
    # Check that suggestion has the required fields
    assert suggestion.suggestion is not None
    assert suggestion.confidence > 0


def test_service_integration_xml_format(analyzer_service, report_assertion_xml):
    """Test PytestAnalyzerService with XML report format."""
    # Analyze the XML report
    suggestions = analyzer_service.analyze_pytest_output(report_assertion_xml)
    
    # Verify the results
    assert suggestions is not None
    assert len(suggestions) > 0
    
    # Check that the first suggestion is properly structured
    suggestion = suggestions[0]
    assert suggestion.failure is not None
    assert "test_simple_fail" in suggestion.failure.test_name
    assert suggestion.failure.error_type == "AssertionError"
    assert "Values are not equal" in suggestion.failure.error_message
    
    # Check that suggestion has the required fields
    assert suggestion.suggestion is not None
    assert suggestion.confidence > 0


@patch('src.pytest_analyzer.core.analyzer_service.collect_failures_with_plugin')
def test_service_integration_with_plugin(mock_collect, analyzer_service):
    """Test PytestAnalyzerService with direct pytest plugin integration."""
    # Set preferred format to plugin
    analyzer_service.settings.preferred_format = "plugin"
    
    # Create a mock PytestFailure
    mock_failure = PytestFailure(
        test_name="test_file.py::test_function",
        test_file="test_file.py",
        error_type="AssertionError",
        error_message="assert 1 == 2",
        traceback="E       assert 1 == 2\nE       +  where 1 = func()",
        line_number=42,
        relevant_code="def test_function():\n    assert 1 == 2"
    )
    
    # Mock the plugin to return our test failure
    mock_collect.return_value = [mock_failure]
    
    # Run the analysis
    suggestions = analyzer_service.run_and_analyze("test_path")
    
    # Verify the results
    assert suggestions is not None
    assert len(suggestions) > 0
    assert mock_collect.called
    assert suggestions[0].failure == mock_failure


def test_service_integration_with_llm(analyzer_service_with_llm, report_assertion_json, mock_llm_suggester):
    """Test PytestAnalyzerService with LLM integration."""
    # Analyze the JSON report
    suggestions = analyzer_service_with_llm.analyze_pytest_output(report_assertion_json)
    
    # Verify the results
    assert suggestions is not None
    assert len(suggestions) > 0
    
    # Check if we get at least one suggestion with LLM as source
    assert any(
        suggestion.code_changes and suggestion.code_changes.get('source') == 'llm'
        for suggestion in suggestions
    )


def test_service_integration_no_failures(analyzer_service, report_passing_json):
    """Test PytestAnalyzerService with a report that has no failures."""
    # Analyze the passing report
    suggestions = analyzer_service.analyze_pytest_output(report_passing_json)
    
    # Verify the results - should be an empty list
    assert suggestions is not None
    assert len(suggestions) == 0


@patch('subprocess.run')
def test_service_integration_run_pytest(mock_subprocess, analyzer_service, tmp_path):
    """Test PytestAnalyzerService running pytest and analyzing results."""
    # Create a mock subprocess result
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_subprocess.return_value = mock_result
    
    # Create a temp JSON report file that will be "created" by pytest
    report_path = tmp_path / "json-report.json"
    report_path.write_text("""
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
    """)
    
    # Configure the service to use JSON format
    analyzer_service.settings.preferred_format = "json"
    
    # Mock the temporary file creation to return our prepared path
    with patch('tempfile.NamedTemporaryFile') as mock_tmp_file:
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