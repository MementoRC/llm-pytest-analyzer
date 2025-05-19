"""
Tests for the LLMServiceFactory class.
"""

from unittest.mock import MagicMock, patch

from pytest_analyzer.core.llm.async_llm_service import AsyncLLMService
from pytest_analyzer.core.llm.llm_service import LLMService
from pytest_analyzer.core.llm.llm_service_factory import LLMServiceFactory
from pytest_analyzer.core.llm.llm_service_protocol import (
    AsyncLLMServiceProtocol,
    LLMServiceProtocol,
)
from pytest_analyzer.core.parsers.response_parser import ResponseParser
from pytest_analyzer.core.prompts.prompt_builder import PromptBuilder
from pytest_analyzer.utils.resource_manager import ResourceMonitor


class TestLLMServiceFactory:
    """Tests for the LLMServiceFactory class."""

    def test_create_sync_service(self):
        """Test creating a synchronous LLM service."""
        service = LLMServiceFactory.create_service(sync_mode=True)
        assert isinstance(service, LLMService)
        assert isinstance(service, LLMServiceProtocol)

    def test_create_async_service(self):
        """Test creating an asynchronous LLM service."""
        service = LLMServiceFactory.create_service(sync_mode=False)
        assert isinstance(service, AsyncLLMService)
        assert isinstance(service, AsyncLLMServiceProtocol)

    def test_create_service_with_deps(self):
        """Test creating a service with explicit dependencies."""
        # Create mock dependencies
        prompt_builder = MagicMock(spec=PromptBuilder)
        response_parser = MagicMock(spec=ResponseParser)
        resource_monitor = MagicMock(spec=ResourceMonitor)
        llm_client = MagicMock()

        # Create service with the dependencies
        service = LLMServiceFactory.create_service(
            sync_mode=True,
            prompt_builder=prompt_builder,
            response_parser=response_parser,
            resource_monitor=resource_monitor,
            llm_client=llm_client,
            timeout_seconds=30,
            max_tokens=2000,
            model_name={"openai": "custom-model"},
        )

        # Verify the dependencies were injected correctly
        assert service.prompt_builder is prompt_builder
        assert service.response_parser is response_parser
        assert service.resource_monitor is resource_monitor
        assert service.llm_client is llm_client
        assert service.timeout_seconds == 30
        assert service.max_tokens == 2000
        assert service.model_name["openai"] == "custom-model"

    def test_create_service_with_auto_deps(self):
        """Test creating a service with auto-created dependencies."""
        service = LLMServiceFactory.create_service(
            sync_mode=True,
            max_prompt_size=3000,
        )

        # Verify auto-created dependencies
        assert isinstance(service.prompt_builder, PromptBuilder)
        assert isinstance(service.response_parser, ResponseParser)
        assert isinstance(service.resource_monitor, ResourceMonitor)
        assert service.prompt_builder.max_prompt_size == 3000

    def test_create_service_with_templates_dir(self):
        """Test creating a service with a templates directory."""
        with patch.object(PromptBuilder, "_load_templates_from_dir"):
            service = LLMServiceFactory.create_service(
                sync_mode=True,
                templates_dir="/path/to/templates",
            )

            # Verify the PromptBuilder was initialized with the templates directory
            assert service.prompt_builder.templates_dir is not None
            assert str(service.prompt_builder.templates_dir) == "/path/to/templates"
