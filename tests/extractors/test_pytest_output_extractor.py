"""Tests for the pytest output extractor."""

import os
from pathlib import Path

import pytest

from src.pytest_analyzer.core.errors import ExtractionError
from src.pytest_analyzer.core.extraction.pytest_output_extractor import (
    PytestOutputExtractor,
)
from src.pytest_analyzer.utils.path_resolver import PathResolver


@pytest.fixture
def path_resolver():
    """Provide a PathResolver instance for testing."""
    return PathResolver()


@pytest.fixture
def extractor(path_resolver):
    """Provide a PytestOutputExtractor instance for testing."""
    return PytestOutputExtractor(path_resolver=path_resolver)


@pytest.fixture
def sample_pytest_output():
    """Sample pytest output with failures."""
    return """
============================= test session starts ==============================
platform linux -- Python 3.8.10, pytest-7.0.1, pluggy-1.0.0
rootdir: /home/user/myproject
plugins: cov-4.0.0
collected 10 items

test_module.py::test_passing PASSED                                     [ 10%]
test_module.py::test_failing FAILED                                     [ 20%]
test_module.py::test_error ERROR                                        [ 30%]
other_module.py::test_other PASSED                                      [ 40%]
...

================================== FAILURES ===================================
________________________________ test_failing ________________________________

    def test_failing():
>       assert 1 == 2
E       assert 1 == 2

test_module.py:25: AssertionError
_________________________________ test_error _________________________________

    def test_error():
>       raise ValueError("This is an error")
E       ValueError: This is an error

test_module.py:29: ValueError
========================= 2 failed, 8 passed in 0.12s =========================
"""


@pytest.fixture
def sample_test_file(tmp_path):
    """Create a sample test file for testing."""
    test_file = tmp_path / "test_module.py"
    content = """
def test_passing():
    assert True

def test_failing():
    assert 1 == 2

def test_error():
    raise ValueError("This is an error")
"""
    test_file.write_text(content)
    return test_file


def test_extract_failures_from_text(extractor, sample_pytest_output, monkeypatch):
    """Test extracting failures from pytest output text."""
    # Create mock test files
    from tempfile import NamedTemporaryFile

    # Create temporary files to stand in for the test files
    with NamedTemporaryFile(suffix=".py", delete=False, mode="w") as tmp_file:
        tmp_file.write("""
def test_passing():
    assert True

def test_failing():
    assert 1 == 2

def test_error():
    raise ValueError("This is an error")
""")
        test_file_path = tmp_file.name

    # Patch the path resolver to return our temp file
    def mock_resolve_path(path):
        return test_file_path

    monkeypatch.setattr(extractor.path_resolver, "resolve_path", mock_resolve_path)

    # Mock the _extract_error_details method to ensure we get the expected error types
    def mock_extract_error_details(section_text):
        if "assert 1 == 2" in section_text:
            return "AssertionError", "assert 1 == 2", section_text, 25
        elif "ValueError" in section_text:
            return "ValueError", "This is an error", section_text, 29
        else:
            return "Error", "", section_text, None

    monkeypatch.setattr(extractor, "_extract_error_details", mock_extract_error_details)

    # Also mock the _extract_test_sections method to return the expected sections
    def mock_extract_sections(text):
        return [
            (
                "test_failing",
                """
    def test_failing():
>       assert 1 == 2
E       assert 1 == 2

test_module.py:25: AssertionError""",
            ),
            (
                "test_error",
                """
    def test_error():
>       raise ValueError("This is an error")
E       ValueError: This is an error

test_module.py:29: ValueError""",
            ),
        ]

    monkeypatch.setattr(extractor, "_extract_test_sections", mock_extract_sections)

    # Also mock _extract_failed_tests to ensure we get the expected test names
    def mock_extract_failed_tests(text):
        return [("test_module.py", "test_failing"), ("test_module.py", "test_error")]

    monkeypatch.setattr(extractor, "_extract_failed_tests", mock_extract_failed_tests)

    # Extract failures
    failures = extractor.extract_failures_from_text(sample_pytest_output)

    # Verify results
    assert len(failures) == 2

    # Check failure details
    failure1 = next((f for f in failures if f.test_name == "test_failing"), None)
    assert failure1 is not None
    assert failure1.error_type == "AssertionError"
    assert "assert 1 == 2" in failure1.error_message

    failure2 = next((f for f in failures if f.test_name == "test_error"), None)
    assert failure2 is not None
    assert failure2.error_type == "ValueError"
    assert "This is an error" in failure2.error_message

    # Clean up

    os.unlink(test_file_path)


def test_extract_failures_from_file(extractor, sample_pytest_output, tmp_path):
    """Test extracting failures from a pytest output file."""
    # Create a file with sample output
    output_file = tmp_path / "pytest_output.txt"
    output_file.write_text(sample_pytest_output)

    # Extract failures
    failures = extractor.extract_failures(output_file)

    # Verify results
    assert len(failures) == 2


def test_extract_failures_with_real_file(extractor, sample_test_file, monkeypatch):
    """Test extracting failures with a real test file."""
    # Create pytest output that references the real file
    output = f"""
============================= test session starts ==============================
platform linux -- Python 3.8.10, pytest-7.0.1, pluggy-1.0.0
rootdir: /home/user/myproject
plugins: cov-4.0.0
collected 3 items

{sample_test_file.name}::test_passing PASSED                             [ 33%]
{sample_test_file.name}::test_failing FAILED                             [ 66%]
{sample_test_file.name}::test_error ERROR                               [100%]

================================== FAILURES ===================================
________________________________ test_failing ________________________________

    def test_failing():
>       assert 1 == 2
E       assert 1 == 2

{sample_test_file}:5: AssertionError
_________________________________ test_error _________________________________

    def test_error():
>       raise ValueError("This is an error")
E       ValueError: This is an error

{sample_test_file}:8: ValueError
========================= 2 failed, 1 passed in 0.12s =========================
"""

    # Patch resolve_path to return the actual test file path
    def mock_resolve_path(path):
        if path == sample_test_file.name:
            return sample_test_file
        return Path(path)

    monkeypatch.setattr(extractor.path_resolver, "resolve_path", mock_resolve_path)

    # Extract failures from the output
    failures = extractor.extract_failures_from_text(output)

    # Verify results
    assert len(failures) == 2

    # Check that relevant code was extracted
    failure1 = next(f for f in failures if f.test_name == "test_failing")
    assert failure1.line_number == 5
    assert failure1.relevant_code and "assert 1 == 2" in failure1.relevant_code

    failure2 = next(f for f in failures if f.test_name == "test_error")
    assert failure2.line_number == 8
    assert (
        failure2.relevant_code
        and 'raise ValueError("This is an error")' in failure2.relevant_code
    )


def test_extract_failures_empty_output(extractor):
    """Test extracting failures from empty output."""
    failures = extractor.extract_failures_from_text("")
    assert len(failures) == 0


def test_extract_failures_no_failures(extractor):
    """Test extracting failures from output with no failures."""
    output = """
============================= test session starts ==============================
platform linux -- Python 3.8.10, pytest-7.0.1, pluggy-1.0.0
rootdir: /home/user/myproject
plugins: cov-4.0.0
collected 3 items

test_module.py::test_passing PASSED                                     [ 33%]
test_module.py::test_other PASSED                                      [ 66%]
test_module.py::test_third PASSED                                     [100%]

========================= 3 passed in 0.12s =========================
"""
    failures = extractor.extract_failures_from_text(output)
    assert len(failures) == 0


def test_handle_missing_section(extractor):
    """Test handling a missing detailed section for a failed test."""
    output = """
============================= test session starts ==============================
platform linux -- Python 3.8.10, pytest-7.0.1, pluggy-1.0.0
rootdir: /home/user/myproject
plugins: cov-4.0.0
collected 2 items

test_module.py::test_passing PASSED                                     [ 50%]
test_module.py::test_failing FAILED                                    [100%]

========================= 1 failed, 1 passed in 0.12s =========================
"""
    failures = extractor.extract_failures_from_text(output)
    assert len(failures) == 1
    assert failures[0].test_name == "test_failing"
    assert failures[0].error_type == "Unknown"


def test_extract_method_with_text(extractor, sample_pytest_output, monkeypatch):
    """Test extract method with text input."""
    # Mock the path resolver to return our temp file for any input
    from tempfile import NamedTemporaryFile

    # Create temporary files to stand in for the test files
    with NamedTemporaryFile(suffix=".py", delete=False, mode="w") as tmp_file:
        tmp_file.write("""
def test_passing():
    assert True

def test_failing():
    assert 1 == 2

def test_error():
    raise ValueError("This is an error")
""")
        test_file_path = tmp_file.name

    # Patch the path resolver to return our temp file
    def mock_resolve_path(path):
        return test_file_path

    monkeypatch.setattr(extractor.path_resolver, "resolve_path", mock_resolve_path)

    # Extract failures using extract method with text input
    result = extractor.extract(sample_pytest_output)

    # Verify results
    assert "failures" in result
    assert "count" in result
    assert "source" in result
    assert result["source"] == "text"
    assert result["count"] > 0

    # Clean up
    os.unlink(test_file_path)


def test_extract_method_with_file(extractor, sample_pytest_output, tmp_path):
    """Test extract method with a file path."""
    # Create a file with sample output
    output_file = tmp_path / "pytest_output.txt"
    output_file.write_text(sample_pytest_output)

    # Extract failures using extract method with file path
    result = extractor.extract(output_file)

    # Verify results
    assert "failures" in result
    assert "count" in result
    assert "source" in result
    assert result["source"] == str(output_file)
    assert result["count"] > 0


def test_extract_method_with_string_path(extractor, sample_pytest_output, tmp_path):
    """Test extract method with a string path."""
    # Create a file with sample output
    output_file = tmp_path / "pytest_output.txt"
    output_file.write_text(sample_pytest_output)

    # Extract failures using extract method with string path
    result = extractor.extract(str(output_file))

    # Verify results
    assert "failures" in result
    assert "count" in result
    assert "source" in result
    assert result["source"] == str(output_file)
    assert result["count"] > 0


def test_extract_method_nonexistent_file(extractor):
    """Test extract method with a nonexistent file."""
    # For a nonexistent file, the extract method tries to treat it as direct content
    # Since this is just a path string that doesn't exist, it will try to parse it as pytest output
    # It should return an empty result, not raise an exception
    result = extractor.extract("/nonexistent/path.txt")
    assert result["count"] == 0
    assert result["failures"] == []
    assert result["source"] == "text"


def test_extract_method_invalid_input(extractor):
    """Test extract method with invalid input type."""
    # Pass an invalid input type
    with pytest.raises(ExtractionError) as exc_info:
        extractor.extract(123)  # Integer is not a valid input type

    assert "Unsupported test_results type" in str(exc_info.value)
