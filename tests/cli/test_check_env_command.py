"""
Comprehensive tests for the Check Environment CLI Command.

Covers:
- Argument parsing and CLI options
- Mocked environment detection and validation
- Report generation for various environment states
- Suggestion accuracy for common issues
- Multiple environment scenarios (CI, local, missing tools, etc)
- Error handling for unavailable system info
- Output format (JSON, human-readable)
- Integration with SecurityManager and Settings
"""

import json
import sys
from typing import Callable, Optional
from unittest.mock import MagicMock, patch

import pytest

# Import the actual command and its dependencies for type hinting and patching
from pytest_analyzer.cli.check_env import CheckEnvironmentCommand, main
from pytest_analyzer.core.infrastructure.ci_detection import (
    CIEnvironmentDetector,
    DetectionResult,
)
from pytest_analyzer.mcp.security import SecurityManager
from pytest_analyzer.utils.settings import Settings

# --- Fixtures for Mocks ---


@pytest.fixture
def mock_ci_detector_instance():
    """Fixture to provide a mock CIEnvironmentDetector instance."""
    mock = MagicMock(spec=CIEnvironmentDetector)
    # Default behavior for get_detection_result if not overridden in test
    mock.get_detection_result.return_value = MagicMock(spec=DetectionResult)
    mock.get_detection_result.return_value.platform = MagicMock(
        name="local", detected=False, raw_env={}
    )
    mock.get_detection_result.return_value.available_tools = []
    mock.get_detection_result.return_value.missing_tools = []
    mock.get_detection_result.return_value.install_commands = {}
    return mock


@pytest.fixture
def mock_security_manager_instance():
    """Fixture to provide a mock SecurityManager instance."""
    mock = MagicMock(spec=SecurityManager)
    return mock


@pytest.fixture
def mock_settings_instance():
    """Fixture to provide a mock Settings instance."""
    mock = MagicMock(spec=Settings)
    # Ensure no 'security' attribute by default to avoid re-initialization of SecurityManager
    # unless explicitly set by a test.
    # If a test needs security settings, it should set mock.security = MagicMock()
    # and potentially patch SecurityManager class if it wants to control the *re-initialized* instance.
    return mock


@pytest.fixture
def mock_settings_loader_callable(mock_settings_instance):
    """Fixture to provide a mock settings loader callable."""
    mock = MagicMock(spec=Callable[[Optional[str]], Settings])
    mock.return_value = mock_settings_instance
    return mock


# --- CLI Execution Helper ---


@pytest.fixture
def run_cli(monkeypatch):
    """Helper to run the CLI with args and inject mocked dependencies into CheckEnvironmentCommand."""

    def _run(
        args: list,
        ci_detector: MagicMock,
        security_manager: MagicMock,
        settings: MagicMock,
        settings_loader: MagicMock,
    ):
        monkeypatch.setattr(sys, "argv", ["pytest-analyzer-check-env"] + args)

        # Patch CheckEnvironmentCommand's __init__ to inject the provided mocks.
        # This allows us to control the dependencies that the CheckEnvironmentCommand instance uses
        # when it's instantiated by the main() function.
        original_init = CheckEnvironmentCommand.__init__

        def mock_init(self, *init_args, **init_kwargs):
            # Call the original __init__ first to set up default attributes
            original_init(self, *init_args, **init_kwargs)
            # Then override with our injected mocks
            self.ci_detector = ci_detector
            self.security_manager = security_manager
            self._settings_loader = settings_loader
            self._initial_settings = (
                settings  # This is the 'settings' parameter to __init__
            )

        with patch(
            "pytest_analyzer.cli.check_env.CheckEnvironmentCommand.__init__",
            new=mock_init,
        ):
            # Capture stdout/stderr
            import contextlib
            from io import StringIO

            out = StringIO()
            err = StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                try:
                    # Call the main entry point, which will instantiate CheckEnvironmentCommand
                    # and trigger our mock_init
                    code = main()
                except SystemExit as e:
                    code = e.code
            return code, out.getvalue(), err.getvalue()

    return _run


# --- Sample Environment Result (adapted for new mock structure) ---


@pytest.fixture
def sample_env_result_data():
    """Return a sample DetectionResult-like object for CIEnvironmentDetector mock."""

    # These are simple mocks that mimic the structure needed by CheckEnvironmentCommand
    # for its _validate_ci_environment method.
    class DummyPlatform:
        name = "github"
        detected = True
        raw_env = {"GITHUB_ACTIONS": "true"}

    class DummyTool:
        def __init__(self, name, found, version=None):
            self.name = name
            self.found = found
            self.version = version
            self.path = f"/usr/bin/{name}" if found else None

    mock_detection_result = MagicMock(spec=DetectionResult)
    mock_detection_result.platform = DummyPlatform()
    mock_detection_result.available_tools = [
        DummyTool("bandit", True, "1.7.5"),
        DummyTool("safety", False),
        DummyTool("mypy", True, "1.2.3"),
        DummyTool("ruff", False),
    ]
    mock_detection_result.missing_tools = ["safety", "ruff"]
    mock_detection_result.install_commands = {
        "safety": "pip install safety",
        "ruff": "pip install ruff",
    }
    return mock_detection_result


# --- Tests ---


@pytest.mark.parametrize(
    "args,expected_json,expected_human",
    [
        ([], False, True),
        (["--json"], True, False),
    ],
)
def test_cli_argument_parsing(
    run_cli,
    mock_ci_detector_instance,
    mock_security_manager_instance,
    mock_settings_instance,
    mock_settings_loader_callable,
    sample_env_result_data,
    args,
    expected_json,
    expected_human,
):
    """Test CLI argument parsing for output format options."""
    mock_ci_detector_instance.get_detection_result.return_value = sample_env_result_data
    code, out, err = run_cli(
        args,
        ci_detector=mock_ci_detector_instance,
        security_manager=mock_security_manager_instance,
        settings=mock_settings_instance,
        settings_loader=mock_settings_loader_callable,
    )
    assert code == 0
    if expected_json:
        data = json.loads(out)
        assert "platform" in data
        assert data["platform"]["name"] == "github"
        assert "missing_tools" in data
    if expected_human:
        # Check for general human-readable report elements
        assert "Platform Information" in out
        assert "Python Environment" in out
        assert "Development Tools" in out
        assert (
            "Suggestions:" in out
        )  # Expect suggestions section if there are missing tools
        # Specific CI environment details are not displayed in human-readable format by current CLI
        assert (
            "github" not in out
        )  # The platform name 'github' is not directly printed in human-readable
        assert "CI Environment:" not in out  # This specific header is not used


def test_cli_detects_missing_tools_and_suggests_install(
    run_cli,
    mock_ci_detector_instance,
    mock_security_manager_instance,
    mock_settings_instance,
    mock_settings_loader_callable,
    sample_env_result_data,
):
    """Test that missing tools are reported and install suggestions are shown."""
    mock_ci_detector_instance.get_detection_result.return_value = sample_env_result_data
    code, out, err = run_cli(
        [],
        ci_detector=mock_ci_detector_instance,
        security_manager=mock_security_manager_instance,
        settings=mock_settings_instance,
        settings_loader=mock_settings_loader_callable,
    )
    assert code == 0
    assert "Suggestions:" in out  # The section for suggestions
    assert "safety" in out and "ruff" in out  # Missing tools mentioned in suggestions
    assert "pip install safety" in out
    assert "pip install ruff" in out


def test_cli_all_tools_present(
    run_cli,
    mock_ci_detector_instance,
    mock_security_manager_instance,
    mock_settings_instance,
    mock_settings_loader_callable,
):
    """Test output when all required tools are present."""

    class DummyPlatform:
        name = "local"
        detected = False
        raw_env = {}

    class DummyTool:
        def __init__(self, name, found, version=None):
            self.name = name
            self.found = found
            self.version = version
            self.path = f"/usr/bin/{name}" if found else None

    env_result = MagicMock(spec=DetectionResult)
    env_result.platform = DummyPlatform()
    env_result.available_tools = [
        DummyTool("bandit", True, "1.7.5"),
        DummyTool("safety", True, "2.0.0"),
        DummyTool("mypy", True, "1.2.3"),
        DummyTool("ruff", True, "0.3.0"),
    ]
    env_result.missing_tools = []
    env_result.install_commands = {}

    mock_ci_detector_instance.get_detection_result.return_value = env_result
    code, out, err = run_cli(
        [],
        ci_detector=mock_ci_detector_instance,
        security_manager=mock_security_manager_instance,
        settings=mock_settings_instance,
        settings_loader=mock_settings_loader_callable,
    )
    assert code == 0
    assert "Status: HEALTHY" in out  # Check overall status
    assert "Suggestions:" not in out  # No suggestions section if all tools are present


@pytest.mark.parametrize(
    "platform_name,detected,expected_json_name",
    [
        ("github", True, "github"),
        ("gitlab", True, "gitlab"),
        ("jenkins", True, "jenkins"),
        ("circleci", True, "circleci"),
        ("travis", True, "travis"),
        ("azure", True, "azure"),
        ("local", False, "local"),
    ],
)
def test_cli_platform_detection(
    run_cli,
    mock_ci_detector_instance,
    mock_security_manager_instance,
    mock_settings_instance,
    mock_settings_loader_callable,
    platform_name,
    detected,
    expected_json_name,
):
    """Test detection and reporting of various CI platforms in JSON output."""

    class DummyPlatform:
        name = platform_name
        detected = detected
        raw_env = {}

    class DummyTool:
        def __init__(self, name, found, version=None):
            self.name = name
            self.found = found
            self.version = version
            self.path = f"/usr/bin/{name}" if found else None

    env_result = MagicMock(spec=DetectionResult)
    env_result.platform = DummyPlatform()
    env_result.available_tools = [DummyTool("bandit", True)]
    env_result.missing_tools = []
    env_result.install_commands = {}

    mock_ci_detector_instance.get_detection_result.return_value = env_result
    code, out, err = run_cli(
        ["--json"],  # Force JSON output to check platform name
        ci_detector=mock_ci_detector_instance,
        security_manager=mock_security_manager_instance,
        settings=mock_settings_instance,
        settings_loader=mock_settings_loader_callable,
    )
    assert code == 0
    data = json.loads(out)
    assert data["ci_environment"]["platform"]["name"] == expected_json_name
    # Human-readable output does not display CI platform name directly, so no check here.


def test_cli_json_output(
    run_cli,
    mock_ci_detector_instance,
    mock_security_manager_instance,
    mock_settings_instance,
    mock_settings_loader_callable,
    sample_env_result_data,
):
    """Test JSON output format."""
    mock_ci_detector_instance.get_detection_result.return_value = sample_env_result_data
    code, out, err = run_cli(
        ["--json"],
        ci_detector=mock_ci_detector_instance,
        security_manager=mock_security_manager_instance,
        settings=mock_settings_instance,
        settings_loader=mock_settings_loader_callable,
    )
    assert code == 0
    data = json.loads(out)
    assert data["ci_environment"]["platform"]["name"] == "github"
    assert "missing_tools" in data["ci_environment"]
    assert "install_commands" in data["ci_environment"]
    assert "tools" in data  # Check for general tools section
    assert any(tool["name"] == "safety" and not tool["found"] for tool in data["tools"])


def test_cli_error_handling_env_unavailable(
    run_cli,
    mock_ci_detector_instance,
    mock_security_manager_instance,
    mock_settings_instance,
    mock_settings_loader_callable,
):
    """Test error handling when environment info is unavailable."""
    mock_ci_detector_instance.get_detection_result.side_effect = Exception(
        "Env unavailable"
    )
    code, out, err = run_cli(
        [],
        ci_detector=mock_ci_detector_instance,
        security_manager=mock_security_manager_instance,
        settings=mock_settings_instance,
        settings_loader=mock_settings_loader_callable,
    )
    assert code != 0
    assert (
        "error" in out.lower()
        or "unavailable" in out.lower()
        or "exception" in out.lower()
    )


def test_cli_handles_security_manager(
    run_cli,
    mock_ci_detector_instance,
    mock_security_manager_instance,
    mock_settings_instance,
    mock_settings_loader_callable,
    sample_env_result_data,
):
    """Test integration with SecurityManager."""
    mock_ci_detector_instance.get_detection_result.return_value = sample_env_result_data
    code, out, err = run_cli(
        [],
        ci_detector=mock_ci_detector_instance,
        security_manager=mock_security_manager_instance,
        settings=mock_settings_instance,
        settings_loader=mock_settings_loader_callable,
    )
    assert code == 0
    # The test ensures that the command runs successfully with the mocked security manager injected.
    # No specific methods of SecurityManager are called by check_env command in its current implementation,
    # so no further assertions on mock_security_manager_instance are needed here.


def test_cli_handles_settings(
    run_cli,
    mock_ci_detector_instance,
    mock_security_manager_instance,
    mock_settings_instance,
    mock_settings_loader_callable,
    sample_env_result_data,
):
    """Test integration with Settings."""
    mock_ci_detector_instance.get_detection_result.return_value = sample_env_result_data
    code, out, err = run_cli(
        [],
        ci_detector=mock_ci_detector_instance,
        security_manager=mock_security_manager_instance,
        settings=mock_settings_instance,
        settings_loader=mock_settings_loader_callable,
    )
    assert code == 0
    # Verify that the settings loader was called to load settings
    mock_settings_loader_callable.assert_called_once_with(
        None
    )  # Default call without --config-file


@pytest.mark.parametrize(
    "missing_tools,expected_suggestion_parts",
    [
        (["bandit"], ["pip install bandit"]),
        (["mypy", "ruff"], ["pip install mypy", "pip install ruff"]),
    ],
)
def test_cli_suggestion_accuracy(
    run_cli,
    mock_ci_detector_instance,
    mock_security_manager_instance,
    mock_settings_instance,
    mock_settings_loader_callable,
    missing_tools,
    expected_suggestion_parts,
):
    """Test that install suggestions are accurate for missing tools."""

    class DummyPlatform:
        name = "github"
        detected = True
        raw_env = {}

    class DummyTool:
        def __init__(self, name, found, version=None):
            self.name = name
            self.found = found
            self.version = version
            self.path = f"/usr/bin/{name}" if found else None

    tools = [DummyTool(t, False) for t in missing_tools]
    install_commands = {t: f"pip install {t}" for t in missing_tools}

    env_result = MagicMock(spec=DetectionResult)
    env_result.platform = DummyPlatform()
    env_result.available_tools = tools
    env_result.missing_tools = missing_tools
    env_result.install_commands = install_commands

    mock_ci_detector_instance.get_detection_result.return_value = env_result
    code, out, err = run_cli(
        [],
        ci_detector=mock_ci_detector_instance,
        security_manager=mock_security_manager_instance,
        settings=mock_settings_instance,
        settings_loader=mock_settings_loader_callable,
    )
    assert code == 0
    assert "Suggestions:" in out
    for suggestion_part in expected_suggestion_parts:
        assert suggestion_part in out


def test_cli_edge_case_no_tools(
    run_cli,
    mock_ci_detector_instance,
    mock_security_manager_instance,
    mock_settings_instance,
    mock_settings_loader_callable,
):
    """Test edge case where no tools are found at all."""

    class DummyPlatform:
        name = "local"
        detected = False
        raw_env = {}

    env_result = MagicMock(spec=DetectionResult)
    env_result.platform = DummyPlatform()
    env_result.available_tools = []
    env_result.missing_tools = ["bandit", "safety", "mypy", "ruff"]
    env_result.install_commands = {
        "bandit": "pixi add bandit",
        "safety": "pixi add safety",
        "mypy": "pixi add mypy",
        "ruff": "pixi add ruff",
    }
    mock_ci_detector_instance.get_detection_result.return_value = env_result
    code, out, err = run_cli(
        [],
        ci_detector=mock_ci_detector_instance,
        security_manager=mock_security_manager_instance,
        settings=mock_settings_instance,
        settings_loader=mock_settings_loader_callable,
    )
    assert code == 0
    assert "Suggestions:" in out
    assert "pixi add bandit" in out
    assert "pixi add safety" in out
    assert "pixi add mypy" in out
    assert "pixi add ruff" in out


def test_cli_multiple_argument_combinations(
    run_cli,
    mock_ci_detector_instance,
    mock_security_manager_instance,
    mock_settings_instance,
    mock_settings_loader_callable,
    sample_env_result_data,
):
    """Test CLI with multiple argument combinations."""
    mock_ci_detector_instance.get_detection_result.return_value = sample_env_result_data
    # The CLI's argparse only defines --json, not -j.
    for arg in [["--json"]]:
        code, out, err = run_cli(
            arg,
            ci_detector=mock_ci_detector_instance,
            security_manager=mock_security_manager_instance,
            settings=mock_settings_instance,
            settings_loader=mock_settings_loader_callable,
        )
        assert code == 0
        data = json.loads(out)
        assert "platform" in data


def test_cli_help(monkeypatch):
    """Test that --help prints usage and exits."""
    # This test doesn't need dependency injection as it exits early before command instantiation.
    monkeypatch.setattr(sys, "argv", ["pytest-analyzer-check-env", "--help"])
    with pytest.raises(SystemExit) as excinfo:
        main()  # Call the actual main function
    assert excinfo.value.code == 0
