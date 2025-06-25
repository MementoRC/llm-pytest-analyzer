# Analysis Tools

These tools provide the core analysis capabilities for pytest output and test failures.

## suggest_fixes

Generate intelligent fix suggestions from raw pytest output.

### Input Schema

```json
{
  "raw_output": "string (required)",
  "max_suggestions": "integer (default: 10)",
  "confidence_threshold": "number (default: 0.3)",
  "include_alternatives": "boolean (default: true)",
  "filter_by_type": "array of strings (optional)"
}
```

### Example Usage

```json
{
  "raw_output": "tests/test_example.py::test_addition FAILED - AssertionError: assert 3 == 4",
  "max_suggestions": 5,
  "confidence_threshold": 0.5
}
```

## run_and_analyze

Execute pytest and analyze results in a single operation.

### Input Schema

```json
{
  "test_pattern": "string (optional)",
  "pytest_args": "array of strings (default: [])",
  "timeout": "integer (default: 300)",
  "max_suggestions": "integer (default: 10)"
}
```
