# API User Guide

This guide provides comprehensive instructions for using the `pytest-analyzer` both from the command line and as a Python API. It compiles and expands on the usage documentation from the README and other sources.

---

## Command Line Usage

### Basic Usage

```bash
pytest-analyzer path/to/tests
```

### Extraction Format

- JSON (default):
  `pytest-analyzer path/to/tests --json`
- XML:
  `pytest-analyzer path/to/tests --xml`
- Plugin:
  `pytest-analyzer path/to/tests --plugin`

### Analyze Existing Output

```bash
pytest-analyzer --output-file path/to/pytest_output.json
```

### Resource Controls

```bash
pytest-analyzer path/to/tests --timeout 600 --max-memory 2048
```

### Additional Pytest Arguments

```bash
pytest-analyzer path/to/tests --pytest-args "--verbose --no-header"
pytest-analyzer path/to/tests -k "test_specific_function"
pytest-analyzer path/to/tests --env-manager poetry
```

### LLM Integration

Enable LLM-based suggestions:

```bash
pytest-analyzer path/to/tests --use-llm
pytest-analyzer path/to/tests --use-llm --llm-api-key YOUR_API_KEY --llm-model claude-3-haiku
```

---

## Python API Usage

### Basic Example

```python
from pytest_analyzer import PytestAnalyzerService, Settings

settings = Settings(
    max_failures=10,
    max_suggestions=3,
    min_confidence=0.7,
    preferred_format="json"
)

analyzer = PytestAnalyzerService(settings=settings)
suggestions = analyzer.run_and_analyze("tests/", ["--verbose"])

for suggestion in suggestions:
    print(f"Test: {suggestion.failure.test_name}")
    print(f"Error: {suggestion.failure.error_type}: {suggestion.failure.error_message}")
    print(f"Suggestion: {suggestion.suggestion}")
    print(f"Confidence: {suggestion.confidence}")
```

### Analyze Existing Output

```python
suggestions = analyzer.analyze_pytest_output("pytest_output.json")
```

---

## Features Reference

- **Multiple Extraction Formats**: JSON, XML, plugin
- **LLM Integration**: Anthropic Claude, OpenAI GPT, hybrid suggestions
- **Environment Manager Integration**: Pixi, Poetry, Hatch, UV, Pipenv, Pip+Venv
- **Resource Monitoring**: Timeouts, memory limits
- **Path Resolution**: Safe path handling, mock directories
- **Intelligent Fix Suggestions**: Error-type analysis, confidence scoring, code context
- **Rich Console Output**: Syntax highlighting, organized layout, progress info

---

## Configuration

### CLI Flags

- `--json`, `--xml`, `--plugin`: Extraction format
- `--output-file`: Analyze existing output
- `--timeout`, `--max-memory`: Resource limits
- `--pytest-args`: Pass arguments to pytest
- `--env-manager`: Specify environment manager
- `--use-llm`, `--llm-api-key`, `--llm-model`: LLM integration

### Configuration File

You can use `.pytest-analyzer.yaml` or `.pytest-analyzer.json` to set defaults.

```yaml
max_failures: 10
max_suggestions: 3
min_confidence: 0.7
preferred_format: "json"
environment_manager: "poetry"
use_llm: true
llm_model: "auto"
```

---

## Troubleshooting

- **Incorrect environment manager detected**: Use `--env-manager` to override.
- **LLM suggestions not working**: Check API key and model availability.
- **Resource errors**: Adjust `--timeout` and `--max-memory`.
- **No suggestions generated**: Lower `min_confidence` or check test output.

---

## Further Reading

- [Environment Manager Integration](environment-managers.md)
- [Dependency Injection](DEPENDENCY_INJECTION.md)
- [Architecture](architecture.md)
- [Security Practices](security-practices.md)
