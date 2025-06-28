import logging
from typing import Any

# from pytest_analyzer.llm.llm_service_protocol import LLMServiceProtocol
from pytest_analyzer.metrics.token_tracker import TokenTracker

logger = logging.getLogger(__name__)


class AttributeProxy:
    """
    A proxy for non-callable attributes that might have callable methods.
    This allows us to intercept method calls on nested objects like messages.create().
    """

    def __init__(self, wrapped_object: Any, interceptor: "TokenTrackingInterceptor"):
        self._wrapped_object = wrapped_object
        self._interceptor = interceptor

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._wrapped_object, name)
        if callable(attr):
            # If the attribute is callable, wrap it with the interceptor
            return self._interceptor._wrap_method(attr, name)
        return attr


class TokenTrackingInterceptor:
    """
    A generic interceptor for LLM client objects to track token consumption.

    This class wraps an underlying LLM client (e.g., OpenAI client, Anthropic client)
    and intercepts its method calls (like chat completions) to track token usage
    and cost via a TokenTracker instance.
    """

    def __init__(
        self,
        wrapped_llm_client: Any,  # The actual LLM client object (e.g., openai.OpenAI().chat.completions)
        token_tracker: TokenTracker,
        operation_type: str,
        provider_name: str,
        model_name: str,
    ):
        self._wrapped_llm_client = wrapped_llm_client
        self._token_tracker = token_tracker
        self._operation_type = operation_type
        self._provider_name = provider_name
        self._model_name = model_name
        logger.debug(
            f"TokenTrackingInterceptor initialized for {provider_name}/{model_name} ({operation_type})"
        )

    def __getattr__(self, name: str) -> Any:
        """
        Delegates attribute access to the wrapped LLM client.
        This allows the interceptor to behave like the original client.
        """
        attr = getattr(self._wrapped_llm_client, name)
        if callable(attr):
            # If it's a callable attribute (like 'create'), wrap it
            return self._wrap_method(attr, name)
        else:
            # For non-callable attributes, wrap them in a proxy that can intercept method calls
            return AttributeProxy(attr, self)

    def _wrap_method(self, method: Any, method_name: str) -> Any:
        """
        Wraps a method of the underlying LLM client to intercept its calls.
        """

        def intercepted_method(*args, **kwargs):
            prompt_content = ""
            response_content = ""
            try:
                # Attempt to extract prompt from common LLM client call patterns
                if "messages" in kwargs:
                    for msg in kwargs["messages"]:
                        if msg.get("role") == "user":
                            prompt_content = msg.get("content", "")
                            break
                elif "prompt" in kwargs:  # For older completion APIs or specific models
                    prompt_content = kwargs["prompt"]

                # Execute the original method
                response = method(*args, **kwargs)

                # Attempt to extract response from common LLM client response patterns
                if hasattr(response, "choices") and response.choices:
                    response_content = response.choices[0].message.content
                elif (
                    hasattr(response, "content") and response.content
                ):  # Anthropic response
                    response_content = response.content[0].text
                elif hasattr(response, "text"):  # For some older models or embeddings
                    response_content = response.text
                elif isinstance(response, str):  # If the response is directly a string
                    response_content = response

                # Use the model from kwargs if available, otherwise fall back to the initialized model
                model_to_use = kwargs.get("model", self._model_name)

                # Track tokens using the TokenTracker
                self._token_tracker.track_llm_call(
                    prompt=prompt_content,
                    response=response_content,
                    operation_type=self._operation_type,
                    provider=self._provider_name,
                    model=model_to_use,
                )
                return response
            except Exception as e:
                logger.error(f"Error during intercepted LLM call ({method_name}): {e}")
                # Re-raise the exception to not alter original behavior
                raise

        return intercepted_method
