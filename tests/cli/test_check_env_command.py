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
from unittest.mock import MagicMock, patch

import pytest

# Assume the CLI command is in pytest_analyzer.cli.check_env_command
# and the main entrypoint is main()
# The CIEnvironmentDetector is in pytest_analyzer.core.infrastructure.ci_detection


@pytest.fixture
def mock_env_detector():
    """Fixture to patch CIEnvironmentDetector for all tests."""
    with patch("pytest_analyzer.cli.check_env.CIEnvironmentDetector") as mock_cls:
        yield mock_cls


@pytest.fixture
def mock_security_manager():
    """Fixture to patch SecurityManager if used by the CLI."""
    with patch("pytest_analyzer.cli.check_env.SecurityManager") as mock_cls:
        yield mock_cls


@pytest.fixture
def mock_settings():
    """Fixture to patch Settings if used by the CLI."""
    with patch("pytest_analyzer.cli.check_env.Settings") as mock_cls:
        yield mock_cls


@pytest.fixture
def cli_main():
    """Import the CLI main function for invocation."""
    from pytest_analyzer.cli.check_env import main

    return main


@pytest.fixture
def run_cli(monkeypatch, cli_main):
    """Helper to run the CLI with args and capture output."""

    def _run(args, env_detector=None, security_manager=None, settings=None):
        # Patch sys.argv
        monkeypatch.setattr(sys, "argv", ["pytest-analyzer-check-env"] + args)
        # Patch detector if provided
        if env_detector:
            patcher = patch(
                "pytest_analyzer.cli.check_env.CIEnvironmentDetector",
                return_value=env_detector,
            )
            patcher.start()
        if security_manager:
            patcher2 = patch(
                "pytest_analyzer.cli.check_env.SecurityManager",
                return_value=security_manager,
            )
            patcher2.start()
        if settings:
            patcher3 = patch(
                "pytest_analyzer.cli.check_env.Settings", return_value=settings
            )
            patcher3.start()
        # Capture stdout/stderr
        import contextlib
        from io import StringIO

        out = StringIO()
        err = StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = cli_main()
            except SystemExit as e:
                code = e.code
        return code, out.getvalue(), err.getvalue()

    return _run


@pytest.fixture
def sample_env_result():
    """Return a sample DetectionResult-like object."""

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

    return MagicMock(
        platform=DummyPlatform(),
        available_tools=[
            DummyTool("bandit", True, "1.7.5"),
            DummyTool("safety", False),
            DummyTool("mypy", True, "1.2.3"),
            DummyTool("ruff", False),
        ],
        missing_tools=["safety", "ruff"],
        install_commands={"safety": "pip install safety", "ruff": "pip install ruff"},
    )


@pytest.mark.parametrize(
    "args,expected_json,expected_human",
    [
        ([], False, True),
        (["--json"], True, False),
        (["-j"], True, False),
    ],
)
def test_cli_argument_parsing(
    run_cli, sample_env_result, args, expected_json, expected_human
):
    """Test CLI argument parsing for output format options."""
    env_detector = MagicMock()
    env_detector.get_detection_result.return_value = sample_env_result
    code, out, err = run_cli(args, env_detector=env_detector)
    assert code == 0
    if expected_json:
        # Should be valid JSON
        data = json.loads(out)
        assert "platform" in data
        assert data["platform"]["name"] == "github"
        assert "missing_tools" in data
    if expected_human:
        # Should contain human-readable summary
        assert "CI Environment:" in out
        assert "github" in out
        assert "Missing Tools" in out or "missing tools" in out


def test_cli_detects_missing_tools_and_suggests_install(run_cli, sample_env_result):
    """Test that missing tools are reported and install suggestions are shown."""
    env_detector = MagicMock()
    env_detector.get_detection_result.return_value = sample_env_result
    code, out, err = run_cli([], env_detector=env_detector)
    assert code == 0
    assert "Missing Tools" in out
    assert "safety" in out and "ruff" in out
    assert "pip install safety" in out
    assert "pip install ruff" in out


def test_cli_all_tools_present(run_cli):
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

    env_result = MagicMock(
        platform=DummyPlatform(),
        available_tools=[
            DummyTool("bandit", True, "1.7.5"),
            DummyTool("safety", True, "2.0.0"),
            DummyTool("mypy", True, "1.2.3"),
            DummyTool("ruff", True, "0.3.0"),
        ],
        missing_tools=[],
        install_commands={},
    )
    env_detector = MagicMock()
    env_detector.get_detection_result.return_value = env_result
    code, out, err = run_cli([], env_detector=env_detector)
    assert code == 0
    assert "All required tools are available" in out or "No missing tools" in out


@pytest.mark.parametrize(
    "platform_name,detected,expected",
    [
        ("github", True, "GitHub Actions"),
        ("gitlab", True, "GitLab CI"),
        ("jenkins", True, "Jenkins"),
        ("circleci", True, "CircleCI"),
        ("travis", True, "Travis"),
        ("azure", True, "Azure Pipelines"),
        ("local", False, "Local"),
    ],
)
def test_cli_platform_detection(run_cli, platform_name, detected, expected):
    """Test detection and reporting of various CI platforms."""

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

    env_result = MagicMock(
        platform=DummyPlatform(),
        available_tools=[DummyTool("bandit", True)],
        missing_tools=[],
        install_commands={},
    )
    env_detector = MagicMock()
    env_detector.get_detection_result.return_value = env_result
    code, out, err = run_cli([], env_detector=env_detector)
    assert code == 0
    assert expected.lower() in out.lower() or platform_name in out.lower()


def test_cli_json_output(run_cli, sample_env_result):
    """Test JSON output format."""
    env_detector = MagicMock()
    env_detector.get_detection_result.return_value = sample_env_result
    code, out, err = run_cli(["--json"], env_detector=env_detector)
    assert code == 0
    data = json.loads(out)
    assert data["platform"]["name"] == "github"
    assert "missing_tools" in data
    assert "install_commands" in data


def test_cli_error_handling_env_unavailable(run_cli):
    """Test error handling when environment info is unavailable."""
    env_detector = MagicMock()
    env_detector.get_detection_result.side_effect = Exception("Env unavailable")
    code, out, err = run_cli([], env_detector=env_detector)
    assert code != 0
    assert (
        "error" in out.lower()
        or "unavailable" in out.lower()
        or "exception" in out.lower()
    )


def test_cli_handles_security_manager(
    run_cli, sample_env_result, mock_security_manager
):
    """Test integration with SecurityManager if used."""
    env_detector = MagicMock()
    env_detector.get_detection_result.return_value = sample_env_result
    sec_manager = MagicMock()
    code, out, err = run_cli(
        [], env_detector=env_detector, security_manager=sec_manager
    )
    assert code == 0
    # If SecurityManager is used, check it was called
    if hasattr(sec_manager, "check_permissions"):
        sec_manager.check_permissions.assert_called()


def test_cli_handles_settings(run_cli, sample_env_result, mock_settings):
    """Test integration with Settings if used."""
    env_detector = MagicMock()
    env_detector.get_detection_result.return_value = sample_env_result
    settings = MagicMock()
    code, out, err = run_cli([], env_detector=env_detector, settings=settings)
    assert code == 0
    # If Settings is used, check it was accessed
    if hasattr(settings, "validate"):
        settings.validate.assert_called()


@pytest.mark.parametrize(
    "missing_tools,expected_suggestion",
    [
        (["bandit"], "pip install bandit"),
        (["mypy", "ruff"], "pip install mypy"),
    ],
)
def test_cli_suggestion_accuracy(run_cli, missing_tools, expected_suggestion):
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
    env_result = MagicMock(
        platform=DummyPlatform(),
        available_tools=tools,
        missing_tools=missing_tools,
        install_commands={t: f"pip install {t}" for t in missing_tools},
    )
    env_detector = MagicMock()
    env_detector.get_detection_result.return_value = env_result
    code, out, err = run_cli([], env_detector=env_detector)
    assert code == 0
    for t in missing_tools:
        assert f"pip install {t}" in out


def test_cli_edge_case_no_tools(run_cli):
    """Test edge case where no tools are found at all."""

    class DummyPlatform:
        name = "local"
        detected = False
        raw_env = {}

    env_result = MagicMock(
        platform=DummyPlatform(),
        available_tools=[],
        missing_tools=["bandit", "safety", "mypy", "ruff"],
        install_commands={
            "bandit": "pixi add bandit",
            "safety": "pixi add safety",
            "mypy": "pixi add mypy",
            "ruff": "pixi add ruff",
        },
    )
    env_detector = MagicMock()
    env_detector.get_detection_result.return_value = env_result
    code, out, err = run_cli([], env_detector=env_detector)
    assert code == 0
    assert "Missing Tools" in out
    assert "pixi add bandit" in out


def test_cli_multiple_argument_combinations(run_cli, sample_env_result):
    """Test CLI with multiple argument combinations."""
    env_detector = MagicMock()
    env_detector.get_detection_result.return_value = sample_env_result
    # --json and -j should both work
    for arg in [["--json"], ["-j"]]:
        code, out, err = run_cli(arg, env_detector=env_detector)
        assert code == 0
        data = json.loads(out)
        assert "platform" in data


def test_cli_help(monkeypatch):
    """Test that --help prints usage and exits."""
    from pytest_analyzer.cli import check_env

    monkeypatch.setattr(sys, "argv", ["pytest-analyzer-check-env", "--help"])
    with pytest.raises(SystemExit) as excinfo:
        check_env.main()
    assert excinfo.value.code == 0
