# Error Handling and Logging Standardization Analysis

## Overview

This analysis examines the current state of error handling and logging throughout the pytest-analyzer codebase and identifies areas that need standardization to use the centralized error handling utilities and structured logging.

## Current Infrastructure

### Available Error Handling Utilities

1. **Custom Exception Hierarchy** (`src/pytest_analyzer/core/errors.py`):
   - `BaseError` - Enhanced base class with error codes, context, and original exception tracking
   - `PytestAnalyzerError` - Base for all analyzer errors
   - Specific exception types: `ConfigurationError`, `ExtractionError`, `AnalysisError`, `ParsingError`, `LLMServiceError`, `FixApplicationError`, `DependencyResolutionError`, `RetryError`, `CircuitBreakerOpenError`

2. **Error Handling Decorators and Utilities** (`src/pytest_analyzer/core/cross_cutting/error_handling.py`):
   - `@error_handler` decorator for function-level error handling
   - `@retry` decorator with exponential backoff
   - `@circuit_breaker` decorator for service resilience
   - `error_context` context manager
   - `batch_operation` utility for bulk operations

3. **Structured Logging** (`src/pytest_analyzer/utils/logging_config.py`):
   - `JsonFormatter` for structured logging
   - `configure_logging` function with correlation ID support
   - Correlation ID context variables
   - Multiple output formats (console, file, JSON)

## Analysis Results

### Files Using Generic Exceptions (Need Standardization)

#### High Priority - Core Business Logic

1. **`src/pytest_analyzer/core/llm/llm_service.py`**
   - ✅ **Already using custom exceptions**: Uses `LLMServiceError`, `ParsingError`
   - ✅ **Custom error context**: Has local `error_context` function
   - ⚠️ **Needs improvement**: Should use centralized `@error_handler` decorator
   - ⚠️ **Missing structured logging**: Using basic logging

2. **`src/pytest_analyzer/core/analysis/suggester_factory.py`**
   - ❌ **Generic exceptions**: `raise ValueError(f"Invalid suggester type: {suggester_type}")`
   - ⚠️ **Basic error handling**: Try/catch with basic logging
   - ❌ **No custom exceptions**: Should use `ConfigurationError` or `AnalysisError`

3. **`src/pytest_analyzer/core/extraction/json_extractor.py`**
   - ✅ **Some custom exceptions**: Uses `ExtractionError`
   - ❌ **Mixed approach**: Also uses `TypeError` for input validation
   - ⚠️ **Basic logging**: Standard logging without structure

4. **`src/pytest_analyzer/mcp/facade.py`**
   - ❌ **Generic exceptions**: Uses basic `Exception` handling
   - ⚠️ **Custom error handling**: Has local async error handler
   - ❌ **No custom exceptions**: Should use appropriate domain exceptions

5. **`src/pytest_analyzer/core/analysis/llm_suggester.py`**
   - ❌ **Generic exceptions**: Basic exception handling in multiple places
   - ⚠️ **Performance tracking**: Good use of performance utilities
   - ❌ **No error handler decorators**: Could benefit from `@retry` and `@circuit_breaker`

#### Medium Priority - Infrastructure and Utilities

6. **`src/pytest_analyzer/utils/configuration.py`**
   - ❌ **Generic exceptions**: Uses `ValueError`, `RuntimeError`, etc.
   - ❌ **Should use**: `ConfigurationError` consistently

7. **`src/pytest_analyzer/core/extraction/extractor_factory.py`**
   - ❌ **Generic exceptions**: Uses `ValueError` for invalid extractor types
   - ❌ **Should use**: `ConfigurationError` or `ExtractionError`

8. **`src/pytest_analyzer/core/infrastructure/base_factory.py`**
   - ❌ **Generic exceptions**: Uses `ValueError`, `TypeError`
   - ❌ **Should use**: `DependencyResolutionError` or `ConfigurationError`

9. **`src/pytest_analyzer/core/application/services/analyzer_service.py`**
   - ❌ **Generic exceptions**: Uses various generic exceptions
   - ❌ **Should use**: Domain-specific exceptions

10. **`src/pytest_analyzer/core/extraction/xml_extractor.py`**
    - ❌ **Generic exceptions**: Uses `ValueError`, `RuntimeError`
    - ❌ **Should use**: `ExtractionError`

### Files with Try/Except Blocks (Candidates for @error_handler)

#### Files that would benefit from `@error_handler` decorator:

1. **LLM Service Methods** (`llm_service.py`):
   - `send_prompt()`, `analyze_failure()`, `suggest_fixes()`
   - Current: Custom error_context
   - Improvement: Use `@error_handler` for consistency

2. **MCP Facade Methods** (`mcp/facade.py`):
   - All async methods have similar error handling patterns
   - Current: Custom async_error_handler
   - Improvement: Standardize with centralized utilities

3. **Extraction Classes**:
   - `JsonResultExtractor.extract()`
   - `XmlExtractor` methods
   - Current: Mixed error handling approaches
   - Improvement: Use `@error_handler` consistently

4. **Factory Classes**:
   - `create_suggester()`, `create_extractor()`
   - Current: Basic try/catch
   - Improvement: Use `@error_handler` with appropriate error types

### Files Using Basic Logging (Need Structured Logging)

#### Files that should import from `logging_config`:

**Currently NO files use structured logging from `logging_config`!**

All 56+ files using `import logging` should be evaluated for structured logging integration:

**High Priority Files:**
1. `src/pytest_analyzer/core/llm/llm_service.py` - Core LLM operations
2. `src/pytest_analyzer/mcp/facade.py` - MCP API operations
3. `src/pytest_analyzer/core/analysis/llm_suggester.py` - Analysis operations
4. `src/pytest_analyzer/core/extraction/json_extractor.py` - Data extraction
5. `src/pytest_analyzer/core/test_executor.py` - Test execution

**Medium Priority Files:**
- All factory classes
- Configuration management
- Resource management utilities
- CLI interfaces

### Files Already Using Error Handling Infrastructure

#### ✅ **Good Examples** (Minimal changes needed):

1. **`src/pytest_analyzer/core/cross_cutting/error_handling.py`**
   - ✅ Already imports and uses custom exceptions
   - ✅ Implements all error handling utilities

2. **`src/pytest_analyzer/core/domain/services/base_failure_analyzer.py`**
   - ✅ Uses custom exceptions from `pytest_analyzer.core.errors`

3. **`src/pytest_analyzer/core/domain/services/base_fix_suggester.py`**
   - ✅ Uses custom exceptions from `pytest_analyzer.core.errors`

4. **`src/pytest_analyzer/core/analysis/fix_applier_adapter.py`**
   - ✅ Uses custom exceptions from `pytest_analyzer.core.errors`

#### ⚠️ **Partial Usage** (Only using @error_handler):

1. **`src/pytest_analyzer/mcp/server.py`**
   - ✅ Uses `@error_handler` decorator
   - ❌ Still needs custom exceptions and structured logging

## Standardization Recommendations

### Phase 1: Critical Business Logic (Week 1)

1. **Replace Generic Exceptions**:
   ```python
   # Bad
   raise ValueError("Invalid suggester type")

   # Good
   raise ConfigurationError(
       f"Invalid suggester type: {suggester_type}",
       context={"available_types": ["rule-based", "llm-based", "composite"]},
       error_code="SUGGESTER_001"
   )
   ```

2. **Add Error Handler Decorators**:
   ```python
   # Add to methods with complex error handling
   @error_handler("analyze_test_failure", AnalysisError)
   def analyze_failure(self, failure: PytestFailure) -> FailureAnalysis:
   ```

3. **Implement Structured Logging**:
   ```python
   # Bad
   import logging
   logger = logging.getLogger(__name__)

   # Good
   from pytest_analyzer.utils.logging_config import configure_logging, set_correlation_id
   import logging
   logger = logging.getLogger(__name__)

   # In operation
   set_correlation_id()
   logger.info("Starting analysis", extra={"extra_data": {"test_count": len(failures)}})
   ```

### Phase 2: Infrastructure and Utilities (Week 2)

1. **Factory Classes**: Replace ValueError with ConfigurationError/DependencyResolutionError
2. **Configuration Management**: Use ConfigurationError consistently
3. **Extraction Modules**: Use ExtractionError consistently

### Phase 3: Enhanced Resilience (Week 3)

1. **Add Circuit Breakers**: For LLM services and external API calls
2. **Add Retry Logic**: For transient failures
3. **Batch Operations**: For processing multiple failures

### Phase 4: MCP and CLI Integration (Week 4)

1. **MCP Server**: Integrate structured logging and error handling
2. **CLI Interfaces**: Add correlation IDs and structured output
3. **Resource Management**: Add monitoring and timeout handling

## Implementation Priority

### Immediate (This Sprint)
1. `suggester_factory.py` - Replace ValueError with ConfigurationError
2. `llm_service.py` - Add @error_handler decorators and structured logging
3. `json_extractor.py` - Replace TypeError with ExtractionError

### Short Term (Next Sprint)
1. `mcp/facade.py` - Integrate custom exceptions and structured logging
2. `llm_suggester.py` - Add @retry and @circuit_breaker decorators
3. Factory classes - Standardize exception types

### Medium Term (Month 2)
1. All extraction modules - Use ExtractionError consistently
2. Configuration management - Use ConfigurationError
3. Infrastructure services - Add resilience patterns

### Long Term (Month 3)
1. Complete structured logging rollout
2. Add comprehensive monitoring
3. Performance optimization with error handling metrics

## Success Metrics

1. **Exception Consistency**: 0 generic exceptions in core business logic
2. **Error Handler Coverage**: 80% of public methods use @error_handler
3. **Structured Logging**: 100% of core modules use structured logging
4. **Resilience Patterns**: All external service calls use circuit breakers
5. **Error Context**: All errors include meaningful context and error codes

## Breaking Changes Impact

**Low Impact**: Most changes are internal implementation details
**Medium Impact**: Some method signatures may change to include context
**High Impact**: Error message formats will be more structured (JSON logs)

## Testing Strategy

1. **Unit Tests**: Verify error types and context are correct
2. **Integration Tests**: Ensure error handling works across module boundaries
3. **Error Injection**: Test circuit breakers and retry mechanisms
4. **Log Validation**: Verify structured logging format and correlation IDs
