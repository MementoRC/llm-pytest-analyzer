# Facade Architecture for Backward Compatibility

## Overview

The facade pattern in this codebase serves as a bridge between the legacy API (`PytestAnalyzerService`) and the new modular architecture that uses dependency injection and protocol-based interfaces. This document explains the design decisions, implementation details, and usage patterns for the facade.

## Design Goals

1. **Maintain Backward Compatibility**: Ensure that code using the original API continues to work without modifications.
2. **Leverage New Architecture**: Internally use the new components and state machine to benefit from improved design.
3. **Provide Seamless Migration Path**: Allow gradual migration from the old API to the new architecture.
4. **Minimize Duplication**: Avoid duplicating logic between old and new architecture.
5. **Facilitate Testing**: Make the system easier to test with proper separation of concerns.

## Implementation Components

### PytestAnalyzerFacade

The `PytestAnalyzerFacade` class is the core of our compatibility layer. It:

- Implements the same interface as the original `PytestAnalyzerService`
- Uses the dependency injection container internally
- Delegates work to the `AnalyzerStateMachine` and various protocol implementations
- Handles error cases and maintains the expected return formats
- Manages temporary resources like files

### Legacy API Support (PytestAnalyzerService)

For full backward compatibility, we provide the `PytestAnalyzerService` class which:

- Inherits from `PytestAnalyzerFacade`
- Provides the same constructor signature as the original implementation
- Issues a deprecation warning to encourage migration to the new API

## Architecture Diagram

```
Legacy Code
    │
    ▼
┌─────────────────────┐
│PytestAnalyzerService│
│(Backward Compatible)│
└─────────────────────┘
          │
          │ inherits from
          ▼
┌─────────────────────┐      ┌───────────────────┐
│ PytestAnalyzerFacade ├─────►DI Container       │
└─────────────────────┘      └───────────────────┘
          │                            │
          │ delegates to               │ resolves
          ▼                            ▼
┌─────────────────────┐      ┌───────────────────┐
│AnalyzerStateMachine │      │Protocol Interfaces│
└─────────────────────┘      └───────────────────┘
          │                            │
          │ coordinates                │ implements
          ▼                            ▼
┌─────────────────────┐      ┌───────────────────┐
│Different States     │      │Concrete Components│
└─────────────────────┘      └───────────────────┘
```

## Key Benefits

1. **Isolation of Changes**: Changes to the internal architecture don't affect external consumers.
2. **Testing Simplicity**: Each layer can be tested independently.
3. **Clean Migration**: New code can use the newer, more modular interfaces while legacy code continues to work.
4. **Future Extension**: New features can be added to the new architecture without affecting backward compatibility.

## Usage Examples

### Legacy API Usage (Still Supported)

```python
from pytest_analyzer.core.analyzer_service import PytestAnalyzerService

# Create service with default settings
service = PytestAnalyzerService()

# Analyze test failures
failures = service.run_pytest_only("tests/")
suggestions = service.run_and_analyze("tests/")
```

### New Facade API Usage (Recommended)

```python
from pytest_analyzer.core.analyzer_facade import PytestAnalyzerFacade

# Create facade with default settings
facade = PytestAnalyzerFacade()

# Analyze test failures
failures = facade.run_pytest_only("tests/")
suggestions = facade.run_and_analyze("tests/")
```

### DI-Based API (Advanced)

```python
from pytest_analyzer.core.di import get_container
from pytest_analyzer.core.analyzer_service_di import DIPytestAnalyzerService

# Get or create the DI container
container = get_container()

# Resolve the service from the container
service = container.resolve(DIPytestAnalyzerService)

# Use the service
suggestions = service.run_and_analyze("tests/")
```

## Future Considerations

1. **Deprecation Timeline**: Consider a phased approach to eventually remove the legacy API.
2. **Feature Parity**: Ensure all new features are accessible through the facade.
3. **Documentation**: Keep documentation updated as the architecture evolves.
4. **Performance Monitoring**: Compare performance between old and new implementations.
