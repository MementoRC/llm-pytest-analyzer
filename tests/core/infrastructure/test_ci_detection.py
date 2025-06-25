"""
Tests for CI Environment Detection
"""

import os
from unittest.mock import patch

from pytest_analyzer.core.infrastructure.ci_detection import (
    CIEnvironment,
    CIEnvironmentDetector,
    CIPlatform,
    DetectionResult,
    ToolInfo,
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

    @patch.dict(os.environ, {"GITHUB_ACTIONS": "true"})
    def test_detect_github_actions(self):
        """Test detection of GitHub Actions environment"""
        detector = CIEnvironmentDetector()
        env = detector.detect_environment()

        assert env.name == "github"
        assert env.detected is True

    @patch.dict(os.environ, {"GITLAB_CI": "true", "GITHUB_ACTIONS": ""})
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


class TestEnhancedCIEnvironmentDetector:
    """Test enhanced CI environment detection functionality"""

    def test_ci_platform_dataclass(self):
        """Test CIPlatform dataclass"""
        platform = CIPlatform(name="github", detected=True)
        assert platform.name == "github"
        assert platform.detected is True
        assert isinstance(platform.raw_env, dict)

    def test_tool_info_dataclass(self):
        """Test ToolInfo dataclass"""
        tool = ToolInfo(
            name="pytest", found=True, path="/usr/bin/pytest", version="7.4.0"
        )
        assert tool.name == "pytest"
        assert tool.found is True
        assert tool.path == "/usr/bin/pytest"
        assert tool.version == "7.4.0"

    def test_detection_result_dataclass(self):
        """Test DetectionResult dataclass"""
        platform = CIPlatform(name="github", detected=True)
        tool = ToolInfo(name="pytest", found=True)
        result = DetectionResult(
            platform=platform,
            available_tools=[tool],
            missing_tools=["bandit"],
            install_commands={"bandit": "pip install bandit"},
        )
        assert result.platform == platform
        assert len(result.available_tools) == 1
        assert result.missing_tools == ["bandit"]
        assert "bandit" in result.install_commands

    @patch.dict(os.environ, {"GITHUB_ACTIONS": "true"})
    def test_detect_ci_platform_enhanced(self):
        """Test enhanced detect_ci_platform method"""
        detector = CIEnvironmentDetector()
        platform = detector.detect_ci_platform()

        assert isinstance(platform, CIPlatform)
        assert platform.name == "github"
        assert platform.detected is True
        assert isinstance(platform.raw_env, dict)

    @patch("shutil.which")
    def test_scan_available_tools_enhanced(self, mock_which):
        """Test enhanced scan_available_tools method"""
        mock_which.side_effect = (
            lambda tool: "/usr/bin/" + tool if tool in ["pytest", "ruff"] else None
        )

        detector = CIEnvironmentDetector()
        tools = detector.scan_available_tools()

        assert isinstance(tools, list)
        assert all(isinstance(tool, ToolInfo) for tool in tools)

        pytest_tools = [t for t in tools if t.name == "pytest"]
        assert len(pytest_tools) == 1
        assert pytest_tools[0].found is True
        assert pytest_tools[0].path == "/usr/bin/pytest"

    def test_get_missing_tools_enhanced(self):
        """Test enhanced get_missing_tools method"""
        detector = CIEnvironmentDetector()
        available_tools = [
            ToolInfo(name="pytest", found=True),
            ToolInfo(name="ruff", found=True),
            ToolInfo(name="bandit", found=False),
        ]
        required_tools = ["pytest", "ruff", "bandit", "mypy"]

        missing = detector.get_missing_tools(required_tools, available_tools)
        assert "bandit" in missing
        assert "mypy" in missing
        assert "pytest" not in missing
        assert "ruff" not in missing

    def test_generate_install_commands_enhanced(self):
        """Test enhanced generate_install_commands method"""
        detector = CIEnvironmentDetector()
        platform = CIPlatform(name="github", detected=True)
        missing_tools = ["bandit", "mypy"]

        commands = detector.generate_install_commands(platform, missing_tools)
        assert isinstance(commands, dict)
        assert "bandit" in commands
        assert "mypy" in commands
        assert "pip install bandit" in commands["bandit"]

    def test_get_detection_result(self):
        """Test get_detection_result method"""
        detector = CIEnvironmentDetector()
        detector.clear_cache()  # Ensure fresh result

        result = detector.get_detection_result()
        assert isinstance(result, DetectionResult)
        assert isinstance(result.platform, CIPlatform)
        assert isinstance(result.available_tools, list)
        assert isinstance(result.missing_tools, list)
        assert isinstance(result.install_commands, dict)

    def test_caching_mechanism(self):
        """Test caching mechanism"""
        detector = CIEnvironmentDetector()
        detector.clear_cache()

        # First call should populate cache
        result1 = detector.get_detection_result()

        # Second call should use cache (same object)
        result2 = detector.get_detection_result()
        assert result1 is result2

    def test_clear_cache(self):
        """Test cache clearing"""
        detector = CIEnvironmentDetector()
        detector.get_detection_result()  # Populate cache
        detector.clear_cache()

        # Should get new result after cache clear
        result = detector.get_detection_result()
        assert isinstance(result, DetectionResult)
