"""
Factory for creating LLM service instances.

This module provides a factory class for creating instances of LLM services
with appropriate dependencies injected, along with utilities for detecting
and configuring LLM clients from various providers.

The module handles automatic detection of available LLM clients based on:
1. Installed packages (anthropic, openai, azure, together, ollama)
2. Available API keys (from settings or environment variables)
3. Provider preferences specified by the user

Key components:
- LLMServiceFactory: Creates LLM service instances with proper configuration
- detect_llm_client: Auto-detects and initializes available LLM clients
- LLMProvider: Enum of supported providers for consistent identification
- determine_provider: Identifies the provider from a client instance

This module allows the system to work with multiple LLM providers
and gracefully handle fallbacks when preferred providers are unavailable.
It provides a consistent interface for the rest of the system while
abstracting away the implementation details of specific provider SDKs.

Example usage:
    # Detect available client with automatic fallback
    client, provider = detect_llm_client(settings, preferred_provider="anthropic")

    # Create service with the detected client
    service = LLMServiceFactory.create_service(llm_client=client)
"""

import logging
import os
import socket
from enum import Enum, auto
from typing import Any, Dict, Optional, Tuple, Union

# Attempt to import supported LLM clients
try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None  # type: ignore

try:
    import openai
except ImportError:
    openai = None  # type: ignore

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

from ...utils.resource_manager import ResourceMonitor
from ...utils.settings import Settings
from ..parsers.response_parser import ResponseParser
from ..prompts.prompt_builder import PromptBuilder
from .async_llm_service import AsyncLLMService
from .llm_service import LLMService
from .llm_service_protocol import AsyncLLMServiceProtocol, LLMServiceProtocol

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

    if isinstance(client, Anthropic) or "anthropic" in module_name:
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


class LLMServiceFactory:
    """
    Factory for creating LLM service instances with appropriate dependencies.

    This class creates properly configured instances of LLM services,
    injecting dependencies as needed. It handles the creation of both
    synchronous and asynchronous LLM services with consistent configuration,
    and manages the creation of required dependencies if they're not provided.

    The factory provides:
    - Automatic creation of missing dependencies (prompt builder, response parser, etc.)
    - Support for both synchronous and asynchronous service variants
    - Consistent configuration across all service types
    - Proper resource monitoring and timeout handling

    This centralized factory approach ensures that all LLM services are created
    with consistent configuration and dependencies, regardless of where in the
    application they're needed, avoiding configuration duplication and potential
    inconsistencies between service instances.
    """

    @staticmethod
    def create_service(
        sync_mode: bool = True,
        prompt_builder: Optional[PromptBuilder] = None,
        response_parser: Optional[ResponseParser] = None,
        resource_monitor: Optional[ResourceMonitor] = None,
        llm_client: Optional[Any] = None,
        timeout_seconds: int = 60,
        max_tokens: int = 1500,
        model_name: Optional[Dict[str, str]] = None,
        max_prompt_size: int = 4000,
        templates_dir: Optional[str] = None,
    ) -> Union[LLMServiceProtocol, AsyncLLMServiceProtocol]:
        """
        Create an LLM service instance with appropriate dependencies.

        Args:
            sync_mode: Whether to create a synchronous or asynchronous service
            prompt_builder: Optional prompt builder instance (created if None)
            response_parser: Optional response parser instance (created if None)
            resource_monitor: Optional resource monitor (created if None)
            llm_client: Optional pre-configured LLM client
            timeout_seconds: Timeout for LLM API requests
            max_tokens: Maximum tokens in the response
            model_name: Model names for different providers
            max_prompt_size: Maximum size for generated prompts
            templates_dir: Directory containing prompt templates

        Returns:
            A configured LLM service instance (sync or async)
        """
        # Create dependencies if not provided
        if not prompt_builder:
            prompt_builder = PromptBuilder(
                templates_dir=templates_dir,
                max_prompt_size=max_prompt_size,
            )

        if not response_parser:
            response_parser = ResponseParser()

        if not resource_monitor:
            resource_monitor = ResourceMonitor(
                max_memory_mb=None,
                max_time_seconds=timeout_seconds,
            )

        # Create and return the appropriate service type
        if sync_mode:
            logger.debug("Creating synchronous LLM service")
            return LLMService(
                prompt_builder=prompt_builder,
                response_parser=response_parser,
                resource_monitor=resource_monitor,
                llm_client=llm_client,
                timeout_seconds=timeout_seconds,
                max_tokens=max_tokens,
                model_name=model_name,
            )
        else:
            logger.debug("Creating asynchronous LLM service")
            return AsyncLLMService(
                prompt_builder=prompt_builder,
                response_parser=response_parser,
                resource_monitor=resource_monitor,
                llm_client=llm_client,
                timeout_seconds=timeout_seconds,
                max_tokens=max_tokens,
                model_name=model_name,
            )


def detect_llm_client(
    settings: Optional[Settings] = None,
    preferred_provider: Optional[str] = None,
    fallback: bool = True,
) -> Tuple[Optional[Any], Optional[LLMProvider]]:
    """
    Detect and initialize an LLM client based on available libraries and credentials.

    This function attempts to create a client for one of the supported LLM providers
    based on available libraries and API keys. It tries to detect credentials from
    environment variables or from the provided settings.

    Detection process:
    1. Determine provider preference (from parameter or settings)
    2. Build priority list of providers to try (preferred first, then fallbacks if enabled)
    3. For each provider in priority order:
       a. Check if the required library is installed
       b. Look for API keys in settings and environment variables
       c. Attempt to initialize a client if prerequisites are met
    4. Return the first successfully initialized client and its provider type

    Supported providers:
    - "anthropic": Anthropic Claude models (requires anthropic package and API key)
    - "openai": OpenAI GPT models (requires openai package and API key)
    - "azure": Azure OpenAI service (requires openai package, API key, and endpoint)
    - "together": Together.ai models (requires together package and API key)
    - "ollama": Local Ollama deployments (requires ollama package and running service)

    Fallback behavior:
    If fallback=True (default), the function will try all available providers in a
    sensible order if the preferred provider is unavailable or fails. If fallback=False,
    it will only try the preferred provider.

    Args:
        settings: Optional settings containing API keys and configuration
        preferred_provider: Optional name of preferred provider (anthropic, openai, azure, together, ollama)
        fallback: Whether to try other providers if the preferred one fails

    Returns:
        A tuple of (initialized LLM client, provider enum) or (None, None) if no suitable client could be created
    """
    if settings is None:
        settings = Settings()

    # Initialize provider priority based on preference
    providers = []

    # If a preferred provider is specified, try it first
    if preferred_provider:
        if preferred_provider.lower() == "anthropic":
            providers.append(LLMProvider.ANTHROPIC)
        elif preferred_provider.lower() == "openai":
            providers.append(LLMProvider.OPENAI)
        elif preferred_provider.lower() in ["azure", "azure_openai"]:
            providers.append(LLMProvider.AZURE_OPENAI)
        elif preferred_provider.lower() == "together":
            providers.append(LLMProvider.TOGETHER)
        elif preferred_provider.lower() == "ollama":
            providers.append(LLMProvider.OLLAMA)

    # Add remaining providers if fallback is enabled (maintaining a sensible order)
    if fallback or not providers:
        remaining = [
            LLMProvider.ANTHROPIC,
            LLMProvider.OPENAI,
            LLMProvider.AZURE_OPENAI,
            LLMProvider.TOGETHER,
            LLMProvider.OLLAMA,
        ]
        # Only add providers that aren't already in the list
        for provider in remaining:
            if provider not in providers:
                providers.append(provider)

    # Try providers in priority order
    for provider in providers:
        client = _try_initialize_client(provider, settings)
        if client:
            return client, provider

    logger.warning("No suitable LLM client could be detected or initialized")
    return None, None


def _try_initialize_client(provider: LLMProvider, settings: Settings) -> Optional[Any]:
    """
    Try to initialize a client for the specified provider.

    Args:
        provider: The provider to initialize
        settings: Settings containing API keys and configuration

    Returns:
        Initialized client or None if initialization failed
    """
    # Anthropic (Claude)
    if provider == LLMProvider.ANTHROPIC:
        if Anthropic is not None:
            api_key = settings.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")
            if api_key:
                try:
                    logger.info("Creating Anthropic client for LLM requests")
                    return Anthropic(api_key=api_key)
                except Exception as e:
                    logger.warning(f"Failed to initialize Anthropic client: {e}")

    # OpenAI (GPT models)
    elif provider == LLMProvider.OPENAI:
        if openai is not None and hasattr(openai, "OpenAI"):
            api_key = settings.openai_api_key or os.environ.get("OPENAI_API_KEY")
            if api_key:
                try:
                    logger.info("Creating OpenAI client for LLM requests")
                    return openai.OpenAI(api_key=api_key)
                except Exception as e:
                    logger.warning(f"Failed to initialize OpenAI client: {e}")

    # Azure OpenAI
    elif provider == LLMProvider.AZURE_OPENAI:
        if AZURE_OPENAI_AVAILABLE:
            api_key = settings.azure_api_key or os.environ.get("AZURE_OPENAI_API_KEY")
            endpoint = settings.azure_endpoint or os.environ.get(
                "AZURE_OPENAI_ENDPOINT"
            )

            if api_key and endpoint:
                try:
                    logger.info("Creating Azure OpenAI client for LLM requests")
                    return AzureOpenAI(
                        api_key=api_key,
                        azure_endpoint=endpoint,
                        api_version=settings.azure_api_version or "2023-05-15",
                    )
                except Exception as e:
                    logger.warning(f"Failed to initialize Azure OpenAI client: {e}")

    # Together.ai
    elif provider == LLMProvider.TOGETHER:
        if TOGETHER_AVAILABLE:
            api_key = settings.together_api_key or os.environ.get("TOGETHER_API_KEY")
            if api_key:
                try:
                    logger.info("Creating Together.ai client for LLM requests")
                    return Together(api_key=api_key)
                except Exception as e:
                    logger.warning(f"Failed to initialize Together.ai client: {e}")

    # Ollama (local models)
    elif provider == LLMProvider.OLLAMA:
        if OLLAMA_AVAILABLE:
            try:
                # Check if Ollama is running by attempting to connect to its default port
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    # Short timeout to quickly determine if Ollama is running
                    s.settimeout(0.5)
                    # Try to connect to default Ollama port
                    result = s.connect_ex(("localhost", 11434))
                    if result == 0:
                        logger.info("Creating Ollama client for local LLM requests")
                        # Ollama client doesn't need specific initialization
                        return ollama
                    else:
                        logger.warning("Ollama service not detected on port 11434")
            except Exception as e:
                logger.warning(f"Failed to check/initialize Ollama: {e}")

    return None
