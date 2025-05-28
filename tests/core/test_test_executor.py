"""
Tests for the TestExecutor class.
"""

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

from pytest_analyzer.core.test_executor import TestExecutor


class MockEnvironmentManager:
    """Mock environment manager for testing."""

    NAME = "MockManager"

    def __init__(self, project_path: Path):
        self.project_path = project_path

    def build_command(self, command: list[str]) -> list[str]:
        return ["mock-env", "run"] + command

    def activate(self) -> None:
        pass

    def deactivate(self) -> None:
        pass


class TestTestExecutor:
    """Tests for TestExecutor class."""

    def test_init_with_project_path(self, tmp_path: Path):
        """Test TestExecutor initialization with project path."""
        with patch(
            "pytest_analyzer.core.test_executor.EnvironmentManagerDetector"
        ) as mock_detector:
            mock_detector.return_value.get_active_manager.return_value = None

            executor = TestExecutor(project_path=tmp_path)

            assert executor.project_path == tmp_path.resolve()
            assert executor.env_manager is None
            mock_detector.assert_called_once_with(project_path=tmp_path)

    def test_init_with_env_manager(self, tmp_path: Path):
        """Test TestExecutor initialization with provided environment manager."""
        mock_env = MockEnvironmentManager(tmp_path)

        executor = TestExecutor(project_path=tmp_path, env_manager=mock_env)

        assert executor.project_path == tmp_path.resolve()
        assert executor.env_manager is mock_env

    def test_init_auto_detect_env_manager(self, tmp_path: Path):
        """Test TestExecutor auto-detection of environment manager."""
        mock_env = MockEnvironmentManager(tmp_path)

        with patch(
            "pytest_analyzer.core.test_executor.EnvironmentManagerDetector"
        ) as mock_detector:
            mock_detector.return_value.get_active_manager.return_value = mock_env

            executor = TestExecutor(project_path=tmp_path)

            assert executor.env_manager is mock_env

    @patch("pytest_analyzer.core.test_executor.subprocess.run")
    def test_run_tests_with_env_manager(self, mock_run, tmp_path: Path):
        """Test running tests with environment manager."""
        mock_env = MockEnvironmentManager(tmp_path)
        mock_run.return_value.returncode = 0

        executor = TestExecutor(project_path=tmp_path, env_manager=mock_env)
        result = executor.run_tests(test_paths=["tests/"], options=["-v"])

        assert result == 0
        mock_run.assert_called_once_with(
            ["mock-env", "run", "pytest", "-v", "tests/"],
            cwd=tmp_path,
            timeout=300,
            capture_output=False,
        )

    @patch("pytest_analyzer.core.test_executor.subprocess.run")
    def test_run_tests_without_env_manager(self, mock_run, tmp_path: Path):
        """Test running tests without environment manager."""
        mock_run.return_value.returncode = 0

        executor = TestExecutor(project_path=tmp_path, env_manager=None)
        result = executor.run_tests(test_paths=["tests/"], options=["-v"])

        assert result == 0
        mock_run.assert_called_once_with(
            ["pytest", "-v", "tests/"],
            cwd=tmp_path,
            timeout=300,
            capture_output=False,
        )

    @patch("pytest_analyzer.core.test_executor.subprocess.run")
    def test_run_tests_default_parameters(self, mock_run, tmp_path: Path):
        """Test running tests with default parameters."""
        mock_run.return_value.returncode = 0

        executor = TestExecutor(project_path=tmp_path, env_manager=None)
        result = executor.run_tests()

        assert result == 0
        mock_run.assert_called_once_with(
            ["pytest", "."],
            cwd=tmp_path,
            timeout=300,
            capture_output=False,
        )

    @patch("pytest_analyzer.core.test_executor.subprocess.run")
    def test_run_linter_with_env_manager(self, mock_run, tmp_path: Path):
        """Test running linter with environment manager."""
        mock_env = MockEnvironmentManager(tmp_path)
        mock_run.return_value.returncode = 0

        executor = TestExecutor(project_path=tmp_path, env_manager=mock_env)
        result = executor.run_linter(paths=["src/"], options=["--select=F,E9"])

        assert result == 0
        mock_run.assert_called_once_with(
            ["mock-env", "run", "ruff", "check", "--select=F,E9", "src/"],
            cwd=tmp_path,
            timeout=120,
            capture_output=False,
        )

    @patch("pytest_analyzer.core.test_executor.subprocess.run")
    def test_run_formatter(self, mock_run, tmp_path: Path):
        """Test running formatter."""
        mock_run.return_value.returncode = 0

        executor = TestExecutor(project_path=tmp_path, env_manager=None)
        result = executor.run_formatter(paths=["src/"], options=["--check"])

        assert result == 0
        mock_run.assert_called_once_with(
            ["ruff", "format", "--check", "src/"],
            cwd=tmp_path,
            timeout=120,
            capture_output=False,
        )

    @patch("pytest_analyzer.core.test_executor.subprocess.run")
    def test_run_type_checker(self, mock_run, tmp_path: Path):
        """Test running type checker."""
        mock_run.return_value.returncode = 0

        executor = TestExecutor(project_path=tmp_path, env_manager=None)
        result = executor.run_type_checker(paths=["src/"], options=["--strict"])

        assert result == 0
        mock_run.assert_called_once_with(
            ["mypy", "--strict", "src/"],
            cwd=tmp_path,
            timeout=180,
            capture_output=False,
        )

    @patch("pytest_analyzer.core.test_executor.subprocess.run")
    def test_run_pre_commit(self, mock_run, tmp_path: Path):
        """Test running pre-commit."""
        mock_run.return_value.returncode = 0

        executor = TestExecutor(project_path=tmp_path, env_manager=None)
        result = executor.run_pre_commit()

        assert result == 0
        mock_run.assert_called_once_with(
            ["pre-commit", "run", "--all-files"],
            cwd=tmp_path,
            timeout=300,
            capture_output=False,
        )

    @patch("pytest_analyzer.core.test_executor.subprocess.run")
    def test_run_custom_command(self, mock_run, tmp_path: Path):
        """Test running custom command."""
        mock_env = MockEnvironmentManager(tmp_path)
        mock_run.return_value.returncode = 0

        executor = TestExecutor(project_path=tmp_path, env_manager=mock_env)
        result = executor.run_custom_command(["python", "-m", "build"])

        assert result == 0
        mock_run.assert_called_once_with(
            ["mock-env", "run", "python", "-m", "build"],
            cwd=tmp_path,
            timeout=180,
            capture_output=False,
        )

    @patch("pytest_analyzer.core.test_executor.subprocess.run")
    def test_timeout_handling(self, mock_run, tmp_path: Path):
        """Test timeout handling."""
        mock_run.side_effect = subprocess.TimeoutExpired("cmd", 300)

        executor = TestExecutor(project_path=tmp_path, env_manager=None)
        result = executor.run_tests(test_paths=["tests/"])

        assert result == 124  # Standard timeout exit code

    @patch("pytest_analyzer.core.test_executor.subprocess.run")
    def test_command_not_found_handling(self, mock_run, tmp_path: Path):
        """Test command not found handling."""
        mock_run.side_effect = FileNotFoundError("command not found")

        executor = TestExecutor(project_path=tmp_path, env_manager=None)
        result = executor.run_tests(test_paths=["tests/"])

        assert result == 127  # Standard command not found exit code

    @patch("pytest_analyzer.core.test_executor.subprocess.run")
    def test_general_exception_handling(self, mock_run, tmp_path: Path):
        """Test general exception handling."""
        mock_run.side_effect = RuntimeError("general error")

        executor = TestExecutor(project_path=tmp_path, env_manager=None)
        result = executor.run_tests(test_paths=["tests/"])

        assert result == 1

    @patch("pytest_analyzer.core.test_executor.subprocess.run")
    def test_run_quality_suite_all_enabled(self, mock_run, tmp_path: Path):
        """Test running complete quality suite with all tools enabled."""
        mock_run.return_value.returncode = 0

        executor = TestExecutor(project_path=tmp_path, env_manager=None)
        results = executor.run_quality_suite(
            include_tests=True,
            include_linting=True,
            include_formatting=True,
            include_type_checking=True,
            include_pre_commit=True,
        )

        assert len(results) == 5
        assert all(code == 0 for code in results.values())
        assert set(results.keys()) == {
            "tests",
            "linting",
            "formatting",
            "type_checking",
            "pre_commit",
        }

        # Should have called subprocess.run 5 times
        assert mock_run.call_count == 5

    @patch("pytest_analyzer.core.test_executor.subprocess.run")
    def test_run_quality_suite_partial(self, mock_run, tmp_path: Path):
        """Test running quality suite with only some tools enabled."""
        mock_run.return_value.returncode = 0

        executor = TestExecutor(project_path=tmp_path, env_manager=None)
        results = executor.run_quality_suite(
            include_tests=True,
            include_linting=True,
            include_formatting=False,
            include_type_checking=False,
            include_pre_commit=False,
        )

        assert len(results) == 2
        assert set(results.keys()) == {"tests", "linting"}
        assert mock_run.call_count == 2

    @patch("pytest_analyzer.core.test_executor.subprocess.run")
    def test_run_quality_suite_with_failures(self, mock_run, tmp_path: Path):
        """Test quality suite with some failures."""
        # Mock different return codes for different tools
        mock_run.side_effect = [
            Mock(returncode=0),  # tests pass
            Mock(returncode=1),  # linting fails
            Mock(returncode=0),  # formatting passes
        ]

        executor = TestExecutor(project_path=tmp_path, env_manager=None)
        results = executor.run_quality_suite(
            include_tests=True,
            include_linting=True,
            include_formatting=True,
            include_type_checking=False,
            include_pre_commit=False,
        )

        assert results["tests"] == 0
        assert results["linting"] == 1
        assert results["formatting"] == 0

    @patch("pytest_analyzer.core.test_executor.subprocess.run")
    def test_run_quality_suite_with_options(self, mock_run, tmp_path: Path):
        """Test quality suite with custom options for each tool."""
        mock_run.return_value.returncode = 0

        executor = TestExecutor(project_path=tmp_path, env_manager=None)
        executor.run_quality_suite(
            include_tests=True,
            include_linting=True,
            include_formatting=False,
            include_type_checking=False,
            include_pre_commit=False,
            test_options=["-v", "--tb=short"],
            lint_options=["--select=F,E9"],
        )

        # Check that custom options were passed
        calls = mock_run.call_args_list

        # First call should be pytest with custom options
        assert calls[0][0][0] == ["pytest", "-v", "--tb=short", "."]

        # Second call should be ruff with custom options
        assert calls[1][0][0] == ["ruff", "check", "--select=F,E9", "."]


class TestTestExecutorIntegration:
    """Integration tests for TestExecutor with real environment managers."""

    def test_with_real_pixi_manager(self, tmp_path: Path):
        """Test TestExecutor with a real Pixi manager."""
        from pytest_analyzer.core.environment.pixi import PixiManager

        # Create pixi.toml to trigger detection
        pixi_file = tmp_path / "pixi.toml"
        pixi_file.write_text("""
[project]
name = "test-project"
""")

        pixi_manager = PixiManager(project_path=tmp_path)
        executor = TestExecutor(project_path=tmp_path, env_manager=pixi_manager)

        # Test command building
        with patch("pytest_analyzer.core.test_executor.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0

            executor.run_tests(test_paths=["tests/"])

            # Should have called with pixi run pytest
            mock_run.assert_called_once_with(
                ["pixi", "run", "pytest", "tests/"],
                cwd=tmp_path,
                timeout=300,
                capture_output=False,
            )

    def test_with_real_poetry_manager(self, tmp_path: Path):
        """Test TestExecutor with a real Poetry manager."""
        from pytest_analyzer.core.environment.poetry import PoetryManager

        # Create pyproject.toml with poetry configuration
        pyproject_file = tmp_path / "pyproject.toml"
        pyproject_file.write_text("""
[tool.poetry]
name = "test-project"
version = "0.1.0"
""")

        poetry_manager = PoetryManager(project_path=tmp_path)
        executor = TestExecutor(project_path=tmp_path, env_manager=poetry_manager)

        # Test command building
        with patch("pytest_analyzer.core.test_executor.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0

            executor.run_linter(paths=["src/"])

            # Should have called with poetry run ruff
            mock_run.assert_called_once_with(
                ["poetry", "run", "ruff", "check", "src/"],
                cwd=tmp_path,
                timeout=120,
                capture_output=False,
            )
