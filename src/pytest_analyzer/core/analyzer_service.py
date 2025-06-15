import asyncio
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from rich.progress import Progress, TaskID

from ..utils.path_resolver import PathResolver
from ..utils.resource_manager import performance_tracker, with_timeout
from ..utils.settings import Settings
from .analysis.fix_applier import FixApplicationResult
from .extraction.extractor_factory import get_extractor
from .extraction.pytest_plugin import collect_failures_with_plugin
from .interfaces.protocols import Applier, Orchestrator
from .models.pytest_failure import FixSuggestion, PytestFailure

logger = logging.getLogger(__name__)


class PytestAnalyzerService:
    """
    Main service for analyzing pytest test failures.
    This class coordinates the extraction and analysis of test failures.
    """

    def __init__(
        self,
        settings: Settings,
        path_resolver: PathResolver,
        orchestrator: Orchestrator,
        fix_applier: Applier,
    ) -> None:
        self.settings = settings
        self.path_resolver = path_resolver
        self.orchestrator = orchestrator
        self.fix_applier = fix_applier
        # Async processing disabled by default for now
        self.use_async = getattr(settings, "use_async", False)

        from ..utils.git_manager import confirm_git_setup

        self.git_available = False
        if self.settings.check_git:
            project_root = str(self.path_resolver.project_root)
            self.git_available = confirm_git_setup(project_root)
            logger.info(
                f"Git integration {'enabled' if self.git_available else 'disabled'}"
            )

        if self.use_async:
            try:
                asyncio.get_event_loop()
            except RuntimeError:
                asyncio.set_event_loop(asyncio.new_event_loop())

        logger.info(f"Async processing: {'enabled' if self.use_async else 'disabled'}")

    @with_timeout(300)
    def analyze_pytest_output(self, output_path: str | Path) -> list[FixSuggestion]:
        """Analyze pytest output from a file and generate fix suggestions."""
        path = Path(output_path)
        if not path.exists():
            logger.error(f"Output file does not exist: {path}")
            return []

        try:
            extractor = get_extractor(path, self.settings, self.path_resolver)
            failures = extractor.extract_failures(path)
            if len(failures) > self.settings.max_failures:
                logger.warning(
                    f"Found {len(failures)} failures, limiting to {self.settings.max_failures}"
                )
                failures = failures[: self.settings.max_failures]
            return self._generate_suggestions(failures, use_async=self.use_async)
        except Exception as e:
            logger.error(f"Error analyzing pytest output: {e}")
            return []

    @with_timeout(300)
    def run_pytest_only(
        self,
        test_path: str,
        pytest_args: list[str] | None = None,
        quiet: bool = False,
        progress: Progress | None = None,
        task_id: TaskID | None = None,
    ) -> list[PytestFailure]:
        """Run pytest on the given path and return failures."""
        pytest_task_id: TaskID | None = None
        if progress and task_id is not None:
            pytest_task_id = progress.add_task(
                "[cyan]Running pytest...", total=None, parent=task_id
            )

        try:
            args_copy: list[str] = list(pytest_args) if pytest_args else []
            if quiet:
                if "-qq" not in args_copy:
                    args_copy = [
                        arg for arg in args_copy if arg not in ("-q", "--quiet")
                    ]
                    args_copy.append("-qq")
                if "--tb=short" not in args_copy:
                    args_copy.append("--tb=short")
                if "-W" not in args_copy and "--disable-warnings" not in args_copy:
                    args_copy.append("--disable-warnings")

            if self.settings.preferred_format == "plugin":
                all_args: list[str] = [test_path] + args_copy
                failures = collect_failures_with_plugin(all_args)
            elif self.settings.preferred_format == "json":
                failures = self._run_and_extract_json(test_path, args_copy)
            elif self.settings.preferred_format == "xml":
                failures = self._run_and_extract_xml(test_path, args_copy)
            else:
                failures = self._run_and_extract_json(test_path, args_copy)

            if progress and pytest_task_id is not None:
                progress.update(
                    pytest_task_id,
                    description="[green]Pytest complete!",
                    completed=True,
                )
            return failures
        except Exception as e:
            if progress and pytest_task_id is not None:
                progress.update(
                    pytest_task_id,
                    description=f"[red]Pytest failed: {e}",
                    completed=True,
                )
            logger.error(f"Error running tests: {e}")
            return []

    @with_timeout(300)
    def run_and_analyze(
        self,
        test_path: str,
        pytest_args: list[str] | None = None,
        quiet: bool = False,
        use_async: bool | None = None,
    ) -> list[FixSuggestion]:
        """Run pytest on the given path and analyze the output."""
        pytest_args = pytest_args or []
        from rich.console import Console
        from rich.progress import (
            BarColumn,
            Progress,
            SpinnerColumn,
            TextColumn,
            TimeElapsedColumn,
        )

        try:
            from ..cli.analyzer_cli import console
        except (ImportError, AttributeError):
            console = Console(force_terminal=True)

        if "-s" not in pytest_args and "--capture=no" not in pytest_args:
            pytest_args.append("-s")
        if "--disable-warnings" not in pytest_args:
            pytest_args.append("--disable-warnings")

        progress_config = (
            (SpinnerColumn(), TextColumn("[cyan]{task.description}"))
            if quiet
            else (
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TimeElapsedColumn(),
            )
        )

        with Progress(*progress_config, console=console, transient=quiet) as progress:
            main_task_id = progress.add_task("Running tests...", total=2)
            failures = self.run_pytest_only(
                test_path,
                pytest_args,
                quiet=quiet,
                progress=progress,
                task_id=main_task_id,
            )
            progress.update(
                main_task_id, advance=1, description="Analyzing failures..."
            )

            try:
                if len(failures) > self.settings.max_failures:
                    failures = failures[: self.settings.max_failures]

                suggestions = self._generate_suggestions(
                    failures,
                    quiet=quiet,
                    progress=progress,
                    parent_task_id=main_task_id,
                    use_async=use_async,
                )
                progress.update(
                    main_task_id, description="Analysis complete!", completed=True
                )
                return suggestions
            except Exception as e:
                progress.update(main_task_id, description=f"Error: {e}", completed=True)
                logger.error(f"Error analyzing tests: {e}")
                return []

    def _run_and_extract_json(
        self, test_path: str, pytest_args: list[str] | None = None
    ) -> list[PytestFailure]:
        """Run pytest with JSON output and extract failures."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            json_report_path = tmp.name
        try:
            cmd: list[str] = [
                "pytest",
                test_path,
                "--json-report",
                f"--json-report-file={json_report_path}",
            ] + (pytest_args or [])
            self._run_pytest_subprocess(cmd, pytest_args)
            extractor = get_extractor(
                Path(json_report_path), self.settings, self.path_resolver
            )
            return extractor.extract_failures(Path(json_report_path))
        except subprocess.TimeoutExpired:
            logger.error(
                f"Pytest execution timed out after {self.settings.pytest_timeout} seconds"
            )
            return []
        finally:
            if os.path.exists(json_report_path):
                os.remove(json_report_path)

    def _run_and_extract_xml(
        self, test_path: str, pytest_args: list[str] | None = None
    ) -> list[PytestFailure]:
        """Run pytest with XML output and extract failures."""
        with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as tmp:
            xml_report_path = tmp.name
        try:
            cmd: list[str] = [
                "pytest",
                test_path,
                f"--junit-xml={xml_report_path}",
            ] + (pytest_args or [])
            self._run_pytest_subprocess(cmd, pytest_args)
            extractor = get_extractor(
                Path(xml_report_path), self.settings, self.path_resolver
            )
            return extractor.extract_failures(Path(xml_report_path))
        except subprocess.TimeoutExpired:
            logger.error(
                f"Pytest execution timed out after {self.settings.pytest_timeout} seconds"
            )
            return []
        finally:
            if os.path.exists(xml_report_path):
                os.remove(xml_report_path)

    def _run_pytest_subprocess(
        self, cmd: list[str], pytest_args: list[str] | None
    ) -> None:
        args: list[str] = pytest_args or []
        quiet_mode = "-q" in args or "-qq" in args or "--quiet" in args
        if quiet_mode:
            with open(os.devnull, "w") as devnull:
                subprocess.run(
                    cmd,
                    timeout=self.settings.pytest_timeout,
                    check=False,
                    stdout=devnull,
                    stderr=devnull,
                )
        else:
            subprocess.run(cmd, timeout=self.settings.pytest_timeout, check=False)

    def _generate_suggestions(
        self,
        failures: list[PytestFailure],
        quiet: bool = False,
        progress: Progress | None = None,
        parent_task_id: TaskID | None = None,
        use_async: bool | None = None,
    ) -> list[FixSuggestion]:
        """Generate fix suggestions for the given failures."""
        with performance_tracker.track("generate_suggestions"):
            should_use_async = self.use_async if use_async is None else use_async
            if should_use_async:
                try:
                    loop = asyncio.get_event_loop()
                    return loop.run_until_complete(
                        self.orchestrator.generate_suggestions(
                            failures=failures,
                            quiet=quiet,
                            progress=progress,
                            parent_task_id=parent_task_id,
                        )
                    )
                except Exception as e:
                    logger.error(
                        f"Error in async suggestions generation, falling back to sync: {e}"
                    )

            # Fallback to sync or if async is disabled
            return self._sync_generate_suggestions(
                failures=failures,
                quiet=quiet,
                progress=progress,
                parent_task_id=parent_task_id,
            )

    def _sync_generate_suggestions(
        self,
        failures: list[PytestFailure],
        quiet: bool = False,
        progress: Progress | None = None,
        parent_task_id: TaskID | None = None,
    ) -> list[FixSuggestion]:
        """Generate fix suggestions synchronously."""
        # The new orchestrator is async-only. The old sync logic was complex and tied to the state machine.
        # For this refactoring, we will run the async orchestrator in a sync context.
        logger.info(
            "Running async orchestrator in a sync context for suggestion generation."
        )
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(
            self.orchestrator.generate_suggestions(
                failures=failures,
                quiet=quiet,
                progress=progress,
                parent_task_id=parent_task_id,
            )
        )

    def apply_suggestion(self, suggestion: FixSuggestion) -> FixApplicationResult:
        """Safely apply a fix suggestion to the target files."""
        with performance_tracker.track("apply_suggestion"):
            return self.fix_applier.apply_fix_suggestion(suggestion)

    def get_performance_metrics(self) -> dict[str, Any]:
        """Get performance metrics."""
        return performance_tracker.get_metrics()

    def generate_performance_report(self) -> str:
        """Generate a human-readable performance report."""
        return performance_tracker.report()

    def reset_performance_metrics(self) -> None:
        """Reset all performance metrics."""
        performance_tracker.reset()
