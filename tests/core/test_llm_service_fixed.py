import logging
from unittest.mock import MagicMock, patch

from pytest_analyzer.core.llm.llm_service import LLMService


# Mock classes for external clients
class MockAnthropicClient:
    def __init__(self):
        self.messages = MagicMock()
        # Mock structure for response: message.content[0].text
        mock_message_content = MagicMock()
        mock_message_content.text = "Anthropic response"
        mock_response = MagicMock()
        mock_response.content = [mock_message_content]
        self.messages.create.return_value = mock_response
        # Add mock module attribute
        self.__class__.__module__ = "anthropic"


class MockOpenAIClient:
    def __init__(self):
        self.chat = MagicMock()
        self.chat.completions = MagicMock()
        # Mock structure for response: completion.choices[0].message.content
        mock_choice = MagicMock()
        mock_choice.message = MagicMock()
        mock_choice.message.content = "OpenAI response"
        mock_completion = MagicMock()
        mock_completion.choices = [mock_choice]
        self.chat.completions.create.return_value = mock_completion
        # Add mock module attribute
        self.__class__.__module__ = "openai"


class TestLLMServiceFixed:
    def test_auto_detect_anthropic_client(self, caplog):
        # Create a fresh mock for Anthropic
        mock_anthropic_instance = MockAnthropicClient()
        mock_anthropic_class = MagicMock(return_value=mock_anthropic_instance)

        # Patch the imports
        with (
            patch(
                "pytest_analyzer.core.llm.llm_service.Anthropic", mock_anthropic_class
            ),
            patch("pytest_analyzer.core.llm.llm_service.openai", None),
        ):
            # Set the logger level for the specific module
            with caplog.at_level(
                logging.INFO, logger="pytest_analyzer.core.llm.llm_service"
            ):
                service = LLMService()

        assert service._llm_request_func is not None
        assert "Using Anthropic client for LLM requests." in caplog.text
        # Test sending a prompt to ensure the mock client is used
        response = service.send_prompt("test anthropic auto")
        assert response == "Anthropic response"

    def test_auto_detect_openai_client(self, caplog):
        # We need to ensure openai itself is not None for the hasattr check
        mock_openai_class = MagicMock(return_value=MockOpenAIClient())
        mock_openai_module = MagicMock()
        mock_openai_module.OpenAI = mock_openai_class

        with (
            patch("pytest_analyzer.core.llm.llm_service.Anthropic", None),
            patch("pytest_analyzer.core.llm.llm_service.openai", mock_openai_module),
        ):
            # Set the logger level for the specific module
            with caplog.at_level(
                logging.INFO, logger="pytest_analyzer.core.llm.llm_service"
            ):
                service = LLMService()

        assert service._llm_request_func is not None
        assert "Using OpenAI client for LLM requests." in caplog.text
        response = service.send_prompt("test openai auto")
        assert response == "OpenAI response"

    def test_auto_detect_prefers_anthropic(self, caplog):
        # Ensure openai.OpenAI exists but Anthropic is preferred
        mock_anthropic_instance = MockAnthropicClient()
        mock_anthropic_class = MagicMock(return_value=mock_anthropic_instance)

        mock_openai_module = MagicMock()
        mock_openai_module.OpenAI = MagicMock(return_value=MockOpenAIClient())

        with (
            patch(
                "pytest_analyzer.core.llm.llm_service.Anthropic", mock_anthropic_class
            ),
            patch("pytest_analyzer.core.llm.llm_service.openai", mock_openai_module),
        ):
            # Set the logger level for the specific module
            with caplog.at_level(
                logging.INFO, logger="pytest_analyzer.core.llm.llm_service"
            ):
                _ = LLMService()

        assert "Using Anthropic client for LLM requests." in caplog.text
        assert (
            "Using OpenAI client" not in caplog.text
        )  # Ensure it didn't also try OpenAI

    def test_auto_detect_anthropic_init_fails(self, caplog):
        # Mock Anthropic to raise an exception during initialization
        anthropic_class_mock = MagicMock(side_effect=Exception("Anthropic init failed"))

        mock_openai_module = MagicMock()
        mock_openai_module.OpenAI = MagicMock(return_value=MockOpenAIClient())

        with (
            patch(
                "pytest_analyzer.core.llm.llm_service.Anthropic", anthropic_class_mock
            ),
            patch("pytest_analyzer.core.llm.llm_service.openai", mock_openai_module),
        ):
            # Need DEBUG level for initialization failures
            with caplog.at_level(
                logging.DEBUG, logger="pytest_analyzer.core.llm.llm_service"
            ):
                service = LLMService()  # Auto-detection

        # Check logs
        assert (
            "Failed to initialize Anthropic client: Anthropic init failed"
            in caplog.text
        )
        # Should fall back to OpenAI if Anthropic init fails
        assert service._llm_request_func is not None
        assert "Using OpenAI client for LLM requests." in caplog.text

    def test_auto_detect_openai_init_fails(self, caplog):
        # First test: When both are available, Anthropic is preferred
        # Use fresh mocks to ensure proper patching
        anthropic_mock = MagicMock(return_value=MockAnthropicClient())

        with patch("pytest_analyzer.core.llm.llm_service.Anthropic", anthropic_mock):
            # Set the logger level for the specific module
            with caplog.at_level(
                logging.INFO, logger="pytest_analyzer.core.llm.llm_service"
            ):
                # Make a fresh service with Anthropic available
                service = LLMService()

        assert service._llm_request_func is not None
        assert "Using Anthropic client for LLM requests." in caplog.text

        # Reset the log for the next test
        caplog.clear()

        # Second test: When Anthropic is not available but OpenAI fails
        # Create a new service with Anthropic unavailable and OpenAI failing
        mock_openai_module = MagicMock()
        mock_openai_module.OpenAI.side_effect = Exception("OpenAI init failed")

        with (
            patch("pytest_analyzer.core.llm.llm_service.Anthropic", None),
            patch("pytest_analyzer.core.llm.llm_service.openai", mock_openai_module),
        ):
            # Need DEBUG level to catch init failures
            with caplog.at_level(
                logging.DEBUG, logger="pytest_analyzer.core.llm.llm_service"
            ):
                service_openai_fails = LLMService()

        # Ensure the logs contain our messages
        assert "Failed to initialize OpenAI client: OpenAI init failed" in caplog.text
        assert service_openai_fails._llm_request_func is None
        assert (
            "No suitable language model clients found or auto-detected." in caplog.text
        )
