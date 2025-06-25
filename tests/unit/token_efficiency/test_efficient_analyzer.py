import pytest

from pytest_analyzer.analysis.token_efficient_analyzer import (
    AnalysisResult,
    BulkFix,
    FailurePattern,
    RankedFailure,
    TokenEfficientAnalyzer,
)


@pytest.fixture
def sample_pytest_output():
    return """
test_math.py::test_addition FAILED AssertionError: assert 1 + 2 == 3
test_math.py::test_subtraction FAILED AssertionError: assert 5 - 3 == 1
test_imports.py::test_import FAILED ImportError: No module named 'missing_module'
test_math.py::test_division FAILED AssertionError: assert 10 / 2 == 4
    """


@pytest.fixture
def analyzer():
    return TokenEfficientAnalyzer()


def test_detect_failure_patterns(analyzer, sample_pytest_output):
    patterns = analyzer.detect_failure_patterns(sample_pytest_output)
    assert isinstance(patterns, list)
    assert all(isinstance(p, FailurePattern) for p in patterns)
    # Check that all failures are detected
    assert len(patterns) == 4
    # Check that the error types are correct
    failure_types = {p.failure_type for p in patterns}
    assert "AssertionError" in failure_types
    assert "ImportError" in failure_types


def test_rank_failures(analyzer, sample_pytest_output):
    patterns = analyzer.detect_failure_patterns(sample_pytest_output)
    ranked = analyzer.rank_failures(patterns)
    assert isinstance(ranked, list)
    assert all(isinstance(r, RankedFailure) for r in ranked)
    # Should be sorted by priority_score (highest first)
    assert ranked[0].priority_score >= ranked[-1].priority_score
    # All frequencies should be 1 in this sample
    assert all(r.frequency == 1 for r in ranked)
    # Check that suggested fixes are present
    assert any(r.suggested_fix is not None for r in ranked)


def test_identify_bulk_fixes(analyzer, sample_pytest_output):
    patterns = analyzer.detect_failure_patterns(sample_pytest_output)
    ranked = analyzer.rank_failures(patterns)
    bulk_fixes = analyzer.identify_bulk_fixes(ranked)
    assert isinstance(bulk_fixes, list)
    assert all(isinstance(b, BulkFix) for b in bulk_fixes)
    # Should have bulk fix for AssertionError (3 instances)
    assert any(b.fix_type == "AssertionError" for b in bulk_fixes)
    # Check affected count is correct
    for b in bulk_fixes:
        if b.fix_type == "AssertionError":
            assert b.affected_count == 3  # 3 AssertionError failures


def test_generate_structured_summary(analyzer, sample_pytest_output):
    patterns = analyzer.detect_failure_patterns(sample_pytest_output)
    ranked = analyzer.rank_failures(patterns)
    bulk_fixes = analyzer.identify_bulk_fixes(ranked)
    analysis = AnalysisResult(
        failure_patterns=patterns,
        ranked_failures=ranked,
        bulk_fixes=bulk_fixes,
        summary={"total_failures": len(patterns)},
    )
    summary = analyzer.generate_structured_summary(analysis)
    assert isinstance(summary, dict)
    # Check that the summary contains the correct structure
    assert "failure_patterns" in summary
    assert "ranked_failures" in summary
    assert "bulk_fixes" in summary
    assert "summary" in summary
