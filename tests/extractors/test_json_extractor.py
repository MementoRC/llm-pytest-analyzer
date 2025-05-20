"""Tests for the JSON result extractor."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.pytest_analyzer.core.errors import ExtractionError
from src.pytest_analyzer.core.extraction.json_extractor import JsonResultExtractor
from src.pytest_analyzer.utils.path_resolver import PathResolver
from src.pytest_analyzer.utils.resource_manager import TimeoutError


@pytest.fixture
def sample_json_data():
    """Provide sample JSON data for testing."""
    return {
        "tests": [
            {
                "nodeid": "test_file.py::test_function",
                "outcome": "failed",
                "call": {
                    "exc_info": {"type": "AssertionError"},
                    "longrepr": "assert 1 == 2",
                    "traceback": ["line 1", "line 2"],
                    "source": "def test_function():\n    assert 1 == 2",
                },
            },
            {"nodeid": "test_file.py::test_passing", "outcome": "passed"},
        ]
    }


@pytest.fixture
def json_extractor():
    """Provide a JsonResultExtractor instance for testing."""
    return JsonResultExtractor()


def test_extract_failures(tmp_path, json_extractor, sample_json_data):
    """Test extracting failures from a valid JSON file."""
    # Create a temporary JSON file
    json_path = tmp_path / "report.json"
    with open(json_path, "w") as f:
        json.dump(sample_json_data, f)

    # Extract failures
    failures = json_extractor.extract_failures(json_path)

    # Verify results
    assert len(failures) == 1
    assert failures[0].test_name == "test_file.py::test_function"
    assert failures[0].error_type == "AssertionError"
    assert failures[0].error_message == "assert 1 == 2"
    assert failures[0].relevant_code == "def test_function():\n    assert 1 == 2"


def test_extract_failures_nonexistent_file(json_extractor):
    """Test extracting failures from a nonexistent file."""
    with tempfile.TemporaryDirectory() as temp_dir:
        nonexistent_path = Path(temp_dir) / "nonexistent.json"

        # Verify the function handles nonexistent files
        failures = json_extractor.extract_failures(nonexistent_path)
        assert failures == []


def test_extract_failures_invalid_json(tmp_path, json_extractor):
    """Test extracting failures from an invalid JSON file."""
    # Create an invalid JSON file
    json_path = tmp_path / "invalid.json"
    with open(json_path, "w") as f:
        f.write("This is not valid JSON")

    # Extract failures
    failures = json_extractor.extract_failures(json_path)

    # Verify results
    assert failures == []


def test_extract_failures_empty_json(tmp_path, json_extractor):
    """Test extracting failures from an empty JSON file."""
    # Create an empty JSON file
    json_path = tmp_path / "empty.json"
    with open(json_path, "w") as f:
        json.dump({}, f)

    # Extract failures
    failures = json_extractor.extract_failures(json_path)

    # Verify results
    assert failures == []


def test_extract_failures_no_tests(tmp_path, json_extractor):
    """Test extracting failures from a JSON file with no tests."""
    # Create a JSON file with no tests
    json_path = tmp_path / "no_tests.json"
    with open(json_path, "w") as f:
        json.dump({"summary": "No tests"}, f)

    # Extract failures
    failures = json_extractor.extract_failures(json_path)

    # Verify results
    assert failures == []


@patch(
    "src.pytest_analyzer.core.extraction.json_extractor.JsonResultExtractor._do_extract"
)
def test_extract_failures_timeout(
    mock_do_extract, tmp_path, json_extractor, sample_json_data
):
    """Test handling of timeout during extraction (simulating @with_timeout triggering)."""
    # Configure the mock _do_extract to raise TimeoutError
    mock_do_extract.side_effect = TimeoutError("Simulated Timeout")

    # Create a temporary JSON file
    json_path = tmp_path / "report.json"
    with open(json_path, "w") as f:
        json.dump(sample_json_data, f)

    # Extract failures - the TimeoutError should be caught in the try/except block
    failures = json_extractor.extract_failures(json_path)

    # Verify results - should return empty list when an exception occurs
    assert failures == []

    # Verify _do_extract was called with the correct path
    mock_do_extract.assert_called_once_with(json_path)


@patch("src.pytest_analyzer.utils.path_resolver.PathResolver.resolve_path")
def test_create_failure_from_test(mock_resolve_path):
    """Test creating a PytestFailure object from a test entry."""
    # Configure the mock to return the input path
    mock_resolve_path.side_effect = lambda path: path

    # Create a JsonResultExtractor instance
    extractor = JsonResultExtractor()

    # Test data
    test_entry = {
        "nodeid": "test_file.py::test_function",
        "file": "test_file.py",
        "line": 10,
        "outcome": "failed",
        "call": {
            "exc_info": {"type": "AssertionError"},
            "longrepr": "assert 1 == 2",
            "traceback": ["line 1", "line 2"],
            "source": "def test_function():\n    assert 1 == 2",
        },
    }

    # Create a PytestFailure object
    failure = extractor._create_failure_from_test(test_entry)

    # Verify the result
    assert failure is not None
    assert failure.test_name == "test_file.py::test_function"
    assert failure.test_file == "test_file.py"
    assert failure.line_number == 10
    assert failure.error_type == "AssertionError"
    assert failure.error_message == "assert 1 == 2"
    assert failure.traceback == "line 1\nline 2"
    assert failure.relevant_code == "def test_function():\n    assert 1 == 2"


def test_create_failure_from_test_exception():
    """Test handling of exceptions during PytestFailure creation."""
    # Create a JsonResultExtractor instance
    extractor = JsonResultExtractor()

    # Test data with missing required fields
    test_entry = {}

    # Create a PytestFailure object
    failure = extractor._create_failure_from_test(test_entry)

    # Verify the result
    assert failure is None


def test_path_resolver_integration(tmp_path):
    """Test integration with PathResolver."""
    # Create a custom path resolver with a temporary directory
    path_resolver = PathResolver(project_root=tmp_path)

    # Create a JsonResultExtractor with the custom path resolver
    extractor = JsonResultExtractor(path_resolver=path_resolver)

    # Verify that the path resolver is used
    assert extractor.path_resolver is path_resolver

    # Verify the mock directory was created
    assert (tmp_path / "mocked").exists()


def test_extract_method_with_file(tmp_path, json_extractor, sample_json_data):
    """Test extract method with a file path."""
    # Create a temporary JSON file
    json_path = tmp_path / "report.json"
    with open(json_path, "w") as f:
        json.dump(sample_json_data, f)

    # Extract failures using extract method
    result = json_extractor.extract(json_path)

    # Verify results
    assert "failures" in result
    assert "count" in result
    assert "source" in result
    assert result["source"] == str(json_path)
    assert result["count"] == 1
    assert len(result["failures"]) == 1
    assert result["failures"][0].test_name == "test_file.py::test_function"
    assert result["failures"][0].error_type == "AssertionError"


def test_extract_method_with_string_path(tmp_path, json_extractor, sample_json_data):
    """Test extract method with a string path."""
    # Create a temporary JSON file
    json_path = tmp_path / "report.json"
    with open(json_path, "w") as f:
        json.dump(sample_json_data, f)

    # Extract failures using extract method with string path
    result = json_extractor.extract(str(json_path))

    # Verify results
    assert "failures" in result
    assert "count" in result
    assert "source" in result
    assert result["source"] == str(json_path)
    assert result["count"] == 1
    assert len(result["failures"]) == 1


def test_extract_method_with_dict(json_extractor, sample_json_data):
    """Test extract method with a dictionary."""
    # Extract failures using extract method with dictionary
    result = json_extractor.extract(sample_json_data)

    # Verify results
    assert "failures" in result
    assert "count" in result
    assert result["count"] == 1
    assert len(result["failures"]) == 1
    assert result["failures"][0].test_name == "test_file.py::test_function"
    assert result["failures"][0].error_type == "AssertionError"


def test_extract_method_nonexistent_file(json_extractor):
    """Test extract method with a nonexistent file."""
    with tempfile.TemporaryDirectory() as temp_dir:
        nonexistent_path = Path(temp_dir) / "nonexistent.json"

        # Verify the function raises ExtractionError
        with pytest.raises(ExtractionError) as exc_info:
            json_extractor.extract(nonexistent_path)

        assert "Results file not found" in str(exc_info.value)


def test_extract_method_invalid_input(json_extractor):
    """Test extract method with invalid input type."""
    # Pass an invalid input type
    with pytest.raises(ExtractionError) as exc_info:
        json_extractor.extract(123)  # Integer is not a valid input type

    assert "Unsupported test_results type" in str(exc_info.value)


def test_extract_method_invalid_json(tmp_path, json_extractor):
    """Test extract method with invalid JSON file."""
    # Create an invalid JSON file
    json_path = tmp_path / "invalid.json"
    with open(json_path, "w") as f:
        f.write("This is not valid JSON")

    # Verify the function raises ExtractionError
    with pytest.raises(ExtractionError) as exc_info:
        json_extractor.extract(json_path)

    assert "Invalid JSON format" in str(exc_info.value)
