"""
PromptBuilder for pytest_analyzer.

This module provides a PromptBuilder class that constructs prompts
for LLM interactions based on pytest failures and configuration.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Union

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
    _DEFAULT_TEMPLATES = {
        "analysis": """
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
    """,
        "suggestion": """
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
    """,
        "batch_analysis": """
    Analyze the following group of related pytest test failures and identify the common root cause:

    {failure_details}

    Please provide:
    1. Common Root Cause: What is causing all these tests to fail
    2. Error Pattern: The pattern of errors across these failures
    3. Suggested Fix: A single approach that could address all failures

    Format your response with these headers.
    """,
        "llm_suggestion": """
    You are an expert Python developer specializing in pytest. Your task is to analyze a failing test and suggest how to fix it.

    === Test Failure Information ===
    Test: {test_name}
    File: {test_file}
    Line: {line_number}
    Error Type: {error_type}
    Error Message: {error_message}

    === Traceback ===
    {traceback}

    === Code Context ===
    {code_context}

    === Instructions ===
    1. Analyze the test failure and determine the root cause
    2. Provide specific suggestions to fix the issue
    3. Include code snippets where appropriate
    4. Format your response as follows:

    ```json
    [
      {{
        "suggestion": "Your first suggestion here",
        "confidence": 0.9,
        "explanation": "Detailed explanation of the issue and the fix",
        "code_changes": {{
          "file": "path/to/file.py",
          "original_code": "def problematic_function():\n    return 1",
          "fixed_code": "def problematic_function():\n    return 2"
        }}
      }},
      {{
        "suggestion": "Your second suggestion here (if applicable)",
        "confidence": 0.7,
        "explanation": "Alternative explanation and fix",
        "code_changes": {{
          "file": "path/to/file.py",
          "original_code": "...",
          "fixed_code": "..."
        }}
      }}
    ]
    ```

    Provide your analysis:
    """,
    }

    def __init__(
        self,
        templates: Optional[Dict[str, str]] = None,
        analysis_template: Optional[str] = None,  # For backward compatibility
        suggestion_template: Optional[str] = None,  # For backward compatibility
        templates_dir: Optional[Union[str, Path]] = None,
        max_prompt_size: int = 4000,
    ):
        """
        Initialize the PromptBuilder.

        Args:
            templates: Custom templates dictionary (overrides default templates)
            analysis_template: Custom template for analysis prompts (deprecated, use templates)
            suggestion_template: Custom template for suggestion prompts (deprecated, use templates)
            templates_dir: Directory containing template files
            max_prompt_size: Maximum size (in chars) of generated prompts
        """
        # Start with default templates
        self.templates = self._DEFAULT_TEMPLATES.copy()

        # Override with any provided custom templates
        if templates:
            self.templates.update(templates)

        # Handle backward compatibility
        if analysis_template:
            self.templates["analysis"] = analysis_template
        if suggestion_template:
            self.templates["suggestion"] = suggestion_template

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

        logger.debug("PromptBuilder initialized with max prompt size: %d", max_prompt_size)

    def _load_templates_from_dir(self) -> None:
        """Load templates from the templates directory if available."""
        try:
            # Look for each template type in the directory
            for template_name in self.templates.keys():
                template_file = self.templates_dir / f"{template_name}_template.txt"
                if template_file.exists():
                    self.templates[template_name] = template_file.read_text()
                    logger.debug("Loaded %s template from %s", template_name, template_file)
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
            "code_context": failure.relevant_code or "Not available",  # Alias for compatibility
        }

        # Format the template with the failure details
        template = self.templates.get("analysis")
        if not template:
            logger.warning("Analysis template not found, using default")
            template = self._DEFAULT_TEMPLATES["analysis"]

        prompt = template.format(**context)

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
            "code_context": failure.relevant_code or "Not available",  # Alias for compatibility
        }

        # Format the template with the failure details
        template = self.templates.get("suggestion")
        if not template:
            logger.warning("Suggestion template not found, using default")
            template = self._DEFAULT_TEMPLATES["suggestion"]

        prompt = template.format(**context)

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

        # Generate the failure details section
        failure_details = ""
        for i, failure in enumerate(failures, 1):
            failure_details += f"""
            --- Failure {i} ---
            Test name: {failure.test_name}
            Error type: {failure.error_type}
            Error message: {failure.error_message}

            """

        # Get the batch analysis template
        template = self.templates.get("batch_analysis")
        if not template:
            logger.warning("Batch analysis template not found, using default")
            template = self._DEFAULT_TEMPLATES["batch_analysis"]

        # Format the template with the failure details
        prompt = template.format(failure_details=failure_details)

        return self._truncate_prompt_if_needed(prompt)

    def build_llm_suggestion_prompt(self, failure: PytestFailure) -> str:
        """
        Build a prompt for generating LLM-based fix suggestions.

        This is specifically designed to integrate with the LLMSuggester.

        Args:
            failure: The test failure to generate fix suggestions for

        Returns:
            Formatted prompt string for the LLM
        """
        # Extract context from the failure
        context = {
            "test_name": failure.test_name,
            "test_file": failure.test_file,
            "error_type": failure.error_type,
            "error_message": failure.error_message,
            "traceback": failure.traceback or "Not available",
            "line_number": str(failure.line_number) if failure.line_number else "Unknown",
            "code_context": failure.relevant_code or "Not available",
            "relevant_code": failure.relevant_code
            or "Not available",  # Alias for backward compatibility
        }

        # Get the LLM suggestion template
        template = self.templates.get("llm_suggestion")
        if not template:
            logger.warning("LLM suggestion template not found, using default")
            template = self._DEFAULT_TEMPLATES["llm_suggestion"]

        # Format the template with the context
        prompt = template.format(**context)

        # Truncate if necessary to stay within limits
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
