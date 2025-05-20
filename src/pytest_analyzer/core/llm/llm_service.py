"""
Synchronous LLM service implementation.

This module provides a synchronous implementation of the LLM service
for interacting with Language Models.
"""

import contextlib
import logging
from typing import Any, Callable, Dict, List, Optional, Type

# Attempt to import specific LLM SDKs
try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None  # type: ignore

try:
    import openai
except ImportError:
    openai = None  # type: ignore

from ...utils.resource_manager import ResourceMonitor, TimeoutError
from ...utils.settings import Settings
from ..errors import LLMServiceError, ParsingError
from ..models.failure_analysis import FailureAnalysis
from ..models.pytest_failure import FixSuggestion, PytestFailure
from ..parsers.response_parser import ResponseParser
from ..prompts.prompt_builder import PromptBuilder
from .llm_service_protocol import LLMServiceProtocol

logger = logging.getLogger(__name__)


@contextlib.contextmanager
def error_context(error_type: Type[Exception], error_message: str):
    """
    Context manager for consistent error handling.

    Args:
        error_type: Type of exception to raise on error
        error_message: Error message to include

    Yields:
        Control back to the caller
    """
    try:
        yield
    except TimeoutError as e:
        logger.error(f"{error_message}: Timeout - {str(e)}")
        raise error_type(f"{error_message}: Timeout - {str(e)}") from e
    except Exception as e:
        logger.error(f"{error_message}: {str(e)}")
        raise error_type(f"{error_message}: {str(e)}") from e


class LLMService(LLMServiceProtocol):
    """
    Synchronous implementation for sending prompts to a Language Model.
    Uses dependency injection for configuration and resources.
    """

    def __init__(
        self,
        prompt_builder: PromptBuilder,
        response_parser: ResponseParser,
        resource_monitor: Optional[ResourceMonitor] = None,
        llm_client: Optional[Any] = None,
        disable_auto_detection: bool = False,
        settings: Optional[Settings] = None,
        timeout_seconds: int = 60,
        max_tokens: int = 1500,
        model_name: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize the LLMService.

        Args:
            prompt_builder: Component for building prompts
            response_parser: Component for parsing responses
            resource_monitor: Optional resource usage monitor
            llm_client: Optional pre-configured LLM client
            disable_auto_detection: If True, disables auto-detection of LLM clients
                                      when llm_client is None.
            settings: Optional application settings.
            timeout_seconds: Timeout for LLM API requests
            max_tokens: Maximum tokens in the response
            model_name: Model names for different providers (e.g., {"openai": "gpt-3.5-turbo", "anthropic": "claude-3-haiku-20240307"})
        """
        self.prompt_builder = prompt_builder
        self.response_parser = response_parser
        self.resource_monitor = resource_monitor or ResourceMonitor(
            max_memory_mb=None,
            max_time_seconds=timeout_seconds,
        )
        self.llm_client = llm_client
        self.disable_auto_detection = disable_auto_detection
        self.settings = settings
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens
        self.model_name = model_name or {
            "openai": "gpt-3.5-turbo",
            "anthropic": "claude-3-haiku-20240307",
        }

        # Set up the appropriate request function based on available clients
        self._llm_request_func = self._get_llm_request_function()

        if not self._llm_request_func and not self.llm_client:
            logger.warning(
                "No LLM client available or configured for LLMService. "
                "Install 'anthropic' or 'openai' packages, or provide an llm_client."
            )

    def send_prompt(self, prompt: str) -> str:
        """
        Send a prompt to the LLM and get the response.

        Args:
            prompt: The prompt to send to the LLM

        Returns:
            The LLM's response as a string

        Raises:
            LLMServiceError: If there's an error communicating with the LLM
        """
        if not self._llm_request_func:
            logger.error(
                "LLMService cannot send prompt: No LLM request function configured."
            )
            raise LLMServiceError("No LLM request function configured")

        with error_context(LLMServiceError, "Failed to send prompt to language model"):
            # Start the resource monitor
            with self.resource_monitor:
                result = self._llm_request_func(prompt)
                return result

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
        # Build the prompt
        prompt = self.prompt_builder.build_analysis_prompt(failure)

        # Send the prompt to the LLM
        with error_context(
            LLMServiceError, "Failed to get test failure analysis from language model"
        ):
            response = self.send_prompt(prompt)

        # Parse the response
        try:
            analysis = self.response_parser.parse_analysis_response(failure, response)
            return analysis
        except Exception as e:
            raise ParsingError(f"Failed to parse analysis response: {str(e)}") from e

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
        # If we don't have an analysis yet, get one first
        if not analysis:
            analysis = self.analyze_failure(failure)

        # Build the prompt for suggestions
        prompt = self.prompt_builder.build_suggestion_prompt(
            failure, root_cause=analysis.root_cause
        )

        # Send the prompt to the LLM
        with error_context(
            LLMServiceError, "Failed to get fix suggestions from language model"
        ):
            response = self.send_prompt(prompt)

        # Parse the response
        try:
            suggestions = self.response_parser.parse_suggestion_response(
                failure, analysis, response
            )
            return suggestions
        except Exception as e:
            raise ParsingError(f"Failed to parse suggestion response: {str(e)}") from e

    def _get_llm_request_function(self) -> Optional[Callable[[str], str]]:
        """
        Get the appropriate function for making LLM requests.
        Detects available LLM clients if no specific client is provided.

        Returns:
            Callable function or None if no suitable client found
        """
        # If a client was explicitly provided
        if self.llm_client:
            client_module_name = self.llm_client.__class__.__module__.lower()

            if "anthropic" in client_module_name and hasattr(
                self.llm_client, "messages"
            ):
                # For Anthropic client
                return lambda p: self._request_with_anthropic(p)
            elif "openai" in client_module_name and hasattr(self.llm_client, "chat"):
                # For OpenAI client
                return lambda p: self._request_with_openai(p)
            else:
                logger.warning(
                    f"Provided LLM client type ({client_module_name}) is not explicitly supported. "
                    "Using a generic approach."
                )
                # Try a generic approach if known methods exist
                if hasattr(self.llm_client, "generate"):
                    return lambda p: str(
                        self.llm_client.generate(prompt=p, max_tokens=self.max_tokens)
                    )
                elif hasattr(self.llm_client, "completions") and hasattr(
                    self.llm_client.completions, "create"
                ):
                    return lambda p: str(
                        self.llm_client.completions.create(
                            prompt=p, max_tokens=self.max_tokens
                        )
                    )
                return None

        # If llm_client is None and auto-detection is disabled, return None
        if self.disable_auto_detection:
            logger.info("LLM client auto-detection is disabled.")
            return None

        # Auto-detect available clients
        if Anthropic:
            try:
                client = Anthropic()
                logger.info("Using Anthropic client for LLM requests.")
                self.llm_client = client
                return lambda p: self._request_with_anthropic(p)
            except Exception as e:
                logger.debug(f"Failed to initialize Anthropic client: {e}")

        if openai and hasattr(openai, "OpenAI"):
            try:
                client = openai.OpenAI()
                logger.info("Using OpenAI client for LLM requests.")
                self.llm_client = client
                return lambda p: self._request_with_openai(p)
            except Exception as e:
                logger.debug(f"Failed to initialize OpenAI client: {e}")

        logger.warning("No suitable language model clients found or auto-detected.")
        return None

    def _request_with_anthropic(self, prompt: str) -> str:
        """
        Make a request with the Anthropic Claude API.

        Args:
            prompt: The prompt to send

        Returns:
            The response text

        Raises:
            Exception: If there's an error with the request
        """
        try:
            message = self.llm_client.messages.create(
                model=self.model_name.get("anthropic", "claude-3-haiku-20240307"),
                max_tokens=self.max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            if (
                message.content
                and isinstance(message.content, list)
                and message.content[0].text
            ):
                return message.content[0].text
            return ""
        except Exception as e:
            logger.error(f"Error making request with Anthropic API: {e}")
            raise

    def _request_with_openai(self, prompt: str) -> str:
        """
        Make a request with the OpenAI API.

        Args:
            prompt: The prompt to send

        Returns:
            The response text

        Raises:
            Exception: If there's an error with the request
        """
        try:
            completion = self.llm_client.chat.completions.create(
                model=self.model_name.get("openai", "gpt-3.5-turbo"),
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert Python developer helping to fix pytest failures.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=self.max_tokens,
            )
            if completion.choices and completion.choices[0].message:
                return completion.choices[0].message.content or ""
            return ""
        except Exception as e:
            logger.error(f"Error making request with OpenAI API: {e}")
            raise
