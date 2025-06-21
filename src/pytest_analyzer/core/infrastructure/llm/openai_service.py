import queue
import threading
from functools import lru_cache
from typing import Any, Dict, List, Optional

from ...errors import LLMServiceError
from ...llm.llm_service_protocol import LLMServiceProtocol
from ...models.failure_analysis import FailureAnalysis
from ...models.pytest_failure import FixSuggestion, PytestFailure
from .base_llm_service import BaseLLMService


class OpenAIConnectionPool:
    """
    Basic connection pool for OpenAI client.
    """

    def __init__(self, create_client_func, maxsize=4):
        self._pool = queue.Queue(maxsize)
        self._create_client_func = create_client_func
        self._lock = threading.Lock()
        for _ in range(maxsize):
            self._pool.put(self._create_client_func())

    def acquire(self):
        return self._pool.get()

    def release(self, client):
        self._pool.put(client)

    def __enter__(self):
        self._client = self.acquire()
        return self._client

    def __exit__(self, _exc_type, _exc_val, _exc_tb):
        self.release(self._client)


class OpenAIService(BaseLLMService, LLMServiceProtocol):
    """Handles OpenAI API calls."""

    _pool = None
    _pool_lock = threading.Lock()

    def _create_default_provider(self) -> Any:
        """Create the default OpenAI provider based on settings."""
        # For testing and mock scenarios, return None
        # In real implementation, this would create OpenAI client
        self.logger.info("Creating mock OpenAI provider for testing")
        return None

    @classmethod
    def get_pool(cls):
        with cls._pool_lock:
            if cls._pool is None:
                # In real implementation, replace lambda: ... with actual OpenAI client creation
                cls._pool = OpenAIConnectionPool(lambda: None, maxsize=4)
            return cls._pool

    @lru_cache(maxsize=128)
    def _cached_generate(self, prompt: str) -> str:
        # Use connection pool for real client if implemented
        if self.provider is None:
            return f"OpenAI mock response to: {prompt[:50]}..."
        if hasattr(self.provider, "send_request"):
            return self.provider.send_request(prompt)
        return f"OpenAI response to: {prompt[:50]}..."

    def generate(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Generate a response from OpenAI based on the prompt and context."""
        # Use LRU cache for prompt/response
        return self._cached_generate(prompt)

    def send_prompt(self, prompt: str) -> str:
        try:
            return self.generate(prompt)
        except Exception as e:
            self.logger.error(f"Error sending prompt to OpenAI: {e}")
            raise LLMServiceError("Failed to send prompt to OpenAI")

    def analyze_failure(self, failure: PytestFailure) -> FailureAnalysis:
        try:
            # Implement analysis logic using OpenAI
            prompt = f"Analyze the following failure: {failure.error_message}"
            response = self.send_prompt(prompt)
            # Parse response into FailureAnalysis
            return FailureAnalysis(
                failure=failure,
                root_cause=response,
                error_type="OpenAI",
                confidence=0.8,
            )
        except Exception as e:
            self.logger.error(f"Error analyzing failure with OpenAI: {e}")
            raise LLMServiceError("Failed to analyze failure with OpenAI")

    def suggest_fixes(
        self, failure: PytestFailure, analysis: Optional[FailureAnalysis] = None
    ) -> List[FixSuggestion]:
        try:
            # Implement fix suggestion logic using OpenAI
            prompt = f"Suggest fixes for the following failure: {failure.error_message}"
            response = self.send_prompt(prompt)
            # Parse response into a list of FixSuggestion
            return [FixSuggestion(failure=failure, suggestion=response, confidence=0.7)]
        except Exception as e:
            self.logger.error(f"Error suggesting fixes with OpenAI: {e}")
            raise LLMServiceError("Failed to suggest fixes with OpenAI")
