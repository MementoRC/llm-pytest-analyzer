"""
Tests for the suggester factory.

This module contains tests for the suggester factory functions that create
different types of suggester implementations.
"""

import unittest
from unittest.mock import MagicMock

from src.pytest_analyzer.core.analysis.composite_suggester import CompositeSuggester
from src.pytest_analyzer.core.analysis.fix_suggester import FixSuggester
from src.pytest_analyzer.core.analysis.llm_suggester import LLMSuggester
from src.pytest_analyzer.core.analysis.suggester_factory import (
    create_composite_suggester,
    create_llm_based_suggester,
    create_rule_based_suggester,
    create_suggester,
)
from src.pytest_analyzer.core.llm.llm_service_protocol import LLMServiceProtocol
from src.pytest_analyzer.core.prompts.prompt_builder import PromptBuilder


class TestSuggesterFactory(unittest.TestCase):
    """Test the suggester factory functions."""

    def setUp(self):
        """Set up test fixtures."""
        # Create mock LLM service
        self.llm_service = MagicMock(spec=LLMServiceProtocol)

        # Create mock prompt builder with templates attribute
        self.prompt_builder = MagicMock(spec=PromptBuilder)
        self.prompt_builder.templates = {}

    def test_create_rule_based_suggester(self):
        """Test creating a rule-based suggester."""
        # Create a rule-based suggester
        config = {"min_confidence": 0.6}
        suggester = create_rule_based_suggester(config)

        # Verify result
        self.assertIsInstance(suggester, FixSuggester)
        self.assertEqual(suggester.min_confidence, 0.6)

    def test_create_llm_based_suggester(self):
        """Test creating an LLM-based suggester."""
        # Mock prompt_templates to avoid issue with testing equality
        mock_prompt_templates = {"template_key": "template_value"}

        # Create an LLM-based suggester
        config = {
            "min_confidence": 0.8,
            "max_prompt_length": 5000,
            "max_context_lines": 30,
            "timeout_seconds": 90,
            "prompt_template": "Custom template",
            "prompt_templates": mock_prompt_templates,
        }

        suggester = create_llm_based_suggester(config, self.llm_service, self.prompt_builder)

        # Verify result
        self.assertIsInstance(suggester, LLMSuggester)
        self.assertEqual(suggester.min_confidence, 0.8)
        self.assertEqual(suggester.max_prompt_length, 5000)
        self.assertEqual(suggester.max_context_lines, 30)
        self.assertEqual(suggester.timeout_seconds, 90)
        self.assertIs(suggester.llm_client, self.llm_service)
        # Remove prompt_builder assertion as it's not stored as an attribute in the class

    def test_create_llm_based_suggester_without_llm_service(self):
        """Test creating an LLM-based suggester without an LLM service."""
        config = {"min_confidence": 0.8}

        # Should raise ValueError
        with self.assertRaises(ValueError):
            create_llm_based_suggester(config)

    def test_create_composite_suggester(self):
        """Test creating a composite suggester."""
        # Create a composite suggester
        config = {
            "min_confidence": 0.6,
            "max_suggestions_per_failure": 5,
            "deduplicate": False,
            "suggesters": [
                {"type": "rule-based", "min_confidence": 0.5},
                {"type": "llm-based", "min_confidence": 0.7},
            ],
        }

        suggester = create_composite_suggester(config, self.llm_service, self.prompt_builder)

        # Verify result
        self.assertIsInstance(suggester, CompositeSuggester)
        self.assertEqual(suggester.min_confidence, 0.6)
        self.assertEqual(suggester.max_suggestions_per_failure, 5)
        self.assertEqual(suggester.deduplicate, False)
        self.assertEqual(len(suggester.suggesters), 2)
        self.assertIsInstance(suggester.suggesters[0], FixSuggester)
        self.assertIsInstance(suggester.suggesters[1], LLMSuggester)

    def test_create_suggester_rule_based(self):
        """Test creating a suggester with type rule-based."""
        config = {"type": "rule-based", "min_confidence": 0.6}
        suggester = create_suggester(config)

        # Verify result
        self.assertIsInstance(suggester, FixSuggester)

    def test_create_suggester_llm_based(self):
        """Test creating a suggester with type llm-based."""
        config = {"type": "llm-based", "min_confidence": 0.8}
        suggester = create_suggester(config, self.llm_service)

        # Verify result
        self.assertIsInstance(suggester, LLMSuggester)

    def test_create_suggester_composite(self):
        """Test creating a suggester with type composite."""
        config = {
            "type": "composite",
            "min_confidence": 0.6,
            "suggesters": [{"type": "rule-based"}, {"type": "llm-based"}],
        }

        suggester = create_suggester(config, self.llm_service)

        # Verify result
        self.assertIsInstance(suggester, CompositeSuggester)

    def test_create_suggester_invalid_type(self):
        """Test creating a suggester with an invalid type."""
        config = {"type": "invalid"}

        # Should raise ValueError
        with self.assertRaises(ValueError):
            create_suggester(config)

    def test_create_composite_suggester_default_suggesters(self):
        """Test creating a composite suggester with default suggesters."""
        # Create a composite suggester without specifying suggesters
        config = {"min_confidence": 0.6}

        suggester = create_composite_suggester(config, self.llm_service, self.prompt_builder)

        # Verify result
        self.assertIsInstance(suggester, CompositeSuggester)
        self.assertEqual(len(suggester.suggesters), 2)
        self.assertIsInstance(suggester.suggesters[0], FixSuggester)
        self.assertIsInstance(suggester.suggesters[1], LLMSuggester)

    def test_create_composite_suggester_error_handling(self):
        """Test error handling when creating suggester fails."""
        # Configure config with one valid and one invalid suggester
        config = {
            "suggesters": [
                {"type": "rule-based"},
                {"type": "invalid"},
                {"type": "llm-based"},
            ]
        }

        # Should not raise exception, but log error and continue
        suggester = create_composite_suggester(config, self.llm_service, self.prompt_builder)

        # Verify result
        self.assertIsInstance(suggester, CompositeSuggester)
        self.assertEqual(len(suggester.suggesters), 2)  # Only 2 valid suggesters


if __name__ == "__main__":
    unittest.main()
