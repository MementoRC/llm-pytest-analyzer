from typing import Any, Dict, List, Optional

from ...errors import LLMServiceError
from ...llm.llm_service_protocol import LLMServiceProtocol
from ...models.failure_analysis import FailureAnalysis
from ...models.pytest_failure import FixSuggestion, PytestFailure
from .base_llm_service import BaseLLMService


class AnthropicService(BaseLLMService, LLMServiceProtocol):
    """Handles Anthropic API calls."""

    def _create_default_provider(self) -> Any:
        """Create the default Anthropic provider based on settings."""
        # For testing and mock scenarios, return None
        # In real implementation, this would create Anthropic client
        self.logger.info("Creating mock Anthropic provider for testing")
        return None

    def generate(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Generate a response from Anthropic based on the prompt and context."""
        if self.provider is None:
            # Mock implementation for testing
            return f"Anthropic mock response to: {prompt[:50]}..."

        # If provider has send_request method (mock), use it
        if hasattr(self.provider, "send_request"):
            return self.provider.send_request(prompt)

        # Real implementation would use Anthropic API here
        return f"Anthropic response to: {prompt[:50]}..."

    def send_prompt(self, prompt: str) -> str:
        try:
            return self.generate(prompt)
        except Exception as e:
            self.logger.error(f"Error sending prompt to Anthropic: {e}")
            raise LLMServiceError("Failed to send prompt to Anthropic")

    def analyze_failure(self, failure: PytestFailure) -> FailureAnalysis:
        try:
            # Implement analysis logic using Anthropic
            prompt = f"Analyze the following failure: {failure.error_message}"
            response = self.send_prompt(prompt)
            # Parse response into FailureAnalysis
            return FailureAnalysis(
                failure=failure,
                root_cause=response,
                error_type="Anthropic",
                confidence=0.8,
            )
        except Exception as e:
            self.logger.error(f"Error analyzing failure with Anthropic: {e}")
            raise LLMServiceError("Failed to analyze failure with Anthropic")

    def suggest_fixes(
        self, failure: PytestFailure, analysis: Optional[FailureAnalysis] = None
    ) -> List[FixSuggestion]:
        try:
            # Implement fix suggestion logic using Anthropic
            prompt = f"Suggest fixes for the following failure: {failure.error_message}"
            response = self.send_prompt(prompt)
            # Parse response into a list of FixSuggestion
            return [FixSuggestion(failure=failure, suggestion=response, confidence=0.7)]
        except Exception as e:
            self.logger.error(f"Error suggesting fixes with Anthropic: {e}")
            raise LLMServiceError("Failed to suggest fixes with Anthropic")
