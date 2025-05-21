"""
Pytest fixtures for Dependency Injection.

This module provides fixtures for using the DI container in tests,
making it easy to inject mock objects and control test dependencies.
"""

import logging
from typing import Optional
from unittest.mock import MagicMock

import pytest

from pytest_analyzer.core.analysis.failure_analyzer import FailureAnalyzer
from pytest_analyzer.core.analysis.fix_applier import FixApplier
from pytest_analyzer.core.analysis.fix_suggester import FixSuggester
from pytest_analyzer.core.analysis.llm_suggester import LLMSuggester

# Import this at function scope to avoid circular imports
from pytest_analyzer.core.analyzer_state_machine import (
    AnalyzerContext,
    AnalyzerStateMachine,
)
from pytest_analyzer.core.di import Container, initialize_container, set_container
from pytest_analyzer.core.di.service_collection import configure_services
from pytest_analyzer.core.llm.llm_service_protocol import LLMServiceProtocol
from pytest_analyzer.utils.path_resolver import PathResolver
from pytest_analyzer.utils.settings import Settings

logger = logging.getLogger(__name__)


@pytest.fixture
def di_container():
    """
    Create a clean DI container for testing.

    This fixture creates a new, empty container for each test,
    ensuring tests don't affect each other through the container.

    Returns:
        A fresh Container instance
    """
    # Create a new container
    container = Container()

    # Make it the global container for this test
    set_container(container)

    # Yield container for test use
    yield container

    # Reset after test
    set_container(None)


@pytest.fixture
def configured_container(di_container, tmp_path):
    """
    Configure a DI container with default services.

    This fixture provides a container that has all the standard services
    registered, using a temporary directory as the project root.

    Args:
        di_container: The base container to configure
        tmp_path: Pytest temporary directory

    Returns:
        A Container with all standard services registered
    """
    # Create settings with temporary project root
    settings = Settings()
    settings.project_root = tmp_path

    # Configure the container
    configure_services(di_container, settings)

    return di_container


@pytest.fixture
def mock_di_services(di_container):
    """
    Register mock services in the DI container.

    This fixture registers mock services for key components,
    allowing tests to control their behavior.

    Args:
        di_container: The container to register mocks in

    Returns:
        A dictionary containing all the mock services
    """
    # Create mock services
    mocks = {
        "settings": MagicMock(spec=Settings),
        "path_resolver": MagicMock(spec=PathResolver),
        "analyzer": MagicMock(spec=FailureAnalyzer),
        "suggester": MagicMock(spec=FixSuggester),
        "fix_applier": MagicMock(spec=FixApplier),
        "llm_service": MagicMock(spec=LLMServiceProtocol),
        "llm_suggester": MagicMock(spec=LLMSuggester),
    }

    # Register mocks in the container
    di_container.register_instance(Settings, mocks["settings"])
    di_container.register_instance(PathResolver, mocks["path_resolver"])
    di_container.register_instance(FailureAnalyzer, mocks["analyzer"])
    di_container.register_instance(FixSuggester, mocks["suggester"])
    di_container.register_instance(FixApplier, mocks["fix_applier"])
    di_container.register_instance(LLMServiceProtocol, mocks["llm_service"])
    di_container.register_instance(LLMSuggester, mocks["llm_suggester"])

    # Create and register context with mock dependencies
    context = AnalyzerContext(
        settings=mocks["settings"],
        path_resolver=mocks["path_resolver"],
        llm_service=mocks["llm_service"],
    )
    context.analyzer = mocks["analyzer"]
    context.suggester = mocks["suggester"]
    context.fix_applier = mocks["fix_applier"]
    context.llm_suggester = mocks["llm_suggester"]
    di_container.register_instance(AnalyzerContext, context)

    # Create and register state machine with context
    state_machine = AnalyzerStateMachine(context)
    di_container.register_instance(AnalyzerStateMachine, state_machine)

    # Create analyzer service with the dependencies (import here to avoid circular imports)
    from pytest_analyzer.core.analyzer_service_di import DIPytestAnalyzerService

    service = DIPytestAnalyzerService(
        settings=mocks["settings"],
        path_resolver=mocks["path_resolver"],
        state_machine=state_machine,
        llm_service=mocks["llm_service"],
    )
    di_container.register_instance(DIPytestAnalyzerService, service)

    return mocks


@pytest.fixture
def di_analyzer_service(configured_container):
    """
    Get the analyzer service from the configured container.

    This fixture provides a fully configured analyzer service with real dependencies.

    Args:
        configured_container: The configured DI container

    Returns:
        A DIPytestAnalyzerService instance
    """
    from pytest_analyzer.core.analyzer_service_di import DIPytestAnalyzerService

    return configured_container.resolve(DIPytestAnalyzerService)


@pytest.fixture
def di_analyzer_service_with_mocks(di_container, mock_di_services):
    """
    Get the analyzer service with all dependencies mocked.

    This fixture provides an analyzer service with mock dependencies
    that can be controlled in tests.

    Args:
        di_container: The DI container
        mock_di_services: Dictionary of mock services

    Returns:
        A DIPytestAnalyzerService instance with mock dependencies
    """
    from pytest_analyzer.core.analyzer_service_di import DIPytestAnalyzerService

    return di_container.resolve(DIPytestAnalyzerService)


@pytest.fixture
def di_cli_invoke():
    """
    Helper fixture to invoke the DI-based CLI.

    This fixture provides a function to call the DI-based CLI with arguments,
    setting up the DI container and temporary settings for each invocation.

    Returns:
        A function to invoke the CLI
    """
    import sys

    from pytest_analyzer.cli.analyzer_cli_di import main

    def _invoke(*args, use_settings: Optional[Settings] = None):
        # Save original argv
        original_argv = sys.argv.copy()

        try:
            # Set up argv for the CLI
            sys.argv = ["pytest-analyzer-di"] + list(args)

            # Initialize container with settings if provided
            if use_settings:
                initialize_container(use_settings)

            # Run the CLI
            result = main()

            return result
        finally:
            # Restore original argv
            sys.argv = original_argv
            # Reset container
            set_container(None)

    return _invoke
