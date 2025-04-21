"""Pytest configuration for end-to-end tests."""

import pytest
import sys
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

# Add the src directory to the Python path for imports
sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

# Import from the package


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client for testing."""
    mock_client = MagicMock()
    mock_client.messages.create.return_value.content = [
        MagicMock(text="This is a mock LLM response.")
    ]
    return mock_client


@pytest.fixture
def mock_llm_response():
    """Create a mock LLM response for testing."""
    return """```json
[
    {
        "suggestion": "E2E LLM suggestion",
        "confidence": 0.9,
        "explanation": "Mock LLM explanation from E2E test",
        "code_changes": {
            "fixed_code": "def test_simple_fail():\\n    x = 1\\n    y = 1\\n    assert x == y, \\"Values are equal\\""
        }
    }
]
```"""


@pytest.fixture
def sample_assertion_file(tmp_path):
    """Create a sample pytest file with an assertion error."""
    # Create the test file
    test_file = tmp_path / "test_assertion.py"
    test_file.write_text("""
import pytest

def test_assertion_error():
    x = 1
    y = 2
    assert x == y, "Values are not equal"
""")
    return test_file


@pytest.fixture
def sample_import_error_file(tmp_path):
    """Create a sample pytest file with an import error."""
    # Create the test file
    test_file = tmp_path / "test_import.py"
    test_file.write_text("""
import pytest
import nonexistent_module

def test_function():
    assert True
""")
    return test_file


@pytest.fixture
def sample_syntax_error_file(tmp_path):
    """Create a sample pytest file with a syntax error."""
    # Create the test file
    test_file = tmp_path / "test_syntax.py"
    test_file.write_text("""
import pytest

def test_syntax_error():
    # Missing closing parenthesis
    print("Hello world"
""")
    return test_file


@pytest.fixture
def sample_json_report(tmp_path):
    """Create a sample JSON report file."""
    report_file = tmp_path / "report.json"
    content = """{
  "created": 1712621338.818604,
  "duration": 0.01588892936706543,
  "exitcode": 1,
  "root": "/tmp/pytest-of-user/pytest-1/test0",
  "summary": {
    "failed": 1,
    "total": 1
  },
  "tests": [
    {
      "nodeid": "test_assertion.py::test_assertion_error",
      "lineno": 4,
      "outcome": "failed",
      "message": "AssertionError: Values are not equal\\nassert 1 == 2",
      "duration": 0.00019192695617675781,
      "call": {
        "traceback": [
          {
            "path": "test_assertion.py",
            "lineno": 6,
            "message": "AssertionError: Values are not equal"
          }
        ]
      }
    }
  ]
}"""
    report_file.write_text(content)
    return report_file


class MockProcess:
    """Mock subprocess result."""

    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


@pytest.fixture
def patch_subprocess(monkeypatch):
    """Patch subprocess.run for testing."""

    def mock_run(cmd, *args, **kwargs):
        # Record the command that was executed
        mock_run.last_command = cmd

        # Return a success result by default
        return MockProcess(returncode=0, stdout="Test output", stderr="")

    # Initialize the last_command attribute
    mock_run.last_command = None

    # Apply the monkeypatch
    monkeypatch.setattr(subprocess, "run", mock_run)

    return mock_run
