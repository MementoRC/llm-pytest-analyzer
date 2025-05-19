"""
Tests for the ServiceCollection class.

This module tests the fluent API for registering services with the DI container.
"""

from pathlib import Path
from typing import Any, Dict, List, Protocol
from unittest.mock import Mock

import pytest

from src.pytest_analyzer.core.di.container import Container
from src.pytest_analyzer.core.di.service_collection import ServiceCollection
from src.pytest_analyzer.core.llm.llm_service_protocol import LLMServiceProtocol
from src.pytest_analyzer.utils.path_resolver import PathResolver
from src.pytest_analyzer.utils.settings import Settings


# Test protocols and classes (reusing some from test_container.py)
class IService(Protocol):
    """Test protocol for a service interface."""

    def execute(self) -> str:
        """Execute the service."""
        ...


class Service:
    """Test implementation of a service interface."""

    def execute(self) -> str:
        """Execute the service."""
        return "Service executed"


class ServiceWithDependency:
    """Test implementation with a dependency."""

    def __init__(self, settings: Settings):
        """Initialize with settings dependency."""
        self.settings = settings

    def execute(self) -> str:
        """Execute the service using settings."""
        return f"Service executed with project root: {self.settings.project_root}"


class TestServiceCollection:
    """Tests for the ServiceCollection class."""

    def test_service_collection_creation(self):
        """Test creating a service collection."""
        services = ServiceCollection()
        assert services is not None
        assert isinstance(services.container, Container)

    def test_add_singleton(self):
        """Test adding a singleton service."""
        services = ServiceCollection()
        result = services.add_singleton(IService, Service)

        # Test fluent API returns self
        assert result is services

        # Test service was registered correctly
        service1 = services.container.resolve(IService)
        service2 = services.container.resolve(IService)
        assert isinstance(service1, Service)
        assert service1 is service2  # Same instance (singleton)

    def test_add_transient(self):
        """Test adding a transient service."""
        services = ServiceCollection()
        result = services.add_transient(IService, Service)

        # Test fluent API returns self
        assert result is services

        # Test service was registered correctly
        service1 = services.container.resolve(IService)
        service2 = services.container.resolve(IService)
        assert isinstance(service1, Service)
        assert service1 is not service2  # Different instances (transient)

    def test_add_factory(self):
        """Test adding a factory for a service."""
        services = ServiceCollection()
        factory_called = False

        def factory():
            nonlocal factory_called
            factory_called = True
            return Service()

        result = services.add_factory(IService, factory)

        # Test fluent API returns self
        assert result is services

        # Test factory was registered correctly
        service = services.container.resolve(IService)
        assert isinstance(service, Service)
        assert factory_called

    def test_configure_core_services(self):
        """Test configure_core_services method."""
        services = ServiceCollection()
        result = services.configure_core_services()

        # Test fluent API returns self
        assert result is services

        # Test core services were registered
        # For example, test that Settings is registered
        settings = services.container.resolve(Settings)
        assert isinstance(settings, Settings)

        # Test that LLMServiceProtocol is registered
        llm_service = services.container.resolve(LLMServiceProtocol)
        assert llm_service is not None

    def test_configure_extractors(self):
        """Test configure_extractors method."""
        services = ServiceCollection()
        # Configure core services first since extractors relies on it
        services.configure_core_services()
        result = services.configure_extractors()

        # Test fluent API returns self
        assert result is services

        # Test that extractors are properly configured
        # This is more of an integration test that depends on configure_core_services

    def test_configure_llm_services_with_client(self):
        """Test configure_llm_services with a mock client."""
        services = ServiceCollection()
        mock_client = object()  # Simple mock object
        result = services.configure_llm_services(mock_client)

        # Test fluent API returns self
        assert result is services

        # Test LLM service was registered
        try:
            llm_service = services.container.resolve(LLMServiceProtocol)
            assert llm_service is not None
        except Exception:
            pytest.fail("LLM service should be resolvable after configuration")

    def test_build_container(self):
        """Test building the container."""
        services = ServiceCollection()
        services.add_singleton(IService, Service)

        container = services.build_container()
        assert isinstance(container, Container)

        # Test that services registered with ServiceCollection are resolvable from the container
        service = container.resolve(IService)
        assert isinstance(service, Service)

    def test_chained_configuration(self):
        """Test chaining multiple configuration methods."""
        services = ServiceCollection()

        # Use method chaining to configure services
        result = (
            services.add_singleton(IService, Service)
            .configure_core_services()
            .configure_extractors()
            .configure_llm_services()
        )

        # Test fluent API returns self
        assert result is services

        # Test that services were registered
        service = services.container.resolve(IService)
        assert isinstance(service, Service)

        settings = services.container.resolve(Settings)
        assert isinstance(settings, Settings)

        llm_service = services.container.resolve(LLMServiceProtocol)
        assert llm_service is not None

    def test_constructor_injection_with_service_collection(self):
        """Test constructor injection with ServiceCollection."""
        services = ServiceCollection()

        # Register Settings and a service that depends on Settings
        services.add_singleton(Settings, Settings())
        services.add_singleton(IService, ServiceWithDependency)

        # Resolve the service
        service = services.container.resolve(IService)
        assert isinstance(service, ServiceWithDependency)
        assert isinstance(service.settings, Settings)

        # Test that the service can be executed
        result = service.execute()
        assert "Service executed with project root" in result

    def test_nested_dependency_injection(self):
        """Test nested dependency injection with ServiceCollection."""

        # Define a class with nested dependencies
        class NestedService:
            def __init__(self, path_resolver: PathResolver):
                self.path_resolver = path_resolver

            def execute(self) -> str:
                return f"Nested service with path_resolver for: {self.path_resolver.project_root}"

        class TopLevelService:
            def __init__(self, settings: Settings, nested: NestedService):
                self.settings = settings
                self.nested = nested

            def execute(self) -> str:
                return f"Top service using: {self.nested.execute()}"

        # Configure the service collection
        services = ServiceCollection()

        # Add settings with a specific project root
        test_settings = Settings()
        test_settings.project_root = Path("/test/project")
        services.add_singleton(Settings, test_settings)

        # Register the path resolver and services
        services.add_factory(
            PathResolver,
            lambda: PathResolver(services.container.resolve(Settings).project_root),
        )
        services.add_singleton(NestedService, NestedService)
        services.add_singleton(IService, TopLevelService)

        # Resolve the top-level service
        service = services.container.resolve(IService)

        # Verify the dependencies were properly injected
        assert isinstance(service, TopLevelService)
        assert service.settings is test_settings
        assert isinstance(service.nested, NestedService)
        assert isinstance(service.nested.path_resolver, PathResolver)
        assert str(service.nested.path_resolver.project_root) == "/test/project"

        # Test that the service can be executed
        result = service.execute()
        assert "Top service using: Nested service with path_resolver for:" in result
        assert "/test/project" in result

    def test_mocked_dependencies(self):
        """Test using mocked dependencies in the ServiceCollection."""

        # Define an interface that will be mocked
        class IDatabaseClient(Protocol):
            def query(self, sql: str) -> List[dict]: ...

        # Define a service that uses the database
        class DataService:
            def __init__(self, db_client: IDatabaseClient):
                self.db_client = db_client

            def get_users(self) -> List[dict]:
                return self.db_client.query("SELECT * FROM users")

        # Set up the service collection with a mock
        services = ServiceCollection()

        # Create a mock database client
        mock_db = Mock(spec=IDatabaseClient)
        mock_db.query.return_value = [{"id": 1, "name": "Test User"}]

        # Register the mock and the service
        services.add_singleton(IDatabaseClient, mock_db)
        services.add_singleton(DataService, DataService)

        # Resolve the service
        service = services.container.resolve(DataService)

        # Test the service with the mock
        users = service.get_users()
        assert len(users) == 1
        assert users[0]["name"] == "Test User"

        # Verify the mock was called correctly
        mock_db.query.assert_called_once_with("SELECT * FROM users")

    def test_integration_with_basic_services(self):
        """Test integration with basic services."""
        # Create a service collection
        services = ServiceCollection()

        # Add core services manually instead of using configure_core_services
        test_settings = Settings()
        # Ensure the project root is a Path object
        test_settings.project_root = Path("/test/integration")
        services.add_singleton(Settings, test_settings)

        # Add a PathResolver that depends on Settings
        services.add_factory(
            PathResolver,
            lambda: PathResolver(services.container.resolve(Settings).project_root),
        )

        # Create a test service that depends on both
        class TestService:
            def __init__(self, settings: Settings, path_resolver: PathResolver):
                self.settings = settings
                self.path_resolver = path_resolver

            def get_paths(self) -> Dict[str, Any]:
                return {
                    "settings_root": self.settings.project_root,
                    "resolver_root": self.path_resolver.project_root,
                }

        # Register and resolve the test service
        services.add_singleton(TestService, TestService)
        service = services.container.resolve(TestService)

        # Verify correct dependency injection
        assert service.settings is test_settings
        assert isinstance(service.path_resolver, PathResolver)
        assert service.path_resolver.project_root == test_settings.project_root

        # Test the service functionality
        paths = service.get_paths()
        assert paths["settings_root"] == test_settings.project_root
        assert paths["resolver_root"] == service.path_resolver.project_root
