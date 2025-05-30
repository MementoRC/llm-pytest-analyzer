from .base_llm_service import BaseLLMService
from ..llm_service_protocol import LLMServiceProtocol
from ...models.failure_analysis import FailureAnalysis
from ...models.pytest_failure import PytestFailure, FixSuggestion

class MockLLMService(BaseLLMService, LLMServiceProtocol):
    """Returns mock responses for testing."""

    def send_prompt(self, prompt: str) -> str:
        # Return a mock response
        return "Mock response"

    def analyze_failure(self, failure: PytestFailure) -> FailureAnalysis:
        # Return a mock FailureAnalysis
        return FailureAnalysis(failure=failure, root_cause="Mock root cause", error_type="Mock")

    def suggest_fixes(self, failure: PytestFailure, analysis: Optional[FailureAnalysis] = None) -> List[FixSuggestion]:
        # Return a mock list of FixSuggestion
        return [FixSuggestion.create(failure_id=failure.id, suggestion_text="Mock fix suggestion")]
