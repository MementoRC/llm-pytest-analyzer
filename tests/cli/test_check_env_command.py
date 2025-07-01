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
    # Create a "healthy" default environment
    class DummyPlatform:
        name = "local"
        detected = False
        raw_env = {}

    class DummyTool:
        def __init__(self, name, found=True, version="1.0.0"):
            self.name = name
            self.found = found
            self.version = version
            self.path = f"/usr/bin/{name}" if found else None

    mock_detection_result = MagicMock(spec=DetectionResult)
    mock_detection_result.platform = DummyPlatform()
    mock_detection_result.available_tools = [
        DummyTool("bandit", True, "1.7.5"),
        DummyTool("safety", True, "2.0.0"),
        DummyTool("mypy", True, "1.2.3"),
        DummyTool("ruff", True, "0.3.0"),
    ]
    mock_detection_result.missing_tools = []
    mock_detection_result.install_commands = {}

    mock.get_detection_result.return_value = mock_detection_result
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
        **kwargs,
    ):
        monkeypatch.setattr(sys, "argv", ["pytest-analyzer-check-env"] + args)

        # Patch CheckEnvironmentCommand's __init__ to inject the provided mocks.
        # This allows us to control the dependencies that the CheckEnvironmentCommand instance uses
        # when it's instantiated by the main() function.
        original_init = CheckEnvironmentCommand.__init__

        def mock_init(self, *init_args, **init_kwargs):
            # Call the original __init__ with our injected mocks
            original_init(
                self,
                ci_detector=ci_detector,
                security_manager=security_manager,
                settings=settings,
                settings_loader=settings_loader,
            )

        # Allow tests to override the _check_tool mock behavior
        check_tool_mock = kwargs.get("check_tool_mock", None)

        def default_check_tool(tool_name):
            return {
                "name": tool_name,
                "found": True,
                "path": f"/usr/bin/{tool_name}",
                "version": "1.0.0",
            }

        def custom_check_tool(tool_name):
            if callable(check_tool_mock):
                return check_tool_mock(tool_name)
            else:
                return check_tool_mock

        check_tool_func = custom_check_tool if check_tool_mock else default_check_tool

        with (
            patch(
                "pytest_analyzer.cli.check_env.CheckEnvironmentCommand.__init__",
                new=mock_init,
            ),
            patch(
                "pytest_analyzer.cli.check_env.CheckEnvironmentCommand._check_tool",
                side_effect=check_tool_func,
            ),
        ):
            # Capture stdout/stderr
            import contextlib
            from io import StringIO

            out = StringIO()
            err = StringIO()

            # Create a more comprehensive Rich console mock
            from rich.console import Console

            # Create a mock console that captures all output methods
            mock_console = Console(
                file=out,
                width=80,
                legacy_windows=False,
                force_terminal=False,
                _environ={},
            )

            with patch("pytest_analyzer.cli.check_env.console", mock_console):
                # Also capture regular print() calls for JSON output
                with patch("builtins.print") as mock_print:

                    def capture_print(*args, **kwargs):
                        # Write to our captured output
                        import sys

                        file = kwargs.get("file", sys.stdout)
                        if file == sys.stdout:
                            # Redirect stdout prints to our captured output
                            out.write(
                                " ".join(str(arg) for arg in args)
                                + kwargs.get("end", "\n")
                            )
                        else:
                            # For other files, use the original print
                            __builtins__["print"](*args, **kwargs)

                    mock_print.side_effect = capture_print

                    with (
                        contextlib.redirect_stdout(out),
                        contextlib.redirect_stderr(err),
                    ):
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
        DummyTool("safety", True, "2.0.0"),
        DummyTool("mypy", True, "1.2.3"),
        DummyTool("ruff", True, "0.3.0"),
    ]
    mock_detection_result.missing_tools = []
    mock_detection_result.install_commands = {}
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
        assert "ci_environment" in data
        assert data["ci_environment"]["platform"]["name"] == "github"
        assert "missing_tools" in data["ci_environment"]
    if expected_human:
        # Check for general human-readable report elements
        assert "Platform Information" in out
        assert "Python Environment" in out
        assert "Development Tools" in out
        # Note: No suggestions section expected for healthy environment (all tools found)
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
):
    """Test that missing tools are reported and install suggestions are shown."""

    # Create environment data with missing tools for this specific test
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

    mock_ci_detector_instance.get_detection_result.return_value = mock_detection_result

    # Create a custom check_tool function that simulates missing tools
    def check_tool_with_missing(tool_name):
        missing_tools = ["poetry"]  # Make poetry missing to trigger suggestions
        if tool_name in missing_tools:
            return {"name": tool_name, "found": False, "path": None, "version": None}
        else:
            return {
                "name": tool_name,
                "found": True,
                "path": f"/usr/bin/{tool_name}",
                "version": "1.0.0",
            }

    code, out, err = run_cli(
        [],
        ci_detector=mock_ci_detector_instance,
        security_manager=mock_security_manager_instance,
        settings=mock_settings_instance,
        settings_loader=mock_settings_loader_callable,
        check_tool_mock=check_tool_with_missing,
    )
    assert code == 1  # Warning status due to missing tools
    assert "Suggestions:" in out  # The section for suggestions
    assert "poetry" in out  # Missing tool mentioned in suggestions
    assert "Install poetry:" in out  # Install suggestion for poetry


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
        def __init__(self, platform_name, detected):
            self.name = platform_name
            self.detected = detected
            self.raw_env = {}

    class DummyTool:
        def __init__(self, name, found, version=None):
            self.name = name
            self.found = found
            self.version = version
            self.path = f"/usr/bin/{name}" if found else None

    env_result = MagicMock(spec=DetectionResult)
    env_result.platform = DummyPlatform(platform_name, detected)
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
    # Verify JSON structure contains tool information (healthy environment should have all tools found)
    assert len(data["tools"]) > 0
    assert all("name" in tool and "found" in tool for tool in data["tools"])


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
    # CI environment detection failure should not cause overall failure
    # The CLI should gracefully handle this and continue with other validations
    assert code == 0  # Should still succeed with other validations
    # But should indicate the CI detection issue in output or logs
    # Note: The warning is logged, not displayed in human-readable output


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
        settings=None,  # Don't inject settings so the loader gets called
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
        (["poetry"], ["Install poetry:"]),  # poetry is in the CLI's common_tools list
        (["mypy", "ruff"], ["Install mypy:", "Install ruff:"]),
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

    # Create a custom check_tool function that simulates the specific missing tools
    def check_tool_with_specific_missing(tool_name):
        if tool_name in missing_tools:
            return {"name": tool_name, "found": False, "path": None, "version": None}
        else:
            return {
                "name": tool_name,
                "found": True,
                "path": f"/usr/bin/{tool_name}",
                "version": "1.0.0",
            }

    code, out, err = run_cli(
        [],
        ci_detector=mock_ci_detector_instance,
        security_manager=mock_security_manager_instance,
        settings=mock_settings_instance,
        settings_loader=mock_settings_loader_callable,
        check_tool_mock=check_tool_with_specific_missing,
    )
    assert code == 1  # Warning status due to missing tools
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
    # Focus on tools that the CLI actually checks
    missing_tools_list = ["pixi", "poetry", "mypy", "ruff"]
    env_result.missing_tools = missing_tools_list
    env_result.install_commands = {
        tool: f"pixi add {tool}" for tool in missing_tools_list
    }

    mock_ci_detector_instance.get_detection_result.return_value = env_result

    # Create a custom check_tool function that makes most tools missing
    def check_tool_all_missing(tool_name):
        # Keep critical tools (python, pip) to avoid critical status
        if tool_name in ["python", "pip", "git", "pytest"]:
            return {
                "name": tool_name,
                "found": True,
                "path": f"/usr/bin/{tool_name}",
                "version": "1.0.0",
            }
        else:
            return {"name": tool_name, "found": False, "path": None, "version": None}

    code, out, err = run_cli(
        [],
        ci_detector=mock_ci_detector_instance,
        security_manager=mock_security_manager_instance,
        settings=mock_settings_instance,
        settings_loader=mock_settings_loader_callable,
        check_tool_mock=check_tool_all_missing,
    )
    assert code == 1  # Warning status due to missing tools
    assert "Suggestions:" in out
    # Check for install suggestions for the missing tools
    assert "Install pixi:" in out
    assert "Install poetry:" in out
    assert "Install mypy:" in out
    assert "Install ruff:" in out


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
