from typing import Any, Optional

from ....utils.config_types import Settings
from ...cross_cutting.error_handling import error_context
from ...errors import LLMServiceError
from ...llm.llm_service_protocol import LLMServiceProtocol
from ..base_factory import BaseFactory
from .anthropic_service import AnthropicService
from .mock_service import MockLLMService
from .openai_service import OpenAIService


class LLMServiceFactory(BaseFactory):
    """Factory for creating LLM services based on configuration."""

    def __init__(self, settings: Optional[Settings] = None):
        super().__init__(settings)
        self._register_default_services()

    def _register_default_services(self) -> None:
        """Register the default LLM services."""
        self.register("openai", OpenAIService)
        self.register("anthropic", AnthropicService)
        self.register("mock", MockLLMService)

    def create(
        self, provider_type: Optional[str] = None, provider: Optional[Any] = None
    ) -> LLMServiceProtocol:
        """Create an LLM service with the specified provider.

        Args:
            provider_type: Type of LLM provider to use, or None to use settings
            provider: Optional pre-configured provider instance

        Returns:
            An instance of the appropriate LLM service
        """
        with error_context("Creating LLM service", self.logger, LLMServiceError):
            if provider_type is None:
                provider_type = getattr(self.settings, "llm_provider", "openai")

            # Handle "auto" by defaulting to openai for now
            if provider_type == "auto":
                provider_type = "openai"

            service_class = self.get_implementation(provider_type)
            return service_class(provider=provider, settings=self.settings)
