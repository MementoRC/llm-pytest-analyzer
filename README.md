# pytest_analyzer

Enhanced pytest failure analyzer with robust extraction strategies and intelligent fix suggestions.

## Overview

This package provides an improved implementation for analyzing pytest failures and suggesting fixes, addressing the issues found in the original test_analyzer implementation:

- **Robust Extraction**: Uses structured data (JSON, XML) instead of regex-based parsing to avoid infinite loops
- **Resource Management**: Implements timeout and memory limits for all operations
- **Multiple Extraction Strategies**: Supports JSON, XML, and direct pytest plugin integration
- **Path Resolution**: Safely handles absolute paths to prevent permission issues
- **Modular Design**: Separates extraction, analysis, and fix suggestion into distinct components

## Installation

```bash
# From source
pip install -e /path/to/pytest_analyzer

# Once published
pip install pytest-analyzer
```

## Usage

### Command Line

```bash
# Basic usage
pytest-analyzer path/to/tests

# Specify extraction format
pytest-analyzer path/to/tests --json
pytest-analyzer path/to/tests --xml
pytest-analyzer path/to/tests --plugin

# Analyze existing output file
pytest-analyzer --output-file path/to/pytest_output.json

# Control resource usage
pytest-analyzer path/to/tests --timeout 600 --max-memory 2048

# Additional pytest arguments
pytest-analyzer path/to/tests --pytest-args "--verbose --no-header"
pytest-analyzer path/to/tests -k "test_specific_function"
```

### Python API

```python
from pytest_analyzer import TestAnalyzerService, Settings

# Configure settings
settings = Settings(
    max_failures=10,
    max_suggestions=3,
    min_confidence=0.7,
    preferred_format="json"
)

# Initialize the analyzer service
analyzer = TestAnalyzerService(settings=settings)

# Run tests and analyze failures
suggestions = analyzer.run_and_analyze("tests/", ["--verbose"])

# Analyze existing output file
suggestions = analyzer.analyze_pytest_output("pytest_output.json")

# Process suggestions
for suggestion in suggestions:
    print(f"Test: {suggestion.failure.test_name}")
    print(f"Error: {suggestion.failure.error_type}: {suggestion.failure.error_message}")
    print(f"Suggestion: {suggestion.suggestion}")
    print(f"Confidence: {suggestion.confidence}")
```

## Features

- **Multiple Extraction Formats**: JSON, XML, and direct pytest plugin integration
- **Resource Monitoring**: Timeouts and memory limits prevent infinite loops and excessive resource usage
- **Path Resolution**: Safely handles absolute paths that might cause permission issues
- **Intelligent Fix Suggestions**: Analyzes failure patterns to generate relevant fix suggestions
- **Rich Console Output**: Clear, well-formatted display of failures and suggestions
- **Configurable Settings**: Extensive configuration options for fine-tuning behavior

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.