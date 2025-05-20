"""Tests for the XML result extractor."""

import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

import pytest

from src.pytest_analyzer.core.errors import ExtractionError
from src.pytest_analyzer.core.extraction.xml_extractor import XmlResultExtractor
from src.pytest_analyzer.utils.path_resolver import PathResolver
from src.pytest_analyzer.utils.resource_manager import TimeoutError


@pytest.fixture
def sample_xml_content():
    """Provide sample XML content for testing."""
    return """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" errors="0" failures="1" skipped="0" tests="2">
    <testcase classname="test_module" name="test_function" file="test_module.py" line="10">
      <failure message="AssertionError: assert 1 == 2">def test_function():
>       assert 1 == 2
E       assert 1 == 2</failure>
    </testcase>
    <testcase classname="test_module" name="test_passing" file="test_module.py" line="15"></testcase>
  </testsuite>
</testsuites>
"""


@pytest.fixture
def xml_extractor():
    """Provide a XmlResultExtractor instance for testing."""
    return XmlResultExtractor()


def test_extract_failures(tmp_path, xml_extractor, sample_xml_content):
    """Test extracting failures from a valid XML file."""
    # Create a temporary XML file
    xml_path = tmp_path / "report.xml"
    with open(xml_path, "w") as f:
        f.write(sample_xml_content)

    # Extract failures
    failures = xml_extractor.extract_failures(xml_path)

    # Verify results
    assert len(failures) == 1
    assert failures[0].test_name == "test_module.test_function"
    assert failures[0].error_type == "AssertionError"
    assert failures[0].error_message == "AssertionError: assert 1 == 2"
    assert "assert 1 == 2" in failures[0].traceback


def test_extract_failures_nonexistent_file(xml_extractor):
    """Test extracting failures from a nonexistent file."""
    with tempfile.TemporaryDirectory() as temp_dir:
        nonexistent_path = Path(temp_dir) / "nonexistent.xml"

        # Verify the function handles nonexistent files
        failures = xml_extractor.extract_failures(nonexistent_path)
        assert failures == []


def test_extract_failures_invalid_xml(tmp_path, xml_extractor):
    """Test extracting failures from an invalid XML file."""
    # Create an invalid XML file
    xml_path = tmp_path / "invalid.xml"
    with open(xml_path, "w") as f:
        f.write("This is not valid XML")

    # Extract failures
    failures = xml_extractor.extract_failures(xml_path)

    # Verify results
    assert failures == []


def test_extract_failures_empty_xml(tmp_path, xml_extractor):
    """Test extracting failures from an empty XML file."""
    # Create an empty XML file
    xml_path = tmp_path / "empty.xml"
    with open(xml_path, "w") as f:
        f.write("<testsuites></testsuites>")

    # Extract failures
    failures = xml_extractor.extract_failures(xml_path)

    # Verify results
    assert failures == []


@patch(
    "src.pytest_analyzer.core.extraction.xml_extractor.XmlResultExtractor._parse_xml_report"
)
def test_extract_failures_timeout(
    mock_parse_xml, tmp_path, xml_extractor, sample_xml_content
):
    """Test handling of timeout during extraction (simulating parsing timeout)."""
    # Configure the mock _parse_xml_report to raise TimeoutError
    mock_parse_xml.side_effect = TimeoutError("Simulated Timeout during XML parsing")

    # Create a temporary XML file
    xml_path = tmp_path / "report.xml"
    with open(xml_path, "w") as f:
        f.write(sample_xml_content)

    # Extract failures - the TimeoutError should be caught in the try/except block
    failures = xml_extractor.extract_failures(xml_path)

    # Verify results - should return an empty list when an exception occurs
    assert failures == []

    # Verify _parse_xml_report was called with the correct path
    mock_parse_xml.assert_called_once_with(xml_path)


@patch("xml.etree.ElementTree.parse")
def test_extract_failures_parse_error(
    mock_et_parse, tmp_path, xml_extractor, sample_xml_content
):
    """Test handling of XML parse errors."""
    # Make ET.parse raise a ParseError
    mock_et_parse.side_effect = ET.ParseError("Parse error")

    # Create a temporary XML file
    xml_path = tmp_path / "report.xml"
    with open(xml_path, "w") as f:
        f.write(sample_xml_content)

    # Extract failures
    failures = xml_extractor.extract_failures(xml_path)

    # Verify results
    assert failures == []


def test_extract_line_number_from_traceback():
    """Test extracting line number from traceback text."""
    # Create a XmlResultExtractor instance
    extractor = XmlResultExtractor()

    # Test data
    traceback_text = """def test_function():
>       assert 1 == 2
E       assert 1 == 2
/path/to/test_file.py:42: AssertionError"""

    # Extract line number
    line_number = extractor._extract_line_number_from_traceback(traceback_text)

    # Verify the result
    assert line_number == 42


def test_extract_line_number_from_traceback_no_match():
    """Test extracting line number from traceback text with no line number."""
    # Create a XmlResultExtractor instance
    extractor = XmlResultExtractor()

    # Test data with no line number
    traceback_text = "No line number here"

    # Extract line number
    line_number = extractor._extract_line_number_from_traceback(traceback_text)

    # Verify the result
    assert line_number is None


def test_extract_line_number_from_traceback_multiple_matches():
    """Test extracting line number from traceback text with multiple line numbers."""
    # Create a XmlResultExtractor instance
    extractor = XmlResultExtractor()

    # Test data with multiple line numbers
    traceback_text = """Traceback (most recent call last):
  File "/path/to/file.py", line 10, in func1
    return func2()
  File "/path/to/file2.py", line 20, in func2
    return func3()
  File "/path/to/file3.py", line 30, in func3
    assert False"""

    # Extract line number
    line_number = extractor._extract_line_number_from_traceback(traceback_text)

    # Verify the result (should be the last line number)
    assert line_number == 30


def test_path_resolver_integration(tmp_path):
    """Test integration with PathResolver."""
    # Create a custom path resolver with a temporary directory
    path_resolver = PathResolver(project_root=tmp_path)

    # Create a XmlResultExtractor with the custom path resolver
    extractor = XmlResultExtractor(path_resolver=path_resolver)

    # Verify that the path resolver is used
    assert extractor.path_resolver is path_resolver

    # Verify the mock directory was created
    assert (tmp_path / "mocked").exists()


def test_extract_method_with_file(tmp_path, xml_extractor, sample_xml_content):
    """Test extract method with a file path."""
    # Create a temporary XML file
    xml_path = tmp_path / "report.xml"
    with open(xml_path, "w") as f:
        f.write(sample_xml_content)

    # Extract failures using extract method
    result = xml_extractor.extract(xml_path)

    # Verify results
    assert "failures" in result
    assert "count" in result
    assert "source" in result
    assert result["count"] == 1
    assert len(result["failures"]) == 1
    assert result["failures"][0].test_name == "test_module.test_function"
    assert result["failures"][0].error_type == "AssertionError"


def test_extract_method_with_element(xml_extractor, sample_xml_content):
    """Test extract method with an XML element."""
    # Parse XML to create an element
    root = ET.fromstring(sample_xml_content)

    # Extract failures using extract method
    result = xml_extractor.extract(root)

    # Verify results
    assert "failures" in result
    assert "count" in result
    assert result["count"] == 1
    assert len(result["failures"]) == 1
    assert result["failures"][0].test_name == "test_module.test_function"
    assert result["failures"][0].error_type == "AssertionError"


def test_extract_method_with_string(tmp_path, xml_extractor, sample_xml_content):
    """Test extract method with a string path."""
    # Create a temporary XML file
    xml_path = tmp_path / "report.xml"
    with open(xml_path, "w") as f:
        f.write(sample_xml_content)

    # Extract failures using extract method with string path
    result = xml_extractor.extract(str(xml_path))

    # Verify results
    assert "failures" in result
    assert "count" in result
    assert "source" in result
    assert result["count"] == 1
    assert len(result["failures"]) == 1


def test_extract_method_nonexistent_file(xml_extractor):
    """Test extract method with a nonexistent file."""
    with tempfile.TemporaryDirectory() as temp_dir:
        nonexistent_path = Path(temp_dir) / "nonexistent.xml"

        # Verify the function raises ExtractionError
        with pytest.raises(ExtractionError) as exc_info:
            xml_extractor.extract(nonexistent_path)

        assert "XML report file not found" in str(exc_info.value)


def test_extract_method_invalid_input(xml_extractor):
    """Test extract method with invalid input type."""
    # Pass an invalid input type
    with pytest.raises(ExtractionError) as exc_info:
        xml_extractor.extract(123)  # Integer is not a valid input type

    assert "Unsupported test_results type" in str(exc_info.value)
