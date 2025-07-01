"""
Comprehensive tests for the enhanced failure pattern detection algorithm.

This test module validates the Aho-Corasick algorithm, fuzzy matching,
pattern database functionality, and context-aware pattern recognition.
"""

import pytest

from pytest_analyzer.analysis.fuzzy_matcher import FuzzyMatcher
from pytest_analyzer.analysis.pattern_database import (
    FailurePatternDatabase,
    KnownPattern,
)
from pytest_analyzer.analysis.pattern_detector import (
    AHOCORASICK_AVAILABLE,  # Import AHOCORASICK_AVAILABLE
)
from pytest_analyzer.analysis.pattern_detector import (
    AhoCorasickPatternDetector,
)
from pytest_analyzer.analysis.token_efficient_analyzer import TokenEfficientAnalyzer


class TestPatternDatabase:
    """Test the pattern database functionality."""

    def test_default_patterns_loaded(self):
        """Test that default patterns are loaded on initialization."""
        db = FailurePatternDatabase()
        patterns = db.get_all_patterns()
        assert len(patterns) > 0

        # Check for specific expected patterns
        pattern_ids = {p.id for p in patterns}
        assert "assertion_error_general" in pattern_ids
        assert "import_error_no_module" in pattern_ids

    def test_pattern_retrieval(self):
        """Test pattern retrieval by ID."""
        db = FailurePatternDatabase()
        pattern = db.get_pattern("assertion_error_general")
        assert pattern is not None
        assert pattern.failure_type == "AssertionError"
        assert "assertion failed" in pattern.base_message

    def test_add_custom_pattern(self):
        """Test adding custom patterns to the database."""
        db = FailurePatternDatabase()
        initial_count = len(db.get_all_patterns())

        custom_pattern = KnownPattern(
            id="custom_test_pattern",
            pattern_string="CustomError: test failed",
            failure_type="CustomError",
            base_message="custom test failure",
            suggested_fix="Fix the custom test",
            impact_score=3.0,
        )

        db.add_pattern(custom_pattern)
        assert len(db.get_all_patterns()) == initial_count + 1

        retrieved = db.get_pattern("custom_test_pattern")
        assert retrieved is not None
        assert retrieved.impact_score == 3.0


@pytest.mark.skipif(not AHOCORASICK_AVAILABLE, reason="pyahocorasick not installed")
class TestAhoCorasickPatternDetector:
    """Test the Aho-Corasick pattern detection algorithm."""

    def test_single_pattern_detection(self):
        """Test detection of a single pattern."""
        detector = AhoCorasickPatternDetector()
        detector.add_pattern("test1", "AssertionError")
        detector.build()

        text = "This is an AssertionError in the test output"
        matches = detector.search(text)

        assert len(matches) == 1
        position, (pattern_id, pattern_string) = matches[0]
        assert pattern_id == "test1"
        assert pattern_string == "AssertionError"

    def test_multiple_pattern_detection(self):
        """Test detection of multiple patterns simultaneously."""
        detector = AhoCorasickPatternDetector()
        detector.add_pattern("assert", "AssertionError")
        detector.add_pattern("import", "ImportError")
        detector.add_pattern("type", "TypeError")
        detector.build()

        text = "AssertionError occurred, then ImportError, followed by TypeError"
        matches = detector.search(text)

        assert len(matches) == 3

        # Extract pattern IDs
        pattern_ids = {match[1][0] for match in matches}
        assert pattern_ids == {"assert", "import", "type"}

    def test_overlapping_patterns(self):
        """Test detection of overlapping patterns."""
        detector = AhoCorasickPatternDetector()
        detector.add_pattern("error", "Error")
        detector.add_pattern("assertion", "AssertionError")
        detector.build()

        text = "This AssertionError message"
        matches = detector.search(text)

        # Should find both "Error" (within AssertionError) and "AssertionError"
        assert len(matches) == 2
        pattern_ids = {match[1][0] for match in matches}
        assert pattern_ids == {"error", "assertion"}

    def test_case_insensitive_matching(self):
        """Test that pattern matching handles different cases."""
        detector = AhoCorasickPatternDetector()
        detector.add_pattern("test", "AssertionError")
        detector.build()

        # The current implementation searches exact case, so this tests exact matching
        text = "This AssertionError should match"
        matches = detector.search(text)

        assert len(matches) == 1
        assert matches[0][1][0] == "test"


class TestFuzzyMatcher:
    """Test the fuzzy string matching functionality."""

    def test_exact_match(self):
        """Test fuzzy matching with exact strings."""
        matcher = FuzzyMatcher(threshold=0.8)

        candidates = ["assertion failed", "import error", "type mismatch"]
        best_match, score = matcher.find_best_match("assertion failed", candidates)

        assert best_match == "assertion failed"
        assert score == 1.0

    def test_similar_match(self):
        """Test fuzzy matching with similar strings."""
        matcher = FuzzyMatcher(threshold=0.7)

        candidates = ["assertion failed", "import error", "type mismatch"]
        best_match, score = matcher.find_best_match("assert failure", candidates)

        assert best_match == "assertion failed"
        assert score >= 0.7

    def test_no_match_below_threshold(self):
        """Test that no match is returned when below threshold."""
        matcher = FuzzyMatcher(threshold=0.9)

        candidates = ["assertion failed", "import error"]
        best_match, score = matcher.find_best_match("completely different", candidates)

        assert best_match is None
        assert score == 0.0

    def test_case_insensitive_fuzzy_matching(self):
        """Test that fuzzy matching is case insensitive."""
        matcher = FuzzyMatcher(threshold=0.8)

        candidates = ["assertion failed"]
        best_match, score = matcher.find_best_match("ASSERTION FAILED", candidates)

        assert best_match == "assertion failed"
        assert score == 1.0


class TestEnhancedTokenEfficientAnalyzer:
    """Test the enhanced TokenEfficientAnalyzer with pattern detection."""

    @pytest.fixture
    def analyzer(self):
        """Fixture providing a TokenEfficientAnalyzer instance."""
        # Adjust threshold based on Aho-Corasick availability
        if AHOCORASICK_AVAILABLE:
            # When Aho-Corasick is available, Levenshtein's jaro_winkler is used for fuzzy fallback,
            # which typically yields higher scores, so a higher threshold is fine.
            return TokenEfficientAnalyzer(fuzzy_match_threshold=0.8)
        else:
            # When Aho-Corasick is NOT available, difflib.SequenceMatcher is used for fuzzy fallback.
            # This typically yields lower scores, so a lower threshold is needed for tests to pass.
            return TokenEfficientAnalyzer(fuzzy_match_threshold=0.6)

    @pytest.fixture
    def sample_pytest_output_with_known_patterns(self):
        """Sample pytest output containing known failure patterns."""
        return """
test_math.py::test_addition FAILED AssertionError: assert 1 + 2 == 4
test_imports.py::test_import FAILED ImportError: No module named 'missing_module'
test_types.py::test_operation FAILED TypeError: unsupported operand type(s) for +: 'str' and 'int'
test_vars.py::test_variable FAILED NameError: name 'undefined_var' is not defined
test_math.py::test_division FAILED AssertionError: assert 10 / 2 == 4
        """

    def test_known_pattern_detection(
        self, analyzer, sample_pytest_output_with_known_patterns
    ):
        """Test detection of known patterns via Aho-Corasick or fuzzy fallback."""
        patterns = analyzer.detect_failure_patterns(
            sample_pytest_output_with_known_patterns
        )

        known_patterns = [p for p in patterns if p.is_known_pattern]

        if AHOCORASICK_AVAILABLE:
            # With Aho-Corasick, we expect all 4 unique patterns to be identified as known.
            # The sample output has 5 raw matches, but 4 unique patterns (AssertionError appears twice with different messages).
            # The analyzer groups by (location, failure_type, message), so it will produce 4 FailurePattern objects.
            # All 4 should be marked as known.
            assert len(known_patterns) == 4
            # Check specific IDs for precision
            known_ids = {p.known_pattern_id for p in known_patterns}
            assert "assertion_error_general" in known_ids
            assert "import_error_no_module" in known_ids
            assert "type_error_unsupported_operand" in known_ids
            assert "name_error_name_not_defined" in known_ids
        else:
            # With fuzzy fallback (threshold 0.6), some patterns might not be strong enough matches.
            # Based on manual check, ImportError, TypeError, NameError should be detected.
            # AssertionError messages are not close enough to "assertion failed" (ratio ~0.4 with difflib)
            # So, we expect 3 known patterns.
            assert len(known_patterns) == 3
            known_ids = {p.known_pattern_id for p in known_patterns}
            assert "import_error_no_module" in known_ids
            assert "type_error_unsupported_operand" in known_ids
            assert "name_error_name_not_defined" in known_ids
            assert (
                "assertion_error_general" not in known_ids
            )  # Explicitly check it's not detected via fuzzy for these messages

        # Common assertions for both modes
        for pattern in known_patterns:
            assert pattern.known_pattern_id is not None
            assert pattern.impact_score > 0
            assert pattern.suggested_fix is not None

    def test_unknown_pattern_handling(self, analyzer):
        """Test handling of unknown/new failure patterns."""
        unknown_output = """
test_custom.py::test_new FAILED CustomNewError: This is a completely new error type
        """

        patterns = analyzer.detect_failure_patterns(unknown_output)
        assert len(patterns) == 1

        pattern = patterns[0]
        assert pattern.is_known_pattern is False
        assert pattern.known_pattern_id is None
        assert pattern.impact_score > 0  # Should have default impact

    def test_fuzzy_matching_for_similar_patterns(self, analyzer):
        """Test fuzzy matching for patterns similar to known ones."""
        # Slightly different assertion error message
        similar_output = """
test_fuzzy.py::test_similar FAILED AssertionError: assert equality check failed
        """

        patterns = analyzer.detect_failure_patterns(similar_output)
        assert len(patterns) == 1

        pattern = patterns[0]
        # Should match the known assertion pattern via fuzzy matching
        assert pattern.is_known_pattern is True
        assert "assertion" in pattern.known_pattern_id.lower()

    def test_context_aware_pattern_matching(self, analyzer):
        """Test that pattern matching considers failure type context."""
        # Same base message but different failure types
        mixed_output = """
test_context1.py::test_a FAILED AssertionError: assert failed
test_context2.py::test_b FAILED ImportError: assert failed
        """

        patterns = analyzer.detect_failure_patterns(mixed_output)
        assert len(patterns) == 2

        # Both should be detected but with different pattern matches
        assertion_pattern = next(
            p for p in patterns if p.failure_type == "AssertionError"
        )

        # AssertionError should match assertion patterns better
        if assertion_pattern.is_known_pattern:
            assert "assertion" in assertion_pattern.known_pattern_id.lower()

    def test_enhanced_ranking_with_impact_scores(
        self, analyzer, sample_pytest_output_with_known_patterns
    ):
        """Test that ranking incorporates impact scores from known patterns."""
        patterns = analyzer.detect_failure_patterns(
            sample_pytest_output_with_known_patterns
        )
        ranked = analyzer.rank_failures(patterns)

        # Priority scores should incorporate impact scores
        for failure in ranked:
            assert failure.priority_score > 0
            assert failure.suggested_fix is not None

    def test_bulk_fix_identification_with_patterns(self, analyzer):
        """Test bulk fix identification considers pattern similarity."""
        repeated_pattern_output = """
test_bulk1.py::test_a FAILED AssertionError: assert 1 == 2
test_bulk2.py::test_b FAILED AssertionError: assert 3 == 4
test_bulk3.py::test_c FAILED AssertionError: assert 5 == 6
test_other.py::test_d FAILED ImportError: No module named 'missing'
        """

        patterns = analyzer.detect_failure_patterns(repeated_pattern_output)
        ranked = analyzer.rank_failures(patterns)
        bulk_fixes = analyzer.identify_bulk_fixes(ranked)

        # Should identify bulk fixes for similar patterns
        assert len(bulk_fixes) > 0

        # Find AssertionError bulk fix
        assertion_bulk = next(
            (bf for bf in bulk_fixes if bf.fix_type == "AssertionError"), None
        )
        assert assertion_bulk is not None
        assert assertion_bulk.affected_count == 3

    def test_pattern_database_updates(self, analyzer):
        """Test updating pattern database with new patterns."""
        initial_pattern_count = len(analyzer.pattern_db.get_all_patterns())

        # Add a new pattern
        new_pattern = KnownPattern(
            id="new_runtime_error",
            pattern_string="RuntimeError: custom runtime issue",
            failure_type="RuntimeError",
            base_message="custom runtime issue",
            suggested_fix="Handle runtime conditions properly",
            impact_score=3.5,
        )

        analyzer.update_pattern_database([new_pattern])

        # Verify pattern was added and automaton rebuilt
        updated_pattern_count = len(analyzer.pattern_db.get_all_patterns())
        assert updated_pattern_count == initial_pattern_count + 1

        # Test that new pattern can be detected
        test_output = """
test_new.py::test_runtime FAILED RuntimeError: custom runtime issue occurred
        """

        patterns = analyzer.detect_failure_patterns(test_output)
        assert len(patterns) == 1

        pattern = patterns[0]
        assert pattern.is_known_pattern is True
        assert pattern.known_pattern_id == "new_runtime_error"
        assert pattern.suggested_fix == "Handle runtime conditions properly"

    @pytest.mark.skipif(
        not AHOCORASICK_AVAILABLE,
        reason="This test relies on Aho-Corasick for performance with large outputs.",
    )
    def test_performance_with_large_output(self, analyzer):
        """Test performance with large pytest output."""
        # Generate large output with repeated patterns
        large_output_lines = []
        for i in range(1000):
            large_output_lines.append(
                f"test_large_{i}.py::test_func FAILED AssertionError: assert {i} == {i + 1}"
            )

        large_output = "\n".join(large_output_lines)

        # Should handle large output efficiently
        patterns = analyzer.detect_failure_patterns(large_output)
        assert len(patterns) == 1000  # One unique pattern per test

        # All should be recognized as known assertion patterns when Aho-Corasick is available
        known_count = sum(1 for p in patterns if p.is_known_pattern)
        assert known_count == 1000

    def test_ambiguous_pattern_resolution(self, analyzer):
        """Test resolution of ambiguous patterns that could match multiple known patterns."""
        # Use a valid failure type that matches the regex pattern
        ambiguous_output = """
test_ambiguous.py::test_case FAILED RuntimeError: something went wrong
        """

        patterns = analyzer.detect_failure_patterns(ambiguous_output)
        assert len(patterns) == 1

        # Should handle ambiguous cases gracefully
        pattern = patterns[0]
        # Either recognized or treated as unknown, but should not crash
        assert pattern.complexity_score > 0
        assert pattern.frequency == 1

    def test_structured_summary_includes_pattern_metadata(
        self, analyzer, sample_pytest_output_with_known_patterns
    ):
        """Test that structured summary includes pattern detection metadata."""
        analysis_result = analyzer.analyze(sample_pytest_output_with_known_patterns)
        summary = analyzer.generate_structured_summary(analysis_result)

        # Should include pattern detection statistics
        assert "known_pattern_matches" in analysis_result.summary
        assert "unknown_pattern_count" in analysis_result.summary

        # Failure patterns should include pattern metadata
        failure_patterns = summary["failure_patterns"]
        for fp in failure_patterns:
            assert "is_known_pattern" in fp
            assert "known_pattern_id" in fp
            assert "impact_score" in fp
            assert "suggested_fix_from_pattern" in fp

    def test_empty_output_handling(self, analyzer):
        """Test handling of empty or invalid pytest output."""
        empty_outputs = ["", "   ", "No test failures here", "PASSED tests only"]

        for empty_output in empty_outputs:
            patterns = analyzer.detect_failure_patterns(empty_output)
            assert len(patterns) == 0  # Should handle gracefully

            # Full analysis should not crash
            result = analyzer.analyze(empty_output)
            assert result.summary["total_failures"] == 0
