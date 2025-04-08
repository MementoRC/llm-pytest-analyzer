"""Tests for the JSON result extractor."""
import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock

from ...core.extraction.json_extractor import JsonResultExtractor
from ...core.models.test_failure import TestFailure
from ...utils.path_resolver import PathResolver
from ...utils.resource_manager import TimeoutError


@pytest.fixture
def sample_json_data():
    """Provide sample JSON data for testing."""
    return {
        "tests": [
            {
                "nodeid": "test_file.py::test_function",
                "outcome": "failed",
                "call": {
                    "exc_info": {
                        "type": "AssertionError"
                    },
                    "longrepr": "assert 1 == 2",
                    "traceback": ["line 1", "line 2"],
                    "source": "def test_function():\n    assert 1 == 2"
                }
            },
            {
                "nodeid": "test_file.py::test_passing",
                "outcome": "passed"
            }
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
    with open(json_path, 'w') as f:
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
    with open(json_path, 'w') as f:
        f.write("This is not valid JSON")
    
    # Extract failures
    failures = json_extractor.extract_failures(json_path)
    
    # Verify results
    assert failures == []


def test_extract_failures_empty_json(tmp_path, json_extractor):
    """Test extracting failures from an empty JSON file."""
    # Create an empty JSON file
    json_path = tmp_path / "empty.json"
    with open(json_path, 'w') as f:
        json.dump({}, f)
    
    # Extract failures
    failures = json_extractor.extract_failures(json_path)
    
    # Verify results
    assert failures == []


def test_extract_failures_no_tests(tmp_path, json_extractor):
    """Test extracting failures from a JSON file with no tests."""
    # Create a JSON file with no tests
    json_path = tmp_path / "no_tests.json"
    with open(json_path, 'w') as f:
        json.dump({"summary": "No tests"}, f)
    
    # Extract failures
    failures = json_extractor.extract_failures(json_path)
    
    # Verify results
    assert failures == []


@patch('pytest_analyzer.utils.resource_manager.ResourceMonitor')
def test_extract_failures_timeout(mock_resource_monitor, tmp_path, json_extractor, sample_json_data):
    """Test handling of timeout during extraction."""
    # Make ResourceMonitor raise a TimeoutError
    mock_monitor = MagicMock()
    mock_monitor.__enter__.side_effect = TimeoutError("Timeout")
    mock_resource_monitor.return_value = mock_monitor
    
    # Create a temporary JSON file
    json_path = tmp_path / "report.json"
    with open(json_path, 'w') as f:
        json.dump(sample_json_data, f)
    
    # Extract failures
    failures = json_extractor.extract_failures(json_path)
    
    # Verify results
    assert failures == []


def test_create_failure_from_test():
    """Test creating a TestFailure object from a test entry."""
    # Create a JsonResultExtractor instance
    extractor = JsonResultExtractor()
    
    # Test data
    test_entry = {
        "nodeid": "test_file.py::test_function",
        "file": "test_file.py",
        "line": 10,
        "outcome": "failed",
        "call": {
            "exc_info": {
                "type": "AssertionError"
            },
            "longrepr": "assert 1 == 2",
            "traceback": ["line 1", "line 2"],
            "source": "def test_function():\n    assert 1 == 2"
        }
    }
    
    # Create a TestFailure object
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
    """Test handling of exceptions during TestFailure creation."""
    # Create a JsonResultExtractor instance
    extractor = JsonResultExtractor()
    
    # Test data with missing required fields
    test_entry = {}
    
    # Create a TestFailure object
    failure = extractor._create_failure_from_test(test_entry)
    
    # Verify the result
    assert failure is None


def test_path_resolver_integration():
    """Test integration with PathResolver."""
    # Create a custom path resolver
    path_resolver = PathResolver(project_root=Path('/project'))
    
    # Create a JsonResultExtractor with the custom path resolver
    extractor = JsonResultExtractor(path_resolver=path_resolver)
    
    # Verify that the path resolver is used
    assert extractor.path_resolver is path_resolver