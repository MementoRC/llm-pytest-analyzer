"""
CI Environment Detection Module

Detects CI environment and available tools for intelligent test execution.
"""

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List


@dataclass
class CIEnvironment:
    name: str
    detected: bool
    available_tools: List[str]
    missing_tools: List[str]
    tool_install_commands: Dict[str, str]


class CIEnvironmentDetector:
    """Detect CI environment and available tools"""

    def detect_environment(self) -> CIEnvironment:
        """Detect current CI environment and tool availability"""
        ci_name = self._detect_ci_provider()
        available_tools = self._scan_available_tools()
        missing_tools = self._identify_missing_tools(available_tools)
        install_commands = self._get_install_commands(ci_name)

        return CIEnvironment(
            name=ci_name,
            detected=ci_name != "local",
            available_tools=available_tools,
            missing_tools=missing_tools,
            tool_install_commands=install_commands,
        )

    def _detect_ci_provider(self) -> str:
        """Detect which CI provider we're running on"""
        ci_indicators = {
            "github": "GITHUB_ACTIONS",
            "gitlab": "GITLAB_CI",
            "jenkins": "JENKINS_URL",
            "circleci": "CIRCLECI",
            "travis": "TRAVIS",
            "azure": "AZURE_PIPELINES",
        }

        for provider, env_var in ci_indicators.items():
            if os.getenv(env_var):
                return provider
        return "local"

    def _scan_available_tools(self) -> List[str]:
        """Scan for available security and development tools"""
        tools_to_check = [
            "bandit",
            "safety",
            "mypy",
            "ruff",
            "black",
            "pytest",
            "coverage",
            "pre-commit",
        ]

        available = []
        for tool in tools_to_check:
            if shutil.which(tool) or self._check_pixi_tool(tool):
                available.append(tool)

        return available

    def _check_pixi_tool(self, tool: str) -> bool:
        """Check if tool is available in pixi environment"""
        pixi_env_path = Path(".pixi/env/bin") / tool
        return pixi_env_path.exists()

    def _identify_missing_tools(self, available: List[str]) -> List[str]:
        """Identify commonly needed tools that are missing"""
        required_tools = ["bandit", "safety", "mypy", "ruff"]
        return [tool for tool in required_tools if tool not in available]

    def _get_install_commands(self, ci_provider: str) -> Dict[str, str]:
        """Get tool installation commands for specific CI providers"""
        commands = {
            "github": {
                "bandit": "pip install bandit",
                "safety": "pip install safety",
                "mypy": "pip install mypy",
            },
            "local": {
                "bandit": "pixi add bandit",
                "safety": "pixi add safety",
                "mypy": "pixi add mypy",
            },
        }
        return commands.get(ci_provider, commands["local"])


def main():
    """Command line interface for CI detection"""
    detector = CIEnvironmentDetector()
    env = detector.detect_environment()

    print(f"CI Environment: {env.name}")
    print(f"CI Detected: {env.detected}")
    print(f"Available Tools: {', '.join(env.available_tools)}")
    if env.missing_tools:
        print(f"Missing Tools: {', '.join(env.missing_tools)}")
        print("Install commands:")
        for tool in env.missing_tools:
            if tool in env.tool_install_commands:
                print(f"  {tool}: {env.tool_install_commands[tool]}")


if __name__ == "__main__":
    main()
