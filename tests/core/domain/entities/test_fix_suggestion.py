from datetime import datetime
from unittest.mock import patch

from pytest_analyzer.core.domain.entities.fix_suggestion import FixSuggestion
from pytest_analyzer.core.domain.value_objects.suggestion_confidence import (
    SuggestionConfidence,
)


class TestFixSuggestion:
    """Test suite for FixSuggestion domain entity."""

    def test_create_factory_method(self):
        """Test the create factory method."""
        suggestion = FixSuggestion.create(
            failure_id="failure-123",
            suggestion_text="Fix the error by changing X to Y",
            confidence=SuggestionConfidence.HIGH,
            explanation="This change will resolve the issue",
            code_changes=["line 1: change X to Y", "line 2: add import"],
            alternative_approaches=["Alternative 1", "Alternative 2"],
            metadata={"source": "llm", "model": "gpt-4"},
        )

        assert suggestion.failure_id == "failure-123"
        assert suggestion.suggestion_text == "Fix the error by changing X to Y"
        assert suggestion.confidence == SuggestionConfidence.HIGH
        assert suggestion.explanation == "This change will resolve the issue"
        assert suggestion.code_changes == [
            "line 1: change X to Y",
            "line 2: add import",
        ]
        assert suggestion.alternative_approaches == ["Alternative 1", "Alternative 2"]
        assert suggestion.metadata == {"source": "llm", "model": "gpt-4"}
        assert isinstance(suggestion.id, str)
        assert len(suggestion.id) == 36  # UUID4 length
        assert isinstance(suggestion.created_at, datetime)
        assert suggestion.updated_at is None

    def test_create_with_minimal_params(self):
        """Test create with minimal required parameters."""
        suggestion = FixSuggestion.create(
            failure_id="failure-123",
            suggestion_text="Fix the error",
        )

        assert suggestion.failure_id == "failure-123"
        assert suggestion.suggestion_text == "Fix the error"
        assert suggestion.confidence == SuggestionConfidence.MEDIUM
        assert suggestion.explanation == ""
        assert suggestion.code_changes == []
        assert suggestion.alternative_approaches == []
        assert suggestion.metadata == {}

    def test_create_from_score(self):
        """Test create_from_score factory method."""
        suggestion = FixSuggestion.create_from_score(
            failure_id="failure-123",
            suggestion_text="Fix the error",
            confidence_score=0.9,
            explanation="High confidence fix",
        )

        assert suggestion.failure_id == "failure-123"
        assert suggestion.suggestion_text == "Fix the error"
        assert suggestion.confidence == SuggestionConfidence.HIGH
        assert suggestion.explanation == "High confidence fix"

    def test_direct_construction(self):
        """Test direct construction of FixSuggestion."""
        now = datetime.now()

        suggestion = FixSuggestion(
            id="test-id-123",
            failure_id="failure-123",
            suggestion_text="Fix the error",
            confidence=SuggestionConfidence.LOW,
            explanation="Test explanation",
            created_at=now,
        )

        assert suggestion.id == "test-id-123"
        assert suggestion.failure_id == "failure-123"
        assert suggestion.suggestion_text == "Fix the error"
        assert suggestion.confidence == SuggestionConfidence.LOW
        assert suggestion.explanation == "Test explanation"
        assert suggestion.created_at == now

    def test_is_high_confidence_property(self):
        """Test is_high_confidence property."""
        high_suggestion = FixSuggestion.create(
            failure_id="failure-123",
            suggestion_text="Fix",
            confidence=SuggestionConfidence.HIGH,
        )

        medium_suggestion = FixSuggestion.create(
            failure_id="failure-123",
            suggestion_text="Fix",
            confidence=SuggestionConfidence.MEDIUM,
        )

        assert high_suggestion.is_high_confidence is True
        assert medium_suggestion.is_high_confidence is False

    def test_is_low_confidence_property(self):
        """Test is_low_confidence property."""
        low_suggestion = FixSuggestion.create(
            failure_id="failure-123",
            suggestion_text="Fix",
            confidence=SuggestionConfidence.LOW,
        )

        high_suggestion = FixSuggestion.create(
            failure_id="failure-123",
            suggestion_text="Fix",
            confidence=SuggestionConfidence.HIGH,
        )

        assert low_suggestion.is_low_confidence is True
        assert high_suggestion.is_low_confidence is False

    def test_has_code_changes_property(self):
        """Test has_code_changes property."""
        with_changes = FixSuggestion.create(
            failure_id="failure-123",
            suggestion_text="Fix",
            code_changes=["change 1"],
        )

        without_changes = FixSuggestion.create(
            failure_id="failure-123",
            suggestion_text="Fix",
        )

        assert with_changes.has_code_changes is True
        assert without_changes.has_code_changes is False

    def test_has_alternatives_property(self):
        """Test has_alternatives property."""
        with_alternatives = FixSuggestion.create(
            failure_id="failure-123",
            suggestion_text="Fix",
            alternative_approaches=["alt 1"],
        )

        without_alternatives = FixSuggestion.create(
            failure_id="failure-123",
            suggestion_text="Fix",
        )

        assert with_alternatives.has_alternatives is True
        assert without_alternatives.has_alternatives is False

    def test_confidence_score_property(self):
        """Test confidence_score property."""
        high_suggestion = FixSuggestion.create(
            failure_id="failure-123",
            suggestion_text="Fix",
            confidence=SuggestionConfidence.HIGH,
        )

        medium_suggestion = FixSuggestion.create(
            failure_id="failure-123",
            suggestion_text="Fix",
            confidence=SuggestionConfidence.MEDIUM,
        )

        low_suggestion = FixSuggestion.create(
            failure_id="failure-123",
            suggestion_text="Fix",
            confidence=SuggestionConfidence.LOW,
        )

        assert high_suggestion.confidence_score == 0.9
        assert medium_suggestion.confidence_score == 0.7
        assert low_suggestion.confidence_score == 0.3

    def test_add_code_change(self):
        """Test add_code_change method."""
        suggestion = FixSuggestion.create(
            failure_id="failure-123",
            suggestion_text="Fix",
        )

        assert suggestion.updated_at is None

        suggestion.add_code_change("change 1")
        suggestion.add_code_change("change 2")

        assert "change 1" in suggestion.code_changes
        assert "change 2" in suggestion.code_changes
        assert len(suggestion.code_changes) == 2
        assert suggestion.updated_at is not None

        # Adding duplicate should not increase list size
        suggestion.add_code_change("change 1")
        assert len(suggestion.code_changes) == 2

    def test_add_alternative_approach(self):
        """Test add_alternative_approach method."""
        suggestion = FixSuggestion.create(
            failure_id="failure-123",
            suggestion_text="Fix",
        )

        suggestion.add_alternative_approach("alt 1")
        suggestion.add_alternative_approach("alt 2")

        assert "alt 1" in suggestion.alternative_approaches
        assert "alt 2" in suggestion.alternative_approaches
        assert len(suggestion.alternative_approaches) == 2
        assert suggestion.updated_at is not None

        # Adding duplicate should not increase list size
        suggestion.add_alternative_approach("alt 1")
        assert len(suggestion.alternative_approaches) == 2

    def test_update_confidence(self):
        """Test update_confidence method."""
        suggestion = FixSuggestion.create(
            failure_id="failure-123",
            suggestion_text="Fix",
            confidence=SuggestionConfidence.LOW,
        )

        suggestion.update_confidence(SuggestionConfidence.HIGH)

        assert suggestion.confidence == SuggestionConfidence.HIGH
        assert suggestion.updated_at is not None

    def test_update_confidence_from_score(self):
        """Test update_confidence_from_score method."""
        suggestion = FixSuggestion.create(
            failure_id="failure-123",
            suggestion_text="Fix",
            confidence=SuggestionConfidence.LOW,
        )

        suggestion.update_confidence_from_score(0.9)

        assert suggestion.confidence == SuggestionConfidence.HIGH
        assert suggestion.updated_at is not None

    def test_add_metadata(self):
        """Test add_metadata method."""
        suggestion = FixSuggestion.create(
            failure_id="failure-123",
            suggestion_text="Fix",
        )

        suggestion.add_metadata("key1", "value1")
        suggestion.add_metadata("key2", {"nested": "value"})

        assert suggestion.metadata["key1"] == "value1"
        assert suggestion.metadata["key2"] == {"nested": "value"}
        assert suggestion.updated_at is not None

    def test_update_explanation(self):
        """Test update_explanation method."""
        suggestion = FixSuggestion.create(
            failure_id="failure-123",
            suggestion_text="Fix",
            explanation="Old explanation",
        )

        suggestion.update_explanation("New explanation")

        assert suggestion.explanation == "New explanation"
        assert suggestion.updated_at is not None

    def test_is_better_than_by_confidence(self):
        """Test is_better_than method based on confidence."""
        high_suggestion = FixSuggestion.create(
            failure_id="failure-123",
            suggestion_text="Fix",
            confidence=SuggestionConfidence.HIGH,
        )

        medium_suggestion = FixSuggestion.create(
            failure_id="failure-123",
            suggestion_text="Fix",
            confidence=SuggestionConfidence.MEDIUM,
        )

        low_suggestion = FixSuggestion.create(
            failure_id="failure-123",
            suggestion_text="Fix",
            confidence=SuggestionConfidence.LOW,
        )

        assert high_suggestion.is_better_than(medium_suggestion) is True
        assert high_suggestion.is_better_than(low_suggestion) is True
        assert medium_suggestion.is_better_than(low_suggestion) is True

        assert medium_suggestion.is_better_than(high_suggestion) is False
        assert low_suggestion.is_better_than(medium_suggestion) is False

    def test_is_better_than_by_code_changes(self):
        """Test is_better_than method considers code changes when confidence is equal."""
        with_code = FixSuggestion.create(
            failure_id="failure-123",
            suggestion_text="Fix",
            confidence=SuggestionConfidence.MEDIUM,
            code_changes=["change 1"],
        )

        without_code = FixSuggestion.create(
            failure_id="failure-123",
            suggestion_text="Fix",
            confidence=SuggestionConfidence.MEDIUM,
        )

        assert with_code.is_better_than(without_code) is True
        assert without_code.is_better_than(with_code) is False

    def test_merge_with(self):
        """Test merge_with method."""
        suggestion1 = FixSuggestion.create(
            failure_id="failure-123",
            suggestion_text="Fix 1",
            confidence=SuggestionConfidence.MEDIUM,
            code_changes=["change 1"],
            alternative_approaches=["alt 1"],
            metadata={"key1": "value1"},
        )

        suggestion2 = FixSuggestion.create(
            failure_id="failure-123",
            suggestion_text="Fix 2",
            confidence=SuggestionConfidence.HIGH,
            code_changes=["change 2", "change 1"],  # Include duplicate
            alternative_approaches=["alt 2"],
            metadata={"key2": "value2", "key1": "different"},  # Include duplicate key
        )

        suggestion1.merge_with(suggestion2)

        # Should take higher confidence
        assert suggestion1.confidence == SuggestionConfidence.HIGH

        # Should merge code changes (no duplicates)
        assert set(suggestion1.code_changes) == {"change 1", "change 2"}

        # Should merge alternatives (no duplicates)
        assert set(suggestion1.alternative_approaches) == {"alt 1", "alt 2"}

        # Should merge metadata (no overwrite of existing keys)
        assert suggestion1.metadata["key1"] == "value1"  # Original value preserved
        assert suggestion1.metadata["key2"] == "value2"  # New value added

        assert suggestion1.updated_at is not None

    def test_equality_based_on_id(self):
        """Test that equality is based on entity identity (id)."""
        suggestion1 = FixSuggestion(
            id="same-id",
            failure_id="failure-123",
            suggestion_text="Fix 1",
            confidence=SuggestionConfidence.HIGH,
        )

        suggestion2 = FixSuggestion(
            id="same-id",
            failure_id="failure-456",  # Different content
            suggestion_text="Fix 2",  # Different content
            confidence=SuggestionConfidence.LOW,  # Different content
        )

        suggestion3 = FixSuggestion(
            id="different-id",
            failure_id="failure-123",  # Same content as suggestion1
            suggestion_text="Fix 1",
            confidence=SuggestionConfidence.HIGH,
        )

        # Same ID means equal, regardless of content
        assert suggestion1 == suggestion2

        # Different ID means not equal, even with same content
        assert suggestion1 != suggestion3
        assert suggestion2 != suggestion3

    def test_hash_based_on_id(self):
        """Test that hash is based on entity identity (id)."""
        suggestion1 = FixSuggestion(
            id="same-id",
            failure_id="failure-123",
            suggestion_text="Fix 1",
            confidence=SuggestionConfidence.HIGH,
        )

        suggestion2 = FixSuggestion(
            id="same-id",
            failure_id="failure-456",  # Different content
            suggestion_text="Fix 2",
            confidence=SuggestionConfidence.LOW,
        )

        suggestion3 = FixSuggestion(
            id="different-id",
            failure_id="failure-123",
            suggestion_text="Fix 1",
            confidence=SuggestionConfidence.HIGH,
        )

        # Same ID means same hash
        assert hash(suggestion1) == hash(suggestion2)

        # Different ID means different hash
        assert hash(suggestion1) != hash(suggestion3)

        # Can be used in sets
        suggestion_set = {suggestion1, suggestion2, suggestion3}
        assert len(suggestion_set) == 2  # suggestion1 and suggestion2 are the same

    def test_comparison_methods(self):
        """Test that suggestions can be compared by quality."""
        low_suggestion = FixSuggestion.create(
            failure_id="failure-123",
            suggestion_text="Fix",
            confidence=SuggestionConfidence.LOW,
        )

        medium_suggestion = FixSuggestion.create(
            failure_id="failure-123",
            suggestion_text="Fix",
            confidence=SuggestionConfidence.MEDIUM,
        )

        high_suggestion = FixSuggestion.create(
            failure_id="failure-123",
            suggestion_text="Fix",
            confidence=SuggestionConfidence.HIGH,
        )

        # Test is_better_than logic
        assert high_suggestion.is_better_than(medium_suggestion) is True
        assert high_suggestion.is_better_than(low_suggestion) is True
        assert medium_suggestion.is_better_than(low_suggestion) is True

        assert low_suggestion.is_better_than(medium_suggestion) is False
        assert low_suggestion.is_better_than(high_suggestion) is False
        assert medium_suggestion.is_better_than(high_suggestion) is False

    def test_mutable_fields(self):
        """Test that entity fields can be modified (unlike value objects)."""
        suggestion = FixSuggestion.create(
            failure_id="failure-123",
            suggestion_text="Original text",
        )

        # Should be able to modify fields
        suggestion.suggestion_text = "Modified text"
        suggestion.explanation = "New explanation"
        suggestion.code_changes.append("new change")
        suggestion.metadata["new_key"] = "new_value"

        assert suggestion.suggestion_text == "Modified text"
        assert suggestion.explanation == "New explanation"
        assert "new change" in suggestion.code_changes
        assert suggestion.metadata["new_key"] == "new_value"

    @patch("pytest_analyzer.core.domain.entities.fix_suggestion.datetime")
    def test_mark_updated_sets_timestamp(self, mock_datetime):
        """Test that _mark_updated sets the updated_at timestamp."""
        fixed_time = datetime(2023, 1, 1, 12, 0, 0)
        mock_datetime.now.return_value = fixed_time

        suggestion = FixSuggestion.create(
            failure_id="failure-123",
            suggestion_text="Fix",
        )

        # Call a method that should mark as updated
        suggestion.add_code_change("test change")

        assert suggestion.updated_at == fixed_time
