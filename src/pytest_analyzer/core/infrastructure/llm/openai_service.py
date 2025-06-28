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
                provider_name=self.provider_name,
                model_name=self.model,
            )

    @property
    def provider_name(self) -> str:
        return "openai"

    def _create_default_provider(self) -> Any:
        """Create the default OpenAI provider based on settings."""
        # For testing and mock scenarios, return a mock object that simulates OpenAI client behavior
        # In real implementation, this would create openai.OpenAI client
        self.logger.info("Creating mock OpenAI provider for testing")

        class MockOpenAIClient:
            def __init__(self, model_name: str):
                self.model_name = model_name
                self.chat = self._MockChat(model_name)

            class _MockChat:
                def __init__(self, model_name: str):
                    self.completions = self._MockCompletions(model_name)

                class _MockCompletions:
                    def __init__(self, model_name: str):
                        self.model_name = model_name

                    def create(self, messages: List[Dict[str, str]], **kwargs) -> Any:
                        prompt = messages[-1]["content"] if messages else ""
                        response_text = f"OpenAI mock response to: {prompt[:50]}..."

                        # Simulate a response object with choices and message content
                        class MockMessage:
                            content = response_text

                        class MockChoice:
                            message = MockMessage()

                        class MockResponse:
                            choices = [MockChoice()]
                            # Add token usage for more realistic testing
                            usage = type(
                                "Usage",
                                (object,),
                                {
                                    "prompt_tokens": len(prompt) // 4,
                                    "completion_tokens": len(response_text) // 4,
                                    "total_tokens": len(prompt) // 4
                                    + len(response_text) // 4,
                                },
                            )()

                        return MockResponse()

        return MockOpenAIClient(self.model)

    @classmethod
    def get_pool(cls):
        with cls._pool_lock:
            if cls._pool is None:
                # In real implementation, replace lambda: ... with actual OpenAI client creation
                # For now, it creates a mock client for the pool
                cls._pool = OpenAIConnectionPool(
                    lambda: cls()._create_default_provider(), maxsize=4
                )
            return cls._pool

    @lru_cache(maxsize=128)
    def _cached_generate(self, prompt: str) -> str:
        # Use connection pool for real client if implemented
        # The self.provider is now potentially the TokenTrackingInterceptor
        if self.provider is None:
            return f"OpenAI mock response to: {prompt[:50]}..."

        # The interceptor will wrap the actual call to the LLM client's API
        # We assume self.provider is either the raw client or the interceptor
        # and it exposes a chat.completions.create method for chat models.
        try:
            messages = self._prepare_messages(prompt)
            # This call will be intercepted if self.provider is a TokenTrackingInterceptor
            response_obj = self.provider.chat.completions.create(
                messages=messages,
                model=self.model,
                temperature=0.7,  # Example parameter
                max_tokens=500,  # Example parameter
            )
            return response_obj.choices[0].message.content
        except AttributeError:
            # Fallback if provider doesn't have chat.completions.create (e.g., older mock or direct string provider)
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
            # The generate call will use the configured interceptor if present
            response = self.generate(prompt)
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
            # The generate call will use the configured interceptor if present
            response = self.generate(prompt)
            # Parse response into a list of FixSuggestion
            return [FixSuggestion(failure=failure, suggestion=response, confidence=0.7)]
        except Exception as e:
            self.logger.error(f"Error suggesting fixes with OpenAI: {e}")
            raise LLMServiceError("Failed to suggest fixes with OpenAI")
