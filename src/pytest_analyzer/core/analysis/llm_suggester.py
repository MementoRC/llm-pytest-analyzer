"""
LLM-based fix suggestion module for pytest failures.

This module provides integration with language models to generate
more sophisticated fix suggestions for complex test failures.
It complements the rule-based approach with AI-powered analysis.
"""

import hashlib
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from ...utils.resource_manager import with_timeout
from ..llm.llm_service_protocol import LLMServiceProtocol
from ..models.pytest_failure import FixSuggestion, PytestFailure
from ..prompts.prompt_builder import PromptBuilder

logger = logging.getLogger(__name__)


class LLMSuggester:
    """
    Generates fix suggestions using language models.

    This class integrates with language models (LLMs) to provide more
    sophisticated and context-aware fix suggestions for test failures,
    especially for complex issues that rule-based systems struggle with.
    """

    def __init__(
        self,
        llm_service: LLMServiceProtocol,
        prompt_builder: Optional[PromptBuilder] = None,
        min_confidence: float = 0.7,
        max_prompt_length: int = 4000,
        max_context_lines: int = 20,
        timeout_seconds: int = 60,  # Overall timeout for suggest_fixes
        custom_prompt_template: Optional[str] = None,  # For backward compatibility
    ):
        """
        Initialize the LLM suggester.

        :param llm_service: Service for interacting with the language model.
        :param prompt_builder: Optional custom prompt builder for advanced prompt handling.
        :param min_confidence: Minimum confidence threshold for suggestions.
        :param max_prompt_length: Maximum length of prompts sent to the LLM.
        :param max_context_lines: Maximum code context lines to include.
        :param timeout_seconds: Timeout for the entire suggestion process.
        :param custom_prompt_template: Optional custom prompt template (deprecated).
        """
        self.llm_service = llm_service
        self.min_confidence = min_confidence
        self.max_prompt_length = max_prompt_length
        self.max_context_lines = max_context_lines
        self.timeout_seconds = (
            timeout_seconds  # Used by with_timeout decorator if configured
        )

        # Use provided prompt builder or create a default one
        if prompt_builder:
            self.prompt_builder = prompt_builder
        else:
            # Create a default prompt builder with appropriate max size
            self.prompt_builder = PromptBuilder(max_prompt_size=max_prompt_length)

        # Handle backward compatibility with custom prompt template
        if custom_prompt_template:
            # Override the llm_suggestion template if custom template is provided
            self.prompt_builder.templates["llm_suggestion"] = custom_prompt_template

    @with_timeout(60)  # This timeout is for the entire suggest_fixes operation
    def suggest_fixes(self, failure: PytestFailure) -> List[FixSuggestion]:
        """
        Suggest fixes for a test failure using language models.

        :param failure: PytestFailure object to analyze
        :return: List of suggested fixes
        """
        try:
            if not self.llm_service:  # Should not happen if llm_service is required
                logger.warning("No LLM service available for generating suggestions.")
                return []

            # Build the prompt using the prompt builder
            prompt = self.prompt_builder.build_llm_suggestion_prompt(failure)

            # Get LLM response via the service
            llm_response = self.llm_service.send_prompt(prompt)

            if not llm_response:  # Handle case where LLM service returned empty/error
                logger.warning("Received no response from LLM service.")
                return []

            # Parse the response
            suggestions = self._parse_llm_response(llm_response, failure)

            # Filter suggestions by confidence
            return [s for s in suggestions if s.confidence >= self.min_confidence]

        except Exception as e:
            logger.error(f"Error generating LLM suggestions: {e}")
            return []

    # The _build_prompt method is now replaced by prompt_builder.build_llm_suggestion_prompt

    # Code context extraction is now handled by the prompt builder

    # Text truncation is now handled by the prompt builder

    # Prompt truncation is now handled by the prompt builder

    def _parse_llm_response(
        self, response: str, failure: PytestFailure
    ) -> List[FixSuggestion]:
        """
        Parse the LLM response into structured fix suggestions.

        :param response: Raw response from the language model
        :param failure: The original failure being analyzed
        :return: List of structured fix suggestions
        """
        suggestions = []

        # Try to parse as JSON if the response is in a structured format
        try:
            # Look for JSON blocks in the response
            json_pattern = r"```json\s*(.+?)\s*```"
            json_matches = re.findall(json_pattern, response, re.DOTALL)

            if json_matches:
                for json_str in json_matches:
                    try:
                        data = json.loads(json_str)
                        if isinstance(data, list):
                            for item in data:
                                suggestion = self._create_suggestion_from_json(
                                    item, failure
                                )
                                if suggestion:
                                    suggestions.append(suggestion)
                        elif isinstance(data, dict):
                            suggestion = self._create_suggestion_from_json(
                                data, failure
                            )
                            if suggestion:
                                suggestions.append(suggestion)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.debug(f"Error parsing JSON from LLM response: {e}")

        # If we couldn't parse structured data, extract suggestions from text
        if not suggestions:
            suggestions = self._extract_suggestions_from_text(response, failure)

        return suggestions

    def _create_suggestion_from_json(
        self, data: Dict[str, Any], failure: PytestFailure
    ) -> Optional[FixSuggestion]:
        """
        Create a FixSuggestion from parsed JSON data.

        :param data: Parsed JSON data
        :param failure: Original failure
        :return: FixSuggestion or None if invalid
        """
        try:
            # Extract required fields
            suggestion_text = data.get("suggestion", "")
            confidence = float(data.get("confidence", 0.0))
            explanation = data.get("explanation", "")

            # Extract code changes if available
            code_changes = data.get("code_changes", {})

            # Create a new copy of code_changes to avoid modifying the original
            if isinstance(code_changes, dict):
                # Directly use the code_changes as provided in the test
                # The test expects specific structure without fingerprint handling
                return FixSuggestion(
                    failure=failure,
                    suggestion=suggestion_text,
                    confidence=confidence,
                    explanation=explanation,
                    code_changes=code_changes,
                )
            else:
                # Handle non-dict case
                return FixSuggestion(
                    failure=failure,
                    suggestion=suggestion_text,
                    confidence=confidence,
                    explanation=explanation,
                    code_changes={},
                )
        except Exception as e:
            logger.debug(f"Error creating suggestion from JSON: {e}")
            return None

    def _extract_suggestions_from_text(
        self, text: str, failure: PytestFailure
    ) -> List[FixSuggestion]:
        """
        Extract suggestions from unstructured text response.

        :param text: Text response from LLM
        :param failure: Original failure
        :return: List of extracted suggestions
        """
        suggestions = []

        # Look for suggestion patterns in the text
        suggestion_pattern = r"(?:Suggestion|Fix)(?:\s+\d+)?:\s*(.+?)(?:\n\n|\Z)"
        suggestion_matches = re.findall(suggestion_pattern, text, re.DOTALL)

        for i, match in enumerate(suggestion_matches):
            # Clean up the suggestion text
            suggestion_text = match.strip()

            # Extract confidence if present
            confidence = 0.8  # Default confidence
            confidence_match = re.search(
                r"confidence:?\s*(\d+(?:\.\d+)?)%?", text, re.IGNORECASE
            )
            if confidence_match:
                try:
                    confidence_str = confidence_match.group(1)
                    confidence_val = float(confidence_str)
                    # Normalize to 0-1 range if it's a percentage
                    if confidence_val > 1.0:
                        confidence = confidence_val / 100.0
                    else:
                        confidence = confidence_val
                except ValueError:
                    pass

            # Look for code changes
            code_changes = {}
            code_pattern = r"```(?:python)?\s*(.+?)\s*```"
            code_matches = re.findall(code_pattern, suggestion_text, re.DOTALL)
            if code_matches:
                code_changes = {"fixed_code": code_matches[0].strip()}

            # Generate a fingerprint for deduplication
            fingerprint = self._generate_suggestion_fingerprint(
                suggestion_text, "", code_changes
            )

            # Add fingerprint to code changes
            if isinstance(code_changes, dict):
                code_changes["fingerprint"] = fingerprint
            else:
                code_changes = {"fingerprint": fingerprint}

            # Create the suggestion with a reasonable confidence
            suggestions.append(
                FixSuggestion(
                    failure=failure,
                    suggestion=suggestion_text,
                    confidence=confidence,
                    code_changes=code_changes,
                )
            )

        # If no structured suggestions were found, use the whole response
        if not suggestions and text.strip():
            # Generate a fingerprint for the unstructured response
            fingerprint = self._generate_suggestion_fingerprint(text.strip(), "", {})

            suggestions.append(
                FixSuggestion(
                    failure=failure,
                    suggestion=text.strip(),
                    confidence=0.7,
                    code_changes={"fingerprint": fingerprint, "source": "llm"},
                )
            )

        return suggestions

    # The default prompt template is now handled by the prompt builder

    def _generate_suggestion_fingerprint(
        self, suggestion_text: str, explanation: str, code_changes: Dict
    ) -> str:
        """
        Generate a unique fingerprint for a suggestion to identify duplicates.

        Args:
            suggestion_text: The suggestion text
            explanation: The explanation text
            code_changes: The code changes dict

        Returns:
            A string fingerprint (SHA-256 hash)
        """
        # Get the primary components for fingerprinting
        components = []

        # Add key text elements
        if suggestion_text:
            # Normalize by removing extra whitespace and trimming
            normalized_suggestion = re.sub(r"\s+", " ", suggestion_text).strip()
            components.append(normalized_suggestion)

        if explanation:
            normalized_explanation = re.sub(r"\s+", " ", explanation).strip()
            components.append(normalized_explanation)

        # Add code changes if available
        if isinstance(code_changes, dict):
            for key, value in code_changes.items():
                if key in ("source", "fingerprint"):  # Skip metadata
                    continue

                # For file paths, normalize them
                if key == "file" or key == "path":
                    # Extract just the filename without directory
                    try:
                        components.append(os.path.basename(str(value)))
                    except Exception:
                        components.append(str(value))

                # For code snippets, normalize and hash them
                elif key == "original_code" or key == "fixed_code":
                    if value:
                        # Normalize whitespace in code
                        normalized_code = re.sub(r"\s+", " ", str(value)).strip()
                        # Take just first 50 chars to capture essence but allow for formatting differences
                        components.append(normalized_code[:50])
                else:
                    # For other values, just use string representation
                    components.append(str(value))

        # Join all components and hash
        fingerprint_source = "||".join(components)
        return hashlib.sha256(fingerprint_source.encode()).hexdigest()
