"""
Factory for creating suggester instances.

This module provides a factory for creating different types of suggester
implementations (rule-based, LLM-based, composite, etc.) based on configuration.
"""

import logging
from typing import Any, Dict, Optional

from ..llm.llm_service_protocol import LLMServiceProtocol
from ..prompts.prompt_builder import PromptBuilder
from ..protocols import Suggester
from .composite_suggester import CompositeSuggester
from .fix_suggester import FixSuggester
from .llm_suggester import LLMSuggester

logger = logging.getLogger(__name__)


def create_suggester(
    config: Dict[str, Any],
    llm_service: Optional[LLMServiceProtocol] = None,
    prompt_builder: Optional[PromptBuilder] = None,
) -> Suggester:
    """
    Create a suggester based on the provided configuration.

    Args:
        config: Configuration dictionary with suggester options
        llm_service: Optional LLM service for LLM-based suggesters
        prompt_builder: Optional prompt builder for LLM-based suggesters

    Returns:
        A suggester implementation

    Raises:
        ValueError: If an invalid suggester type is specified
    """
    suggester_type = config.get("type", "rule-based").lower()

    if suggester_type == "rule-based":
        return create_rule_based_suggester(config)
    elif suggester_type == "llm-based":
        return create_llm_based_suggester(config, llm_service, prompt_builder)
    elif suggester_type == "composite":
        return create_composite_suggester(config, llm_service, prompt_builder)
    else:
        raise ValueError(f"Invalid suggester type: {suggester_type}")


def create_rule_based_suggester(config: Dict[str, Any]) -> FixSuggester:
    """
    Create a rule-based suggester.

    Args:
        config: Configuration dictionary with suggester options

    Returns:
        A rule-based suggester implementation
    """
    min_confidence = config.get("min_confidence", 0.5)

    return FixSuggester(min_confidence=min_confidence)


def create_llm_based_suggester(
    config: Dict[str, Any],
    llm_service: Optional[LLMServiceProtocol] = None,
    prompt_builder: Optional[PromptBuilder] = None,
) -> LLMSuggester:
    """
    Create an LLM-based suggester.

    Args:
        config: Configuration dictionary with suggester options
        llm_service: Optional LLM service (required if not in config)
        prompt_builder: Optional prompt builder

    Returns:
        An LLM-based suggester implementation

    Raises:
        ValueError: If no LLM service is provided
    """
    # Extract configuration options
    min_confidence = config.get("min_confidence", 0.7)
    max_prompt_length = config.get("max_prompt_length", 4000)
    max_context_lines = config.get("max_context_lines", 20)
    timeout_seconds = config.get("timeout_seconds", 60)
    custom_prompt_template = config.get("prompt_template")

    # Use provided LLM service or one from config
    llm_service_instance = llm_service or config.get("llm_service")

    if not llm_service_instance:
        raise ValueError("LLM service is required for LLM-based suggester")

    # Use provided prompt builder or create a new one
    prompt_builder_instance = prompt_builder
    if not prompt_builder_instance:
        prompt_templates = config.get("prompt_templates", {})
        if prompt_templates:
            prompt_builder_instance = PromptBuilder(
                templates=prompt_templates, max_prompt_size=max_prompt_length
            )

    # Create the LLM suggester
    return LLMSuggester(
        llm_client=llm_service_instance,
        min_confidence=min_confidence,
        max_prompt_length=max_prompt_length,
        max_context_lines=max_context_lines,
        timeout_seconds=timeout_seconds,
        custom_prompt_template=custom_prompt_template,
    )


def create_composite_suggester(
    config: Dict[str, Any],
    llm_service: Optional[LLMServiceProtocol] = None,
    prompt_builder: Optional[PromptBuilder] = None,
) -> CompositeSuggester:
    """
    Create a composite suggester that combines multiple suggesters.

    Args:
        config: Configuration dictionary with suggester options
        llm_service: Optional LLM service for LLM-based suggesters
        prompt_builder: Optional prompt builder for LLM-based suggesters

    Returns:
        A composite suggester implementation
    """
    # Extract configuration options
    min_confidence = config.get("min_confidence", 0.5)
    max_suggestions_per_failure = config.get("max_suggestions_per_failure", 3)
    deduplicate = config.get("deduplicate", True)

    # Get suggester configurations
    suggester_configs = config.get("suggesters", [])

    # If no specific suggesters are configured, default to rule-based and LLM-based
    if not suggester_configs:
        suggester_configs = [{"type": "rule-based"}, {"type": "llm-based"}]

    # Create all specified suggesters
    suggesters = []
    for suggester_config in suggester_configs:
        try:
            suggester = create_suggester(suggester_config, llm_service, prompt_builder)
            suggesters.append(suggester)
        except Exception as e:
            logger.error(f"Error creating suggester: {e}")
            # Continue with other suggesters if one fails

    # Create the composite suggester
    return CompositeSuggester(
        suggesters=suggesters,
        min_confidence=min_confidence,
        max_suggestions_per_failure=max_suggestions_per_failure,
        deduplicate=deduplicate,
    )
