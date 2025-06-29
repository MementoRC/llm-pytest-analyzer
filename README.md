# pytest-analyzer

[![CI](https://github.com/MementoRC/llm-pytest-analyzer/actions/workflows/ci.yml/badge.svg)](https://github.com/MementoRC/llm-pytest-analyzer/actions/workflows/ci.yml) [![Coverage Status](https://img.shields.io/codecov/c/gh/MementoRC/llm-pytest-analyzer?logo=codecov)](https://codecov.io/gh/MementoRC/llm-pytest-analyzer) [![Dependabot Status](https://img.shields.io/badge/dependabot-enabled-brightgreen?logo=dependabot)](https://github.com/MementoRC/llm-pytest-analyzer/network/updates)

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

The `pytest-analyzer` CLI provides several powerful commands for test analysis, environment checking, and efficiency reporting. All commands support `-h`/`--help` for detailed help and examples.

#### Main Command: `analyze`

Analyze pytest failures and suggest fixes.

```bash
pytest-analyzer analyze path/to/tests
```

**Common options:**
- `--json`, `--xml`, `--plugin`: Choose extraction format
- `--output-file FILE`: Analyze an existing pytest output file
- `--timeout SECONDS`: Set a timeout for test runs
- `--max-memory MB`: Limit memory usage
- `--pytest-args "ARGS"`: Pass additional arguments to pytest
- `-k "expr"`: Filter tests by expression
- `--env-manager [auto|poetry|pixi|hatch|uv|pipenv|pip+venv]`: Specify environment manager

**Examples:**
```bash
pytest-analyzer analyze tests/ --json
pytest-analyzer analyze --output-file results.json
pytest-analyzer analyze tests/ --pytest-args "-v -x"
pytest-analyzer analyze tests/ -k "test_login"
pytest-analyzer analyze tests/ --env-manager poetry
```

#### Smart Test Selection: `smart-test`

Intelligently select and run only relevant tests based on code changes, categories, or optimization.

```bash
pytest-analyzer smart-test [OPTIONS]
```

**Key options:**
- `--all`: Run all tests
- `--category [unit|integration|functional|e2e|performance|security]`: Run only a specific category
- `--optimize-order`: Optimize test execution order
- `--parallel`: Plan parallel execution
- `--fast-fail`: Prioritize likely-to-fail tests
- `--historical-data`: Use historical data for optimization
- `--json`: Output results in JSON format
- `--output-file FILE`: Save report to file

**Examples:**
```bash
pytest-analyzer smart-test --all
pytest-analyzer smart-test --category unit
pytest-analyzer smart-test --optimize-order --parallel
pytest-analyzer smart-test --json --output-file smart_report.json
```

#### Environment Check: `check-env`

Validate your development environment for Python, tools, and CI compatibility.

```bash
pytest-analyzer check-env [OPTIONS]
```

**Key options:**
- `--json`: Output results in JSON format
- `--output-file FILE`: Save report to file
- `--skip-ci-checks`: Skip CI environment checks
- `--skip-tool-checks`: Skip tool availability checks

**Examples:**
```bash
pytest-analyzer check-env
pytest-analyzer check-env --json
pytest-analyzer check-env --output-file env_report.txt
```

#### Efficiency Report: `efficiency-report`

Generate reports on test and fix efficiency, including trends and recommendations.

```bash
pytest-analyzer efficiency-report [OPTIONS]
```

**Key options:**
- `--time-range [day|week|month|all]`: Select report period
- `--compare`: Compare with previous period
- `--trends`: Show trend analysis
- `--recommendations`: Show improvement tips
- `--format [table|json]`: Output format
- `--output-file FILE`: Save report to file

**Examples:**
```bash
pytest-analyzer efficiency-report --time-range week
pytest-analyzer efficiency-report --compare --trends
pytest-analyzer efficiency-report --format json --output-file eff.json
```

#### MCP Server: `mcp`

Start and manage the MCP server for AI assistant integration.

```bash
pytest-analyzer mcp start [--stdio|--http] [--host HOST] [--port PORT]
```

**Examples:**
```bash
pytest-analyzer mcp start --stdio
pytest-analyzer mcp start --http --host 0.0.0.0 --port 9000
```

### Interactive Help

For any command, use `-h` or `--help` for detailed help, usage, and examples:

```bash
pytest-analyzer analyze --help
pytest-analyzer smart-test --help
pytest-analyzer check-env --help
pytest-analyzer efficiency-report --help
pytest-analyzer mcp --help
```

### Shell Completion

Bash and Zsh completion scripts are available for enhanced CLI experience:

```bash
# Bash
eval "$(_PYTEST_ANALYZER_COMPLETE=bash_source pytest-analyzer)"

# Zsh
eval "$(_PYTEST_ANALYZER_COMPLETE=zsh_source pytest-analyzer)"
```

Add the above to your shell profile for persistent completion.

### Quick Reference Cheat Sheet

| Command                        | Description                                 |
|--------------------------------|---------------------------------------------|
| `analyze`                      | Analyze test failures and suggest fixes     |
| `smart-test`                   | Run only relevant/impacted tests           |
| `check-env`                    | Validate environment and toolchain         |
| `efficiency-report`            | Show test/fix efficiency and trends        |
| `mcp`                          | Start/manage MCP server for AI integration |

See `pytest-analyzer <command> --help` for all options.

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

### Environment Manager Integration

`pytest-analyzer` can automatically detect and integrate with various Python environment managers to ensure that `pytest` is executed within the correct project environment. This is crucial for projects that rely on specific package versions or configurations managed by tools like Pixi, Poetry, Hatch, UV, Pipenv, or a standard Pip+Venv setup.

**Supported Environment Managers:**

- **Pixi**: Detected by the presence of a `pixi.toml` file.
- **Poetry**: Detected by a `pyproject.toml` file containing a `[tool.poetry]` section.
- **Hatch**: Detected by a `pyproject.toml` file containing a `[tool.hatch]` section.
- **UV**: Detected by a `uv.lock` file or a `pyproject.toml` file with a `[tool.uv]` section.
- **Pipenv**: Detected by `Pipfile` or `Pipfile.lock`.
- **Pip+Venv**: Detected by `requirements.txt` (often used as a fallback if a virtual environment is active).

**How it Works:**

By default, `pytest-analyzer` attempts to auto-detect the active environment manager. You can also manually specify which manager to use via a CLI flag, configuration file, or environment variable. This ensures that commands, especially `pytest` execution, are prefixed correctly (e.g., `poetry run pytest ...`, `hatch run pytest ...`).

For more detailed information on detection logic, configuration hierarchy, and troubleshooting, please refer to the [Environment Managers Documentation](docs/environment-managers.md).

**CLI Example:**
```bash
# Let pytest-analyzer auto-detect the environment manager
pytest-analyzer path/to/tests
# Explicitly specify an environment manager
pytest-analyzer path/to/tests --env-manager poetry
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
