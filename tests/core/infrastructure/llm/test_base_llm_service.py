import logging
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch

import pytest

from pytest_analyzer.core.infrastructure.llm.base_llm_service import BaseLLMService

# Updated import path for Settings
from pytest_analyzer.utils.config_types import Settings

# LLMProvider import removed


# --- Concrete Test Implementation of BaseLLMService ---
class ConcreteTestLLMService(BaseLLMService):
    """A concrete implementation of BaseLLMService for testing purposes."""

    def __init__(
        self,
        provider: Optional[Any] = None,  # Changed LLMProvider to Any
        settings: Optional[Settings] = None,
    ):
        self.created_provider_instance: Optional[Any] = (
            None  # Changed LLMProvider to Any
        )
        self.logger = logging.getLogger(self.__class__.__name__)
        super().__init__(provider=provider, settings=settings)

    def _create_default_provider(self) -> Any:  # Changed LLMProvider to Any
        """Override to provide a mock provider for tests if one isn't passed to __init__."""
        self.logger.info(f"{self.__class__.__name__}._create_default_provider called")
        self.created_provider_instance = MagicMock()  # Removed spec=LLMProvider
        return self.created_provider_instance

    def generate(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Mock implementation of the abstract generate method."""
        self.logger.info(
            f"{self.__class__.__name__}.generate called with prompt: {prompt}"
        )
        return f"Generated response for: {prompt}"


# --- Fixtures ---
@pytest.fixture
def mock_settings_values() -> Dict[str, Any]:  # Changed type hint value to Any
    """Provides a dictionary of settings values for mocking."""
    return {
        "llm_model": "test-model-from-settings",
        "llm_timeout": 45,  # Integer, was string "45" and key "llm.timeout_seconds"
        "llm_provider": "test-provider-from-settings",  # Was "llm.provider"
        # Removed: "llm.temperature", "llm.max_tokens", "llm.system_prompt"
    }


@pytest.fixture
def mock_llm_provider() -> MagicMock:
    """Provides a MagicMock instance."""
    return MagicMock()  # Removed spec=LLMProvider


@pytest.fixture
def mock_settings(mock_settings_values: Dict[str, Any]) -> MagicMock:
    """Provides a MagicMock of the Settings class, configured with mock_settings_values."""
    settings_mock = MagicMock(spec=Settings)
    # Configure attributes directly
    settings_mock.llm_model = mock_settings_values["llm_model"]
    settings_mock.llm_timeout = mock_settings_values["llm_timeout"]
    settings_mock.llm_provider = mock_settings_values["llm_provider"]

    # Ensure any other attributes from Settings dataclass that BaseLLMService might
    # potentially access in the future are defaulted if not in mock_settings_values.
    # For now, llm_model, llm_timeout, llm_provider are the ones used.
    # Example for future:
    # default_s = Settings()
    # if not hasattr(settings_mock, 'llm_api_key'):
    #     settings_mock.llm_api_key = default_s.llm_api_key

    return settings_mock


# --- Test Cases ---


def test_constructor_initialization_with_provider_and_settings(
    mock_settings: MagicMock,
    mock_llm_provider: MagicMock,
    # mock_settings_values: Dict[str, Any], # No longer directly needed for assertions here
):
    """Tests constructor when both provider and settings are explicitly passed."""
    service = ConcreteTestLLMService(provider=mock_llm_provider, settings=mock_settings)

    assert service.settings == mock_settings
    assert service.provider == mock_llm_provider
    assert service.created_provider_instance is None
    assert isinstance(service.logger, logging.Logger)
    assert service.logger.name == "ConcreteTestLLMService"
    assert (
        service.model == mock_settings.llm_model
    )  # Assert against mock_settings attribute
    assert (
        service.timeout == mock_settings.llm_timeout
    )  # Assert against mock_settings attribute
    # Removed temperature and max_tokens assertions


def test_constructor_initialization_with_settings_only(
    mock_settings: MagicMock,
    # mock_settings_values: Dict[str, Any], # No longer directly needed
):
    """Tests constructor when only settings is passed."""
    service = ConcreteTestLLMService(provider=None, settings=mock_settings)

    assert service.settings == mock_settings
    assert service.provider == service.created_provider_instance
    assert service.created_provider_instance is not None
    assert isinstance(service.created_provider_instance, MagicMock)  # No spec
    assert service.model == mock_settings.llm_model
    assert service.timeout == mock_settings.llm_timeout
    # Removed temperature and max_tokens assertions


@patch("pytest_analyzer.core.infrastructure.llm.base_llm_service.Settings")
def test_constructor_initialization_with_default_settings(
    MockSettingsClass: MagicMock, mock_llm_provider: MagicMock
):
    """Tests constructor when no settings are provided, uses Settings() and its defaults."""
    mock_default_settings_instance = MagicMock(spec=Settings)
    actual_default_settings = Settings()  # Get actual defaults

    # Configure the mock to have the same default attributes as a real Settings() instance
    mock_default_settings_instance.llm_model = actual_default_settings.llm_model
    mock_default_settings_instance.llm_timeout = actual_default_settings.llm_timeout
    mock_default_settings_instance.llm_provider = actual_default_settings.llm_provider
    # Add other Settings attributes if BaseLLMService starts using them

    MockSettingsClass.return_value = mock_default_settings_instance

    service = ConcreteTestLLMService(provider=mock_llm_provider, settings=None)

    assert service.settings == mock_default_settings_instance
    assert service.provider == mock_llm_provider
    assert service.model == actual_default_settings.llm_model
    assert service.timeout == actual_default_settings.llm_timeout
    # Removed temperature and max_tokens assertions


def test_prepare_messages_formatting(
    mock_settings: MagicMock,
    mock_llm_provider: MagicMock,
    # mock_settings_values: Dict[str, Any], # No longer needed
):
    """Tests _prepare_messages correctly formats the messages array."""
    service = ConcreteTestLLMService(provider=mock_llm_provider, settings=mock_settings)
    user_prompt = "User query here"
    context = {"some_key": "some_value"}

    messages = service._prepare_messages(user_prompt, context)

    # _get_system_prompt now returns a hardcoded default
    expected_system_prompt = "You are a helpful assistant."
    assert len(messages) == 2
    assert messages[0] == {"role": "system", "content": expected_system_prompt}
    assert messages[1] == {"role": "user", "content": user_prompt}


def test_get_system_prompt_returns_default_value(
    mock_settings: MagicMock,  # mock_settings is not strictly needed but fixtures provide it
    mock_llm_provider: MagicMock,
):
    """Tests _get_system_prompt returns the hardcoded default prompt."""
    service = ConcreteTestLLMService(provider=mock_llm_provider, settings=mock_settings)
    context = {"some_key": "some_value"}

    system_prompt = service._get_system_prompt(context)
    assert system_prompt == "You are a helpful assistant."


# test_get_system_prompt_default_fallback is removed as it's now redundant.


def test_instantiate_abstract_base_llm_service_raises_type_error():
    """Tests that BaseLLMService cannot be instantiated directly due to abstract 'generate'."""
    with pytest.raises(
        TypeError,
        match=r"Can't instantiate abstract class BaseLLMService (with abstract method generate|without an implementation for abstract method 'generate')",
    ):
        BaseLLMService()


def test_subclass_without_generate_raises_type_error(mock_settings: MagicMock):
    """Tests TypeError for subclass not implementing abstract 'generate'."""

    class SubclassWithoutGenerate(BaseLLMService):
        def _create_default_provider(
            self,
        ) -> Any:  # Return type Any
            return MagicMock()  # No spec

    with pytest.raises(
        TypeError,
        match=r"Can't instantiate abstract class SubclassWithoutGenerate (with abstract method generate|without an implementation for abstract method 'generate')",
    ):
        # Provider must be passed, or _create_default_provider must be valid.
        # Here, we pass settings and rely on its _create_default_provider.
        SubclassWithoutGenerate(settings=mock_settings, provider=None)


def test_subclass_calling_base_create_default_provider_raises_not_implemented_error(
    mock_settings: MagicMock,
):
    """
    Tests NotImplementedError if subclass implements 'generate' but calls base _create_default_provider.
    """

    class SubclassRelyingOnBaseCreateDefault(BaseLLMService):
        def generate(
            self, prompt: str, context: Optional[Dict[str, Any]] = None
        ) -> str:
            return "generated"

        # Does not override _create_default_provider, so base's version (which raises NI E) is called if provider=None.

    with pytest.raises(
        NotImplementedError, match="Subclasses must implement _create_default_provider"
    ):
        SubclassRelyingOnBaseCreateDefault(settings=mock_settings, provider=None)

    mock_provider = MagicMock()  # No spec
    try:
        instance = SubclassRelyingOnBaseCreateDefault(
            settings=mock_settings, provider=mock_provider
        )
        assert isinstance(instance, SubclassRelyingOnBaseCreateDefault)
        assert instance.provider == mock_provider
    except NotImplementedError:  # pragma: no cover
        pytest.fail("Instantiation should succeed when provider is supplied.")
