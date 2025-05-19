# Pytest Analyzer Quick Start Guide

This guide will help you get started with the pytest-analyzer tool quickly.

## Installation

```bash
# Install from the repository
pip install -e /path/to/pytest-analyzer

# When published to PyPI, you can install with:
# pip install pytest-analyzer
```

## Basic Usage

### Analyze pytest failures from the command line

The simplest way to use pytest-analyzer is to point it at your test directory:

```bash
pytest-analyzer path/to/tests
```

This will:
1. Run pytest on your test directory
2. Capture any failing tests
3. Analyze the failures
4. Suggest fixes with confidence scores

### Command-line Options

```bash
# Analyze specific test files
pytest-analyzer path/to/specific_test.py

# Filter tests using pytest's -k option
pytest-analyzer path/to/tests -k "test_specific_function"

# Choose an extraction format
pytest-analyzer path/to/tests --json  # Default
pytest-analyzer path/to/tests --xml
pytest-analyzer path/to/tests --plugin

# Limit the number of failures and suggestions
pytest-analyzer path/to/tests --max-failures 5 --max-suggestions 2

# Set a confidence threshold for suggestions
pytest-analyzer path/to/tests --min-confidence 0.7

# Set resource limits
pytest-analyzer path/to/tests --timeout 600 --max-memory 2048

# Pass additional arguments to pytest
pytest-analyzer path/to/tests --pytest-args "--verbose --no-header"

# Enable LLM-powered suggestions
pytest-analyzer path/to/tests --use-llm

# Configure LLM settings
pytest-analyzer path/to/tests --use-llm --llm-timeout 120 --llm-model claude-3-haiku

# Enable debug logging
pytest-analyzer path/to/tests --debug
```

## Python API

You can also use pytest-analyzer programmatically in your Python code:

```python
from pytest_analyzer import PytestAnalyzerService, Settings

# Configure settings
settings = Settings(
    max_failures=10,
    max_suggestions=3,
    min_confidence=0.7,
    preferred_format="json",
    # LLM settings (optional)
    use_llm=True,
    llm_timeout=60
)

# Initialize the analyzer service
analyzer = PytestAnalyzerService(settings=settings)

# Run tests and analyze failures
suggestions = analyzer.run_and_analyze("tests/", ["--verbose"])

# Process suggestions
for suggestion in suggestions:
    print(f"Test: {suggestion.failure.test_name}")
    print(f"Error: {suggestion.failure.error_type}: {suggestion.failure.error_message}")
    print(f"Suggestion: {suggestion.suggestion}")
    print(f"Confidence: {suggestion.confidence}")

    # Access more detailed information
    failure = suggestion.failure
    print(f"File: {failure.test_file}")
    print(f"Line: {failure.line_number}")
    if failure.relevant_code:
        print(f"Code: {failure.relevant_code}")
```

## Analyze Existing Pytest Output

If you already have pytest output files, you can analyze them directly:

```bash
# Analyze a JSON report
pytest-analyzer --output-file path/to/pytest_output.json

# Analyze an XML report
pytest-analyzer --output-file path/to/pytest_output.xml
```

Or using the Python API:

```python
from pytest_analyzer import PytestAnalyzerService

analyzer = PytestAnalyzerService()
suggestions = analyzer.analyze_pytest_output("pytest_output.json")
```

## Running the Demo

The package includes a demo script that shows how to use the different features:

```bash
# Run the demo script
python demo_script.py
```

This creates sample test files with various failure types and demonstrates:
1. Using the Python API
2. Using the command-line interface
3. Testing different extraction strategies

## Common Error Types and Suggestions

The analyzer can handle many types of test failures:

- **AssertionError**: Suggests updates to expected values or implementation code
- **AttributeError**: Suggests adding missing attributes or checking for typos
- **ImportError**: Suggests installing missing packages or checking import paths
- **TypeError**: Suggests fixing argument type mismatches
- **NameError**: Suggests defining missing variables or checking for typos
- **IndexError**: Suggests checking array bounds
- **KeyError**: Suggests using dict.get() with a default value
- **SyntaxError**: Suggests fixing syntax issues like missing colons or parentheses

## Next Steps

- Read the full [README.md](README.md) for more details
- Explore the source code to understand the architecture
- Try running the analyzer on your own test suite
