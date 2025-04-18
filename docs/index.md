# pytest-analyzer Documentation

Welcome to the official documentation for **pytest-analyzer**, an enhanced pytest failure analysis and fix suggestion tool.

## Installation

Install from PyPI:
```bash
pip install pytest-analyzer
```

Or install from source:
```bash
git clone https://github.com/MementoRC/llm-pytest-analyzer.git
cd llm-pytest-analyzer
pip install -e .[dev]
```

## Documentation Structure

- **README**: Core usage, CLI flags, and API examples ([README.md](../README.md)).
- **Configuration**: See the `mkdocs.yml` and docs/ for this site’s configuration.
- **Source Code**: Explore modules under `src/pytest_analyzer/` for internals.

## Building Locally

```bash
pip install mkdocs
mkdocs serve
```