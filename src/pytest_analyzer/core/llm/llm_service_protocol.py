"""
Protocol definitions for LLM interaction services.

This module defines protocols for both synchronous and asynchronous
LLM service implementations.
"""

from typing import List, Optional, Protocol, runtime_checkable

from ..models.failure_analysis import FailureAnalysis
from ..models.pytest_failure import FixSuggestion, PytestFailure


@runtime_checkable
class LLMServiceProtocol(Protocol):
    """
    Protocol for a synchronous service that interacts with a Language Model.
    """

    def send_prompt(self, prompt: str) -> str:
        """
        Sends a prompt to the LLM and returns the model's response string.

        Args:
            prompt: The prompt string to send to the LLM.

        Returns:
            The response string from the LLM.

        Raises:
            TimeoutError: If the LLM request exceeds the configured timeout.
            Exception: For other LLM communication errors.
        """
        ...

    def analyze_failure(self, failure: PytestFailure) -> FailureAnalysis:
        """
        Analyze a test failure using the LLM.

        Args:
            failure: The test failure to analyze

        Returns:
            FailureAnalysis object with the analysis results

        Raises:
            LLMServiceError: If there's an error communicating with the LLM
            ParsingError: If there's an error parsing the LLM response
        """
        ...

    def suggest_fixes(
        self, failure: PytestFailure, analysis: Optional[FailureAnalysis] = None
    ) -> List[FixSuggestion]:
        """
        Get fix suggestions for a test failure.

        Args:
            failure: The test failure to get fixes for
            analysis: Optional pre-existing analysis

        Returns:
            List of FixSuggestion objects

        Raises:
            LLMServiceError: If there's an error communicating with the LLM
            ParsingError: If there's an error parsing the LLM response
        """
        ...


@runtime_checkable
class AsyncLLMServiceProtocol(Protocol):
    """
    Protocol for an asynchronous service that interacts with a Language Model.
    """

    async def send_prompt(self, prompt: str) -> str:
        """
        Asynchronously sends a prompt to the LLM and returns the model's response.

        Args:
            prompt: The prompt string to send to the LLM.

        Returns:
            The response string from the LLM.

        Raises:
            TimeoutError: If the LLM request exceeds the configured timeout.
            Exception: For other LLM communication errors.
        """
        ...

    async def analyze_failure(self, failure: PytestFailure) -> FailureAnalysis:
        """
        Asynchronously analyze a test failure using the LLM.

        Args:
            failure: The test failure to analyze

        Returns:
            FailureAnalysis object with the analysis results

        Raises:
            LLMServiceError: If there's an error communicating with the LLM
            ParsingError: If there's an error parsing the LLM response
        """
        ...

    async def suggest_fixes(
        self, failure: PytestFailure, analysis: Optional[FailureAnalysis] = None
    ) -> List[FixSuggestion]:
        """
        Asynchronously get fix suggestions for a test failure.

        Args:
            failure: The test failure to get fixes for
            analysis: Optional pre-existing analysis

        Returns:
            List of FixSuggestion objects

        Raises:
            LLMServiceError: If there's an error communicating with the LLM
            ParsingError: If there's an error parsing the LLM response
        """
        ...
