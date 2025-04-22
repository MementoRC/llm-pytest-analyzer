"""Pytest configuration for the pytest_analyzer tests."""

import sys
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

from pytest_analyzer.core.models.pytest_failure import FixSuggestion, PytestFailure


# Register custom markers
def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "e2e: mark test as an end-to-end test")


@pytest.fixture(scope="function")
def create_test_project(tmp_path):
    """Factory fixture to create test projects in a temp directory."""
    created_projects = []

    def _create_project(
        name: str, test_content: str, setup_content: Optional[str] = None
    ):
        project_dir = tmp_path / name
        project_dir.mkdir()
        test_file = project_dir / f"test_{name}.py"
        test_file.write_text(test_content)

        if setup_content:
            setup_file = project_dir / "conftest.py"  # Or setup file if needed
            setup_file.write_text(setup_content)

        created_projects.append(project_dir)
        return project_dir

    yield _create_project

    # Optional cleanup if needed beyond tmp_path's automatic cleanup
    # for project in created_projects:
    #     if project.exists():
    #         shutil.rmtree(project)


# --- Specific Project Fixtures (using the factory) ---


@pytest.fixture
def project_assertion_failure(create_test_project):
    content = """
import pytest

def test_simple_fail():
    x = 1
    y = 2
    assert x == y, "Values are not equal"
"""
    return create_test_project("assertion_fail", content)


@pytest.fixture
def project_import_error(create_test_project):
    content = """
import pytest
import non_existent_module

def test_import_fail():
    assert True # This test body might not even be reached
"""
    return create_test_project("import_error", content)


@pytest.fixture
def project_fixture_error(create_test_project):
    setup_content = """
import pytest

@pytest.fixture
def failing_fixture():
    raise ValueError("Setup failed in fixture")
    # yield # In case it's a yield fixture
"""
    test_content = """
import pytest

def test_using_failing_fixture(failing_fixture):
    assert True
"""
    return create_test_project("fixture_error", test_content, setup_content)


@pytest.fixture
def project_no_failures(create_test_project):
    content = """
import pytest

def test_simple_pass():
    assert 1 == 1
"""
    return create_test_project("passing", content)


@pytest.fixture
def project_mixed_failures(create_test_project):
    content = """
import pytest

def test_another_fail():
    assert False # Assertion Error

def test_pass():
    assert 1 == 1
"""
    return create_test_project("mixed_failures", content)


# --- Sample report files ---

SAMPLE_REPORTS_DIR = Path(__file__).parent / "sample_reports"


# Helper to create sample report files if they don't exist
def create_sample_report(file_path, content):
    if not file_path.exists():
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)


# JSON report for assertion failure
@pytest.fixture
def report_assertion_json():
    file_path = SAMPLE_REPORTS_DIR / "assertion_fail_report.json"
    content = """{
  "created": 1712621338.818604,
  "duration": 0.01588892936706543,
  "exitcode": 1,
  "root": "/tmp/pytest-of-user/pytest-1/assertion_fail0",
  "summary": {
    "failed": 1,
    "total": 1
  },
  "tests": [
    {
      "nodeid": "test_assertion_fail.py::test_simple_fail",
      "lineno": 4,
      "outcome": "failed",
      "message": "AssertionError: Values are not equal\\nassert 1 == 2",
      "duration": 0.00019192695617675781,
      "call": {
        "traceback": [
          {
            "path": "test_assertion_fail.py",
            "lineno": 7,
            "message": "AssertionError: Values are not equal"
          }
        ]
      }
    }
  ]
}"""
    create_sample_report(file_path, content)
    return file_path


# XML report for assertion failure
@pytest.fixture
def report_assertion_xml():
    file_path = SAMPLE_REPORTS_DIR / "assertion_fail_report.xml"
    content = """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" errors="0" failures="1" skipped="0" tests="1" time="0.016">
    <testcase classname="test_assertion_fail" name="test_simple_fail" time="0.000">
      <failure message="AssertionError: Values are not equal&#10;assert 1 == 2">def test_simple_fail():
    x = 1
    y = 2
&gt;   assert x == y, "Values are not equal"
E   AssertionError: Values are not equal
E   assert 1 == 2

test_assertion_fail.py:7: AssertionError</failure>
    </testcase>
  </testsuite>
</testsuites>"""
    create_sample_report(file_path, content)
    return file_path


# JSON report for import error
@pytest.fixture
def report_import_error_json():
    file_path = SAMPLE_REPORTS_DIR / "import_error_report.json"
    content = """{
  "created": 1712621338.818604,
  "duration": 0.01588892936706543,
  "exitcode": 1,
  "root": "/tmp/pytest-of-user/pytest-1/import_error0",
  "summary": {
    "failed": 1,
    "total": 1,
    "collected": 0
  },
  "tests": [],
  "collectors": [
    {
      "nodeid": "",
      "outcome": "failed",
      "message": "ImportError: No module named 'non_existent_module'",
      "longrepr": "ImportError while importing test module '/tmp/pytest-of-user/pytest-1/import_error0/test_import_error.py'.\nHint: make sure your test modules/packages have valid Python names.\nTraceback:\n/usr/lib/python3.9/importlib/__init__.py:127: in import_module\n    return _bootstrap._gcd_import(name[level:], package, level)\ntest_import_error.py:2: in <module>\n    import non_existent_module\nE   ModuleNotFoundError: No module named 'non_existent_module'"
    }
  ]
}"""
    create_sample_report(file_path, content)
    return file_path


# JSON report for passing tests
@pytest.fixture
def report_passing_json():
    file_path = SAMPLE_REPORTS_DIR / "passing_report.json"
    content = """{
  "created": 1712621338.818604,
  "duration": 0.01588892936706543,
  "exitcode": 0,
  "root": "/tmp/pytest-of-user/pytest-1/passing0",
  "summary": {
    "failed": 0,
    "total": 1,
    "passed": 1
  },
  "tests": [
    {
      "nodeid": "test_passing.py::test_simple_pass",
      "lineno": 4,
      "outcome": "passed",
      "duration": 0.00019192695617675781
    }
  ]
}"""
    create_sample_report(file_path, content)
    return file_path


# Mock LLM analyzer fixture
@pytest.fixture
def mock_llm_client():
    """Mocks the LLM client for testing."""
    mock_client = MagicMock()

    # Configure the mock to return predefined responses
    mock_response = MagicMock()
    mock_response.content = [
        MagicMock(text="LLM Suggestion: This is a mock LLM suggestion.")
    ]
    mock_client.messages.create.return_value = mock_response

    return mock_client


@pytest.fixture
def mock_llm_suggester():
    """Provides a patched LLMSuggester that uses a mock client."""
    with patch(
        "pytest_analyzer.core.analysis.llm_suggester.LLMSuggester._get_llm_request_function"
    ) as mock_func:
        mock_func.return_value = (
            lambda prompt: "LLM Suggestion: This is a mock LLM response for: "
            + prompt[:20]
            + "..."
        )
        yield


# Test failures and suggestions fixtures
@pytest.fixture
def test_failure():
    """Provide a PytestFailure instance for testing."""
    return PytestFailure(
        test_name="test_file.py::test_function",
        test_file="test_file.py",
        error_type="AssertionError",
        error_message="assert 1 == 2",
        traceback="E       assert 1 == 2\nE       +  where 1 = func()",
        line_number=42,
        relevant_code="def test_function():\n    assert 1 == 2",
    )


@pytest.fixture
def test_suggestion(test_failure):
    """Fixture for a test suggestion."""
    return FixSuggestion(
        failure=test_failure,
        suggestion="Fix the assertion to expect 1 instead of 2",
        confidence=0.8,
        explanation="The test expected 2 but got 1",
    )


@pytest.fixture
def llm_suggestion(test_failure):
    """Fixture for an LLM-based suggestion."""
    return FixSuggestion(
        failure=test_failure,
        suggestion="Use assertEqual(1, 2) for better error messages",
        confidence=0.9,
        explanation="Using assertEqual provides more detailed failure output",
        code_changes={
            "source": "llm",
            "fixed_code": "def test_function():\n    assertEqual(1, 2)",
        },
    )


# CLI invocation fixture
@pytest.fixture
def cli_invoke():
    """Helper fixture to invoke the CLI main function."""

    def _invoke(*args, **kwargs):
        from pytest_analyzer.cli.analyzer_cli import main

        # Save original argv
        original_argv = sys.argv.copy()

        try:
            # Set up argv for the CLI
            sys.argv = ["pytest-analyzer"] + list(args)

            # Capture output (optional)
            # TODO: Implement output capture if needed

            # Run the CLI
            result = main()

            return result
        finally:
            # Restore original argv
            sys.argv = original_argv

    return _invoke
