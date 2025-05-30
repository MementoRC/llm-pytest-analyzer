from typing import Optional
from .base_factory import BaseFactory
from .openai_service import OpenAIService
from .anthropic_service import AnthropicService
from .mock_service import MockLLMService
from ..llm_service_protocol import LLMServiceProtocol
from ...utils.config_types import Settings

class LLMServiceFactory(BaseFactory):
    """Factory for creating LLM services based on provider type."""

    def __init__(self, settings: Optional[Settings] = None):
        super().__init__(settings)
        self.register("openai", OpenAIService)
        self.register("anthropic", AnthropicService)
        self.register("mock", MockLLMService)

    def create(self, provider_type: str, *args, **kwargs) -> LLMServiceProtocol:
        """Create an LLM service based on the provider type."""
        service_class = self.get_implementation(provider_type)
        return service_class(*args, **kwargs)
