# Error Handling Strategy

This document outlines the comprehensive error handling strategy for the `pytest-analyzer` project. The goal is to create a robust, predictable, and maintainable system for managing errors, improving both developer experience and application stability.

## 1. Guiding Principles

- **Clarity and Specificity**: Errors should be easy to understand and trace. Use specific exception types over generic ones.
- **Centralization**: Provide centralized utilities (decorators, context managers) to ensure consistent error handling logic.
- **Context is Key**: Exceptions should carry as much context as possible, including the original error, error codes, and relevant operational data.
- **Resilience**: The system should be ableto recover from transient failures and degrade gracefully under sustained failure conditions.
- **Traceability**: Integrated structured logging with correlation IDs allows for tracing an operation or request through the entire system.

## 2. Exception Hierarchy

All custom exceptions inherit from a common `BaseError` class, which provides a standard structure for all errors.

### `BaseError`

The root of our custom exception hierarchy.

- **Attributes**:
  - `message` (str): A human-readable error message.
  - `error_code` (Optional[str]): A unique, machine-readable code (e.g., `CONFIG_001`).
  - `context` (Optional[Dict]): A dictionary containing relevant data about the error's circumstances.
  - `original_exception` (Optional[Exception]): The underlying exception that was caught and wrapped.

### `PytestAnalyzerError`

Inherits from `BaseError`. This is the base class for all errors specific to the `pytest-analyzer` application logic.

### Specific Exception Types

These inherit from `PytestAnalyzerError` and represent specific failure scenarios. Each has a predefined `error_code`.

| Exception Class             | Error Code        | Description                                                  |
| --------------------------- | ----------------- | ------------------------------------------------------------ |
| `ConfigurationError`        | `CONFIG_001`      | Invalid or missing configuration.                            |
| `ExtractionError`           | `EXTRACT_001`     | Failure to extract test failure data from a source.          |
| `AnalysisError`             | `ANALYSIS_001`    | Failure during the analysis of test data.                    |
| `ParsingError`              | `PARSE_001`       | Failure to parse data (e.g., JSON, XML).                     |
| `LLMServiceError`           | `LLM_001`         | Error communicating with an external LLM service.            |
| `FixApplicationError`       | `FIX_APPLY_001`   | Failure to apply a suggested code fix.                       |
| `DependencyResolutionError` | `DEPS_001`        | Failure to resolve a dependency from the DI container.       |
| `RetryError`                | `RETRY_001`       | An operation failed after all configured retry attempts.     |
| `CircuitBreakerOpenError`   | `CIRCUIT_001`     | A call was blocked because the circuit breaker is open.      |

## 3. Structured Logging

To enhance traceability, we use structured (JSON) logging, which can be enabled via configuration.

### Correlation ID

- A unique ID (`correlation_id`) is used to trace a single logical operation or request across multiple function calls and modules.
- It is managed using `contextvars` for implicit propagation.
- **Usage**:
  ```python
  from pytest_analyzer.utils.logging_config import set_correlation_id

  # At the start of a high-level operation (e.g., an API request handler)
  set_correlation_id()

  # All subsequent log messages within this context will have the same correlation_id.
  ```

### JSON Log Format

When enabled, logs are formatted as JSON objects with the following key fields:

- `timestamp`: ISO 8601 timestamp.
- `level`: Log level (e.g., `INFO`, `ERROR`).
- `message`: The log message.
- `name`: The logger name (e.g., `pytest_analyzer.core.service`).
- `correlation_id`: The active correlation ID.
- `exception`: Full exception traceback, if an exception was logged.
- `extra_data`: Any additional dictionary passed to the logger.

## 4. Centralized Error Handling Utilities

These utilities, located in `src.pytest_analyzer.core.cross_cutting.error_handling`, provide the building blocks for our strategy.

### `@error_handler` Decorator

Wraps a function to provide standardized try/except logic.

- **Purpose**: To catch, log, and wrap exceptions in a consistent manner.
- **Usage**:
  ```python
  from pytest_analyzer.core.cross_cutting.error_handling import error_handler
  from pytest_analyzer.core.errors import AnalysisError

  @error_handler(operation_name="failure analysis", error_type=AnalysisError)
  def analyze_failures(failures):
      # ... analysis logic that might fail ...
      pass
  ```

### `@retry` Decorator

Wraps a function to automatically retry it upon failure.

- **Purpose**: To handle transient errors (e.g., network hiccups, temporary service unavailability).
- **Parameters**:
  - `attempts` (int): Maximum number of attempts.
  - `delay` (float): Initial delay between retries in seconds.
  - `backoff` (float): Multiplier for the delay after each failed attempt.
  - `handled_exceptions` (Type[Exception]): The specific exception(s) to catch and trigger a retry.
- **Usage**:
  ```python
  from pytest_analyzer.core.cross_cutting.error_handling import retry
  from pytest_analyzer.core.errors import LLMServiceError

  @retry(attempts=3, delay=2, backoff=2, handled_exceptions=LLMServiceError)
  def call_llm_api(prompt):
      # ... logic to call an external API ...
      pass
  ```

### `CircuitBreaker` and `@circuit_breaker` Decorator

Implements the Circuit Breaker pattern to prevent an application from repeatedly trying to execute an operation that is likely to fail.

- **Purpose**: To provide stability and prevent cascading failures when a downstream service is unavailable.
- **States**: `CLOSED`, `OPEN`, `HALF_OPEN`.
- **Usage**:
  ```python
  from pytest_analyzer.core.cross_cutting.error_handling import CircuitBreaker, circuit_breaker

  # Typically, a single CircuitBreaker instance is shared for all calls to a specific service.
  llm_api_breaker = CircuitBreaker(failure_threshold=5, reset_timeout=60)

  @circuit_breaker(breaker=llm_api_breaker)
  @retry(handled_exceptions=LLMServiceError)
  def call_llm_api_with_breaker(prompt):
      # ... logic ...
      pass
  ```

## 5. Best Practices

1.  **Catch Specific Exceptions**: Whenever possible, catch the most specific exception type instead of a generic `Exception`.
2.  **Use the Utilities**: Prefer using `@error_handler`, `@retry`, and `@circuit_breaker` over writing custom try/except blocks to ensure consistency.
3.  **Add Meaningful Context**: When manually raising an exception, provide a clear message and useful `context`.
    ```python
    from pytest_analyzer.core.errors import ConfigurationError

    if not api_key:
        raise ConfigurationError(
            "LLM API key is missing.",
            context={"config_source": settings_file}
        )
    ```
4.  **Don't Swallow Exceptions**: Avoid catching an exception and doing nothing with it. If you catch an exception, either handle it completely, log it, or re-raise it (preferably wrapped in one of our custom types).
5.  **Layer Decorators Correctly**: The order of decorators matters. The standard order should be:
    1. `@error_handler` (outermost)
    2. `@circuit_breaker`
    3. `@retry` (innermost)
    This ensures that retries happen first. If all retries fail, the circuit breaker records the failure. The `@error_handler` provides a final safety net.
