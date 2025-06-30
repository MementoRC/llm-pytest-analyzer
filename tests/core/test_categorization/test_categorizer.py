from pathlib import Path

import pytest

from pytest_analyzer.core.infrastructure.ci_detection import CIEnvironment
from pytest_analyzer.core.test_categorization import TestCategorizer, TestCategory


@pytest.fixture
def categorizer():
    return TestCategorizer()


@pytest.fixture
def tmp_test_file(tmp_path):
    def _make(content: str) -> Path:
        file = tmp_path / "test_sample.py"
        file.write_text(content)
        return file

    return _make


def make_ci_env(tools=None):
    return CIEnvironment(
        name="github",
        detected=True,
        available_tools=tools or [],
        missing_tools=[],
        tool_install_commands={},
    )


def test_unit_categorization(categorizer, tmp_test_file):
    content = "import os\nimport pytest\ndef test_foo():\n    assert 1"
    file = tmp_test_file(content)
    assert categorizer.categorize_test(file) == TestCategory.UNIT


def test_integration_categorization(categorizer, tmp_test_file):
    content = "import requests\ndef test_api():\n    assert True"
    file = tmp_test_file(content)
    assert categorizer.categorize_test(file) == TestCategory.INTEGRATION


def test_e2e_categorization_by_marker(categorizer, tmp_test_file):
    content = "@pytest.mark.e2e\ndef test_e2e():\n    pass"
    file = tmp_test_file(content)
    assert categorizer.categorize_test(file) == TestCategory.E2E


def test_e2e_categorization_by_import(categorizer, tmp_test_file):
    content = "import selenium\ndef test_browser(): pass"
    file = tmp_test_file(content)
    assert categorizer.categorize_test(file) == TestCategory.E2E


def test_performance_categorization(categorizer, tmp_test_file):
    content = "@pytest.mark.performance\nimport pytest_benchmark\ndef test_perf(): pass"
    file = tmp_test_file(content)
    assert categorizer.categorize_test(file) == TestCategory.PERFORMANCE


def test_security_categorization(categorizer, tmp_test_file):
    content = "@pytest.mark.security\nimport bandit\ndef test_sec(): pass"
    file = tmp_test_file(content)
    assert categorizer.categorize_test(file) == TestCategory.SECURITY


def test_functional_fallback(categorizer, tmp_test_file):
    content = "import something_custom\ndef test_func(): pass"
    file = tmp_test_file(content)
    assert categorizer.categorize_test(file) == TestCategory.FUNCTIONAL


def test_extract_tool_dependencies(categorizer, tmp_test_file):
    content = "import os\nimport requests\nfrom selenium import webdriver\n"
    file = tmp_test_file(content)
    deps = categorizer.extract_tool_dependencies(file)
    assert "requests" in deps
    assert "selenium" in deps
    assert "os" not in deps


def test_assess_ci_compatibility_true(categorizer, tmp_test_file):
    content = "import requests\ndef test_api(): pass"
    file = tmp_test_file(content)
    ci_env = make_ci_env(tools=["requests"])
    assert categorizer.assess_ci_compatibility(file, ci_env) is True


def test_assess_ci_compatibility_false(categorizer, tmp_test_file):
    content = "@pytest.mark.e2e\nimport selenium\ndef test_e2e(): pass"
    file = tmp_test_file(content)
    ci_env = make_ci_env(tools=["pytest"])
    assert categorizer.assess_ci_compatibility(file, ci_env) is False


def test_generate_skip_marker(categorizer, tmp_test_file):
    file = tmp_test_file("def test_skip(): pass")
    marker = categorizer.generate_skip_marker(file, "Not supported in CI")
    assert marker.startswith("@pytest.mark.skip")
    assert "Not supported in CI" in marker
