from pathlib import Path

import pytest

from pytest_analyzer.core.test_maintenance.test_maintainer import (
    TestMaintainer,
    TestMaintainerError,
)

SIMPLE_SOURCE = """
def add(a, b):
    return a + b

def subtract(a, b):
    return a - b
"""

SIMPLE_TEST = """
def test_add():
    assert add(1, 2) == 3

def test_subtract():
    assert subtract(2, 1) == 1

def test_orphaned():
    assert True
"""


def write_file(path: Path, content: str):
    path.write_text(content, encoding="utf-8")


@pytest.fixture
def temp_test_and_source(tmp_path):
    src = tmp_path / "math_utils.py"
    test = tmp_path / "test_math_utils.py"
    write_file(src, SIMPLE_SOURCE)
    write_file(test, SIMPLE_TEST)
    return src, test


def test_traceability_analysis(temp_test_and_source):
    src, test = temp_test_and_source
    maintainer = TestMaintainer()
    result = maintainer.analyze_traceability(test, [src])
    assert "add" in result["tested_functions"]
    assert "subtract" in result["tested_functions"]
    assert "test_orphaned" in result["orphaned_tests"]


def test_deprecated_detection(temp_test_and_source):
    src, test = temp_test_and_source
    maintainer = TestMaintainer()
    deprecated = maintainer.detect_deprecated_tests(test, [src])
    assert "test_orphaned" in deprecated


def test_effectiveness_scoring(temp_test_and_source):
    src, test = temp_test_and_source
    maintainer = TestMaintainer()
    scores = maintainer.score_test_effectiveness(
        test,
        [src],
        historical_failures={
            "test_add": 0.5,
            "test_subtract": 0.2,
            "test_orphaned": 0.0,
        },
        coverage_data={"test_add": 1.0, "test_subtract": 1.0, "test_orphaned": 0.0},
        execution_times={"test_add": 0.1, "test_subtract": 0.2, "test_orphaned": 0.1},
        maintenance_history={"test_add": 1, "test_subtract": 2, "test_orphaned": 0},
        risk_map={"add": 0.8, "subtract": 0.5},
    )
    assert any(s.score > 0 for s in scores)
    assert any(s.details["fail_rate"] == 0.5 for s in scores)


def test_llm_suggestion_handles_error(monkeypatch, temp_test_and_source):
    src, test = temp_test_and_source
    maintainer = TestMaintainer()

    def fake_generate(prompt):
        raise Exception("LLM error")

    maintainer.llm_service.generate = fake_generate
    with pytest.raises(TestMaintainerError):
        maintainer.suggest_test_refactoring(test)


def test_suite_health_metrics(temp_test_and_source):
    src, test = temp_test_and_source
    maintainer = TestMaintainer()
    metrics = maintainer.get_suite_health_metrics([test], [src])
    assert "test_count" in metrics
    assert "coverage" in metrics
