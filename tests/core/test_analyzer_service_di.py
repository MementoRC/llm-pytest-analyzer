#!/usr/bin/env python3
"""
Tests for the DI-based analyzer service implementation.

These tests verify that:
1. The service correctly initializes with injected dependencies
2. The DI container provides the correct dependencies
3. The service functionality works properly with injected dependencies
4. The service can be retrieved from the container
"""

from unittest.mock import Mock

import pytest

from pytest_analyzer.core.analysis.fix_applier import FixApplicationResult

# Import this at function scope to avoid circular imports
from pytest_analyzer.core.analyzer_state_machine import (
    AnalyzerContext,
    AnalyzerStateMachine,
)
from pytest_analyzer.core.di import Container, get_service, initialize_container
from pytest_analyzer.core.di.service_collection import configure_services
from pytest_analyzer.core.llm.llm_service_protocol import LLMServiceProtocol
from pytest_analyzer.core.models.pytest_failure import FixSuggestion, PytestFailure
from pytest_analyzer.utils.path_resolver import PathResolver
from pytest_analyzer.utils.settings import Settings


class TestAnalyzerServiceDI:
    """Test suite for DIPytestAnalyzerService with dependency injection."""

    @pytest.fixture
    def settings(self, tmp_path):
        """Create a Settings object with a temporary project root."""
        settings = Settings()
        settings.project_root = tmp_path
        return settings

    @pytest.fixture
    def path_resolver(self, settings):
        """Create a PathResolver with the temporary project root."""
        return PathResolver(settings.project_root)

    @pytest.fixture
    def analyzer_context(self, settings, path_resolver):
        """Create an AnalyzerContext with dependencies."""
        context = AnalyzerContext(
            settings=settings,
            path_resolver=path_resolver,
        )
        context.suggester = Mock()
        context.analyzer = Mock()
        context.fix_applier = Mock()
        return context

    @pytest.fixture
    def state_machine(self, analyzer_context):
        """Create an AnalyzerStateMachine with the context."""
        return AnalyzerStateMachine(analyzer_context)

    @pytest.fixture
    def analyzer_service(self, settings, path_resolver, state_machine):
        """Create a DIPytestAnalyzerService with injected dependencies."""
        from pytest_analyzer.core.analyzer_service_di import DIPytestAnalyzerService

        return DIPytestAnalyzerService(
            settings=settings,
            path_resolver=path_resolver,
            state_machine=state_machine,
        )

    @pytest.fixture
    def failure(self):
        """Create a dummy PytestFailure for testing."""
        return PytestFailure(
            test_name="test_module::test_function",
            test_file="/path/to/test_file.py",
            error_type="AssertionError",
            error_message="assert 1 == 2",
            traceback="...",
            line_number=10,
            relevant_code="assert value == expected",
        )

    @pytest.fixture
    def fix_suggestion(self, failure):
        """Create a FixSuggestion with code changes for testing."""
        return FixSuggestion(
            failure=failure,
            suggestion="Fix the assertion by correcting the expected value",
            confidence=0.9,
            code_changes={
                "/path/to/source_file.py": "corrected code content",
                "fingerprint": "abcdef123456",  # Metadata key
                "source": "llm",  # Metadata key
            },
            explanation="The test expected 2 but the function returns 1",
        )

    def test_service_initialization(
        self, analyzer_service, settings, path_resolver, state_machine
    ):
        """Test that the service correctly initializes with injected dependencies."""
        assert analyzer_service.settings is settings
        assert analyzer_service.path_resolver is path_resolver
        assert analyzer_service.state_machine is state_machine
        assert analyzer_service.context is state_machine.context
        assert analyzer_service.llm_service is None  # Default is None

    def test_service_initialization_with_llm(
        self, settings, path_resolver, state_machine
    ):
        """Test that the service correctly initializes with an LLM service."""
        from pytest_analyzer.core.analyzer_service_di import DIPytestAnalyzerService

        llm_service = Mock(spec=LLMServiceProtocol)
        service = DIPytestAnalyzerService(
            settings=settings,
            path_resolver=path_resolver,
            state_machine=state_machine,
            llm_service=llm_service,
        )
        assert service.llm_service is llm_service

    def test_apply_suggestion_delegates_to_fix_applier(
        self, analyzer_service, fix_suggestion
    ):
        """Test that apply_suggestion delegates to the fix applier in the context."""
        # Mock the fix applier
        expected_result = FixApplicationResult(
            success=True,
            message="Fix applied successfully",
            applied_files=["/path/to/source_file.py"],
            rolled_back_files=[],
        )
        analyzer_service.context.fix_applier.apply_fix_suggestion.return_value = (
            expected_result
        )

        # Apply suggestion
        result = analyzer_service.apply_suggestion(fix_suggestion)

        # Check that fix applier was called
        analyzer_service.context.fix_applier.apply_fix_suggestion.assert_called_once_with(
            fix_suggestion
        )
        assert result is expected_result

    def test_apply_suggestion_handles_missing_fix_applier(
        self, analyzer_service, fix_suggestion
    ):
        """Test that apply_suggestion handles a missing fix applier gracefully."""
        # Remove fix applier from context
        analyzer_service.context.fix_applier = None

        # Apply suggestion
        result = analyzer_service.apply_suggestion(fix_suggestion)

        # Check result
        assert result is None

    def test_service_from_container(self, settings):
        """Test that the service can be retrieved from the container."""
        # Import here to avoid circular imports
        from pytest_analyzer.core.analyzer_service_di import DIPytestAnalyzerService

        # Explicitly set use_llm to False for this test
        settings.use_llm = False

        # Set up a new container with registered settings
        container = Container()
        container.register_instance(Settings, settings)
        # Configure after we ensure that use_llm is False
        configure_services(container, settings)

        # Get the service from the container
        service = container.resolve(DIPytestAnalyzerService)

        # Check that the service was correctly resolved and initialized
        assert isinstance(service, DIPytestAnalyzerService)
        assert service.settings is container.resolve(Settings)
        assert isinstance(service.path_resolver, PathResolver)
        assert isinstance(service.state_machine, AnalyzerStateMachine)

        # LLM service should be None if use_llm is False
        assert service.llm_service is None, (
            f"LLM service should be None when use_llm is False, got {service.llm_service}"
        )

    def test_service_from_container_with_llm(self, settings):
        """Test that the service can be retrieved from the container with LLM enabled."""
        # Import here to avoid circular imports
        from pytest_analyzer.core.analyzer_service_di import DIPytestAnalyzerService

        # Set up a new container with LLM enabled
        settings.use_llm = True
        container = Container()
        container.register_instance(Settings, settings)
        configure_services(container, settings)

        # Get the service from the container
        service = container.resolve(DIPytestAnalyzerService)

        # Check that the service was correctly resolved and initialized with LLM
        assert isinstance(service, DIPytestAnalyzerService)
        assert service.settings is container.resolve(Settings)
        assert isinstance(service.path_resolver, PathResolver)
        assert isinstance(service.state_machine, AnalyzerStateMachine)
        assert service.llm_service is not None
        # Check the type of the service - different instances are created when resolved multiple times
        assert isinstance(
            service.llm_service, type(container.resolve(LLMServiceProtocol))
        )

    def test_global_container_initialization(self, settings):
        """Test that the global container can be initialized and used to get services."""
        # Import here to avoid circular imports
        from pytest_analyzer.core.analyzer_service_di import DIPytestAnalyzerService

        # Explicitly set use_llm to False for this test
        settings.use_llm = False

        # Initialize global container
        initialize_container(settings)

        # Get the service from the global container
        service = get_service(DIPytestAnalyzerService)

        # Check that the service was correctly resolved and initialized
        assert isinstance(service, DIPytestAnalyzerService)
        assert service.settings.project_root == settings.project_root
        assert isinstance(service.path_resolver, PathResolver)
        assert isinstance(service.state_machine, AnalyzerStateMachine)

        # LLM service should be None if use_llm is False
        assert service.llm_service is None, (
            f"LLM service should be None when use_llm is False, got {service.llm_service}"
        )


if __name__ == "__main__":
    pytest.main(["-v", __file__])
