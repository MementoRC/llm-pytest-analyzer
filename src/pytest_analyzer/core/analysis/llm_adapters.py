"""
LLM Client Adapter classes for LLMSuggester.

This module provides abstraction for different LLM clients (Anthropic, OpenAI, etc.)
to decouple client-specific logic from the main LLM suggestion workflow.
"""

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


class LLMClientAdapter:
    """
    Abstract base class for LLM client adapters.
    """

    def request(self, prompt: str) -> str:
        raise NotImplementedError

    async def async_request(self, prompt: str) -> str:
        raise NotImplementedError


class AnthropicAdapter(LLMClientAdapter):
    """
    Adapter for Anthropic Claude API.
    """

    def __init__(self, client: Any):
        self.client = client

    def request(self, prompt: str) -> str:
        try:
            message = self.client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}],
            )
            return message.content[0].text
        except Exception as e:
            logger.error(f"Error making request with Anthropic API: {e}")
            return ""

    async def async_request(self, prompt: str) -> str:
        try:
            message = await self.client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}],
            )
            return message.content[0].text
        except Exception as e:
            logger.error(f"Error making async request with Anthropic API: {e}")
            return ""


class OpenAIAdapter(LLMClientAdapter):
    """
    Adapter for OpenAI API.
    """

    def __init__(self, client: Any):
        self.client = client

    def request(self, prompt: str) -> str:
        try:
            completion = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert Python developer helping to fix pytest failures.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=1000,
            )
            return completion.choices[0].message.content
        except Exception as e:
            logger.error(f"Error making request with OpenAI API: {e}")
            return ""

    async def async_request(self, prompt: str) -> str:
        try:
            completion = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert Python developer helping to fix pytest failures.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=1000,
            )
            return completion.choices[0].message.content
        except Exception as e:
            logger.error(f"Error making async request with OpenAI API: {e}")
            return ""


class GenericAdapter(LLMClientAdapter):
    """
    Adapter for generic LLM clients with a 'generate' method.
    """

    def __init__(self, client: Any):
        self.client = client

    def request(self, prompt: str) -> str:
        try:
            response = self.client.generate(prompt=prompt, max_tokens=1000)
            return str(response)
        except Exception as e:
            logger.error(f"Error making request with generic LLM client: {e}")
            return ""

    async def async_request(self, prompt: str) -> str:
        # Fallback: run sync in thread
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.request, prompt)
