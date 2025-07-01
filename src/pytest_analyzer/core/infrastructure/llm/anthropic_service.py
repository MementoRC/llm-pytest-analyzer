import queue
import threading
from functools import lru_cache
from typing import Any, Dict, List, Optional

from pytest_analyzer.metrics.token_tracker import TokenTracker  # New import
from pytest_analyzer.utils.config_types import Settings  # Import Settings

from ...errors import LLMServiceError
from ...llm.llm_service_protocol import LLMServiceProtocol
from ...models.failure_analysis import FailureAnalysis
from ...models.pytest_failure import FixSuggestion, PytestFailure
from .base_llm_service import BaseLLMService
from .token_tracking_interceptor import TokenTrackingInterceptor  # New import


class AnthropicConnectionPool:
    """
    Basic connection pool for Anthropic client.
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


class AnthropicService(BaseLLMService, LLMServiceProtocol):
    """Handles Anthropic API calls."""

    _pool = None
    _pool_lock = threading.Lock()

    def __init__(
        self,
        provider: Optional[Any] = None,
        settings: Optional[Settings] = None,
        token_tracker: Optional[TokenTracker] = None,  # New parameter
        operation_type: str = "general",  # New parameter
    ):
        super().__init__(provider=provider, settings=settings)
        self._token_tracker = token_tracker
        self._operation_type = operation_type

        # If a token_tracker is provided, wrap the actual provider with the interceptor
        if self._token_tracker:
            self.provider = TokenTrackingInterceptor(
                wrapped_llm_client=self.provider,  # This is the mock/real client from _create_default_provider
                token_tracker=self._token_tracker,
                operation_type=self._operation_type,
                provider_name="anthropic",
                model_name=self.model,
            )

    @property
    def provider_name(self) -> str:
        return "anthropic"

    def _create_default_provider(self) -> Any:
        """Create the default Anthropic provider based on settings."""
        # For testing and mock scenarios, return a mock object that simulates Anthropic client behavior
        # In real implementation, this would create anthropic.Anthropic client
        self.logger.info("Creating mock Anthropic provider for testing")

        class MockAnthropicClient:
            def __init__(self, model_name: str):
                self.model_name = model_name
                self.messages = self._MockMessages(model_name)

            class _MockMessages:
                def __init__(self, model_name: str):
                    self.model_name = model_name

                def create(self, messages: List[Dict[str, str]], **kwargs) -> Any:
                    prompt = messages[-1]["content"] if messages else ""
                    response_text = f"Anthropic mock response to: {prompt[:50]}..."

                    # Simulate a response object with content and text
                    class MockContentBlock:
                        text = response_text

                    class MockResponse:
                        content = [MockContentBlock()]
                        # Anthropic responses often include usage, simulate it
                        usage = type(
                            "Usage",
                            (object,),
                            {
                                "input_tokens": len(prompt) // 4,
                                "output_tokens": len(response_text) // 4,
                            },
                        )()

                    return MockResponse()

        return MockAnthropicClient(self.model)

    @classmethod
    def get_pool(cls):
        with cls._pool_lock:
            if cls._pool is None:
                # In real implementation, replace lambda: ... with actual Anthropic client creation
                # For now, it creates a mock client for the pool
                cls._pool = AnthropicConnectionPool(
                    lambda: cls()._create_default_provider(), maxsize=4
                )
            return cls._pool

    @lru_cache(maxsize=128)
    def _cached_generate(self, prompt: str) -> str:
        # Use connection pool for real client if implemented
        # The self.provider is now potentially the TokenTrackingInterceptor
        if self.provider is None:
            return f"Anthropic mock response to: {prompt[:50]}..."

        # The interceptor will wrap the actual call to the LLM client's API
        # We assume self.provider is either the raw client or the interceptor
        # and it exposes a messages.create method for chat models.
        try:
            messages = self._prepare_messages(prompt)
            # This call will be intercepted if self.provider is a TokenTrackingInterceptor
            response_obj = self.provider.messages.create(
                messages=messages,
                model=self.model,
                max_tokens=1024,  # Example parameter
            )
            return response_obj.content[0].text
        except (AttributeError, TypeError):
            # Fallback if provider doesn't have messages.create or doesn't return expected structure
            if hasattr(self.provider, "send_request"):
                return self.provider.send_request(prompt)
            return f"Anthropic response to: {prompt[:50]}..."

    def generate(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Generate a response from Anthropic based on the prompt and context."""
        # Use LRU cache for prompt/response
        return self._cached_generate(prompt)

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
            # The generate call will use the configured interceptor if present
            response = self.generate(prompt)
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
            # The generate call will use the configured interceptor if present
            response = self.generate(prompt)
            # Parse response into a list of FixSuggestion
            return [FixSuggestion(failure=failure, suggestion=response, confidence=0.7)]
        except Exception as e:
            self.logger.error(f"Error suggesting fixes with Anthropic: {e}")
            raise LLMServiceError("Failed to suggest fixes with Anthropic")
