from typing import List, Optional
from .base_llm_service import BaseLLMService
from ..llm_service_protocol import LLMServiceProtocol
from ...models.failure_analysis import FailureAnalysis
from ...models.pytest_failure import PytestFailure, FixSuggestion
from ...errors import LLMServiceError

class AnthropicService(BaseLLMService, LLMServiceProtocol):
    """Handles Anthropic API calls."""

    def send_prompt(self, prompt: str) -> str:
        try:
            # Implement Anthropic API call logic here
            response = self.provider.send_request(prompt)
            return response
        except Exception as e:
            self.logger.error(f"Error sending prompt to Anthropic: {e}")
            raise LLMServiceError("Failed to send prompt to Anthropic")

    def analyze_failure(self, failure: PytestFailure) -> FailureAnalysis:
        try:
            # Implement analysis logic using Anthropic
            prompt = f"Analyze the following failure: {failure.failure_message}"
            response = self.send_prompt(prompt)
            # Parse response into FailureAnalysis
            return FailureAnalysis(failure=failure, root_cause=response, error_type="Anthropic")
        except Exception as e:
            self.logger.error(f"Error analyzing failure with Anthropic: {e}")
            raise LLMServiceError("Failed to analyze failure with Anthropic")

    def suggest_fixes(self, failure: PytestFailure, analysis: Optional[FailureAnalysis] = None) -> List[FixSuggestion]:
        try:
            # Implement fix suggestion logic using Anthropic
            prompt = f"Suggest fixes for the following failure: {failure.failure_message}"
            response = self.send_prompt(prompt)
            # Parse response into a list of FixSuggestion
            return [FixSuggestion.create(failure_id=failure.id, suggestion_text=response)]
        except Exception as e:
            self.logger.error(f"Error suggesting fixes with Anthropic: {e}")
            raise LLMServiceError("Failed to suggest fixes with Anthropic")
