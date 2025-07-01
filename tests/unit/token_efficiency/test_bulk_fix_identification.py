import pytest

from pytest_analyzer.analysis.token_efficient_analyzer import (
    BulkFix,
    RankedFailure,
    TokenEfficientAnalyzer,
)


@pytest.fixture
def sample_ranked_failures():
    # Simulate a set of ranked failures with different types, messages, and locations
    return [
        RankedFailure(
            failure_type="AssertionError",
            message="assert 1 + 2 == 3",
            location="test_math.py::test_addition",
            frequency=1,
            complexity_score=1.0,
            priority_score=2.0,
            suggested_fix="Check test assertions and expected values.",
        ),
        RankedFailure(
            failure_type="AssertionError",
            message="assert 5 - 3 == 1",
            location="test_math.py::test_subtraction",
            frequency=1,
            complexity_score=1.1,
            priority_score=2.1,
            suggested_fix="Check test assertions and expected values.",
        ),
        RankedFailure(
            failure_type="AssertionError",
            message="assert 10 / 2 == 4",
            location="test_math.py::test_division",
            frequency=1,
            complexity_score=1.2,
            priority_score=2.2,
            suggested_fix="Check test assertions and expected values.",
        ),
        RankedFailure(
            failure_type="ImportError",
            message="No module named 'missing_module'",
            location="test_imports.py::test_import",
            frequency=1,
            complexity_score=1.0,
            priority_score=2.0,
            suggested_fix="Check import statements and dependencies.",
        ),
        RankedFailure(
            failure_type="ImportError",
            message="No module named 'other_missing_module'",
            location="test_imports.py::test_import2",
            frequency=1,
            complexity_score=1.0,
            priority_score=2.0,
            suggested_fix="Check import statements and dependencies.",
        ),
    ]


def test_bulk_fix_clustering_and_confidence(sample_ranked_failures):
    analyzer = TokenEfficientAnalyzer()
    bulk_fixes = analyzer.identify_bulk_fixes(sample_ranked_failures)
    # Should group AssertionError and ImportError failures separately
    assert isinstance(bulk_fixes, list)
    assert all(isinstance(b, BulkFix) for b in bulk_fixes)
    # There should be at least one bulk fix for AssertionError and one for ImportError
    fix_types = {b.fix_type for b in bulk_fixes}
    assert "AssertionError" in fix_types
    assert "ImportError" in fix_types
    # Confidence and impact should be present as attributes
    for b in bulk_fixes:
        assert hasattr(b, "confidence_score")
        assert hasattr(b, "impact_prediction")
        assert hasattr(b, "fix_suggestion")
        # Confidence should be between 0.5 and 1.0
        assert 0.5 <= b.confidence_score <= 1.0


def test_bulk_fix_visualization_and_ast(sample_ranked_failures, tmp_path):
    # Create a dummy python file for AST analysis
    test_file = tmp_path / "test_math.py"
    test_file.write_text(
        "def test_addition():\n    assert 1 + 2 == 3\n"
        "def test_subtraction():\n    assert 5 - 3 == 1\n"
    )
    analyzer = TokenEfficientAnalyzer()
    bulk_fixes = analyzer.identify_bulk_fixes(
        sample_ranked_failures, codebase_paths=[str(test_file)]
    )
    for b in bulk_fixes:
        # AST analysis should be attached if codebase_paths is provided
        assert hasattr(b, "ast_analysis")
        if b.ast_analysis:
            assert str(test_file) in b.ast_analysis
            assert isinstance(b.ast_analysis[str(test_file)], list)
        # Visualization graph should be attached if networkx is available
        assert hasattr(b, "visualization_graph")


def test_apply_bulk_fix_api(sample_ranked_failures):
    analyzer = TokenEfficientAnalyzer()
    bulk_fixes = analyzer.identify_bulk_fixes(sample_ranked_failures)
    for b in bulk_fixes:
        result = analyzer.apply_bulk_fix(b)
        assert isinstance(result, dict)
        assert result["success"] is True
        assert "applied_fix_type" in result
        assert "description" in result
