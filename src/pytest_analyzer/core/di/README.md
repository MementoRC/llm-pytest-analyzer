# Dependency Injection Container

The `pytest_analyzer.core.di` module provides a powerful dependency injection container for managing component dependencies, facilitating better separation of concerns, improved testability, and easier maintenance.

## Table of Contents

- [Basic Usage](#basic-usage)
- [Registration Modes](#registration-modes)
- [Constructor Injection](#constructor-injection)
- [Decorator-Based Registration](#decorator-based-registration)
- [Scoped Registrations](#scoped-registrations)
- [Container Hierarchies](#container-hierarchies)
- [Utility Methods](#utility-methods)
- [Global Container](#global-container)
- [Tips and Best Practices](#tips-and-best-practices)

## Basic Usage

```python
from pytest_analyzer.core.di import Container

# Create a container
container = Container()

# Register dependencies
container.register(IDatabase, Database)
container.register(ILogger, Logger)
container.register(IRepository, Repository)  # Repository has IDatabase dependency

# Resolve dependencies
db = container.resolve(IDatabase)  # Returns Database instance
repo = container.resolve(IRepository)  # Returns Repository with Database injected
```

## Registration Modes

The container supports several registration modes:

### Singleton Mode (Default)

A single instance is created and reused for all resolutions:

```python
# Default mode is singleton
container.register(IDatabase, Database)

# Explicit singleton registration
container.register_singleton(IDatabase, Database)

# Register existing instance as singleton
db = Database(connection_string="...")
container.register_instance(IDatabase, db)
```

### Transient Mode

A new instance is created for each resolution:

```python
from pytest_analyzer.core.di import RegistrationMode

# Register as transient with mode parameter
container.register(ILogger, Logger, RegistrationMode.TRANSIENT)

# Or use the convenience method
container.register_transient(ILogger, Logger)

# Each resolution creates a new instance
logger1 = container.resolve(ILogger)
logger2 = container.resolve(ILogger)
assert logger1 is not logger2  # True
```

### Factory Mode

A factory function is used to create instances:

```python
# Register a factory function
def create_database():
    return Database(connection_string=get_connection_string())

container.register_factory(IDatabase, create_database)
```

### Scoped Mode

A single instance is created per scope:

```python
# Register a scoped dependency
container.register_scoped(ISession, Session)

# Create a scope
with container.create_scope():
    session1 = container.resolve(ISession)
    session2 = container.resolve(ISession)
    assert session1 is session2  # Same instance within scope

# Or using explicit scope management
container.begin_scope()
session = container.resolve(ISession)
container.end_scope()
```

## Constructor Injection

The container automatically injects dependencies based on constructor parameters:

```python
class Repository:
    def __init__(self, database: IDatabase, logger: ILogger):
        self.database = database
        self.logger = logger

# Register dependencies
container.register(IDatabase, Database)
container.register(ILogger, Logger)
container.register(IRepository, Repository)

# Resolve with automatic constructor injection
repo = container.resolve(IRepository)
# Repository is created with database and logger injected automatically
```

## Decorator-Based Registration

The module provides decorators for cleaner registration syntax:

```python
from pytest_analyzer.core.di import register, singleton, transient, factory, inject

# Create a container
container = Container()

# Register with decorator
@register(container, IService)
class ServiceImpl:
    def execute(self):
        return "Service executed"

# Convenience decorators for different modes
@singleton(container, IDatabase)
class DatabaseImpl(Database):
    pass

@transient(container, ILogger)
class LoggerImpl(Logger):
    pass

@factory(container, ISession)
def create_session():
    return Session()
```

## Parameter Injection

The `inject` decorator allows automatic injection of dependencies into function parameters:

```python
# Using the global container
@inject
def process_data(repository: IRepository, logger: ILogger):
    logger.log("Processing data...")
    return repository.get_all()

# Using a specific container
@inject(container)
def analyze_data(analyzer: IAnalyzer, data: str):
    return analyzer.analyze(data)

# Call without passing dependencies
result = process_data()  # Dependencies injected automatically

# Can also provide explicit dependencies
my_logger = Logger()
result = process_data(logger=my_logger)  # Only repository is injected
```

It also works with methods:

```python
class DataProcessor:
    @inject(container)
    def process(self, logger: ILogger, data: str):
        logger.log(f"Processing: {data}")
        return f"Processed: {data}"

processor = DataProcessor()
result = processor.process(data="test data")  # logger is injected
```

## Scoped Registrations

Scoped registrations create instances that are shared within a scope but not between scopes:

```python
# Register a scoped dependency
container.register_scoped(ISession, Session)

# Begin a scope
container.begin_scope()

# Resolve within the scope
session1 = container.resolve(ISession)
session2 = container.resolve(ISession)
assert session1 is session2  # Same instance within scope

# End the scope
container.end_scope()

# Create a new scope
container.begin_scope()
session3 = container.resolve(ISession)
assert session1 is not session3  # Different instance in different scope
container.end_scope()
```

You can also use the context manager pattern:

```python
# Create and use a scope as a context manager
with container.create_scope() as scope:
    session = container.resolve(ISession)
    # Session is valid within this block
# Scope is automatically disposed when the block exits
```

## Container Hierarchies

You can create parent-child container hierarchies:

```python
# Create parent container with common services
parent = Container()
parent.register(ILogger, Logger)
parent.register(IDatabase, Database)

# Create child container with specialized services
child = Container(parent=parent)
child.register(IService, Service)

# Child resolves from parent if not found locally
service = child.resolve(IService)  # From child
logger = child.resolve(ILogger)    # From parent

# Parent cannot resolve child's registrations
with pytest.raises(DependencyResolutionError):
    parent.resolve(IService)
```

## Utility Methods

The container provides several utility methods:

```python
# Register multiple dependencies at once
container.register_many({
    ILogger: Logger,
    IDatabase: Database,
    IRepository: Repository
}, mode=RegistrationMode.SINGLETON)

# Register an instance directly
logger = Logger()
container.register_instance(ILogger, logger)
```

## Global Container

The module provides a global container that can be accessed from anywhere:

```python
from pytest_analyzer.core.di import get_container, set_container

# Get the global container (creates one if it doesn't exist)
container = get_container()

# Register dependencies with the global container
container.register(ILogger, Logger)

# Set a pre-configured container as the global container
my_container = Container()
my_container.register(ILogger, CustomLogger)
set_container(my_container)
```

## Tips and Best Practices

1. **Use interfaces**: Register against interface types (Protocols in Python) rather than concrete implementations.

2. **Prefer constructor injection**: Inject dependencies through constructors rather than setters or properties.

3. **Avoid service locator pattern**: Don't use the container as a service locator by passing it around.

4. **Create container at composition root**: Set up your container at the application's entry point.

5. **Use scoped registrations for request-scoped data**: Session data, request context, etc. are good candidates for scoped registration.

6. **Register in modules**: Use a modular approach to register related dependencies together.

7. **Test with mock containers**: Use container hierarchies to override services with mocks in tests.
