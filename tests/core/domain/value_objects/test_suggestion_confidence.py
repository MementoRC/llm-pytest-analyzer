from pytest_analyzer.core.domain.value_objects.suggestion_confidence import (
    SuggestionConfidence,
)


class TestSuggestionConfidence:
    """Test suite for SuggestionConfidence value object."""

    def test_all_confidence_levels_exist(self):
        """Test that all expected confidence levels are defined."""
        expected_levels = {"HIGH", "MEDIUM", "LOW"}
        actual_levels = {sc.name for sc in SuggestionConfidence}
        assert actual_levels == expected_levels

    def test_confidence_values(self):
        """Test that confidence levels have correct string values."""
        assert SuggestionConfidence.HIGH.value == "high"
        assert SuggestionConfidence.MEDIUM.value == "medium"
        assert SuggestionConfidence.LOW.value == "low"

    def test_from_score_high_confidence(self):
        """Test creating HIGH confidence from scores."""
        assert SuggestionConfidence.from_score(1.0) == SuggestionConfidence.HIGH
        assert SuggestionConfidence.from_score(0.9) == SuggestionConfidence.HIGH
        assert SuggestionConfidence.from_score(0.8) == SuggestionConfidence.HIGH

    def test_from_score_medium_confidence(self):
        """Test creating MEDIUM confidence from scores."""
        assert SuggestionConfidence.from_score(0.79) == SuggestionConfidence.MEDIUM
        assert SuggestionConfidence.from_score(0.7) == SuggestionConfidence.MEDIUM
        assert SuggestionConfidence.from_score(0.6) == SuggestionConfidence.MEDIUM
        assert SuggestionConfidence.from_score(0.5) == SuggestionConfidence.MEDIUM

    def test_from_score_low_confidence(self):
        """Test creating LOW confidence from scores."""
        assert SuggestionConfidence.from_score(0.49) == SuggestionConfidence.LOW
        assert SuggestionConfidence.from_score(0.3) == SuggestionConfidence.LOW
        assert SuggestionConfidence.from_score(0.1) == SuggestionConfidence.LOW
        assert SuggestionConfidence.from_score(0.0) == SuggestionConfidence.LOW

    def test_from_score_with_integers(self):
        """Test creating confidence from integer scores."""
        assert SuggestionConfidence.from_score(1) == SuggestionConfidence.HIGH
        assert SuggestionConfidence.from_score(0) == SuggestionConfidence.LOW

    def test_numeric_value_property(self):
        """Test the numeric_value property."""
        assert SuggestionConfidence.HIGH.numeric_value == 0.9
        assert SuggestionConfidence.MEDIUM.numeric_value == 0.7
        assert SuggestionConfidence.LOW.numeric_value == 0.3

    def test_comparison_less_than(self):
        """Test less than comparison."""
        assert SuggestionConfidence.LOW < SuggestionConfidence.MEDIUM
        assert SuggestionConfidence.MEDIUM < SuggestionConfidence.HIGH
        assert SuggestionConfidence.LOW < SuggestionConfidence.HIGH

        # Test that equal values are not less than
        assert not (SuggestionConfidence.HIGH < SuggestionConfidence.HIGH)
        assert not (SuggestionConfidence.MEDIUM < SuggestionConfidence.MEDIUM)

    def test_comparison_less_than_or_equal(self):
        """Test less than or equal comparison."""
        assert SuggestionConfidence.LOW <= SuggestionConfidence.MEDIUM
        assert SuggestionConfidence.MEDIUM <= SuggestionConfidence.HIGH
        assert SuggestionConfidence.LOW <= SuggestionConfidence.HIGH

        # Test equal values
        assert SuggestionConfidence.HIGH <= SuggestionConfidence.HIGH
        assert SuggestionConfidence.MEDIUM <= SuggestionConfidence.MEDIUM
        assert SuggestionConfidence.LOW <= SuggestionConfidence.LOW

    def test_comparison_greater_than(self):
        """Test greater than comparison."""
        assert SuggestionConfidence.HIGH > SuggestionConfidence.MEDIUM
        assert SuggestionConfidence.MEDIUM > SuggestionConfidence.LOW
        assert SuggestionConfidence.HIGH > SuggestionConfidence.LOW

        # Test that equal values are not greater than
        assert not (SuggestionConfidence.HIGH > SuggestionConfidence.HIGH)
        assert not (SuggestionConfidence.MEDIUM > SuggestionConfidence.MEDIUM)

    def test_comparison_greater_than_or_equal(self):
        """Test greater than or equal comparison."""
        assert SuggestionConfidence.HIGH >= SuggestionConfidence.MEDIUM
        assert SuggestionConfidence.MEDIUM >= SuggestionConfidence.LOW
        assert SuggestionConfidence.HIGH >= SuggestionConfidence.LOW

        # Test equal values
        assert SuggestionConfidence.HIGH >= SuggestionConfidence.HIGH
        assert SuggestionConfidence.MEDIUM >= SuggestionConfidence.MEDIUM
        assert SuggestionConfidence.LOW >= SuggestionConfidence.LOW

    def test_comparison_equality(self):
        """Test equality comparison."""
        assert SuggestionConfidence.HIGH == SuggestionConfidence.HIGH
        assert SuggestionConfidence.MEDIUM == SuggestionConfidence.MEDIUM
        assert SuggestionConfidence.LOW == SuggestionConfidence.LOW

        assert SuggestionConfidence.HIGH != SuggestionConfidence.MEDIUM
        assert SuggestionConfidence.MEDIUM != SuggestionConfidence.LOW
        assert SuggestionConfidence.HIGH != SuggestionConfidence.LOW

    def test_sorting(self):
        """Test that confidence levels can be sorted."""
        confidences = [
            SuggestionConfidence.LOW,
            SuggestionConfidence.HIGH,
            SuggestionConfidence.MEDIUM,
            SuggestionConfidence.LOW,
            SuggestionConfidence.HIGH,
        ]

        sorted_confidences = sorted(confidences)
        expected = [
            SuggestionConfidence.LOW,
            SuggestionConfidence.LOW,
            SuggestionConfidence.MEDIUM,
            SuggestionConfidence.HIGH,
            SuggestionConfidence.HIGH,
        ]

        assert sorted_confidences == expected

    def test_round_trip_conversion(self):
        """Test converting to score and back preserves confidence level."""
        for confidence in SuggestionConfidence:
            score = confidence.numeric_value
            converted = SuggestionConfidence.from_score(score)
            assert converted == confidence
