"""Core LLM module for pytest-analyzer."""

# Import the backward-compatible LLMService for existing code
# Also export the modern implementation under a different name
from .async_llm_service import AsyncLLMService
from .backward_compat import LLMService
from .llm_service import LLMService as ModernLLMService
from .llm_service_factory import LLMServiceFactory
from .llm_service_protocol import AsyncLLMServiceProtocol, LLMServiceProtocol

__all__ = [
    "LLMService",
    "LLMServiceProtocol",
    "AsyncLLMServiceProtocol",
    "ModernLLMService",
    "AsyncLLMService",
    "LLMServiceFactory",
]
