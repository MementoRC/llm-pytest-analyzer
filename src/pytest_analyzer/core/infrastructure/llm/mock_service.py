from typing import Any, Dict, List, Optional

from ...llm.llm_service_protocol import LLMServiceProtocol
from ...models.failure_analysis import FailureAnalysis
from ...models.pytest_failure import FixSuggestion, PytestFailure
from .base_llm_service import BaseLLMService


class MockLLMService(BaseLLMService, LLMServiceProtocol):
    """Returns mock responses for testing."""

    def _create_default_provider(self) -> Any:
        """Create the default mock provider."""
        # Mock service doesn't need a real provider
        self.logger.info("Creating mock provider for testing")
        return None

    def generate(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Generate a mock response."""
        return "Mock response"

    def send_prompt(self, prompt: str) -> str:
        # Return a mock response using generate method
        return self.generate(prompt)

    def analyze_failure(self, failure: PytestFailure) -> FailureAnalysis:
        # Return a mock FailureAnalysis
        return FailureAnalysis(
            failure=failure,
            root_cause="Mock root cause",
            error_type="Mock",
            confidence=0.5,
        )

    def suggest_fixes(
        self, failure: PytestFailure, analysis: Optional[FailureAnalysis] = None
    ) -> List[FixSuggestion]:
        # Return a mock list of FixSuggestion
        return [
            FixSuggestion(
                failure=failure, suggestion="Mock fix suggestion", confidence=0.5
            )
        ]
