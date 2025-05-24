import logging
from unittest.mock import MagicMock, patch

import pytest

from pytest_analyzer.core.llm.backward_compat import LLMService
from pytest_analyzer.core.llm.llm_service_protocol import LLMServiceProtocol
from pytest_analyzer.utils.resource_manager import TimeoutError as ResourceManagerTimeoutError


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


class MockGenericClientWithGenerate:
    def generate(self, prompt: str, max_tokens: int):
        return f"Generic response to: {prompt}"

    def __init__(self):
        self.__class__.__module__ = "generic_llm"


class MockGenericClientWithCompletions:
    def __init__(self):
        self.completions = MagicMock()
        self.completions.create.return_value = "Generic completions response"
        self.__class__.__module__ = "generic_completions"


class TestLLMService:
    def test_protocol_compliance(self):
        """Test that LLMService implements LLMServiceProtocol."""
        assert isinstance(LLMService(), LLMServiceProtocol)
        # The static check in llm_service.py also helps ensure this.

    def test_init_with_anthropic_client(self):
        mock_client = MockAnthropicClient()
        service = LLMService(llm_client=mock_client)
        assert service.llm_client == mock_client
        assert service._llm_request_func is not None

    def test_init_with_openai_client(self):
        mock_client = MockOpenAIClient()
        service = LLMService(llm_client=mock_client)
        assert service.llm_client == mock_client
        assert service._llm_request_func is not None

    def test_init_with_generic_client_generate(self):
        mock_client = MockGenericClientWithGenerate()
        service = LLMService(llm_client=mock_client)
        assert service.llm_client == mock_client
        assert service._llm_request_func is not None
        # Test that it can call the generic client's method
        response = service.send_prompt("test")
        assert "Generic response to: test" in response

    def test_init_with_generic_client_completions_create(self):
        mock_client = MockGenericClientWithCompletions()
        service = LLMService(llm_client=mock_client)
        assert service.llm_client == mock_client
        assert service._llm_request_func is not None
        response = service.send_prompt("test")
        assert "Generic completions response" in response

    def test_init_with_unsupported_generic_client(self, caplog):
        mock_client = MagicMock()  # A generic mock with no known methods
        # Ensure it doesn't have 'generate' or 'completions'
        del mock_client.generate
        del mock_client.completions
        mock_client.__class__.__module__ = "unknown"

        service = LLMService(llm_client=mock_client)
        assert service.llm_client == mock_client
        assert service._llm_request_func is None
        assert "Provided LLM client type" in caplog.text
        assert "is not explicitly supported" in caplog.text

    def test_init_with_timeout(self):
        service = LLMService(timeout_seconds=30)
        assert service.timeout_seconds == 30

    def test_auto_detect_anthropic_client(self, caplog):
        # Create a fresh mock for Anthropic
        mock_anthropic_instance = MockAnthropicClient()
        mock_anthropic_class = MagicMock(return_value=mock_anthropic_instance)

        # Patch the imports
        with (
            patch("pytest_analyzer.core.llm.llm_service.Anthropic", mock_anthropic_class),
            patch("pytest_analyzer.core.llm.llm_service.openai", None),
        ):
            # Set the logger level for the specific module
            with caplog.at_level(logging.INFO, logger="pytest_analyzer.core.llm.llm_service"):
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
            with caplog.at_level(logging.INFO, logger="pytest_analyzer.core.llm.llm_service"):
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
            patch("pytest_analyzer.core.llm.llm_service.Anthropic", mock_anthropic_class),
            patch("pytest_analyzer.core.llm.llm_service.openai", mock_openai_module),
        ):
            # Set the logger level for the specific module
            with caplog.at_level(logging.INFO, logger="pytest_analyzer.core.llm.llm_service"):
                # Create service but don't need to capture it
                _ = LLMService()

        assert "Using Anthropic client for LLM requests." in caplog.text
        assert "Using OpenAI client" not in caplog.text  # Ensure it didn't also try OpenAI

    @patch("pytest_analyzer.core.llm.llm_service.Anthropic", None)
    @patch("pytest_analyzer.core.llm.llm_service.openai", None)
    def test_auto_detect_no_client_available(self, caplog):
        service = LLMService()
        assert service._llm_request_func is None
        assert "No LLM client available or configured" in caplog.text
        assert "No suitable language model clients found or auto-detected" in caplog.text

    def test_send_prompt_with_anthropic_client(self):
        mock_client_instance = MockAnthropicClient()
        service = LLMService(llm_client=mock_client_instance)
        response = service.send_prompt("Hello Anthropic")
        assert response == "Anthropic response"
        mock_client_instance.messages.create.assert_called_once()
        call_args = mock_client_instance.messages.create.call_args
        assert call_args[1]["messages"][0]["content"] == "Hello Anthropic"

    def test_send_prompt_with_openai_client(self):
        mock_client_instance = MockOpenAIClient()
        service = LLMService(llm_client=mock_client_instance)
        response = service.send_prompt("Hello OpenAI")
        assert response == "OpenAI response"
        mock_client_instance.chat.completions.create.assert_called_once()
        call_args = mock_client_instance.chat.completions.create.call_args
        assert call_args[1]["messages"][1]["content"] == "Hello OpenAI"  # User message

    def test_send_prompt_no_client_configured(self, caplog):
        with (
            patch("pytest_analyzer.core.llm.llm_service.Anthropic", None),
            patch("pytest_analyzer.core.llm.llm_service.openai", None),
        ):
            service = LLMService()  # Will have no _llm_request_func

        response = service.send_prompt("test")
        assert response == ""
        assert "LLMService cannot send prompt: No LLM request function configured." in caplog.text

    def test_send_prompt_timeout(self, caplog):
        mock_client = MockAnthropicClient()

        # Make the client's method simulate a delay that causes a timeout
        def long_running_call(*args, **kwargs):
            import time

            time.sleep(0.2)  # Sleep longer than timeout
            # Should not be reached if timeout works
            mock_message_content = MagicMock()
            mock_message_content.text = "This should not be returned"
            mock_response = MagicMock()
            mock_response.content = [mock_message_content]
            return mock_response

        mock_client.messages.create.side_effect = long_running_call

        service = LLMService(llm_client=mock_client, timeout_seconds=0.1)

        with pytest.raises(ResourceManagerTimeoutError):
            service.send_prompt("test timeout")

        assert "LLM request timed out after 0.1 seconds." in caplog.text

    def test_send_prompt_timeout_using_resource_manager_exception(self, caplog):
        mock_client = MockAnthropicClient()
        # Simulate the resource_manager's with_timeout raising the error directly
        mock_client.messages.create.side_effect = ResourceManagerTimeoutError("Simulated timeout")

        service = LLMService(
            llm_client=mock_client, timeout_seconds=1
        )  # Timeout value doesn't matter as much here

        with pytest.raises(ResourceManagerTimeoutError):
            service.send_prompt("test timeout direct")

        assert (
            "LLM request timed out after 1 seconds." in caplog.text
        )  # The service's timeout is logged

    def test_send_prompt_anthropic_api_error(self, caplog):
        mock_client = MockAnthropicClient()
        mock_client.messages.create.side_effect = Exception("Anthropic API Error")
        service = LLMService(llm_client=mock_client)

        with caplog.at_level(logging.ERROR):
            response = service.send_prompt("test anthropic error")

        assert response == ""  # As per _request_with_anthropic error handling
        # Check that error messages were logged
        assert any(
            "Error making request with Anthropic API: Anthropic API Error" in msg
            for msg in caplog.messages
        )
        # The high-level error is only logged when the exception bubbles up; in this case, it's caught and returns ""
        assert "Error making request with Anthropic API: Anthropic API Error" in caplog.text

    def test_send_prompt_openai_api_error(self, caplog):
        mock_client = MockOpenAIClient()
        mock_client.chat.completions.create.side_effect = Exception("OpenAI API Error")
        service = LLMService(llm_client=mock_client)

        with caplog.at_level(logging.ERROR):
            response = service.send_prompt("test openai error")

        assert response == ""  # As per _request_with_openai error handling
        # Check that error messages were logged
        assert any(
            "Error making request with OpenAI API: OpenAI API Error" in msg
            for msg in caplog.messages
        )
        # The high-level error is only logged when the exception bubbles up; in this case, it's caught and returns ""
        assert "Error making request with OpenAI API: OpenAI API Error" in caplog.text

    def test_send_prompt_generic_client_error(self, caplog):
        mock_client = MockGenericClientWithGenerate()
        mock_client.generate = MagicMock(side_effect=Exception("Generic Client Error"))
        service = LLMService(llm_client=mock_client)

        response = service.send_prompt("test generic error")
        # The generic call path in _get_llm_request_function wraps str(),
        # and send_prompt catches exceptions from timed_request_func
        assert response == ""
        assert "Error during LLM request: Generic Client Error" in caplog.text

    def test_internal_request_with_anthropic_empty_response(self, caplog):
        mock_anthropic_client = MagicMock()
        mock_anthropic_client.__class__.__module__ = "anthropic"
        # Simulate various empty/malformed responses
        mock_anthropic_client.messages.create.return_value = MagicMock(content=None)
        service = LLMService(llm_client=mock_anthropic_client)
        assert service._request_with_anthropic("prompt", mock_anthropic_client) == ""

        mock_anthropic_client.messages.create.return_value = MagicMock(content=[])
        assert service._request_with_anthropic("prompt", mock_anthropic_client) == ""

        mock_text_obj = MagicMock(text=None)
        mock_anthropic_client.messages.create.return_value = MagicMock(content=[mock_text_obj])
        assert service._request_with_anthropic("prompt", mock_anthropic_client) == ""

    def test_internal_request_with_openai_empty_response(self, caplog):
        mock_openai_client = MagicMock()
        mock_openai_client.__class__.__module__ = "openai"
        # Simulate various empty/malformed responses
        mock_openai_client.chat.completions.create.return_value = MagicMock(choices=None)
        service = LLMService(llm_client=mock_openai_client)
        assert service._request_with_openai("prompt", mock_openai_client) == ""

        mock_openai_client.chat.completions.create.return_value = MagicMock(choices=[])
        assert service._request_with_openai("prompt", mock_openai_client) == ""

        mock_choice_no_msg = MagicMock(message=None)
        mock_openai_client.chat.completions.create.return_value = MagicMock(
            choices=[mock_choice_no_msg]
        )
        assert service._request_with_openai("prompt", mock_openai_client) == ""

        mock_msg_no_content = MagicMock(content=None)
        mock_choice_msg_no_content = MagicMock(message=mock_msg_no_content)
        mock_openai_client.chat.completions.create.return_value = MagicMock(
            choices=[mock_choice_msg_no_content]
        )
        assert service._request_with_openai("prompt", mock_openai_client) == ""

    def test_auto_detect_anthropic_init_fails(self, caplog):
        # Mock Anthropic to raise an exception during initialization
        anthropic_class_mock = MagicMock(side_effect=Exception("Anthropic init failed"))

        mock_openai_module = MagicMock()
        mock_openai_module.OpenAI = MagicMock(return_value=MockOpenAIClient())

        with (
            patch("pytest_analyzer.core.llm.llm_service.Anthropic", anthropic_class_mock),
            patch("pytest_analyzer.core.llm.llm_service.openai", mock_openai_module),
        ):
            # Need DEBUG level for initialization failures
            with caplog.at_level(logging.DEBUG, logger="pytest_analyzer.core.llm.llm_service"):
                service = LLMService()  # Auto-detection

        # Check logs
        assert "Failed to initialize Anthropic client: Anthropic init failed" in caplog.text
        # Should fall back to OpenAI if Anthropic init fails
        assert service._llm_request_func is not None
        assert "Using OpenAI client for LLM requests." in caplog.text

    def test_auto_detect_openai_init_fails(self, caplog):
        # First test: When both are available, Anthropic is preferred
        # Use fresh mocks to ensure proper patching
        anthropic_mock = MagicMock(return_value=MockAnthropicClient())

        with patch("pytest_analyzer.core.llm.llm_service.Anthropic", anthropic_mock):
            # Set the logger level for the specific module
            with caplog.at_level(logging.INFO, logger="pytest_analyzer.core.llm.llm_service"):
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
            with caplog.at_level(logging.DEBUG, logger="pytest_analyzer.core.llm.llm_service"):
                service_openai_fails = LLMService()

        # Ensure the logs contain our messages
        assert "Failed to initialize OpenAI client: OpenAI init failed" in caplog.text
        assert service_openai_fails._llm_request_func is None
        assert "No suitable language model clients found or auto-detected." in caplog.text
