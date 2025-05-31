# Environment Manager Integration

`pytest-analyzer` is designed to work seamlessly with various Python project and environment managers. This integration ensures that `pytest` and other related commands are executed within the context of the project's defined environment, respecting its dependencies and configurations.

## Introduction

Modern Python development often involves tools like Poetry, Hatch, Pixi, UV, or Pipenv to manage project dependencies and virtual environments. `pytest-analyzer` can detect these tools and adapt its command execution accordingly. For example, instead of just running `pytest`, it might run `poetry run pytest` or `hatch run test`.

This feature helps in:
- Ensuring tests are run with the correct dependencies.
- Utilizing environment-specific scripts or configurations.
- Providing a more consistent development experience.

## Supported Environment Managers

`pytest-analyzer` currently supports the detection and integration of the following environment managers:

| Manager    | Detection Heuristic                                       |
|------------|-----------------------------------------------------------|
| **Pixi**   | Presence of a `pixi.toml` file.                           |
| **Poetry** | Presence of `pyproject.toml` with a `[tool.poetry]` section. |
| **Hatch**  | Presence of `pyproject.toml` with a `[tool.hatch]` section.  |
| **UV**     | Presence of `uv.lock` or `pyproject.toml` with `[tool.uv]` section. |
| **Pipenv** | Presence of `Pipfile` or `Pipfile.lock`.                  |
| **Pip+Venv**| Presence of `requirements.txt` (often as a fallback, assuming an active virtual environment). |

## Detection Mechanism

When `pytest-analyzer` is invoked, it attempts to identify the active environment manager for the project root.

1.  **File-Based Detection**: The detection process primarily relies on the presence of specific configuration files in the project's root directory (e.g., `pixi.toml`, `pyproject.toml`, `Pipfile`).
2.  **Order of Precedence**: The managers are checked in a specific order. The first manager detected "wins". The default order is:
    1.  Pixi
    2.  Poetry
    3.  Hatch
    4.  UV
    5.  Pipenv
    6.  Pip+Venv (typically a fallback)
3.  **Caching**: To improve performance, the detected manager for a project path is cached. The cache considers file modification times of relevant project files (`pixi.toml`, `pyproject.toml`, `Pipfile`, `Pipfile.lock`, `requirements.txt`, `uv.lock`) and has a Time-To-Live (TTL). If any of these files change, the cache is invalidated for that project.

## Configuration

You can control `pytest-analyzer`'s environment manager behavior through several means, following a clear hierarchy of precedence:

1.  **Command-Line Interface (CLI) Flag (`--env-manager`)**: Highest priority.
2.  **Configuration File (`environment_manager` setting)**:
    - Project-specific: `.pytest-analyzer.yaml` or `.pytest-analyzer.json` in the project root.
    - User-specific: Global configuration file (e.g., `~/.config/pytest-analyzer/config.yaml`).
3.  **Environment Variable (`PYTEST_ANALYZER_ENV_MANAGER`)**:
4.  **Auto-Detection**: Lowest priority (this is the default behavior if no override is specified).

### 1. CLI Flag

The `--env-manager` flag allows you to specify the environment manager directly when running `pytest-analyzer` from the command line.

```bash
pytest-analyzer path/to/your/tests --env-manager poetry
```

Accepted values for `--env-manager`:
- `auto` (default): Enables auto-detection.
- `pixi`
- `poetry`
- `hatch`
- `uv`
- `pipenv`
- `pip+venv` (for pip with a virtual environment)

Example:
```bash
# Force using Pipenv, even if other managers might be detected
pytest-analyzer . --env-manager pipenv

# Disable specific manager integration and rely on system pytest (if 'auto' fails or is not desired)
# This is effectively what happens if 'auto' finds nothing and no specific manager is set.
# To explicitly use a generic pip+venv setup if requirements.txt exists:
pytest-analyzer . --env-manager pip+venv
```

### 2. Configuration File

You can set the `environment_manager` in your `pytest-analyzer` configuration file (e.g., `.pytest-analyzer.yaml`).

```yaml
# .pytest-analyzer.yaml
# ... other settings ...
environment_manager: "poetry" # or "pixi", "hatch", "uv", "pipenv", "pip+venv", null for auto
# ... other settings ...
```

If `environment_manager` is set to `null` or omitted in the config file, auto-detection will be used (unless overridden by CLI or environment variable).

### 3. Environment Variable

Set the `PYTEST_ANALYZER_ENV_MANAGER` environment variable:

```bash
export PYTEST_ANALYZER_ENV_MANAGER="hatch"
pytest-analyzer path/to/your/tests
```

Accepted values are the same as for the CLI flag.

### 4. Auto-Detection (Default)

If no override is provided through the CLI, configuration file, or environment variable, `pytest-analyzer` will automatically try to detect the environment manager based on the project files.

## Programmatic Usage (Python API)

When using `pytest-analyzer` as a Python library, you can specify the environment manager through the `Settings` object:

```python
from pytest_analyzer.utils.settings import Settings
from pytest_analyzer.core.analyzer_service import PytestAnalyzerService

# To force a specific manager:
settings = Settings(
    project_root="path/to/your/project",
    environment_manager="poetry"  # Or "pixi", "hatch", "uv", "pipenv", "pip+venv"
)

# To rely on auto-detection (default behavior):
settings_auto = Settings(
    project_root="path/to/your/project",
    environment_manager=None # or omit the parameter
)

analyzer = PytestAnalyzerService(settings=settings)
# ... proceed with analysis ...
```

## Troubleshooting

- **Incorrect Detection**: If `pytest-analyzer` detects the wrong manager, or none at all:
    - Ensure the characteristic file for your desired manager (e.g., `poetry.lock` for Poetry, `pixi.toml` for Pixi) is present in the project root.
    - Use the `--env-manager` CLI flag or the `environment_manager` configuration setting to explicitly specify the correct manager.
    - Check the file permissions for the project files.
- **"Manager Not Found" Errors**: If you specify a manager that isn't installed or configured correctly in the project (e.g., `poetry run` fails because Poetry isn't managing the project), `pytest-analyzer` might fail. Ensure the chosen manager is appropriate for the project.
- **Cache Issues**: If you've recently changed your project's environment management setup, detection might rely on a cached value. While file modification times should invalidate the cache, you can try running with a slightly modified relevant file (e.g., add a comment to `pyproject.toml`) or wait for the cache TTL to expire (default 5 minutes). Forcing a re-detection in CI/CD might involve clearing any persistent cache if applicable, though `pytest-analyzer`'s cache is in-memory per process.

## Examples

Minimal project setups demonstrating detection for each supported environment manager can be found in the `examples/` directory of the `pytest-analyzer` repository:

- [`examples/pixi-project/`](../../examples/pixi-project/)
- [`examples/poetry-project/`](../../examples/poetry-project/)
- [`examples/hatch-project/`](../../examples/hatch-project/)
- [`examples/uv-project/`](../../examples/uv-project/)
- [`examples/pipenv-project/`](../../examples/pipenv-project/)
- [`examples/pip-venv-project/`](../../examples/pip-venv-project/)

These examples contain the basic files needed for `pytest-analyzer` to detect the respective environment manager.
