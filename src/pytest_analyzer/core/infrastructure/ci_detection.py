"""
CI Environment Detection Module

Detects CI environment and available tools for intelligent test execution.
"""

import logging
import os
import shutil
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger("pytest_analyzer.ci_detection")
logger.addHandler(logging.NullHandler())

# --- New Dataclasses ---


@dataclass(frozen=True)
class CIPlatform:
    name: str
    detected: bool
    raw_env: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolInfo:
    name: str
    found: bool
    path: Optional[str] = None
    version: Optional[str] = None


@dataclass(frozen=True)
class DetectionResult:
    platform: CIPlatform
    available_tools: List[ToolInfo]
    missing_tools: List[str]
    install_commands: Dict[str, str]


# --- Backward compatibility dataclass ---


@dataclass
class CIEnvironment:
    name: str
    detected: bool
    available_tools: List[str]
    missing_tools: List[str]
    tool_install_commands: Dict[str, str]


# --- Enhanced CIEnvironmentDetector ---


class CIEnvironmentDetector:
    """Detect CI environment and available tools (enhanced)"""

    _cache_lock = threading.Lock()
    _cache: Optional[DetectionResult] = None

    # --- Platform detection ---

    def detect_ci_platform(self) -> CIPlatform:
        """Detect which CI platform we're running on and return CIPlatform"""
        ci_indicators = {
            "github": "GITHUB_ACTIONS",
            "gitlab": "GITLAB_CI",
            "jenkins": "JENKINS_URL",
            "circleci": "CIRCLECI",
            "travis": "TRAVIS",
            "azure": "AZURE_PIPELINES",
        }
        env = {k: v for k, v in os.environ.items()}
        for provider, env_var in ci_indicators.items():
            if os.getenv(env_var):
                logger.info(f"Detected CI platform: {provider}")
                return CIPlatform(name=provider, detected=True, raw_env=env)
        logger.info("No CI platform detected, assuming local")
        return CIPlatform(name="local", detected=False, raw_env=env)

    # --- Tool scanning ---

    def scan_available_tools(self) -> List[ToolInfo]:
        """Scan for available security and development tools, with version info"""
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
        found_tools: List[ToolInfo] = []
        for tool in tools_to_check:
            path = self._find_tool(tool)
            found = path is not None
            version = self._get_tool_version(tool, path) if found else None
            found_tools.append(
                ToolInfo(name=tool, found=found, path=path, version=version)
            )
        return found_tools

    def _find_tool(self, tool: str) -> Optional[str]:
        """Find tool in PATH or pixi env, return path or None"""
        try:
            path = shutil.which(tool)
            if path:
                return path
            # Check pixi env
            pixi_env_path = Path(".pixi/env/bin") / tool
            if pixi_env_path.exists():
                return str(pixi_env_path.resolve())
        except Exception as e:
            logger.error(f"Error finding tool {tool}: {e}")
        return None

    def _get_tool_version(self, tool: str, path: Optional[str]) -> Optional[str]:
        """Try to get the version of a tool by running '<tool> --version'"""
        if not path:
            return None
        import subprocess

        try:
            # Some tools print version to stderr, some to stdout
            result = subprocess.run(
                [path, "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=2,
            )
            output = result.stdout.strip() or result.stderr.strip()
            # Try to extract version number
            import re

            match = re.search(r"(\d+\.\d+\.\d+)", output)
            if match:
                return match.group(1)
            return output.split()[-1] if output else None
        except Exception as e:
            logger.warning(f"Could not get version for {tool}: {e}")
            return None

    # --- Missing tools ---

    def get_missing_tools(
        self, required_tools: List[str], available_tools: List[ToolInfo]
    ) -> List[str]:
        """Return list of required tools not found in available_tools"""
        available_names = {t.name for t in available_tools if t.found}
        return [tool for tool in required_tools if tool not in available_names]

    # --- Install commands ---

    def generate_install_commands(
        self, platform: CIPlatform, missing_tools: List[str]
    ) -> Dict[str, str]:
        """Get tool installation commands for specific CI platforms"""
        commands = {
            "github": {
                "bandit": "pip install bandit",
                "safety": "pip install safety",
                "mypy": "pip install mypy",
                "ruff": "pip install ruff",
            },
            "local": {
                "bandit": "pixi add bandit",
                "safety": "pixi add safety",
                "mypy": "pixi add mypy",
                "ruff": "pixi add ruff",
            },
        }
        platform_cmds = commands.get(platform.name, commands["local"])
        return {
            tool: platform_cmds.get(tool, f"pip install {tool}")
            for tool in missing_tools
        }

    # --- Caching ---

    def get_detection_result(self) -> DetectionResult:
        """Get full detection result, using cache if available"""
        with self._cache_lock:
            if self._cache is not None:
                logger.debug("Using cached DetectionResult")
                return self._cache
            try:
                platform = self.detect_ci_platform()
                available_tools = self.scan_available_tools()
                required_tools = ["bandit", "safety", "mypy", "ruff"]
                missing_tools = self.get_missing_tools(required_tools, available_tools)
                install_commands = self.generate_install_commands(
                    platform, missing_tools
                )
                result = DetectionResult(
                    platform=platform,
                    available_tools=available_tools,
                    missing_tools=missing_tools,
                    install_commands=install_commands,
                )
                self._cache = result
                logger.info("DetectionResult cached")
                return result
            except Exception as e:
                logger.error(f"Error during detection: {e}")
                raise

    def clear_cache(self):
        """Clear the detection result cache"""
        with self._cache_lock:
            self._cache = None
            logger.info("DetectionResult cache cleared")

    # --- Backward compatibility ---

    def detect_environment(self) -> CIEnvironment:
        """
        Backward compatible: Detect current CI environment and tool availability.
        """
        result = self.get_detection_result()
        return CIEnvironment(
            name=result.platform.name,
            detected=result.platform.detected,
            available_tools=[t.name for t in result.available_tools if t.found],
            missing_tools=result.missing_tools,
            tool_install_commands=result.install_commands,
        )

    # --- Legacy methods for compatibility ---

    def _detect_ci_provider(self) -> str:
        """Legacy: Detect which CI provider we're running on (returns str)"""
        return self.detect_ci_platform().name

    def _scan_available_tools(self) -> List[str]:
        """Legacy: Scan for available tools (returns list of names)"""
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

    def _identify_missing_tools(self, available: List[str]) -> List[str]:
        """Legacy: Identify missing tools (from list of names)"""
        required_tools = ["bandit", "safety", "mypy", "ruff"]
        return [tool for tool in required_tools if tool not in available]

    def _get_install_commands(self, ci_provider: str) -> Dict[str, str]:
        """Legacy: Get install commands for provider (from str)"""
        platform = CIPlatform(name=ci_provider, detected=(ci_provider != "local"))
        # For legacy compatibility, assume all standard required tools are missing
        # to ensure comprehensive install commands are returned for the platform.
        # This bypasses the actual scan for the purpose of generating commands.
        required_tools_for_commands = ["bandit", "safety", "mypy", "ruff"]
        return self.generate_install_commands(platform, required_tools_for_commands)

    def _check_pixi_tool(self, tool: str) -> bool:
        """Legacy: Check if tool is available in pixi environment"""
        pixi_env_path = Path(".pixi/env/bin") / tool
        return pixi_env_path.exists()


# --- CLI for manual testing ---


def main():
    """Command line interface for CI detection"""
    logging.basicConfig(level=logging.INFO)
    detector = CIEnvironmentDetector()
    result = detector.get_detection_result()
    print(f"CI Environment: {result.platform.name}")
    print(f"CI Detected: {result.platform.detected}")
    print("Available Tools:")
    for tool in result.available_tools:
        status = "FOUND" if tool.found else "MISSING"
        version = f" (v{tool.version})" if tool.version else ""
        print(f"  {tool.name}: {status}{version}")
    if result.missing_tools:
        print(f"Missing Tools: {', '.join(result.missing_tools)}")
        print("Install commands:")
        for tool in result.missing_tools:
            if tool in result.install_commands:
                print(f"  {tool}: {result.install_commands[tool]}")


if __name__ == "__main__":
    main()
