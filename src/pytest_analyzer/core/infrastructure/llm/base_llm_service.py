import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

# Import from the existing structure
from pytest_analyzer.utils.config_types import Settings


class BaseLLMService(ABC):
    """Base class for LLM services to eliminate code duplication between sync and async implementations."""

    def __init__(
        self,
        provider: Optional[Any] = None,  # Changed LLMProvider to Any
        settings: Optional[Settings] = None,
    ):
        self.settings = settings or Settings()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.provider = provider or self._create_default_provider()
        self.model = self.settings.llm_model  # Direct attribute access
        # self.temperature removed
        # self.max_tokens removed
        self.timeout = (
            self.settings.llm_timeout
        )  # Direct attribute access, was llm.timeout_seconds

    def _create_default_provider(self) -> Any:  # Changed LLMProvider to Any
        """Create the default LLM provider based on settings."""
        provider_name = self.settings.llm_provider  # Direct attribute access
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
        # Settings dataclass does not have llm.system_prompt, so return a hardcoded default.
        return "You are a helpful assistant."

    @abstractmethod
    def generate(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Generate a response from the LLM based on the prompt and context."""
        pass
