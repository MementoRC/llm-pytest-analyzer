# pytest-analyzer

Enhanced pytest failure analyzer with robust extraction strategies and intelligent fix suggestions.

## Overview

This package provides an improved implementation for analyzing pytest failures and suggesting fixes, addressing the issues found in traditional test result parsing:

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
from pytest_analyzer import PytestAnalyzerService, Settings

# Configure settings
settings = Settings(
    max_failures=10,
    max_suggestions=3,
    min_confidence=0.7,
    preferred_format="json"
)

# Initialize the analyzer service
analyzer = PytestAnalyzerService(settings=settings)

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

### Multiple Extraction Formats

The analyzer supports three different methods for extracting test failures:

1. **JSON Format** (default): Uses the `pytest-json-report` plugin to generate a detailed JSON report
2. **XML Format**: Uses pytest's built-in JUnit XML output (`--junit-xml`)
3. **Plugin Integration**: Uses a custom pytest plugin to capture failures directly during test execution

Each extraction method has its advantages:

- JSON is highly detailed and provides the most information
- XML is built into pytest and doesn't require additional plugins
- The plugin method captures failures in real-time and works even for syntax errors

### LLM Integration

The analyzer can leverage large language models (LLMs) to generate more sophisticated fix suggestions:

1. **Hybrid Approach**: Combines rule-based and LLM-generated suggestions
2. **Multiple LLM Providers**: Supports Anthropic Claude and OpenAI GPT models
3. **Configurable Settings**: Control confidence thresholds, timeouts, and model selection

To use LLM-based suggestions:

```bash
# Enable LLM suggestions from the command line
pytest-analyzer path/to/tests --use-llm

# Specify API keys and models
pytest-analyzer path/to/tests --use-llm --llm-api-key YOUR_API_KEY --llm-model claude-3-haiku
```

Or using the Python API:

```python
from pytest_analyzer import PytestAnalyzerService, Settings

# Configure settings with LLM enabled
settings = Settings(
    use_llm=True,
    llm_api_key="YOUR_API_KEY",  # Optional, can use environment variables
    llm_model="auto"             # Auto-select available models
)

analyzer = PytestAnalyzerService(settings=settings)
suggestions = analyzer.run_and_analyze("tests/")
```

### Resource Monitoring

To prevent the analyzer from consuming excessive resources or hanging indefinitely:

- **Timeouts**: All operations have configurable timeouts
- **Memory Limits**: Memory usage is restricted to prevent Out-of-Memory errors
- **Resource Monitoring**: Real-time tracking of resource usage during analysis

### Path Resolution

The analyzer includes a robust path resolution system to handle absolute file paths:

- **Mock Directories**: Creates safe mock paths for absolute paths that might cause permission issues
- **Path Relativization**: Converts absolute paths to project-relative paths for safer reporting
- **Directory Mapping**: Maps system directories to project-specific locations

### Intelligent Fix Suggestions

The analyzer examines failure patterns and generates context-aware fix suggestions:

- **Error-Type Analysis**: Different analysis strategies based on error type
- **Confidence Scoring**: Each suggestion includes a confidence score
- **Code Context**: Uses relevant code snippets to provide more specific suggestions
- **Multiple Suggestions**: Generates multiple possible fixes for each failure

### Rich Console Output

The CLI interface provides well-formatted, color-coded output:

- **Syntax Highlighting**: Code snippets are displayed with syntax highlighting
- **Organized Layout**: Failures and suggestions are clearly separated and formatted
- **Progress Information**: Clear indication of what the analyzer is doing

## Architecture

The package is organized into several modules:

- **Core**:
  - `analyzer_service.py`: Main service coordinating extraction and analysis
  - **Extraction**:
    - `extractor_factory.py`: Factory for creating the appropriate extractor
    - `json_extractor.py`: Extracts failures from JSON output
    - `xml_extractor.py`: Extracts failures from XML output
    - `pytest_plugin.py`: Direct pytest plugin for failure extraction
  - **Analysis**:
    - `failure_analyzer.py`: Analyzes failures and identifies patterns
    - `fix_suggester.py`: Generates rule-based fix suggestions
    - `llm_suggester.py`: Generates AI-powered fix suggestions using language models
  - **Models**:
    - `pytest_failure.py`: Data models for failures and suggestions

- **Utils**:
  - `settings.py`: Configuration settings
  - `path_resolver.py`: Path resolution utilities
  - `resource_manager.py`: Resource management and monitoring

- **CLI**:
  - `analyzer_cli.py`: Command-line interface implementation

## Demo

The project includes a `demo_script.py` that demonstrates the various capabilities of the pytest-analyzer:

```bash
# Run the demo script
python demo_script.py
```

The demo creates sample test files with different types of failures and shows how to:
1. Use the pytest-analyzer as a Python API
2. Use the pytest-analyzer as a CLI tool
3. Try different extraction strategies

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes and commit: `git commit -m 'Add some feature'`
4. Push to the branch: `git push origin feature-name`
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
