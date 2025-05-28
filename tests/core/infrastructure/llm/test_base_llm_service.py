import logging
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch

import pytest

# Assuming these paths are valid in the new structure as per BaseLLMService spec
from pytest_analyzer.core.cross_cutting.configuration.settings import Settings
from pytest_analyzer.core.infrastructure.llm.base_llm_service import BaseLLMService
from pytest_analyzer.core.interfaces.protocols import LLMProvider


# --- Concrete Test Implementation of BaseLLMService ---
class ConcreteTestLLMService(BaseLLMService):
    """A concrete implementation of BaseLLMService for testing purposes."""

    def __init__(
        self,
        provider: Optional[LLMProvider] = None,
        settings: Optional[Settings] = None,
    ):
        self.created_provider_instance: Optional[LLMProvider] = None
        self.logger = logging.getLogger(
            self.__class__.__name__
        )  # Initialize logger before super for its potential use
        super().__init__(provider=provider, settings=settings)

    def _create_default_provider(self) -> LLMProvider:
        """Override to provide a mock provider for tests if one isn't passed to __init__."""
        self.logger.info(f"{self.__class__.__name__}._create_default_provider called")
        self.created_provider_instance = MagicMock(spec=LLMProvider)
        return self.created_provider_instance

    def generate(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Mock implementation of the abstract generate method."""
        self.logger.info(
            f"{self.__class__.__name__}.generate called with prompt: {prompt}"
        )
        return f"Generated response for: {prompt}"


# --- Fixtures ---
@pytest.fixture
def mock_settings_values() -> Dict[str, str]:
    """Provides a dictionary of settings values for mocking."""
    return {
        "llm.model": "test-model-from-settings",
        "llm.temperature": "0.5",
        "llm.max_tokens": "1500",
        "llm.timeout_seconds": "45",
        "llm.system_prompt": "Test system prompt from settings.",
        "llm.provider": "test-provider-from-settings",  # Used by base _create_default_provider if not overridden
    }


@pytest.fixture
def mock_llm_provider() -> MagicMock:
    """Provides a MagicMock instance for LLMProvider."""
    return MagicMock(spec=LLMProvider)


@pytest.fixture
def mock_settings(mock_settings_values: Dict[str, str]) -> MagicMock:
    """Provides a MagicMock of the Settings class, configured with mock_settings_values."""
    settings = MagicMock(spec=Settings)
    # Configure .get() to return values from mock_settings_values or a provided default
    settings.get.side_effect = lambda key, default=None: mock_settings_values.get(
        key, default
    )
    return settings


# --- Test Cases ---


def test_constructor_initialization_with_provider_and_settings(
    mock_settings: MagicMock,
    mock_llm_provider: MagicMock,
    mock_settings_values: Dict[str, str],
):
    """Tests constructor when both provider and settings are explicitly passed."""
    service = ConcreteTestLLMService(provider=mock_llm_provider, settings=mock_settings)

    assert service.settings == mock_settings
    assert service.provider == mock_llm_provider
    assert (
        service.created_provider_instance is None
    )  # _create_default_provider should not be called
    assert isinstance(service.logger, logging.Logger)
    assert service.logger.name == "ConcreteTestLLMService"
    assert service.model == mock_settings_values["llm.model"]
    assert service.temperature == float(mock_settings_values["llm.temperature"])
    assert service.max_tokens == int(mock_settings_values["llm.max_tokens"])
    assert service.timeout == int(mock_settings_values["llm.timeout_seconds"])


def test_constructor_initialization_with_settings_only(
    mock_settings: MagicMock, mock_settings_values: Dict[str, str]
):
    """Tests constructor when only settings is passed (provider is None, so _create_default_provider is called)."""
    service = ConcreteTestLLMService(provider=None, settings=mock_settings)

    assert service.settings == mock_settings
    assert (
        service.provider == service.created_provider_instance
    )  # Provider should be from _create_default_provider
    assert service.created_provider_instance is not None
    assert isinstance(service.created_provider_instance, MagicMock)
    assert service.model == mock_settings_values["llm.model"]
    # ... other assertions for model, temp, tokens, timeout as above ...


@patch("pytest_analyzer.core.infrastructure.llm.base_llm_service.Settings")
def test_constructor_initialization_with_default_settings(
    MockSettingsClass: MagicMock, mock_llm_provider: MagicMock
):
    """Tests constructor when no settings are provided, uses Settings() and its defaults."""
    mock_default_settings_instance = MagicMock(spec=Settings)
    default_values_from_spec = {
        "llm.model": "gpt-3.5-turbo",
        "llm.temperature": "0.7",
        "llm.max_tokens": "2000",
        "llm.timeout_seconds": "30",
        "llm.system_prompt": "You are a helpful assistant.",  # Default for _get_system_prompt
        "llm.provider": "openai",  # Default for _create_default_provider in base
    }
    mock_default_settings_instance.get.side_effect = (
        lambda key, default=None: default_values_from_spec.get(key, default)
    )
    MockSettingsClass.return_value = mock_default_settings_instance

    service = ConcreteTestLLMService(provider=mock_llm_provider, settings=None)

    assert service.settings == mock_default_settings_instance
    assert service.provider == mock_llm_provider  # Explicitly passed provider
    assert service.model == default_values_from_spec["llm.model"]
    assert service.temperature == float(default_values_from_spec["llm.temperature"])
    assert service.max_tokens == int(default_values_from_spec["llm.max_tokens"])
    assert service.timeout == int(default_values_from_spec["llm.timeout_seconds"])


def test_prepare_messages_formatting(
    mock_settings: MagicMock,
    mock_llm_provider: MagicMock,
    mock_settings_values: Dict[str, str],
):
    """Tests _prepare_messages correctly formats the messages array."""
    service = ConcreteTestLLMService(provider=mock_llm_provider, settings=mock_settings)
    user_prompt = "User query here"
    context = {"some_key": "some_value"}  # Context is passed to _get_system_prompt

    messages = service._prepare_messages(user_prompt, context)

    expected_system_prompt = mock_settings_values["llm.system_prompt"]
    assert len(messages) == 2
    assert messages[0] == {"role": "system", "content": expected_system_prompt}
    assert messages[1] == {"role": "user", "content": user_prompt}


def test_get_system_prompt_from_settings(
    mock_settings: MagicMock,
    mock_llm_provider: MagicMock,
    mock_settings_values: Dict[str, str],
):
    """Tests _get_system_prompt retrieves prompt from settings."""
    service = ConcreteTestLLMService(provider=mock_llm_provider, settings=mock_settings)
    context = {
        "some_key": "some_value"
    }  # Context is currently unused by _get_system_prompt in spec

    system_prompt = service._get_system_prompt(context)
    assert system_prompt == mock_settings_values["llm.system_prompt"]


@patch("pytest_analyzer.core.infrastructure.llm.base_llm_service.Settings")
def test_get_system_prompt_default_fallback(
    MockSettingsClass: MagicMock, mock_llm_provider: MagicMock
):
    """Tests _get_system_prompt falls back to default when not in settings."""
    mock_empty_settings_instance = MagicMock(spec=Settings)
    # Make .get return the default for "llm.system_prompt" when key is not found
    # The default is the second arg to .get("llm.system_prompt", "You are a helpful assistant.")
    mock_empty_settings_instance.get.side_effect = (
        lambda key, default=None: default
        if key == "llm.system_prompt"
        else "mock-val-for-other-keys"
    )
    MockSettingsClass.return_value = mock_empty_settings_instance

    service = ConcreteTestLLMService(
        provider=mock_llm_provider, settings=None
    )  # settings=None uses patched Settings()

    system_prompt = service._get_system_prompt()
    assert (
        system_prompt == "You are a helpful assistant."
    )  # Default from BaseLLMService._get_system_prompt spec


def test_instantiate_abstract_base_llm_service_raises_type_error():
    """Tests that BaseLLMService cannot be instantiated directly due to abstract 'generate'."""
    with pytest.raises(
        TypeError,
        match="Can't instantiate abstract class BaseLLMService with abstract method generate",
    ):
        BaseLLMService()


def test_subclass_without_generate_raises_type_error(mock_settings: MagicMock):
    """Tests TypeError for subclass not implementing abstract 'generate'."""

    class SubclassWithoutGenerate(BaseLLMService):
        # Missing 'generate'
        def _create_default_provider(
            self,
        ) -> LLMProvider:  # Must implement this to avoid error from base
            return MagicMock(spec=LLMProvider)

    with pytest.raises(
        TypeError,
        match="Can't instantiate abstract class SubclassWithoutGenerate with abstract method generate",
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

    # Verify it instantiates if a provider IS supplied
    mock_provider = MagicMock(spec=LLMProvider)
    try:
        instance = SubclassRelyingOnBaseCreateDefault(
            settings=mock_settings, provider=mock_provider
        )
        assert isinstance(instance, SubclassRelyingOnBaseCreateDefault)
        assert instance.provider == mock_provider
    except NotImplementedError:  # pragma: no cover
        pytest.fail("Instantiation should succeed when provider is supplied.")
