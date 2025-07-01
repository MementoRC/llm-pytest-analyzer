#!/usr/bin/env python3

"""
Check Environment CLI Command

Provides environment validation and analysis for pytest-analyzer.
"""

import argparse
import json
import logging
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..core.infrastructure.ci_detection import CIEnvironmentDetector
from ..mcp.security import SecurityError, SecurityManager
from ..utils.settings import Settings, load_settings

# Create logger
logger = logging.getLogger("pytest_analyzer.check_env")

# Setup rich console
console = Console()


class CheckEnvironmentCommand:
    """Command to check and validate the development environment."""

    def __init__(
        self,
        ci_detector: Optional[CIEnvironmentDetector] = None,
        security_manager: Optional[SecurityManager] = None,
        settings: Optional[Settings] = None,
        settings_loader: Optional[Callable[[Optional[str]], Settings]] = None,
    ):
        """Initialize the command with required components."""
        self.ci_detector = ci_detector or CIEnvironmentDetector()
        self.security_manager = (
            security_manager  # Initialize later with settings if None
        )
        self._initial_settings = settings
        self._settings_loader = settings_loader or load_settings

    def parse_arguments(self) -> argparse.Namespace:
        """Parse command line arguments for the check-env command."""
        parser = argparse.ArgumentParser(
            prog="pytest-analyzer check-env",
            description="""
Check and validate the development environment for Python, tools, and CI compatibility.

[bold]Examples:[/bold]
  pytest-analyzer check-env
  pytest-analyzer check-env --json
  pytest-analyzer check-env --output-file env_report.txt
""",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )

        # Output format options
        output_group = parser.add_argument_group("Output Options")
        output_group.add_argument(
            "--json",
            action="store_true",
            help="Output results in JSON format",
        )
        output_group.add_argument(
            "--output-file",
            type=str,
            help="Save report to specified file",
        )
        output_group.add_argument(
            "--verbose",
            "-v",
            action="store_true",
            help="Enable verbose output",
        )

        # Configuration options
        config_group = parser.add_argument_group("Configuration")
        config_group.add_argument(
            "--config-file",
            type=str,
            help="Path to configuration file",
        )
        config_group.add_argument(
            "--project-root",
            type=str,
            help="Root directory of the project (auto-detected if not specified)",
        )

        # Validation options
        validation_group = parser.add_argument_group("Validation Options")
        validation_group.add_argument(
            "--skip-ci-checks",
            action="store_true",
            help="Skip CI-specific environment checks",
        )
        validation_group.add_argument(
            "--skip-tool-checks",
            action="store_true",
            help="Skip tool availability checks",
        )

        return parser.parse_args()

    def execute(self, args: Optional[argparse.Namespace] = None) -> int:
        """Execute the environment check command."""
        if args is None:
            args = self.parse_arguments()

        try:
            # Load settings (use injected settings if available)
            settings = self._initial_settings or self._load_settings(args.config_file)

            # Initialize security manager with settings (if not already injected)
            if self.security_manager is None and hasattr(settings, "security"):
                from ..utils.config_types import SecuritySettings

                security_settings = getattr(settings, "security", SecuritySettings())
                self.security_manager = SecurityManager(security_settings)

            # Set up logging based on verbosity
            if args.verbose:
                logging.getLogger("pytest_analyzer").setLevel(logging.DEBUG)

            # Validate environment
            validation_result = self.validate_environment(args, settings)

            # Generate and display report
            report = self.generate_report(validation_result, args.json)

            # Output report
            if args.output_file:
                self._save_report(report, args.output_file, args.json)
                console.print(f"✅ Report saved to: {args.output_file}")
            else:
                self._display_report(report, args.json)

            # Return appropriate exit code
            return self._determine_exit_code(validation_result)

        except SecurityError as e:
            console.print(f"❌ Security error: {e}", style="red")
            return 1
        except Exception as e:
            console.print(f"❌ Unexpected error: {e}", style="red")
            logger.exception("Unexpected error during environment check")
            return 1

    def validate_environment(
        self, args: argparse.Namespace, settings: Settings
    ) -> Dict[str, Any]:
        """Perform comprehensive environment validation."""
        logger.info("Starting environment validation")

        validation_result = {
            "timestamp": str(self._get_timestamp()),
            "platform": self._validate_platform(),
            "python": self._validate_python(),
            "ci_environment": None,
            "tools": [],
            "packages": [],
            "suggestions": [],
            "overall_status": "unknown",
        }

        # CI Environment Detection
        if not args.skip_ci_checks:
            validation_result["ci_environment"] = self._validate_ci_environment()

        # Tool availability checks
        if not args.skip_tool_checks:
            tool_result = self._validate_tools()
            validation_result["tools"] = tool_result["tools"]
            validation_result["suggestions"].extend(tool_result["suggestions"])

        # Package validation
        validation_result["packages"] = self._validate_packages()

        # Determine overall status
        validation_result["overall_status"] = self._determine_overall_status(
            validation_result
        )

        logger.info(
            f"Environment validation completed with status: {validation_result['overall_status']}"
        )
        return validation_result

    def generate_report(
        self, validation_result: Dict[str, Any], json_format: bool = False
    ) -> Dict[str, Any]:
        """Generate a detailed report of the environment validation."""
        if json_format:
            return validation_result

        # For human-readable format, enhance with formatting information
        report = validation_result.copy()
        report["_format"] = "human_readable"
        return report

    def _load_settings(self, config_file: Optional[str]) -> Settings:
        """Load settings from configuration file."""
        try:
            return self._settings_loader(config_file)
        except Exception as e:
            logger.warning(f"Failed to load settings: {e}")
            return Settings()

    def _validate_platform(self) -> Dict[str, Any]:
        """Validate platform information."""
        return {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
        }

    def _validate_python(self) -> Dict[str, Any]:
        """Validate Python environment."""
        return {
            "version": sys.version,
            "executable": sys.executable,
            "path": sys.path[:5],  # First 5 entries
            "major": sys.version_info.major,
            "minor": sys.version_info.minor,
            "micro": sys.version_info.micro,
        }

    def _validate_ci_environment(self) -> Optional[Dict[str, Any]]:
        """Validate CI environment using the detector."""
        try:
            detection_result = self.ci_detector.get_detection_result()
            return {
                "platform": {
                    "name": detection_result.platform.name,
                    "detected": detection_result.platform.detected,
                    "environment_vars": dict(detection_result.platform.raw_env),
                },
                "available_tools": [
                    {
                        "name": tool.name,
                        "found": tool.found,
                        "path": tool.path,
                        "version": tool.version,
                    }
                    for tool in detection_result.available_tools
                ],
                "missing_tools": detection_result.missing_tools,
                "install_commands": detection_result.install_commands,
            }
        except Exception as e:
            logger.warning(f"CI environment detection failed: {e}")
            return None

    def _validate_tools(self) -> Dict[str, Any]:
        """Validate development tools availability."""
        common_tools = [
            "git",
            "python",
            "pip",
            "pytest",
            "pixi",
            "poetry",
            "ruff",
            "mypy",
        ]
        tools = []
        suggestions = []

        for tool_name in common_tools:
            tool_info = self._check_tool(tool_name)
            tools.append(tool_info)

            if not tool_info["found"]:
                suggestions.append(
                    f"Install {tool_name}: {self._get_install_command(tool_name)}"
                )

        return {"tools": tools, "suggestions": suggestions}

    def _check_tool(self, tool_name: str) -> Dict[str, Any]:
        """Check if a specific tool is available."""
        try:
            result = subprocess.run(
                [tool_name, "--version"], capture_output=True, text=True, timeout=5
            )

            if result.returncode == 0:
                return {
                    "name": tool_name,
                    "found": True,
                    "path": subprocess.run(
                        ["which", tool_name], capture_output=True, text=True
                    ).stdout.strip(),
                    "version": result.stdout.strip().split("\n")[0],
                }
        except (
            subprocess.TimeoutExpired,
            FileNotFoundError,
            subprocess.SubprocessError,
        ):
            pass

        return {"name": tool_name, "found": False, "path": None, "version": None}

    def _get_install_command(self, tool_name: str) -> str:
        """Get installation command for a tool."""
        install_commands = {
            "git": "apt-get install git",
            "pip": "python -m ensurepip --upgrade",
            "pytest": "pip install pytest",
            "pixi": "curl -fsSL https://pixi.sh/install.sh | bash",
            "poetry": "curl -sSL https://install.python-poetry.org | python3 -",
            "ruff": "pip install ruff",
            "mypy": "pip install mypy",
        }
        return install_commands.get(tool_name, f"pip install {tool_name}")

    def _validate_packages(self) -> List[Dict[str, Any]]:
        """Validate installed Python packages."""
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "list", "--format=json"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                packages = json.loads(result.stdout)
                return packages[:20]  # Limit to first 20 packages
        except Exception as e:
            logger.warning(f"Failed to get package list: {e}")

        return []

    def _determine_overall_status(self, validation_result: Dict[str, Any]) -> str:
        """Determine overall validation status."""
        has_critical_issues = False
        has_warnings = False

        # Check for critical Python issues
        python_info = validation_result.get("python", {})
        if python_info.get("major", 0) < 3 or python_info.get("minor", 0) < 8:
            has_critical_issues = True

        # Check for missing critical tools
        tools = validation_result.get("tools", [])
        critical_tools = ["python", "pip"]
        for tool in tools:
            if tool["name"] in critical_tools and not tool["found"]:
                has_critical_issues = True

        # Check for warnings
        if validation_result.get("suggestions"):
            has_warnings = True

        if has_critical_issues:
            return "critical"
        elif has_warnings:
            return "warning"
        else:
            return "healthy"

    def _save_report(self, report: Dict[str, Any], output_file: str, json_format: bool):
        """Save report to file."""
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if json_format:
            with open(output_path, "w") as f:
                json.dump(report, f, indent=2)
        else:
            with open(output_path, "w") as f:
                f.write(self._format_human_readable_report(report))

    def _display_report(self, report: Dict[str, Any], json_format: bool):
        """Display report to console."""
        if json_format:
            # Use standard print for JSON to ensure compatibility with test output capture
            print(json.dumps(report, indent=2))
        else:
            self._display_human_readable_report(report)

    def _display_human_readable_report(self, report: Dict[str, Any]):
        """Display human-readable report to console."""
        # Header
        status = report.get("overall_status", "unknown")
        status_color = {
            "healthy": "green",
            "warning": "yellow",
            "critical": "red",
            "unknown": "blue",
        }.get(status, "blue")

        console.print(
            Panel(
                f"Environment Check Report - Status: [{status_color}]{status.upper()}[/{status_color}]",
                title="🔍 Pytest Analyzer Environment Check",
                border_style=status_color,
            )
        )

        # Platform Information
        platform_info = report.get("platform", {})
        platform_table = Table(title="Platform Information")
        platform_table.add_column("Property", style="cyan")
        platform_table.add_column("Value", style="white")

        for key, value in platform_info.items():
            platform_table.add_row(key.title(), str(value))

        console.print(platform_table)

        # Python Information
        python_info = report.get("python", {})
        python_table = Table(title="Python Environment")
        python_table.add_column("Property", style="cyan")
        python_table.add_column("Value", style="white")

        python_table.add_row(
            "Version", python_info.get("version", "Unknown").split()[0]
        )
        python_table.add_row("Executable", python_info.get("executable", "Unknown"))

        console.print(python_table)

        # Tools
        tools = report.get("tools", [])
        if tools:
            tools_table = Table(title="Development Tools")
            tools_table.add_column("Tool", style="cyan")
            tools_table.add_column("Status", style="white")
            tools_table.add_column("Version", style="white")

            for tool in tools:
                status_icon = "✅" if tool["found"] else "❌"
                version = tool.get("version", "N/A") if tool["found"] else "Not Found"
                tools_table.add_row(tool["name"], status_icon, version)

            console.print(tools_table)

        # Suggestions
        suggestions = report.get("suggestions", [])
        if suggestions:
            console.print("\n[yellow]💡 Suggestions:[/yellow]")
            for suggestion in suggestions:
                console.print(f"  • {suggestion}")

    def _format_human_readable_report(self, report: Dict[str, Any]) -> str:
        """Format report as human-readable text."""
        lines = ["Environment Check Report", "=" * 50, ""]

        # Add platform info
        platform_info = report.get("platform", {})
        lines.append("Platform Information:")
        for key, value in platform_info.items():
            lines.append(f"  {key.title()}: {value}")
        lines.append("")

        # Add Python info
        python_info = report.get("python", {})
        lines.append("Python Environment:")
        lines.append(f"  Version: {python_info.get('version', 'Unknown').split()[0]}")
        lines.append(f"  Executable: {python_info.get('executable', 'Unknown')}")
        lines.append("")

        # Add tools
        tools = report.get("tools", [])
        if tools:
            lines.append("Development Tools:")
            for tool in tools:
                status = "✅" if tool["found"] else "❌"
                version = tool.get("version", "N/A") if tool["found"] else "Not Found"
                lines.append(f"  {tool['name']}: {status} {version}")
            lines.append("")

        # Add suggestions
        suggestions = report.get("suggestions", [])
        if suggestions:
            lines.append("Suggestions:")
            for suggestion in suggestions:
                lines.append(f"  • {suggestion}")
            lines.append("")

        lines.append(
            f"Overall Status: {report.get('overall_status', 'unknown').upper()}"
        )

        return "\n".join(lines)

    def _determine_exit_code(self, validation_result: Dict[str, Any]) -> int:
        """Determine appropriate exit code based on validation results."""
        status = validation_result.get("overall_status", "unknown")

        if status == "critical":
            return 2
        elif status == "warning":
            return 1
        elif status == "healthy":
            return 0
        else:
            return 1

    def _get_timestamp(self) -> str:
        """Get current timestamp."""
        from datetime import datetime

        return datetime.now().isoformat()


def main():
    """Main entry point for the check-env command."""
    command = CheckEnvironmentCommand()
    return command.execute()


if __name__ == "__main__":
    sys.exit(main())
