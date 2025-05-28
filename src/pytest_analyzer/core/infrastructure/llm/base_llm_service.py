import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

# Import from the existing structure
from pytest_analyzer.utils.config_types import Settings


class BaseLLMService(ABC):
    """Base class for LLM services to eliminate code duplication between sync and async implementations."""

    def __init__(
        self,
        provider: Optional[LLMProvider] = None,
        settings: Optional[Settings] = None,
    ):
        self.settings = settings or Settings()
        self.provider = provider or self._create_default_provider()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.model = self.settings.get("llm.model", "gpt-3.5-turbo")
        self.temperature = float(self.settings.get("llm.temperature", "0.7"))
        self.max_tokens = int(self.settings.get("llm.max_tokens", "2000"))
        self.timeout = int(self.settings.get("llm.timeout_seconds", "30"))

    def _create_default_provider(self) -> LLMProvider:
        """Create the default LLM provider based on settings."""
        provider_name = self.settings.get("llm.provider", "openai")
        self.logger.info(f"Creating default LLM provider: {provider_name}")

        # This would be implemented in subclasses or use a factory pattern
        raise NotImplementedError("Subclasses must implement _create_default_provider")

    def _prepare_messages(
        self, prompt: str, context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, str]]:
        """Prepare messages for the LLM provider with consistent formatting."""
        messages = [
            {"role": "system", "content": self._get_system_prompt(context)},
            {"role": "user", "content": prompt},
        ]
        return messages

    def _get_system_prompt(self, context: Optional[Dict[str, Any]] = None) -> str:
        """Get the system prompt, potentially customized based on context."""
        return self.settings.get("llm.system_prompt", "You are a helpful assistant.")

    @abstractmethod
    def generate(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Generate a response from the LLM based on the prompt and context."""
        pass
