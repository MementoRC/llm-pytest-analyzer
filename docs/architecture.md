# Pytest Analyzer Architecture

## Overview

Pytest Analyzer is a tool designed to analyze test failures, suggest fixes, and apply them to help developers resolve test failures more efficiently. This document outlines the architecture of the refactored Pytest Analyzer, which implements a modular, maintainable design with clear separation of concerns.

The architecture follows these design principles:
- **Loose coupling**: Components interact through well-defined interfaces
- **Dependency Injection**: Dependencies are provided from the outside, making testing easier
- **State Machine Pattern**: Complex workflows are managed using state machines
- **Protocol-based interfaces**: Clear contracts between components using Python's Protocol type
- **Separation of concerns**: Each component has a single responsibility
- **Both synchronous and asynchronous APIs**: Supporting different usage patterns

## Component Architecture

### Core Components

The system is composed of these primary components:

1. **Extractor**: Extracts test failure information from pytest reports
2. **Analyzer**: Analyzes test failures to determine their root causes
3. **Suggester**: Suggests fixes for test failures
4. **Applier**: Applies suggested fixes to the codebase
5. **LLM Service**: Provides language model capabilities for generating fix suggestions
6. **PromptBuilder**: Constructs prompts for the LLM service
7. **ResponseParser**: Parses and validates responses from the LLM service
8. **Analyzer Service**: Coordinates the overall analysis workflow
9. **State Machine**: Manages the workflow state transitions
10. **DI Container**: Manages dependencies between components

### Component Diagram

```
┌───────────────┐     ┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│   Extractor   │────▶│   Analyzer    │────▶│   Suggester   │────▶│    Applier    │
└───────────────┘     └───────────────┘     └───────────────┘     └───────────────┘
        │                     │                     │                     │
        │                     │                     │                     │
        │                     │                     │                     │
        │                     ▼                     │                     │
        │              ┌───────────────┐           │                     │
        │              │ Analyzer State│           │                     │
        │              │    Machine    │◀──────────┘                     │
        │              └───────────────┘                                 │
        │                     ▲                                          │
        │                     │                                          │
        └─────────────────────┼──────────────────────────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    │  AnalyzerService  │
                    └───────────────────┘
                              ▲
                              │
                    ┌─────────┴─────────┐
                    │     CLI / API     │
                    └───────────────────┘


┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│ PromptBuilder │────▶│  LLM Service  │────▶│ResponseParser │
└───────────────┘     └───────────────┘     └───────────────┘
                            │
                            ▼
                    ┌───────────────┐
                    │  LLM Client   │
                    │ (Anthropic/   │
                    │   OpenAI)     │
                    └───────────────┘
```

### Data Flow

1. The CLI or API initializes the AnalyzerService
2. The AnalyzerService creates a State Machine to manage the analysis workflow
3. The State Machine transitions through states:
   - Extract test results (using Extractor)
   - Analyze failures (using Analyzer)
   - Generate suggestions (using Suggester)
   - Apply fixes (using Applier)
4. The Suggester may use the LLM Service to generate fix suggestions
5. The LLM Service uses the PromptBuilder to create prompts
6. The LLM Service uses the ResponseParser to process responses
7. The Applier applies fixes to the codebase
8. The AnalyzerService reports results back to the CLI or API

## Interface Definitions

### Core Protocols

#### ExtractorProtocol

```python
class ExtractorProtocol(Protocol):
    """Protocol for extracting test failures from test reports."""

    def extract_failures(self, report_path: str) -> List[PytestFailure]:
        """
        Extract failures from a pytest report.

        Args:
            report_path: Path to the pytest report file

        Returns:
            List of PytestFailure objects
        """
        ...
```

#### AnalyzerProtocol

```python
class AnalyzerProtocol(Protocol):
    """Protocol for analyzing test failures."""

    def analyze_failures(self, failures: List[PytestFailure]) -> List[FailureAnalysis]:
        """
        Analyze test failures to determine root causes.

        Args:
            failures: List of test failures to analyze

        Returns:
            List of failure analyses
        """
        ...
```

#### SuggesterProtocol

```python
class SuggesterProtocol(Protocol):
    """Protocol for suggesting fixes for test failures."""

    def suggest_fixes(self, analyses: List[FailureAnalysis]) -> List[FixSuggestion]:
        """
        Suggest fixes for analyzed test failures.

        Args:
            analyses: List of failure analyses

        Returns:
            List of fix suggestions
        """
        ...
```

#### ApplierProtocol

```python
class ApplierProtocol(Protocol):
    """Protocol for applying fixes to the codebase."""

    def apply_fixes(self, suggestions: List[FixSuggestion]) -> List[AppliedFix]:
        """
        Apply suggested fixes to the codebase.

        Args:
            suggestions: List of fix suggestions

        Returns:
            List of applied fixes
        """
        ...
```

#### LLMServiceProtocol

```python
class LLMServiceProtocol(Protocol):
    """Protocol for language model services."""

    def generate_completion(self, prompt: str) -> str:
        """
        Generate a completion from the language model.

        Args:
            prompt: The input prompt

        Returns:
            The generated completion
        """
        ...

    async def generate_completion_async(self, prompt: str) -> str:
        """
        Generate a completion from the language model asynchronously.

        Args:
            prompt: The input prompt

        Returns:
            The generated completion
        """
        ...
```

### State Machine

```python
from typing import Dict, Any, List, Optional, Set, Callable, TypeVar, Generic
from enum import Enum, auto
import logging

T = TypeVar('T', bound=Enum)

class StateMachine(Generic[T]):
    """Base class for state machines."""

    def __init__(self, initial_state: T):
        self.current_state = initial_state
        self.states: Set[T] = {initial_state}
        self.transitions: Dict[T, Dict[T, Callable[..., bool]]] = {}
        self.state_handlers: Dict[T, Callable[..., Any]] = {}
        self.context: Dict[str, Any] = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def add_state(self, state: T, handler: Callable[..., Any]) -> None:
        """Add a state to the state machine."""
        ...

    def add_transition(self, from_state: T, to_state: T, condition: Callable[..., bool]) -> None:
        """Add a transition between states."""
        ...

    def run(self, **kwargs) -> Any:
        """Run the state machine."""
        ...
```

## Dependency Injection

The Dependency Injection (DI) pattern is used throughout the codebase to manage dependencies and facilitate testing. A container is provided to register and resolve dependencies.

### Container

```python
class Container:
    """Dependency injection container."""

    def __init__(self):
        self._registrations = {}

    def register(self, interface, implementation, mode: RegistrationMode = RegistrationMode.TRANSIENT) -> None:
        """Register an implementation for an interface."""
        ...

    def register_instance(self, interface, instance) -> None:
        """Register an existing instance for an interface."""
        ...

    def register_factory(self, interface, factory) -> None:
        """Register a factory function for an interface."""
        ...

    def register_singleton(self, interface, implementation) -> None:
        """Register a singleton implementation for an interface."""
        ...

    def resolve(self, interface):
        """Resolve an implementation for an interface."""
        ...
```

### Service Registration

Services are registered with the container during application startup:

```python
def configure_services(container: Container = None) -> Container:
    """Configure all services in the container."""
    if container is None:
        container = Container()

    # Register core services
    container.register_singleton(Settings, Settings)
    container.register_singleton(PathResolver, PathResolver)

    # Register extractors
    container.register_factory(ExtractorFactory, lambda: ExtractorFactory())

    # Register analyzers
    container.register(FailureAnalyzer, FailureAnalyzer)

    # Register LLM services
    container.register_factory(LLMServiceProtocol, _create_llm_service)

    # Register state machine
    container.register_factory(AnalyzerStateMachine, _create_analyzer_state_machine)

    # Register main service
    container.register_factory(DIPytestAnalyzerService, _create_analyzer_service)

    return container
```

## Error Handling Strategy

The application uses a hierarchical error handling approach:

1. **Component-level errors**: Each component handles its own specific errors
2. **Service-level errors**: The AnalyzerService handles errors from components
3. **Application-level errors**: The CLI or API handles unrecoverable errors

Custom exceptions are defined in `errors.py` to represent different error conditions:

```python
class PytestAnalyzerError(Exception):
    """Base exception for all pytest-analyzer errors."""
    pass

class ExtractionError(PytestAnalyzerError):
    """Error during extraction of test failures."""
    pass

class AnalysisError(PytestAnalyzerError):
    """Error during analysis of test failures."""
    pass

class SuggestionError(PytestAnalyzerError):
    """Error during suggestion generation."""
    pass

class ApplierError(PytestAnalyzerError):
    """Error during fix application."""
    pass

class LLMServiceError(PytestAnalyzerError):
    """Error during language model service operation."""
    pass

class StateMachineError(PytestAnalyzerError):
    """Error during state machine operation."""
    pass
```

## State Machine Design

The state machine design is used to manage the complex workflow of the analyzer service. The states and transitions are defined as follows:

### Analyzer States

```python
class AnalyzerState(Enum):
    """States for the analyzer state machine."""

    INITIAL = auto()
    EXTRACTING = auto()
    ANALYZING = auto()
    SUGGESTING = auto()
    APPLYING = auto()
    COMPLETED = auto()
    ERROR = auto()
```

### State Handlers

Each state has a handler function that performs the work for that state:

```python
def handle_extracting(context: Dict[str, Any], **kwargs) -> None:
    """Handle the EXTRACTING state."""
    extractor = context.get("extractor")
    report_path = context.get("report_path")

    failures = extractor.extract_failures(report_path)
    context["failures"] = failures

def handle_analyzing(context: Dict[str, Any], **kwargs) -> None:
    """Handle the ANALYZING state."""
    analyzer = context.get("analyzer")
    failures = context.get("failures", [])

    analyses = analyzer.analyze_failures(failures)
    context["analyses"] = analyses

# ... more handlers for other states
```

### Transitions

Transitions between states are defined with conditions:

```python
# From INITIAL to EXTRACTING
state_machine.add_transition(
    AnalyzerState.INITIAL,
    AnalyzerState.EXTRACTING,
    lambda context, **kwargs: True  # Always transition to EXTRACTING
)

# From EXTRACTING to ANALYZING
state_machine.add_transition(
    AnalyzerState.EXTRACTING,
    AnalyzerState.ANALYZING,
    lambda context, **kwargs: len(context.get("failures", [])) > 0
)

# From EXTRACTING to COMPLETED (no failures)
state_machine.add_transition(
    AnalyzerState.EXTRACTING,
    AnalyzerState.COMPLETED,
    lambda context, **kwargs: len(context.get("failures", [])) == 0
)

# ... more transitions
```

## Synchronous and Asynchronous APIs

The application provides both synchronous and asynchronous APIs for flexibility. Key async features include:

1. **Async LLM Service**: Provides asynchronous methods for language model interactions
2. **Async Analyzer Service**: An asynchronous version of the analyzer service

Example of synchronous vs asynchronous API:

```python
# Synchronous API
result = analyzer_service.run_and_analyze(report_path="report.xml")

# Asynchronous API
result = await async_analyzer_service.run_and_analyze_async(report_path="report.xml")
```

## Backward Compatibility

To maintain compatibility with existing code, a facade is provided that exposes the same API as the original analyzer service while using the new architecture internally:

```python
class PytestAnalyzerService:
    """Facade for backward compatibility with the original API."""

    def __init__(self, settings: Optional[Settings] = None):
        self._container = initialize_container(settings)
        self._service = self._container.resolve(DIPytestAnalyzerService)

    def run_and_analyze(self, **kwargs):
        """Run pytest and analyze the results."""
        return self._service.run_and_analyze(**kwargs)

    # ... other methods from the original API
```

## Conclusion

This architecture provides a solid foundation for the Pytest Analyzer, allowing for:

1. **Better maintainability**: Clear separation of concerns and well-defined interfaces
2. **Improved testability**: Dependency injection facilitates testing with mocks
3. **Enhanced flexibility**: The state machine pattern allows for complex workflows
4. **Future extensibility**: New components can be added by implementing interfaces
5. **Performance options**: Both synchronous and asynchronous APIs are available

The architecture has been designed to balance immediate refactoring needs with long-term maintainability and extensibility goals.
