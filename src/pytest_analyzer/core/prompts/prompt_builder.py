"""
PromptBuilder for pytest_analyzer.

This module provides a PromptBuilder class that constructs prompts
for LLM interactions based on pytest failures and configuration.
"""

import logging
from pathlib import Path
from typing import List, Optional, Union

from ..models.pytest_failure import PytestFailure

logger = logging.getLogger(__name__)


class PromptBuilder:
    """
    Builds prompts for LLM interactions based on test failures.

    This class encapsulates the logic for constructing prompts for different
    types of analysis and fix suggestions, separating this concern from
    the LLM communication.
    """

    # Default prompt templates
    _DEFAULT_ANALYSIS_TEMPLATE = """
    Analyze the following pytest test failure and help identify the root cause:

    Test name: {test_name}
    Error type: {error_type}
    Error message: {error_message}

    Traceback:
    {traceback}

    Relevant code:
    {relevant_code}

    Please provide the following:
    1. Root Cause: A clear explanation of what is causing the test to fail
    2. Error Type: The category of error (e.g., AssertionError, TypeError, etc.)
    3. Fixes: Specific suggestions to fix the issue

    Format your response with these headers.
    """

    _DEFAULT_SUGGESTION_TEMPLATE = """
    Based on the following pytest test failure and root cause analysis,
    suggest specific fixes:

    Test name: {test_name}
    Error type: {error_type}
    Error message: {error_message}

    Traceback:
    {traceback}

    Relevant code:
    {relevant_code}

    Root cause analysis: {root_cause}

    Please provide 1-3 specific code changes or fixes that would solve this issue.
    For each suggestion:
    1. Clearly describe what needs to be changed
    2. Provide the exact code that should be modified or added
    3. Explain why this fix addresses the root cause

    If appropriate, format your code suggestions using this JSON structure:
    ```json
    [
      {{
        "suggestion": "Brief description of the fix",
        "confidence": 0.85,
        "explanation": "Why this works",
        "code_changes": {{
          "file_path": "path/to/file.py",
          "original_code": "the problematic code",
          "fixed_code": "the corrected code"
        }}
      }}
    ]
    ```
    """

    def __init__(
        self,
        analysis_template: Optional[str] = None,
        suggestion_template: Optional[str] = None,
        templates_dir: Optional[Union[str, Path]] = None,
        max_prompt_size: int = 4000,
    ):
        """
        Initialize the PromptBuilder.

        Args:
            analysis_template: Custom template for analysis prompts
            suggestion_template: Custom template for suggestion prompts
            templates_dir: Directory containing template files
            max_prompt_size: Maximum size (in chars) of generated prompts
        """
        self.analysis_template = analysis_template or self._DEFAULT_ANALYSIS_TEMPLATE
        self.suggestion_template = (
            suggestion_template or self._DEFAULT_SUGGESTION_TEMPLATE
        )
        # Handle templates_dir carefully to avoid file not found errors
        if templates_dir:
            try:
                self.templates_dir = Path(templates_dir)
                # Only store if it exists
                if not self.templates_dir.exists():
                    logger.warning(f"Templates directory not found: {templates_dir}")
                    self.templates_dir = None
            except Exception as e:
                logger.warning(f"Error processing templates directory: {e}")
                self.templates_dir = None
        else:
            self.templates_dir = None

        self.max_prompt_size = max_prompt_size

        # Load templates from files if provided and directory exists
        if self.templates_dir and self.templates_dir.exists():
            self._load_templates_from_dir()

        logger.debug(
            "PromptBuilder initialized with max prompt size: %d", max_prompt_size
        )

    def _load_templates_from_dir(self) -> None:
        """Load templates from the templates directory if available."""
        try:
            analysis_file = self.templates_dir / "analysis_template.txt"
            if analysis_file.exists():
                self.analysis_template = analysis_file.read_text()
                logger.debug("Loaded analysis template from %s", analysis_file)

            suggestion_file = self.templates_dir / "suggestion_template.txt"
            if suggestion_file.exists():
                self.suggestion_template = suggestion_file.read_text()
                logger.debug("Loaded suggestion template from %s", suggestion_file)
        except Exception as e:
            logger.warning("Failed to load templates from directory: %s", e)

    def build_analysis_prompt(self, failure: PytestFailure) -> str:
        """
        Build a prompt for analyzing a test failure.

        Args:
            failure: The test failure to analyze

        Returns:
            Formatted prompt string for the LLM
        """
        # Extract necessary fields from the failure
        context = {
            "test_name": failure.test_name,
            "test_file": failure.test_file,
            "error_type": failure.error_type,
            "error_message": failure.error_message,
            "traceback": failure.traceback or "Not available",
            "relevant_code": failure.relevant_code or "Not available",
            "line_number": failure.line_number or "Unknown",
        }

        # Format the template with the failure details
        prompt = self.analysis_template.format(**context)

        # Truncate if necessary to stay within limits
        return self._truncate_prompt_if_needed(prompt)

    def build_suggestion_prompt(
        self, failure: PytestFailure, root_cause: Optional[str] = None
    ) -> str:
        """
        Build a prompt for suggesting fixes for a test failure.

        Args:
            failure: The test failure to generate fixes for
            root_cause: Optional root cause analysis to include

        Returns:
            Formatted prompt string for the LLM
        """
        # Extract necessary fields from the failure
        context = {
            "test_name": failure.test_name,
            "test_file": failure.test_file,
            "error_type": failure.error_type,
            "error_message": failure.error_message,
            "traceback": failure.traceback or "Not available",
            "relevant_code": failure.relevant_code or "Not available",
            "line_number": failure.line_number or "Unknown",
            "root_cause": root_cause or "Unknown",
        }

        # Format the template with the failure details
        prompt = self.suggestion_template.format(**context)

        # Truncate if necessary to stay within limits
        return self._truncate_prompt_if_needed(prompt)

    def build_batch_analysis_prompt(self, failures: List[PytestFailure]) -> str:
        """
        Build a prompt for analyzing multiple similar test failures.

        Args:
            failures: List of related test failures to analyze together

        Returns:
            Formatted prompt string for the LLM
        """
        if not failures:
            return ""

        # Start with a header explaining the batch analysis
        prompt = """
        Analyze the following group of related pytest test failures and
        identify the common root cause:

        """

        # Add details for each failure
        for i, failure in enumerate(failures, 1):
            failure_section = f"""
            --- Failure {i} ---
            Test name: {failure.test_name}
            Error type: {failure.error_type}
            Error message: {failure.error_message}

            """
            prompt += failure_section

        # Add instructions
        prompt += """
        Please provide:
        1. Common Root Cause: What is causing all these tests to fail
        2. Error Pattern: The pattern of errors across these failures
        3. Suggested Fix: A single approach that could address all failures

        Format your response with these headers.
        """

        return self._truncate_prompt_if_needed(prompt)

    def _truncate_prompt_if_needed(self, prompt: str) -> str:
        """
        Truncate the prompt if it exceeds the maximum size.

        Args:
            prompt: The prompt to truncate

        Returns:
            Truncated prompt that fits within size limits
        """
        if len(prompt) <= self.max_prompt_size:
            return prompt

        logger.warning(
            "Prompt exceeds maximum size (%d > %d). Truncating.",
            len(prompt),
            self.max_prompt_size,
        )

        # Calculate truncation sizes ensuring the final string is within limits
        truncation_message = "\n...[CONTENT TRUNCATED DUE TO SIZE LIMITS]...\n"
        message_len = len(truncation_message)
        available_size = self.max_prompt_size - message_len
        keep_each_side = available_size // 2

        # Keep equal portions from start and end
        return prompt[:keep_each_side] + truncation_message + prompt[-keep_each_side:]
