"""
Tests for the Dependency Injection Container.
"""

from typing import Any, List, Protocol

import pytest

from src.pytest_analyzer.core.di.container import Container, RegistrationMode
from src.pytest_analyzer.core.errors import (
    DependencyResolutionError,
)


# Test classes and protocols for container testing
class IDatabase(Protocol):
    """Test protocol for a database interface."""

    def connect(self) -> bool:
        """Connect to the database."""
        ...

    def query(self, sql: str) -> List[Any]:
        """Execute a query."""
        ...


class Database:
    """Test implementation of a database interface."""

    def connect(self) -> bool:
        """Connect to the database."""
        return True

    def query(self, sql: str) -> List[Any]:
        """Execute a query."""
        return [{"id": 1, "name": "Test"}]


class ILogger(Protocol):
    """Test protocol for a logger interface."""

    def log(self, message: str) -> None:
        """Log a message."""
        ...


class Logger:
    """Test implementation of a logger interface."""

    def log(self, message: str) -> None:
        """Log a message."""
        pass


class IRepository(Protocol):
    """Test protocol for a repository interface."""

    def get_all(self) -> List[Any]:
        """Get all items."""
        ...


class Repository:
    """Test implementation of a repository interface that requires a database."""

    def __init__(self, database: IDatabase):
        """Initialize with a database dependency."""
        self.database = database

    def get_all(self) -> List[Any]:
        """Get all items from the database."""
        return self.database.query("SELECT * FROM items")


class RepositoryWithLogger:
    """Test implementation with multiple dependencies."""

    def __init__(self, database: IDatabase, logger: ILogger):
        """Initialize with database and logger dependencies."""
        self.database = database
        self.logger = logger

    def get_all(self) -> List[Any]:
        """Get all items with logging."""
        self.logger.log("Getting all items")
        return self.database.query("SELECT * FROM items")


class TestContainer:
    """Tests for the DI Container class."""

    def test_container_creation(self):
        """Test creating a container."""
        container = Container()
        assert container is not None

    def test_register_and_resolve_instance(self):
        """Test registering and resolving an instance."""
        container = Container()
        db = Database()
        container.register(IDatabase, db)

        resolved = container.resolve(IDatabase)
        assert resolved is db

    def test_register_and_resolve_type(self):
        """Test registering and resolving a type."""
        container = Container()
        container.register(IDatabase, Database)

        resolved = container.resolve(IDatabase)
        assert isinstance(resolved, Database)

    def test_register_and_resolve_singleton(self):
        """Test singleton registration mode."""
        container = Container()
        container.register(IDatabase, Database, RegistrationMode.SINGLETON)

        resolved1 = container.resolve(IDatabase)
        resolved2 = container.resolve(IDatabase)

        assert resolved1 is resolved2  # Same instance

    def test_register_and_resolve_transient(self):
        """Test transient registration mode."""
        container = Container()
        container.register(IDatabase, Database, RegistrationMode.TRANSIENT)

        resolved1 = container.resolve(IDatabase)
        resolved2 = container.resolve(IDatabase)

        assert resolved1 is not resolved2  # Different instances

    def test_register_and_resolve_factory(self):
        """Test factory registration mode."""
        container = Container()
        container.register_factory(IDatabase, lambda: Database())

        resolved = container.resolve(IDatabase)
        assert isinstance(resolved, Database)

    def test_override_registration(self):
        """Test overriding an existing registration."""
        container = Container()
        container.register(IDatabase, Database)

        # Override with a new implementation
        db = Database()
        container.register(IDatabase, db)

        resolved = container.resolve(IDatabase)
        assert resolved is db

    def test_resolve_unregistered_dependency(self):
        """Test resolving an unregistered dependency."""
        container = Container()

        with pytest.raises(DependencyResolutionError):
            container.resolve(IDatabase)

    def test_factory_error_handling(self):
        """Test handling errors from factory functions."""
        container = Container()

        def failing_factory():
            raise ValueError("Factory error")

        container.register_factory(IDatabase, failing_factory)

        with pytest.raises(DependencyResolutionError) as exc_info:
            container.resolve(IDatabase)

        assert "Factory failed to create instance" in str(exc_info.value)

    def test_constructor_injection(self):
        """Test automatic constructor injection."""
        container = Container()
        container.register(IDatabase, Database)
        container.register(IRepository, Repository)

        # Repository should be created with database dependency
        repo = container.resolve(IRepository)
        assert isinstance(repo, Repository)
        assert isinstance(repo.database, Database)

    def test_constructor_injection_multiple_dependencies(self):
        """Test constructor injection with multiple dependencies."""
        container = Container()
        container.register(IDatabase, Database)
        container.register(ILogger, Logger)
        container.register(IRepository, RepositoryWithLogger)

        # Repository should be created with both dependencies
        repo = container.resolve(IRepository)
        assert isinstance(repo, RepositoryWithLogger)
        assert isinstance(repo.database, Database)
        assert isinstance(repo.logger, Logger)

    def test_constructor_injection_missing_dependency(self):
        """Test error handling for missing dependencies during injection."""
        container = Container()
        # Register repository but not its database dependency
        container.register(IRepository, Repository)

        with pytest.raises(DependencyResolutionError) as exc_info:
            container.resolve(IRepository)

        assert "Cannot resolve dependency" in str(exc_info.value)
