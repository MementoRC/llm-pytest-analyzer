"""
Tests for the composite suggester component.

This module contains tests for the CompositeSuggester, which combines
suggestions from multiple suggester implementations.
"""

import unittest
from unittest.mock import MagicMock

from src.pytest_analyzer.core.analysis.composite_suggester import CompositeSuggester
from src.pytest_analyzer.core.models.failure_analysis import FailureAnalysis
from src.pytest_analyzer.core.models.pytest_failure import FixSuggestion, PytestFailure
from src.pytest_analyzer.core.protocols import Suggester


class TestCompositeSuggester(unittest.TestCase):
    """Test the composite suggester implementation."""

    def setUp(self):
        """Set up test fixtures."""
        # Create mock suggesters
        self.suggester1 = MagicMock(spec=Suggester)
        self.suggester2 = MagicMock(spec=Suggester)

        # Create composite suggester
        self.composite_suggester = CompositeSuggester(
            suggesters=[self.suggester1, self.suggester2],
            min_confidence=0.5,
            max_suggestions_per_failure=3,
            deduplicate=True,
        )

        # Create test failure
        self.failure = PytestFailure(
            test_name="test_example",
            test_file="test_file.py",
            error_type="AssertionError",
            error_message="Expected 1 but got 2",
            traceback="traceback",
            line_number=10,
            relevant_code="assert 1 == 2",
        )

        # Create test analysis
        self.analysis = FailureAnalysis(
            failure=self.failure,
            root_cause="Values differ",
            error_type="AssertionError",
            suggested_fixes=["The test expected 1 but got 2"],
        )

        # Create test suggestions
        self.suggestion1 = FixSuggestion(
            failure=self.failure,
            suggestion="Change expected value to 2",
            confidence=0.8,
            explanation="Update the test to expect 2 instead of 1",
            code_changes={"type": "update_test"},
        )

        self.suggestion2 = FixSuggestion(
            failure=self.failure,
            suggestion="Change implementation to return 1",
            confidence=0.7,
            explanation="Update the implementation to return 1",
            code_changes={"type": "update_implementation"},
        )

        # Duplicate of suggestion1 but with different confidence
        self.suggestion3 = FixSuggestion(
            failure=self.failure,
            suggestion="Change expected value to 2",
            confidence=0.6,
            explanation="Update the test to expect 2 instead of 1",
            code_changes={"type": "update_test"},
        )

        # Low confidence suggestion that should be filtered
        self.suggestion4 = FixSuggestion(
            failure=self.failure,
            suggestion="Low confidence suggestion",
            confidence=0.4,
            explanation="This should be filtered out",
            code_changes={},
        )

    def test_suggest_fix(self):
        """Test suggesting fixes for a specific failure."""
        # Configure mock suggesters
        self.suggester1.suggest_fix.return_value = [self.suggestion1, self.suggestion4]
        self.suggester2.suggest_fix.return_value = [self.suggestion2, self.suggestion3]

        # Call suggest_fix
        results = self.composite_suggester.suggest_fix(self.failure, self.analysis)

        # Verify suggesters were called with correct parameters
        self.suggester1.suggest_fix.assert_called_once_with(self.failure, self.analysis)
        self.suggester2.suggest_fix.assert_called_once_with(self.failure, self.analysis)

        # Verify results
        self.assertEqual(
            len(results), 2
        )  # Suggestion 3 is a duplicate of 1, and 4 is filtered out

        # Verify suggestions are sorted by confidence (descending)
        self.assertEqual(results[0].confidence, 0.8)
        self.assertEqual(results[1].confidence, 0.7)

        # Verify duplicates were removed
        suggestions = [s.suggestion for s in results]
        self.assertEqual(len(set(suggestions)), 2)  # Two unique suggestions
        self.assertIn("Change expected value to 2", suggestions)
        self.assertIn("Change implementation to return 1", suggestions)

    def test_suggest(self):
        """Test suggesting fixes for analysis results."""
        # Create analysis results
        analysis_results = {
            "analyses": [
                {
                    "failure": {
                        "test_name": "test_example",
                        "test_file": "test_file.py",
                        "error_type": "AssertionError",
                        "error_message": "Expected 1 but got 2",
                    },
                    "analysis": {
                        "root_cause": "Values differ",
                        "error_type": "AssertionError",
                        "explanation": "The test expected 1 but got 2",
                    },
                }
            ]
        }

        # Configure mock suggesters
        self.suggester1.suggest.return_value = [
            {
                "suggestion": "Change expected value to 2",
                "confidence": 0.8,
                "explanation": "Update the test to expect 2 instead of 1",
                "code_changes": {"type": "update_test"},
                "failure": {"test_name": "test_example"},
            },
            {
                "suggestion": "Low confidence suggestion",
                "confidence": 0.4,
                "explanation": "This should be filtered out",
                "code_changes": {},
                "failure": {"test_name": "test_example"},
            },
        ]

        self.suggester2.suggest.return_value = [
            {
                "suggestion": "Change implementation to return 1",
                "confidence": 0.7,
                "explanation": "Update the implementation to return 1",
                "code_changes": {"type": "update_implementation"},
                "failure": {"test_name": "test_example"},
            },
            {
                "suggestion": "Change expected value to 2",
                "confidence": 0.6,
                "explanation": "Update the test to expect 2 instead of 1",
                "code_changes": {"type": "update_test"},
                "failure": {"test_name": "test_example"},
            },
        ]

        # Call suggest
        results = self.composite_suggester.suggest(analysis_results)

        # Verify suggesters were called with correct parameters
        self.suggester1.suggest.assert_called_once_with(analysis_results)
        self.suggester2.suggest.assert_called_once_with(analysis_results)

        # Verify results
        self.assertEqual(len(results), 2)  # One is a duplicate, and one is filtered out

        # Verify suggestions are included
        suggestions = [r["suggestion"] for r in results]
        self.assertIn("Change expected value to 2", suggestions)
        self.assertIn("Change implementation to return 1", suggestions)

        # Verify low confidence suggestion was filtered out
        self.assertNotIn("Low confidence suggestion", suggestions)

    def test_error_handling(self):
        """Test error handling when a suggester fails."""
        # Configure first suggester to raise an exception
        self.suggester1.suggest_fix.side_effect = Exception("Test error")
        self.suggester2.suggest_fix.return_value = [self.suggestion2]

        # Call suggest_fix
        results = self.composite_suggester.suggest_fix(self.failure, self.analysis)

        # Verify second suggester was still called
        self.suggester2.suggest_fix.assert_called_once_with(self.failure, self.analysis)

        # Verify results from second suggester are returned
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].suggestion, "Change implementation to return 1")

    def test_empty_suggesters(self):
        """Test with empty list of suggesters."""
        empty_suggester = CompositeSuggester(suggesters=[])

        # Call suggest_fix
        results = empty_suggester.suggest_fix(self.failure, self.analysis)

        # Verify empty list is returned
        self.assertEqual(len(results), 0)

    def test_no_deduplication(self):
        """Test without deduplication."""
        # Create a composite suggester with deduplication disabled
        no_dedup_suggester = CompositeSuggester(
            suggesters=[self.suggester1, self.suggester2],
            min_confidence=0.5,
            deduplicate=False,
        )

        # Configure mock suggesters
        self.suggester1.suggest_fix.return_value = [self.suggestion1]
        self.suggester2.suggest_fix.return_value = [
            self.suggestion3
        ]  # Duplicate of suggestion1

        # Call suggest_fix
        results = no_dedup_suggester.suggest_fix(self.failure, self.analysis)

        # Verify both suggestions are included (no deduplication)
        self.assertEqual(len(results), 2)

    def test_max_suggestions_per_failure(self):
        """Test max suggestions per failure limit."""
        # Create 5 different suggestions
        suggestions = [
            FixSuggestion(
                failure=self.failure,
                suggestion=f"Suggestion {i}",
                confidence=0.9 - (i * 0.1),  # 0.9, 0.8, 0.7, 0.6, 0.5
                explanation=f"Explanation {i}",
                code_changes={"index": i},
            )
            for i in range(5)
        ]

        # Configure suggesters
        self.suggester1.suggest_fix.return_value = suggestions[
            :2
        ]  # First 2 suggestions
        self.suggester2.suggest_fix.return_value = suggestions[2:]  # Last 3 suggestions

        # Set max_suggestions_per_failure to 3
        self.composite_suggester.max_suggestions_per_failure = 3

        # Call suggest_fix
        results = self.composite_suggester.suggest_fix(self.failure, self.analysis)

        # Verify only 3 suggestions are returned
        self.assertEqual(len(results), 3)

        # Verify they are the highest confidence ones
        confidences = [r.confidence for r in results]
        self.assertEqual(confidences, [0.9, 0.8, 0.7])

    def test_min_confidence_threshold(self):
        """Test minimum confidence threshold."""
        # Create suggestions with varying confidences
        suggestions = [
            FixSuggestion(
                failure=self.failure,
                suggestion=f"Suggestion {i}",
                confidence=i * 0.2,  # 0.0, 0.2, 0.4, 0.6, 0.8
                explanation=f"Explanation {i}",
                code_changes={"index": i},
            )
            for i in range(5)
        ]

        # Configure suggesters
        self.suggester1.suggest_fix.return_value = suggestions
        self.suggester2.suggest_fix.return_value = []

        # Set min_confidence to 0.5
        self.composite_suggester.min_confidence = 0.5

        # Call suggest_fix
        results = self.composite_suggester.suggest_fix(self.failure, self.analysis)

        # Verify only suggestions with confidence >= 0.5 are returned
        self.assertEqual(len(results), 2)

        # Verify they are the highest confidence ones
        confidences = [r.confidence for r in results]
        # Round to avoid floating point comparison issues
        rounded_confidences = [round(c, 1) for c in confidences]
        self.assertEqual(rounded_confidences, [0.8, 0.6])


if __name__ == "__main__":
    unittest.main()
