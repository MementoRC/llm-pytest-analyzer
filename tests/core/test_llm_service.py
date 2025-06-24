import logging
from unittest.mock import MagicMock, patch

import pytest

from pytest_analyzer.core.errors import LLMServiceError
from pytest_analyzer.core.llm.llm_service import LLMService
from pytest_analyzer.core.llm.llm_service_protocol import LLMServiceProtocol
from pytest_analyzer.utils.resource_manager import (
    TimeoutError as ResourceManagerTimeoutError,
)


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
        # Remove 'generate' and 'completions' if present (robust for CI)
        try:
            delattr(mock_client, "generate")
        except AttributeError:
            pass
        try:
            delattr(mock_client, "completions")
        except AttributeError:
            pass
        # Set module attribute robustly
        try:
            mock_client.__class__.__module__ = "unknown"
        except Exception:
            pass

        # Ensure logger is set to NOTSET so caplog can capture all levels
        caplog.set_level(logging.NOTSET, logger="pytest_analyzer.core.llm.llm_service")

        service = LLMService(llm_client=mock_client)
        assert service.llm_client == mock_client
        assert service._llm_request_func is None
        # Use robust substring checks for CI log capture
        assert any("Provided LLM client type" in msg for msg in caplog.messages), (
            f"Expected log message not found in caplog: {caplog.messages}"
        )
        assert any("is not explicitly supported" in msg for msg in caplog.messages), (
            f"Expected log message not found in caplog: {caplog.messages}"
        )

    def test_init_with_timeout(self):
        service = LLMService(timeout_seconds=30)
        assert service.timeout_seconds == 30

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
        # Robust log assertion for CI
        assert any(
            "Using Anthropic client for LLM requests." in msg for msg in caplog.messages
        ), f"Expected Anthropic log message not found in caplog: {caplog.messages}"
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
        assert any(
            "Using OpenAI client for LLM requests." in msg for msg in caplog.messages
        ), f"Expected OpenAI log message not found in caplog: {caplog.messages}"
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
                # Create service but don't need to capture it
                _ = LLMService()

        assert any(
            "Using Anthropic client for LLM requests." in msg for msg in caplog.messages
        ), f"Expected Anthropic log message not found in caplog: {caplog.messages}"
        assert not any("Using OpenAI client" in msg for msg in caplog.messages), (
            f"Unexpected OpenAI log message found in caplog: {caplog.messages}"
        )

    @patch("pytest_analyzer.core.llm.llm_service.Anthropic", None)
    @patch("pytest_analyzer.core.llm.llm_service.openai", None)
    def test_auto_detect_no_client_available(self, caplog):
        import logging

        with caplog.at_level(
            logging.INFO, logger="pytest_analyzer.core.llm.llm_service"
        ):
            service = LLMService()
        assert service._llm_request_func is None
        assert any(
            "No LLM client available or configured" in msg for msg in caplog.messages
        ), (
            f"Expected 'No LLM client available or configured' log not found in caplog: {caplog.messages}"
        )
        assert any(
            "No suitable language model clients found or auto-detected" in msg
            for msg in caplog.messages
        ), (
            f"Expected 'No suitable language model clients found or auto-detected' log not found in caplog: {caplog.messages}"
        )

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
            # Ensure ERROR logs are captured for this test
            with caplog.at_level(
                logging.ERROR, logger="pytest_analyzer.core.llm.llm_service"
            ):
                service = LLMService()  # Will have no _llm_request_func
                with pytest.raises(LLMServiceError) as excinfo:
                    service.send_prompt("test")

        assert "No LLM request function configured" in str(excinfo.value)
        assert any(
            "LLMService cannot send prompt: No LLM request function configured." in msg
            for msg in caplog.messages
        ), f"Expected error log not found in caplog: {caplog.messages}"

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

        with caplog.at_level(
            logging.ERROR, logger="pytest_analyzer.core.llm.llm_service"
        ):
            with pytest.raises(LLMServiceError) as excinfo:
                service.send_prompt("test timeout")

        expected_timeout_message = "Operation exceeded time limit of 0.1 seconds"
        assert expected_timeout_message in str(
            excinfo.value
        )  # Check exception message from LLMServiceError
        assert any(
            f"Failed to send prompt to language model: Timeout - {expected_timeout_message}"
            in msg
            for msg in caplog.messages
        ), f"Expected timeout log not found in caplog: {caplog.messages}"

    def test_send_prompt_timeout_using_resource_manager_exception(self, caplog):
        mock_client = MockAnthropicClient()
        # Simulate the resource_manager's with_timeout raising the error directly
        simulated_error_message = "Simulated timeout"
        mock_client.messages.create.side_effect = ResourceManagerTimeoutError(
            simulated_error_message
        )

        service = LLMService(llm_client=mock_client, timeout_seconds=1)

        with caplog.at_level(
            logging.ERROR, logger="pytest_analyzer.core.llm.llm_service"
        ):
            with pytest.raises(LLMServiceError) as excinfo:
                service.send_prompt("test timeout direct")

        assert simulated_error_message in str(excinfo.value)
        assert any(
            f"Failed to send prompt to language model: Timeout - {simulated_error_message}"
            in msg
            for msg in caplog.messages
        ), f"Expected timeout log not found in caplog: {caplog.messages}"

    def test_send_prompt_anthropic_api_error(self, caplog):
        mock_client = MockAnthropicClient()
        mock_client.messages.create.side_effect = Exception("Anthropic API Error")
        service = LLMService(llm_client=mock_client)

        with caplog.at_level(
            logging.ERROR, logger="pytest_analyzer.core.llm.llm_service"
        ):
            with pytest.raises(LLMServiceError) as excinfo:
                service.send_prompt("test anthropic error")

        assert "Anthropic API Error" in str(excinfo.value)
        # Check that error messages were logged
        assert any(
            "Error making request with Anthropic API: Anthropic API Error" in msg
            for msg in caplog.messages
        ), f"Expected Anthropic API error log not found in caplog: {caplog.messages}"
        assert any(
            "Failed to send prompt to language model: Anthropic API Error" in msg
            for msg in caplog.messages
        ), f"Expected Anthropic API error log not found in caplog: {caplog.messages}"

    def test_send_prompt_openai_api_error(self, caplog):
        mock_client = MockOpenAIClient()
        mock_client.chat.completions.create.side_effect = Exception("OpenAI API Error")
        service = LLMService(llm_client=mock_client)

        with caplog.at_level(
            logging.ERROR, logger="pytest_analyzer.core.llm.llm_service"
        ):
            with pytest.raises(LLMServiceError) as excinfo:
                service.send_prompt("test openai error")

        assert "OpenAI API Error" in str(excinfo.value)
        # Check that error messages were logged
        assert any(
            "Error making request with OpenAI API: OpenAI API Error" in msg
            for msg in caplog.messages
        ), f"Expected OpenAI API error log not found in caplog: {caplog.messages}"
        assert any(
            "Failed to send prompt to language model: OpenAI API Error" in msg
            for msg in caplog.messages
        ), f"Expected OpenAI API error log not found in caplog: {caplog.messages}"

    def test_send_prompt_generic_client_error(self, caplog):
        mock_client = MockGenericClientWithGenerate()
        mock_client.generate = MagicMock(side_effect=Exception("Generic Client Error"))
        service = LLMService(llm_client=mock_client)

        with caplog.at_level(
            logging.ERROR, logger="pytest_analyzer.core.llm.llm_service"
        ):
            with pytest.raises(LLMServiceError) as excinfo:
                service.send_prompt("test generic error")

        assert "Generic Client Error" in str(excinfo.value)
        assert any(
            "Failed to send prompt to language model: Generic Client Error" in msg
            for msg in caplog.messages
        ), f"Expected generic client error log not found in caplog: {caplog.messages}"

    def test_internal_request_with_anthropic_empty_response(self, caplog):
        mock_anthropic_client = (
            MockAnthropicClient()
        )  # Use the actual mock client class
        # Simulate various empty/malformed responses

        # Scenario 1: content is None
        mock_anthropic_client.messages.create.return_value = MagicMock(content=None)
        service = LLMService(llm_client=mock_anthropic_client)
        assert service._request_with_anthropic("prompt") == ""

        # Scenario 2: content is empty list
        mock_anthropic_client.messages.create.return_value = MagicMock(content=[])
        service = LLMService(
            llm_client=mock_anthropic_client
        )  # Re-init or ensure client is updated if necessary
        assert service._request_with_anthropic("prompt") == ""

        # Scenario 3: content[0].text is None
        mock_text_obj = MagicMock(text=None)
        mock_anthropic_client.messages.create.return_value = MagicMock(
            content=[mock_text_obj]
        )
        service = LLMService(llm_client=mock_anthropic_client)
        assert service._request_with_anthropic("prompt") == ""

    def test_internal_request_with_openai_empty_response(self, caplog):
        mock_openai_client = MockOpenAIClient()  # Use the actual mock client class

        # Scenario 1: choices is None
        mock_openai_client.chat.completions.create.return_value = MagicMock(
            choices=None
        )
        service = LLMService(llm_client=mock_openai_client)
        assert service._request_with_openai("prompt") == ""

        # Scenario 2: choices is empty list
        mock_openai_client.chat.completions.create.return_value = MagicMock(choices=[])
        service = LLMService(llm_client=mock_openai_client)
        assert service._request_with_openai("prompt") == ""

        # Scenario 3: message is None
        mock_choice_no_msg = MagicMock(message=None)
        mock_openai_client.chat.completions.create.return_value = MagicMock(
            choices=[mock_choice_no_msg]
        )
        service = LLMService(llm_client=mock_openai_client)
        assert service._request_with_openai("prompt") == ""

        # Scenario 4: message.content is None
        mock_msg_no_content = MagicMock(content=None)
        mock_choice_msg_no_content = MagicMock(message=mock_msg_no_content)
        mock_openai_client.chat.completions.create.return_value = MagicMock(
            choices=[mock_choice_msg_no_content]
        )
        service = LLMService(llm_client=mock_openai_client)
        assert service._request_with_openai("prompt") == ""

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
        assert any(
            "Failed to initialize Anthropic client: Anthropic init failed" in msg
            for msg in caplog.messages
        ), f"Expected Anthropic init fail log not found in caplog: {caplog.messages}"
        # Should fall back to OpenAI if Anthropic init fails
        assert service._llm_request_func is not None
        assert any(
            "Using OpenAI client for LLM requests." in msg for msg in caplog.messages
        ), f"Expected OpenAI log message not found in caplog: {caplog.messages}"

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
        assert any(
            "Using Anthropic client for LLM requests." in msg for msg in caplog.messages
        ), f"Expected Anthropic log message not found in caplog: {caplog.messages}"

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
        assert any(
            "Failed to initialize OpenAI client: OpenAI init failed" in msg
            for msg in caplog.messages
        ), f"Expected OpenAI init fail log not found in caplog: {caplog.messages}"
        assert service_openai_fails._llm_request_func is None
        assert any(
            "No suitable language model clients found or auto-detected." in msg
            for msg in caplog.messages
        ), f"Expected no suitable client log not found in caplog: {caplog.messages}"
