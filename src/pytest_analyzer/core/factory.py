"""
Factory functions for creating analyzer service instances.

This module contains factory functions for creating instances of the analyzer service
without using the DI container. These functions are primarily for backward compatibility.
"""

from typing import Any

from ..utils.path_resolver import PathResolver
from ..utils.settings import Settings
from .analyzer_service_di import DIPytestAnalyzerService
from .analyzer_state_machine import AnalyzerContext, AnalyzerStateMachine
from .llm.backward_compat import LLMService


def create_analyzer_service(
    settings: Settings = None, llm_client: Any = None
) -> DIPytestAnalyzerService:
    """
    Create an instance of the DI-based analyzer service.

    This factory function provides a bridge between the old style of instantiating
    services and the new DI approach.

    Args:
        settings: Optional Settings object (creates default settings if None)
        llm_client: Optional LLM client (used if settings.use_llm is True)

    Returns:
        A configured DIPytestAnalyzerService instance
    """
    # Create or use settings
    settings = settings or Settings()

    # Create path resolver
    path_resolver = PathResolver(settings.project_root)

    # Create LLM service if needed
    llm_service = None
    if settings.use_llm:
        llm_service = LLMService(llm_client=llm_client, timeout_seconds=settings.llm_timeout)

    # Create analyzer context
    context = AnalyzerContext(
        settings=settings, path_resolver=path_resolver, llm_service=llm_service
    )

    # Create analyzer state machine
    state_machine = AnalyzerStateMachine(context)

    # Create and return the service
    return DIPytestAnalyzerService(
        settings=settings,
        path_resolver=path_resolver,
        state_machine=state_machine,
        llm_service=llm_service,
    )
