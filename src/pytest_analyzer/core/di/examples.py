"""
Examples demonstrating the use of the Dependency Injection container.

This module provides example implementations and usage patterns for the
DI container to help users understand how to leverage it in their applications.
"""

from typing import List, Optional, Protocol

from .container import Container
from .decorators import factory, inject, register, singleton


# Example interfaces (protocols)
class ILogger(Protocol):
    """Example logger interface."""

    def log(self, message: str) -> None:
        """Log a message."""
        ...


class IDatabase(Protocol):
    """Example database interface."""

    def query(self, sql: str) -> List[dict]:
        """Execute a query."""
        ...

    def close(self) -> None:
        """Close the database connection."""
        ...


class IRepository(Protocol):
    """Example repository interface."""

    def get_all(self) -> List[dict]:
        """Get all items."""
        ...

    def get_by_id(self, id_: int) -> Optional[dict]:
        """Get item by ID."""
        ...

    def save(self, item: dict) -> None:
        """Save an item."""
        ...


class ISession(Protocol):
    """Example session interface."""

    def get_id(self) -> str:
        """Get the session ID."""
        ...


class IService(Protocol):
    """Example service interface."""

    def execute(self) -> str:
        """Execute the service."""
        ...


# Example implementations
class ConsoleLogger:
    """Logger that writes to the console."""

    def log(self, message: str) -> None:
        """Log a message to the console."""
        print(f"[LOG] {message}")


class FileLogger:
    """Logger that writes to a file."""

    def __init__(self, file_path: str = "app.log"):
        """Initialize with a file path."""
        self.file_path = file_path

    def log(self, message: str) -> None:
        """Log a message to the file."""
        with open(self.file_path, "a") as f:
            f.write(f"[LOG] {message}\\n")


class InMemoryDatabase:
    """Example in-memory database."""

    def __init__(self):
        """Initialize with empty data."""
        self.data = {"users": [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]}

    def query(self, sql: str) -> List[dict]:
        """Simulate a query."""
        if "users" in sql.lower():
            return self.data["users"]
        return []

    def close(self) -> None:
        """Close the connection."""
        self.data = {}


class UserRepository:
    """Repository for user data."""

    def __init__(self, database: IDatabase, logger: ILogger):
        """Initialize with dependencies."""
        self.database = database
        self.logger = logger

    def get_all(self) -> List[dict]:
        """Get all users."""
        self.logger.log("Getting all users")
        return self.database.query("SELECT * FROM users")

    def get_by_id(self, id_: int) -> Optional[dict]:
        """Get user by ID."""
        self.logger.log(f"Getting user with ID {id_}")
        users = self.database.query(f"SELECT * FROM users WHERE id = {id_}")
        return users[0] if users else None

    def save(self, user: dict) -> None:
        """Save a user."""
        self.logger.log(f"Saving user: {user}")
        # In a real implementation, this would update the database


class UserSession:
    """User session implementation."""

    def __init__(self):
        """Initialize with a random ID."""
        import uuid

        self._id = str(uuid.uuid4())

    def get_id(self) -> str:
        """Get the session ID."""
        return self._id


class UserService:
    """Service for user operations."""

    def __init__(self, repository: IRepository, session: ISession, logger: ILogger):
        """Initialize with dependencies."""
        self.repository = repository
        self.session = session
        self.logger = logger

    def execute(self) -> str:
        """Execute a sample operation."""
        self.logger.log(f"Executing in session {self.session.get_id()}")
        users = self.repository.get_all()
        return f"Found {len(users)} users"


def basic_example():
    """Basic example of container usage."""
    # Create a container
    container = Container()

    # Register dependencies
    container.register(ILogger, ConsoleLogger)
    container.register(IDatabase, InMemoryDatabase)
    container.register(IRepository, UserRepository)

    # Resolve a repository (with its dependencies)
    repository = container.resolve(IRepository)

    # Use the repository
    users = repository.get_all()
    print(f"Found {len(users)} users")

    # The repository has its dependencies injected automatically
    repository.logger.log("Operation completed")


def registration_modes_example():
    """Example showing different registration modes."""
    container = Container()

    # Singleton registration (default)
    container.register_singleton(IDatabase, InMemoryDatabase)

    # Transient registration
    container.register_transient(ILogger, ConsoleLogger)

    # Factory registration
    container.register_factory(ISession, lambda: UserSession())

    # Register an instance directly
    my_logger = FileLogger("custom.log")
    container.register_instance(ILogger, my_logger)

    # Verify singleton behavior
    db1 = container.resolve(IDatabase)
    db2 = container.resolve(IDatabase)
    assert db1 is db2  # Same instance

    # Verify transient behavior (this would be true if we hadn't registered the instance)
    # logger1 = container.resolve(ILogger)
    # logger2 = container.resolve(ILogger)
    # assert logger1 is not logger2  # Different instances

    # Verify instance registration
    logger = container.resolve(ILogger)
    assert logger is my_logger  # Same instance


def decorator_example():
    """Example using decorator-based registration."""
    container = Container()

    # Register with decorators
    @singleton(container, ILogger)
    class CustomLogger:
        def log(self, message: str) -> None:
            print(f"[CUSTOM] {message}")

    @register(container, IDatabase)
    class CustomDatabase:
        def query(self, sql: str) -> List[dict]:
            return [{"id": 3, "name": "Charlie"}]

        def close(self) -> None:
            pass

    @factory(container, ISession)
    def create_session():
        session = UserSession()
        print(f"Created session: {session.get_id()}")
        return session

    # Register repository via decorators
    @register(container, IRepository)
    class CustomRepository:
        def __init__(self, database: IDatabase, logger: ILogger):
            self.database = database
            self.logger = logger

        def get_all(self) -> List[dict]:
            self.logger.log("CustomRepository.get_all()")
            return self.database.query("SELECT * FROM users")

        def get_by_id(self, id_: int) -> Optional[dict]:
            return None

        def save(self, item: dict) -> None:
            pass

    # Resolve and use
    repo = container.resolve(IRepository)
    users = repo.get_all()
    print(f"Found {len(users)} users via decorated repository")


def inject_example():
    """Example using the inject decorator."""
    container = Container()

    # Register dependencies
    container.register_singleton(ILogger, ConsoleLogger)
    container.register_singleton(IDatabase, InMemoryDatabase)
    container.register_singleton(IRepository, UserRepository)

    # Function with injected dependencies
    @inject(container)
    def process_users(repository: IRepository, logger: ILogger):
        """Process users with injected dependencies."""
        logger.log("Processing users")
        users = repository.get_all()
        return f"Processed {len(users)} users"

    # Call without passing dependencies
    result = process_users()
    print(result)  # "Processed 2 users"

    # Class with method injection
    class UserProcessor:
        @inject(container)
        def process(self, repository: IRepository, query: str = "all"):
            """Process users based on query."""
            if query == "all":
                return repository.get_all()
            return []

    # Create and use the processor
    processor = UserProcessor()
    users = processor.process()  # repository is injected
    print(f"Processor found {len(users)} users")


def scoped_example():
    """Example demonstrating scoped registrations."""
    container = Container()

    # Register dependencies
    container.register_singleton(ILogger, ConsoleLogger)
    container.register_singleton(IDatabase, InMemoryDatabase)
    container.register_singleton(IRepository, UserRepository)
    container.register_scoped(ISession, UserSession)
    container.register(IService, UserService)

    # Begin a scope
    container.begin_scope()

    # Resolve services in this scope
    service1 = container.resolve(IService)
    service2 = container.resolve(IService)

    # Same session within scope
    print(f"Session 1: {service1.session.get_id()}")
    print(f"Session 2: {service2.session.get_id()}")
    assert service1.session is service2.session

    # Execute service
    result = service1.execute()
    print(result)

    # End the scope
    container.end_scope()

    # Begin a new scope
    container.begin_scope()

    # Different session in new scope
    service3 = container.resolve(IService)
    print(f"Session 3: {service3.session.get_id()}")
    assert service1.session is not service3.session

    container.end_scope()


def hierarchical_example():
    """Example demonstrating container hierarchies."""
    # Create parent container with common services
    parent = Container()
    parent.register_singleton(ILogger, ConsoleLogger)
    parent.register_singleton(IDatabase, InMemoryDatabase)

    # Create child container with specialized services
    child = Container(parent=parent)
    child.register_singleton(IRepository, UserRepository)
    child.register_scoped(ISession, UserSession)
    child.register(IService, UserService)

    # Child resolves its own services and parent's services
    repository = child.resolve(IRepository)  # From child
    _ = child.resolve(IDatabase)  # From parent
    _ = child.resolve(ILogger)  # From parent

    # Use the services
    users = repository.get_all()
    print(f"Found {len(users)} users via hierarchical containers")


if __name__ == "__main__":
    # Run the examples
    print("\\n=== Basic Example ===")
    basic_example()

    print("\\n=== Registration Modes Example ===")
    registration_modes_example()

    print("\\n=== Decorator Example ===")
    decorator_example()

    print("\\n=== Inject Decorator Example ===")
    inject_example()

    print("\\n=== Scoped Registration Example ===")
    scoped_example()

    print("\\n=== Hierarchical Containers Example ===")
    hierarchical_example()
