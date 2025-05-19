"""
Response parser for LLM outputs.

This module provides functionality for parsing LLM responses
into structured data, separating this concern from LLM communication.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from ..errors import ParsingError
from ..models.failure_analysis import FailureAnalysis
from ..models.pytest_failure import FixSuggestion, PytestFailure

logger = logging.getLogger(__name__)


class ResponseParser:
    """
    Parses LLM responses into structured data.

    This class is responsible for extracting meaningful information from
    LLM responses and converting it into structured objects like
    FailureAnalysis and FixSuggestion instances.
    """

    @staticmethod
    def parse_analysis_response(
        failure: PytestFailure, response: str
    ) -> FailureAnalysis:
        """
        Parse an LLM response into a FailureAnalysis object.

        Args:
            failure: The original test failure being analyzed
            response: Raw text response from the LLM

        Returns:
            FailureAnalysis object containing structured information

        Raises:
            ParsingError: If response parsing fails
        """
        try:
            # Extract root cause (simple heuristic - can be improved)
            root_cause_match = re.search(
                r"Root Cause:?\s*(.+?)(?:\n|$)", response, re.IGNORECASE
            )
            root_cause = (
                root_cause_match.group(1).strip() if root_cause_match else "Unknown"
            )

            # Extract error type (simple heuristic - can be improved)
            error_type_match = re.search(
                r"Error Type:?\s*(.+?)(?:\n|$)", response, re.IGNORECASE
            )
            error_type = (
                error_type_match.group(1).strip() if error_type_match else "Unknown"
            )

            # Extract suggested fixes (simple heuristic - can be improved)
            fixes = []
            fix_section = re.search(
                r"Fix(?:es)?:?\s*(.+?)(?:\n\n|$)", response, re.DOTALL | re.IGNORECASE
            )
            if fix_section:
                fix_text = fix_section.group(1).strip()
                fixes = [
                    fix.strip()
                    for fix in re.split(r"\n\s*-\s*", fix_text)
                    if fix.strip()
                ]
                # If we didn't find any bullet points, try splitting by newlines
                if not fixes:
                    fixes = [fix.strip() for fix in fix_text.split("\n") if fix.strip()]

            # Calculate confidence (simple heuristic - can be improved)
            confidence = 0.7  # Default medium confidence
            if "uncertain" in response.lower() or "not sure" in response.lower():
                confidence = 0.3
            elif "confident" in response.lower() or "certain" in response.lower():
                confidence = 0.9

            # Look for explicit confidence markers
            confidence_match = re.search(
                r"confidence:?\s*(\d+(?:\.\d+)?)%?", response, re.IGNORECASE
            )
            if confidence_match:
                try:
                    confidence_val = float(confidence_match.group(1))
                    # Handle percentage values
                    if confidence_val > 1.0:
                        confidence = confidence_val / 100.0
                    else:
                        confidence = confidence_val
                except (ValueError, TypeError):
                    pass  # Use the default confidence if parsing fails

            return FailureAnalysis(
                failure=failure,
                root_cause=root_cause,
                error_type=error_type,
                suggested_fixes=fixes,
                confidence=confidence,
            )
        except Exception as e:
            error_msg = f"Failed to parse analysis response: {str(e)}"
            logger.error(error_msg)
            raise ParsingError(error_msg) from e

    @staticmethod
    def parse_suggestion_response(
        failure: PytestFailure, analysis: FailureAnalysis, response: str
    ) -> List[FixSuggestion]:
        """
        Parse an LLM response into FixSuggestion objects.

        Args:
            failure: The original test failure being analyzed
            analysis: The analysis of the failure
            response: Raw text response from the LLM

        Returns:
            List of FixSuggestion objects with structured fix information

        Raises:
            ParsingError: If response parsing fails
        """
        try:
            suggestions = []

            # Try to parse as JSON if the response is in a structured format
            json_pattern = r"```json\s*(.+?)\s*```"
            json_matches = re.findall(json_pattern, response, re.DOTALL)

            if json_matches:
                for json_str in json_matches:
                    try:
                        data = json.loads(json_str)
                        if isinstance(data, list):
                            for item in data:
                                suggestion = (
                                    ResponseParser._create_suggestion_from_json(
                                        item, failure, analysis
                                    )
                                )
                                if suggestion:
                                    suggestions.append(suggestion)
                        elif isinstance(data, dict):
                            suggestion = ResponseParser._create_suggestion_from_json(
                                data, failure, analysis
                            )
                            if suggestion:
                                suggestions.append(suggestion)
                    except json.JSONDecodeError:
                        logger.debug(f"Failed to parse JSON: {json_str}")
                        continue

            # If we couldn't parse structured data, extract suggestions from text
            if not suggestions:
                suggestions = ResponseParser._extract_suggestions_from_text(
                    response, failure, analysis
                )

            return suggestions

        except Exception as e:
            error_msg = f"Failed to parse suggestion response: {str(e)}"
            logger.error(error_msg)
            raise ParsingError(error_msg) from e

    @staticmethod
    def _create_suggestion_from_json(
        data: Dict[str, Any],
        failure: PytestFailure,
        analysis: Optional[FailureAnalysis] = None,
    ) -> Optional[FixSuggestion]:
        """
        Create a FixSuggestion from parsed JSON data.

        Args:
            data: Parsed JSON data
            failure: Original failure
            analysis: Optional analysis of the failure

        Returns:
            FixSuggestion object or None if invalid
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
                # Directly use the code_changes as provided
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

    @staticmethod
    def _extract_suggestions_from_text(
        text: str, failure: PytestFailure, analysis: Optional[FailureAnalysis] = None
    ) -> List[FixSuggestion]:
        """
        Extract suggestions from unstructured text response.

        Args:
            text: Text response from LLM
            failure: Original failure
            analysis: Optional analysis of the failure

        Returns:
            List of extracted suggestions
        """
        suggestions = []

        # First try to find explicitly numbered suggestions
        # Look for patterns like "Suggestion 1: ...", "Fix 2: ...", etc.
        suggestion_pattern = r"(?:Suggestion|Fix)\s+(\d+):\s*(.+?)(?=(?:\n\s*(?:Suggestion|Fix)\s+\d+:)|$)"
        suggestion_matches = re.findall(
            suggestion_pattern, text, re.DOTALL | re.IGNORECASE
        )

        if suggestion_matches:
            # Process numbered suggestions
            for i, (num, content) in enumerate(suggestion_matches):
                suggestion_text = content.strip()

                # Process this suggestion
                suggestion = ResponseParser._process_single_suggestion(
                    suggestion_text, failure, i, text
                )
                suggestions.append(suggestion)
        else:
            # If no numbered suggestions, try to find general suggestion patterns
            suggestion_pattern = r"(?:Suggestion|Fix)(?:\s*\d*)?:\s*(.+?)(?:\n\n|\Z)"
            suggestion_matches = re.findall(suggestion_pattern, text, re.DOTALL)

            for i, match in enumerate(suggestion_matches):
                suggestion_text = match.strip()

                suggestion = ResponseParser._process_single_suggestion(
                    suggestion_text, failure, i, text
                )
                suggestions.append(suggestion)

        # If no structured suggestions were found, use the whole response
        if not suggestions and text.strip():
            suggestions.append(
                FixSuggestion(
                    failure=failure,
                    suggestion=text.strip(),
                    confidence=0.7,
                    code_changes={"source": "llm", "fingerprint": "unstructured"},
                )
            )

        return suggestions

    @staticmethod
    def _process_single_suggestion(
        suggestion_text: str, failure: PytestFailure, index: int, full_text: str
    ) -> FixSuggestion:
        """
        Process a single suggestion text into a FixSuggestion object.

        Args:
            suggestion_text: The text of a single suggestion
            failure: The original test failure
            index: Index of this suggestion for fingerprinting
            full_text: The full response text for confidence extraction

        Returns:
            A FixSuggestion object
        """
        # Extract confidence if present
        confidence = 0.8  # Default confidence
        confidence_match = re.search(
            r"confidence:?\s*(\d+(?:\.\d+)?)%?", full_text, re.IGNORECASE
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
            for j, code in enumerate(code_matches):
                code_changes[f"code_snippet_{j + 1}"] = code.strip()

            # Try to identify file paths before code blocks
            file_pattern = (
                r"(?:in|for|to|update|modify)\s+['\"]?([\/\w\.-]+\.\w+)['\"]?:\s*```"
            )
            file_matches = re.findall(file_pattern, suggestion_text, re.IGNORECASE)
            for j, file_path in enumerate(file_matches):
                if j < len(code_matches):
                    code_changes[f"file_{j + 1}"] = file_path
                    code_changes[f"code_{j + 1}"] = code_matches[j].strip()

        # Generate a fingerprint for source tracking
        fingerprint = f"suggestion_{index}"

        # Add metadata to code changes
        if isinstance(code_changes, dict):
            code_changes["source"] = "llm"
            code_changes["fingerprint"] = fingerprint
        else:
            code_changes = {"source": "llm", "fingerprint": fingerprint}

        # Create the suggestion
        return FixSuggestion(
            failure=failure,
            suggestion=suggestion_text,
            confidence=confidence,
            code_changes=code_changes,
        )
