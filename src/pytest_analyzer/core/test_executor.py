"""
Test executor for running quality validation workflows with environment manager support.

This module provides a TestExecutor class that can run pytest, linting, and other
quality validation commands through the detected environment manager, ensuring
proper environment context for all quality validation workflows.
"""

import logging
import subprocess
from pathlib import Path
from typing import List, Optional

from ..utils.path_resolver import PathResolver
from .environment.detector import EnvironmentManagerDetector
from .environment.protocol import EnvironmentManager

logger = logging.getLogger(__name__)


class TestExecutor:
    """
    Test executor for running quality validation workflows.

    This class provides a unified interface for running pytest, linting, and other
    quality validation commands through the detected environment manager, ensuring
    all commands are executed within the proper environment context.
    """

    def __init__(
        self,
        project_path: Optional[Path] = None,
        env_manager: Optional[EnvironmentManager] = None,
    ):
        """
        Initialize the test executor.

        Args:
            project_path: Path to the project root (uses current directory if None)
            env_manager: Environment manager to use (auto-detects if None)
        """
        self.project_path = Path(project_path or Path.cwd()).resolve()
        self.path_resolver = PathResolver(self.project_path)

        if env_manager:
            self.env_manager = env_manager
        else:
            detector = EnvironmentManagerDetector(project_path=self.project_path)
            self.env_manager = detector.get_active_manager()

        if self.env_manager:
            manager_name = getattr(self.env_manager, "NAME", "UnknownManager")
            logger.debug(f"TestExecutor using environment manager: {manager_name}")
        else:
            logger.debug("TestExecutor using direct command execution (no env manager)")

    def run_tests(
        self,
        test_paths: Optional[List[str]] = None,
        options: Optional[List[str]] = None,
        timeout: int = 300,
    ) -> int:
        """
        Run pytest with the appropriate environment manager.

        Args:
            test_paths: List of test paths to run (uses current directory if None)
            options: Additional pytest options
            timeout: Command timeout in seconds

        Returns:
            Exit code from pytest execution
        """
        if test_paths is None:
            test_paths = ["."]
        if options is None:
            options = []

        command = ["pytest"] + options + test_paths
        return self._execute_command(command, timeout)

    def run_linter(
        self,
        paths: Optional[List[str]] = None,
        options: Optional[List[str]] = None,
        timeout: int = 120,
    ) -> int:
        """
        Run ruff with the appropriate environment manager.

        Args:
            paths: List of paths to lint (uses current directory if None)
            options: Additional ruff options
            timeout: Command timeout in seconds

        Returns:
            Exit code from ruff execution
        """
        if paths is None:
            paths = ["."]
        if options is None:
            options = []

        command = ["ruff", "check"] + options + paths
        return self._execute_command(command, timeout)

    def run_formatter(
        self,
        paths: Optional[List[str]] = None,
        options: Optional[List[str]] = None,
        timeout: int = 120,
    ) -> int:
        """
        Run ruff format with the appropriate environment manager.

        Args:
            paths: List of paths to format (uses current directory if None)
            options: Additional ruff format options
            timeout: Command timeout in seconds

        Returns:
            Exit code from ruff format execution
        """
        if paths is None:
            paths = ["."]
        if options is None:
            options = []

        command = ["ruff", "format"] + options + paths
        return self._execute_command(command, timeout)

    def run_type_checker(
        self,
        paths: Optional[List[str]] = None,
        options: Optional[List[str]] = None,
        timeout: int = 180,
    ) -> int:
        """
        Run mypy with the appropriate environment manager.

        Args:
            paths: List of paths to type check (uses current directory if None)
            options: Additional mypy options
            timeout: Command timeout in seconds

        Returns:
            Exit code from mypy execution
        """
        if paths is None:
            paths = ["."]
        if options is None:
            options = []

        command = ["mypy"] + options + paths
        return self._execute_command(command, timeout)

    def run_pre_commit(
        self,
        options: Optional[List[str]] = None,
        timeout: int = 300,
    ) -> int:
        """
        Run pre-commit with the appropriate environment manager.

        Args:
            options: Additional pre-commit options (defaults to --all-files)
            timeout: Command timeout in seconds

        Returns:
            Exit code from pre-commit execution
        """
        if options is None:
            options = ["--all-files"]

        command = ["pre-commit", "run"] + options
        return self._execute_command(command, timeout)

    def run_custom_command(
        self,
        command: List[str],
        timeout: int = 180,
    ) -> int:
        """
        Run a custom command with the appropriate environment manager.

        Args:
            command: Command and arguments to execute
            timeout: Command timeout in seconds

        Returns:
            Exit code from command execution
        """
        return self._execute_command(command, timeout)

    def _execute_command(self, command: List[str], timeout: int) -> int:
        """
        Execute a command using the environment manager or directly.

        Args:
            command: Command and arguments to execute
            timeout: Command timeout in seconds

        Returns:
            Exit code from command execution
        """
        try:
            # Build final command through environment manager
            if self.env_manager:
                final_command = self.env_manager.build_command(command)
                manager_name = getattr(self.env_manager, "NAME", "UnknownManager")
                logger.debug(
                    f"Executing command via {manager_name}: {' '.join(final_command)}"
                )
            else:
                final_command = command
                logger.debug(f"Executing command directly: {' '.join(final_command)}")

            # Execute the command
            result = subprocess.run(
                final_command,
                cwd=self.project_path,
                timeout=timeout,
                capture_output=False,  # Let output flow through normally
            )

            return result.returncode

        except subprocess.TimeoutExpired:
            logger.error(
                f"Command timed out after {timeout} seconds: {' '.join(command)}"
            )
            return 124  # Standard timeout exit code
        except FileNotFoundError as e:
            logger.error(f"Command not found: {e}")
            return 127  # Standard command not found exit code
        except Exception as e:
            logger.error(f"Error executing command: {e}")
            return 1

    def run_quality_suite(
        self,
        include_tests: bool = True,
        include_linting: bool = True,
        include_formatting: bool = True,
        include_type_checking: bool = True,
        include_pre_commit: bool = False,
        test_options: Optional[List[str]] = None,
        lint_options: Optional[List[str]] = None,
        format_options: Optional[List[str]] = None,
        type_check_options: Optional[List[str]] = None,
        pre_commit_options: Optional[List[str]] = None,
    ) -> dict:
        """
        Run a complete quality validation suite.

        Args:
            include_tests: Whether to run tests
            include_linting: Whether to run linting
            include_formatting: Whether to run formatting
            include_type_checking: Whether to run type checking
            include_pre_commit: Whether to run pre-commit hooks
            test_options: Options for pytest
            lint_options: Options for ruff check
            format_options: Options for ruff format
            type_check_options: Options for mypy
            pre_commit_options: Options for pre-commit

        Returns:
            Dictionary with results for each tool run
        """
        results = {}

        if include_tests:
            logger.info("Running tests...")
            results["tests"] = self.run_tests(options=test_options)

        if include_linting:
            logger.info("Running linting...")
            results["linting"] = self.run_linter(options=lint_options)

        if include_formatting:
            logger.info("Running formatting...")
            results["formatting"] = self.run_formatter(options=format_options)

        if include_type_checking:
            logger.info("Running type checking...")
            results["type_checking"] = self.run_type_checker(options=type_check_options)

        if include_pre_commit:
            logger.info("Running pre-commit hooks...")
            results["pre_commit"] = self.run_pre_commit(options=pre_commit_options)

        # Log summary
        passed = [tool for tool, code in results.items() if code == 0]
        failed = [tool for tool, code in results.items() if code != 0]

        if passed:
            logger.info(f"Quality checks passed: {', '.join(passed)}")
        if failed:
            logger.warning(f"Quality checks failed: {', '.join(failed)}")

        return results
