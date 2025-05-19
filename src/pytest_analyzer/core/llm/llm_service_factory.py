"""
Factory for creating LLM service instances.

This module provides a factory class for creating instances of LLM services
with appropriate dependencies injected.
"""

import logging
from typing import Any, Dict, Optional, Union

from ...utils.resource_manager import ResourceMonitor
from ..parsers.response_parser import ResponseParser
from ..prompts.prompt_builder import PromptBuilder
from .async_llm_service import AsyncLLMService
from .llm_service import LLMService
from .llm_service_protocol import AsyncLLMServiceProtocol, LLMServiceProtocol

logger = logging.getLogger(__name__)


class LLMServiceFactory:
    """
    Factory for creating LLM service instances with appropriate dependencies.

    This class creates properly configured instances of LLM services,
    injecting dependencies as needed.
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
