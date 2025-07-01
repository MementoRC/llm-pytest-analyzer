"""
Asynchronous LLM service implementation.

This module provides an asynchronous implementation of the LLM service
for interacting with Language Models.
"""

import asyncio
import contextlib
import logging
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

# Attempt to import specific LLM SDKs with async support
try:
    import openai
except ImportError:
    openai = None  # type: ignore

try:
    from anthropic import Anthropic, AsyncAnthropic
except ImportError:
    AsyncAnthropic = None  # type: ignore
    Anthropic = None  # type: ignore

# Azure OpenAI
try:
    from openai import AzureOpenAI

    AZURE_OPENAI_AVAILABLE = True
except ImportError:
    AZURE_OPENAI_AVAILABLE = False
    AzureOpenAI = None  # type: ignore

# Together.ai
try:
    from together import Together

    TOGETHER_AVAILABLE = True
except ImportError:
    TOGETHER_AVAILABLE = False
    Together = None  # type: ignore

# Ollama for local models
try:
    import ollama

    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    ollama = None  # type: ignore


from ...utils.resource_manager import ResourceMonitor, TimeoutError
from ..errors import LLMServiceError, ParsingError
from ..infrastructure.llm.base_llm_service import BaseLLMService
from ..models.failure_analysis import FailureAnalysis
from ..models.pytest_failure import FixSuggestion, PytestFailure
from ..parsers.response_parser import ResponseParser
from ..prompts.prompt_builder import PromptBuilder
from .llm_service_protocol import AsyncLLMServiceProtocol

logger = logging.getLogger(__name__)


class LLMProvider(Enum):
    """Supported LLM providers."""

    ANTHROPIC = auto()
    OPENAI = auto()
    AZURE_OPENAI = auto()
    TOGETHER = auto()
    OLLAMA = auto()
    CUSTOM = auto()
    UNKNOWN = auto()


def get_provider_name(provider: LLMProvider) -> str:
    """Get a human-readable name for a provider."""
    return {
        LLMProvider.ANTHROPIC: "Anthropic Claude",
        LLMProvider.OPENAI: "OpenAI",
        LLMProvider.AZURE_OPENAI: "Azure OpenAI",
        LLMProvider.TOGETHER: "Together.ai",
        LLMProvider.OLLAMA: "Ollama (local)",
        LLMProvider.CUSTOM: "Custom",
        LLMProvider.UNKNOWN: "Unknown",
    }.get(provider, "Unknown")


def determine_provider(client: Any) -> LLMProvider:
    """
    Determine the provider type from a client object.

    Args:
        client: An LLM client instance

    Returns:
        The identified provider type
    """
    if client is None:
        return LLMProvider.UNKNOWN

    # Get the module name for provider detection
    module_name = client.__class__.__module__.lower()

    if isinstance(client, (Anthropic, AsyncAnthropic)) or "anthropic" in module_name:
        return LLMProvider.ANTHROPIC
    elif isinstance(client, AzureOpenAI) or "azure" in module_name:
        return LLMProvider.AZURE_OPENAI
    elif "openai" in module_name:
        return LLMProvider.OPENAI
    elif isinstance(client, Together) or "together" in module_name:
        return LLMProvider.TOGETHER
    elif "ollama" in module_name:
        return LLMProvider.OLLAMA
    else:
        return LLMProvider.CUSTOM


@contextlib.asynccontextmanager
async def error_context(error_type: Type[Exception], error_message: str):
    """
    Async context manager for consistent error handling.

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


class AsyncLLMService(BaseLLMService, AsyncLLMServiceProtocol):
    """
    Asynchronous implementation for sending prompts to a Language Model.
    Uses dependency injection for configuration and resources.
    """

    def __init__(
        self,
        prompt_builder: PromptBuilder,
        response_parser: ResponseParser,
        resource_monitor: Optional[ResourceMonitor] = None,
        llm_client: Optional[Any] = None,
        timeout_seconds: int = 60,
        max_tokens: int = 1500,
        model_name: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize the AsyncLLMService.

        Args:
            prompt_builder: Component for building prompts
            response_parser: Component for parsing responses
            resource_monitor: Optional resource usage monitor
            llm_client: Optional pre-configured LLM client
            timeout_seconds: Timeout for LLM API requests
            max_tokens: Maximum tokens in the response
            model_name: Model names for different providers (e.g., {"openai": "gpt-3.5-turbo", "anthropic": "claude-3-haiku-20240307"})
        """
        # Initialize base class with provider and settings
        super().__init__(provider=llm_client, settings=None)

        self.prompt_builder = prompt_builder
        self.response_parser = response_parser
        self.resource_monitor = resource_monitor or ResourceMonitor(
            max_memory_mb=None,
            max_time_seconds=timeout_seconds,
        )
        self.llm_client = llm_client or self.provider  # Use provider from base class
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens
        self.model_name = model_name or {
            "openai": "gpt-3.5-turbo",
            "anthropic": "claude-3-haiku-20240307",
        }

        # Set up the appropriate async request function based on available clients
        self._async_llm_request_func = self._get_async_llm_request_function()

        if not self._async_llm_request_func and not self.llm_client:
            logger.warning(
                "No LLM client available or configured for AsyncLLMService. "
                "Install 'anthropic' or 'openai' packages, or provide an llm_client."
            )

    @property
    def provider_name(self) -> str:
        """Returns the name of the LLM provider (e.g., 'openai', 'anthropic')."""
        provider_enum = determine_provider(self.provider)
        return get_provider_name(provider_enum)

    def generate(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Synchronous wrapper for generate_async.

        This implements the abstract method from BaseLLMService.
        """
        return asyncio.run(self.generate_async(prompt, context))

    async def generate_async(
        self, prompt: str, context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate a response asynchronously from the LLM based on the prompt and context.
        """
        return await self.send_prompt(prompt)

    async def send_prompt(self, prompt: str) -> str:
        """
        Asynchronously send a prompt to the LLM and get the response.

        Args:
            prompt: The prompt to send to the LLM

        Returns:
            The LLM's response as a string

        Raises:
            LLMServiceError: If there's an error communicating with the LLM
        """
        if not self._async_llm_request_func:
            logger.error(
                "AsyncLLMService cannot send prompt: No LLM request function configured."
            )
            raise LLMServiceError("No LLM request function configured")

        async with error_context(
            LLMServiceError, "Failed to send prompt to language model"
        ):
            # Start the resource monitor
            with self.resource_monitor:
                result = await asyncio.wait_for(
                    self._async_llm_request_func(prompt), timeout=self.timeout_seconds
                )
                return result

    async def analyze_failure(self, failure: PytestFailure) -> FailureAnalysis:
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
        async with error_context(
            LLMServiceError, "Failed to get test failure analysis from language model"
        ):
            response = await self.send_prompt(prompt)

        # Parse the response
        try:
            analysis = self.response_parser.parse_analysis_response(failure, response)
            return analysis
        except Exception as e:
            raise ParsingError(f"Failed to parse analysis response: {str(e)}") from e

    async def suggest_fixes(
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
            analysis = await self.analyze_failure(failure)

        # Build the prompt for suggestions
        prompt = self.prompt_builder.build_suggestion_prompt(
            failure, root_cause=analysis.root_cause
        )

        # Send the prompt to the LLM
        async with error_context(
            LLMServiceError, "Failed to get fix suggestions from language model"
        ):
            response = await self.send_prompt(prompt)

        # Parse the response
        try:
            suggestions = self.response_parser.parse_suggestion_response(
                failure, analysis, response
            )
            return suggestions
        except Exception as e:
            raise ParsingError(f"Failed to parse suggestion response: {str(e)}") from e

    def _create_default_provider(self) -> Any:
        """
        Create the default async LLM provider based on settings.

        This implements the abstract method from BaseLLMService.
        """
        # Use auto-detection logic for async clients
        if AsyncAnthropic:
            try:
                return AsyncAnthropic()
            except Exception as e:
                logger.debug(f"Failed to initialize Anthropic async client: {e}")

        if openai and hasattr(openai, "AsyncOpenAI"):
            try:
                return openai.AsyncOpenAI()
            except Exception as e:
                logger.debug(f"Failed to initialize OpenAI async client: {e}")

        return None

    def _get_async_llm_request_function(
        self,
    ) -> Optional[Callable[[str], Tuple[str, Any]]]:
        """
        Get the appropriate async function for making LLM requests.
        Detects available LLM clients if no specific client is provided.

        Returns:
            Asynchronous callable function or None if no suitable client found
        """
        # If a client was explicitly provided
        if self.llm_client:
            client_module_name = self.llm_client.__class__.__module__.lower()

            if "anthropic" in client_module_name and hasattr(
                self.llm_client, "messages"
            ):
                # For Anthropic client
                return self._make_anthropic_async_request
            elif "openai" in client_module_name and hasattr(self.llm_client, "chat"):
                # For OpenAI client
                return self._make_openai_async_request
            else:
                logger.warning(
                    f"Provided LLM client type ({client_module_name}) is not explicitly supported for async. "
                    "Using a generic approach."
                )
                return None

        # Auto-detect available clients
        if AsyncAnthropic:
            try:
                client = AsyncAnthropic()
                logger.info("Using Anthropic async client for LLM requests.")
                self.llm_client = client
                self.provider = client  # Update the provider in base class
                return self._make_anthropic_async_request
            except Exception as e:
                logger.debug(f"Failed to initialize Anthropic async client: {e}")

        if openai and hasattr(openai, "AsyncOpenAI"):
            try:
                client = openai.AsyncOpenAI()
                logger.info("Using OpenAI async client for LLM requests.")
                self.llm_client = client
                self.provider = client  # Update the provider in base class
                return self._make_openai_async_request
            except Exception as e:
                logger.debug(f"Failed to initialize OpenAI async client: {e}")

        logger.warning(
            "No suitable async language model clients found or auto-detected."
        )
        return None

    async def _make_anthropic_async_request(self, prompt: str) -> str:
        """
        Make an asynchronous request with the Anthropic Claude API.

        Args:
            prompt: The prompt to send

        Returns:
            The response text

        Raises:
            Exception: If there's an error with the request
        """
        try:
            message = await self.llm_client.messages.create(
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
            logger.error(f"Error making async request with Anthropic API: {e}")
            raise

    async def _make_openai_async_request(self, prompt: str) -> str:
        """
        Make an asynchronous request with the OpenAI API.

        Args:
            prompt: The prompt to send

        Returns:
            The response text

        Raises:
            Exception: If there's an error with the request
        """
        try:
            completion = await self.llm_client.chat.completions.create(
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
            logger.error(f"Error making async request with OpenAI API: {e}")
            raise
