from typing import Any
from unittest.mock import patch

import pytest

from pytest_analyzer.core.infrastructure.base_factory import BaseFactory
from pytest_analyzer.utils.config_types import Settings


class MockImplementation:
    """Mock implementation for testing."""

    pass


class ConcreteFactory(BaseFactory):
    """Concrete factory implementation for testing."""

    def create(self, *args, **kwargs) -> Any:
        """Test implementation of abstract create method."""
        if args:
            implementation_key = args[0]
            implementation_class = self.get_implementation(implementation_key)
            return implementation_class()
        return MockImplementation()


class TestBaseFactory:
    """Test suite for BaseFactory abstract class."""

    def test_init_with_default_settings(self):
        """Test that factory initializes with default settings when none provided."""
        factory = ConcreteFactory()

        assert factory.settings is not None
        assert isinstance(factory.settings, Settings)
        assert factory.logger.name == "ConcreteFactory"
        assert factory._registry == {}

    def test_init_with_custom_settings(self):
        """Test that factory uses provided settings."""
        custom_settings = Settings()
        factory = ConcreteFactory(settings=custom_settings)

        assert factory.settings is custom_settings
        assert factory.logger.name == "ConcreteFactory"
        assert factory._registry == {}

    def test_register_implementation(self):
        """Test registering an implementation with a key."""
        factory = ConcreteFactory()

        factory.register("mock", MockImplementation)

        assert "mock" in factory._registry
        assert factory._registry["mock"] is MockImplementation

    def test_register_logs_debug_message(self):
        """Test that register logs debug message."""
        factory = ConcreteFactory()

        with patch.object(factory.logger, "debug") as mock_debug:
            factory.register("mock", MockImplementation)

            mock_debug.assert_called_once_with(
                "Registering MockImplementation with key 'mock'"
            )

    def test_get_implementation_returns_correct_class(self):
        """Test that get_implementation returns the correct implementation class."""
        factory = ConcreteFactory()
        factory.register("mock", MockImplementation)

        implementation = factory.get_implementation("mock")

        assert implementation is MockImplementation

    def test_get_implementation_raises_keyerror_for_unknown_key(self):
        """Test that get_implementation raises KeyError for unregistered key."""
        factory = ConcreteFactory()

        with pytest.raises(
            KeyError, match="No implementation registered for key 'unknown'"
        ):
            factory.get_implementation("unknown")

    def test_get_implementation_logs_error_for_unknown_key(self):
        """Test that get_implementation logs error for unregistered key."""
        factory = ConcreteFactory()

        with patch.object(factory.logger, "error") as mock_error:
            with pytest.raises(KeyError):
                factory.get_implementation("unknown")

            mock_error.assert_called_once_with(
                "No implementation registered for key 'unknown'"
            )

    def test_detect_file_type_with_extension(self):
        """Test file type detection with various extensions."""
        factory = ConcreteFactory()

        assert factory._detect_file_type("test.json") == "json"
        assert factory._detect_file_type("report.xml") == "xml"
        assert factory._detect_file_type("data.CSV") == "csv"
        assert factory._detect_file_type("/path/to/file.TXT") == "txt"

    def test_detect_file_type_without_extension(self):
        """Test file type detection for files without extension."""
        factory = ConcreteFactory()

        assert factory._detect_file_type("filename") == ""
        assert factory._detect_file_type("/path/to/filename") == ""

    def test_detect_file_type_with_multiple_dots(self):
        """Test file type detection with multiple dots in filename."""
        factory = ConcreteFactory()

        assert factory._detect_file_type("test.backup.json") == "json"
        assert factory._detect_file_type("file.tar.gz") == "gz"

    def test_abstract_instantiation_raises_typeerror(self):
        """Test that attempting to instantiate BaseFactory directly raises TypeError."""
        with pytest.raises(
            TypeError, match="Can't instantiate abstract class BaseFactory"
        ):
            BaseFactory()

    def test_concrete_subclass_without_create_raises_typeerror(self):
        """Test that subclassing without implementing create raises TypeError."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):

            class IncompleteFactory(BaseFactory):
                pass

            IncompleteFactory()

    def test_create_method_with_registry(self):
        """Test the concrete create method using the registry."""
        factory = ConcreteFactory()
        factory.register("mock", MockImplementation)

        instance = factory.create("mock")

        assert isinstance(instance, MockImplementation)

    def test_create_method_without_args(self):
        """Test the concrete create method without arguments."""
        factory = ConcreteFactory()

        instance = factory.create()

        assert isinstance(instance, MockImplementation)

    def test_multiple_registrations(self):
        """Test multiple implementations can be registered."""
        factory = ConcreteFactory()

        class AnotherImplementation:
            pass

        factory.register("mock1", MockImplementation)
        factory.register("mock2", AnotherImplementation)

        assert factory.get_implementation("mock1") is MockImplementation
        assert factory.get_implementation("mock2") is AnotherImplementation

    def test_registry_isolation_between_instances(self):
        """Test that different factory instances have isolated registries."""
        factory1 = ConcreteFactory()
        factory2 = ConcreteFactory()

        factory1.register("mock", MockImplementation)

        assert "mock" in factory1._registry
        assert "mock" not in factory2._registry
