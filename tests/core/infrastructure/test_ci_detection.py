"""
Tests for CI Environment Detection
"""

import os
from unittest.mock import patch

from pytest_analyzer.core.infrastructure.ci_detection import (
    CIEnvironment,
    CIEnvironmentDetector,
)


class TestCIEnvironmentDetector:
    """Test CI environment detection functionality"""

    def test_detect_local_environment(self):
        """Test detection of local development environment"""
        detector = CIEnvironmentDetector()
        env = detector.detect_environment()

        assert isinstance(env, CIEnvironment)
        assert env.name in [
            "local",
            "github",
            "gitlab",
            "jenkins",
            "circleci",
            "travis",
            "azure",
        ]
        assert isinstance(env.detected, bool)
        assert isinstance(env.available_tools, list)
        assert isinstance(env.missing_tools, list)
        assert isinstance(env.tool_install_commands, dict)

    @patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}, clear=True)
    def test_detect_github_actions(self):
        """Test detection of GitHub Actions environment"""
        detector = CIEnvironmentDetector()
        env = detector.detect_environment()

        assert env.name == "github"
        assert env.detected is True

    @patch.dict(os.environ, {"GITLAB_CI": "true", "GITHUB_ACTIONS": ""}, clear=True)
    def test_detect_gitlab_ci(self):
        """Test detection of GitLab CI environment"""
        detector = CIEnvironmentDetector()
        env = detector.detect_environment()

        assert env.name == "gitlab"
        assert env.detected is True

    @patch("shutil.which")
    def test_scan_available_tools(self, mock_which):
        """Test scanning for available tools"""
        # Mock some tools as available
        mock_which.side_effect = lambda tool: tool in ["pytest", "ruff"]

        detector = CIEnvironmentDetector()
        available = detector._scan_available_tools()

        assert "pytest" in available
        assert "ruff" in available
        assert "bandit" not in available  # Not mocked as available

    def test_identify_missing_tools(self):
        """Test identification of missing tools"""
        detector = CIEnvironmentDetector()
        available = ["pytest", "ruff"]
        missing = detector._identify_missing_tools(available)

        assert "bandit" in missing
        assert "safety" in missing
        assert "mypy" in missing
        assert "pytest" not in missing
        assert "ruff" not in missing

    def test_get_install_commands_github(self):
        """Test install commands for GitHub Actions"""
        detector = CIEnvironmentDetector()
        commands = detector._get_install_commands("github")

        assert "bandit" in commands
        assert "pip install bandit" in commands["bandit"]

    def test_get_install_commands_local(self):
        """Test install commands for local environment"""
        detector = CIEnvironmentDetector()
        commands = detector._get_install_commands("local")

        assert "bandit" in commands
        assert "pixi add bandit" in commands["bandit"]

    @patch("pathlib.Path.exists")
    def test_check_pixi_tool(self, mock_exists):
        """Test checking for tools in pixi environment"""
        mock_exists.return_value = True

        detector = CIEnvironmentDetector()
        assert detector._check_pixi_tool("bandit") is True

        mock_exists.return_value = False
        assert detector._check_pixi_tool("missing_tool") is False
