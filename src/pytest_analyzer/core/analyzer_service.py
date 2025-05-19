import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, List, Optional, Union

from rich.progress import Progress, TaskID

from ..utils.path_resolver import PathResolver
from ..utils.resource_manager import ResourceMonitor, limit_memory, with_timeout
from ..utils.settings import Settings
from .analysis.failure_analyzer import FailureAnalyzer
from .analysis.failure_grouper import group_failures, select_representative_failure
from .analysis.fix_applier import FixApplicationResult, FixApplier
from .analysis.fix_suggester import FixSuggester
from .analysis.llm_suggester import LLMSuggester
from .extraction.extractor_factory import get_extractor
from .extraction.pytest_plugin import collect_failures_with_plugin
from .llm.backward_compat import LLMService
from .models.pytest_failure import FixSuggestion, PytestFailure

logger = logging.getLogger(__name__)


class PytestAnalyzerService:
    """
    Main service for analyzing pytest test failures.

    This class coordinates the extraction and analysis of test failures,
    using different strategies based on the input type and settings.
    """

    def __init__(
        self, settings: Optional[Settings] = None, llm_client: Optional[Any] = None
    ):
        """
        Initialize the test analyzer service.

        :param settings: Settings object
        :param llm_client: Optional client for language model API
        """
        self.settings = settings or Settings()
        self.path_resolver = PathResolver(self.settings.project_root)
        self.analyzer = FailureAnalyzer(max_suggestions=self.settings.max_suggestions)
        self.suggester = FixSuggester(min_confidence=self.settings.min_confidence)

        # Initialize LLM service and suggester if enabled
        self.llm_service = None
        self.llm_suggester = None
        if self.settings.use_llm:
            self.llm_service = LLMService(
                llm_client=llm_client, timeout_seconds=self.settings.llm_timeout
            )
            self.llm_suggester = LLMSuggester(
                llm_service=self.llm_service,
                min_confidence=self.settings.min_confidence,
                timeout_seconds=self.settings.llm_timeout,
            )

        # Initialize fix applier for applying suggestions
        self.fix_applier = FixApplier(
            project_root=self.settings.project_root,
            backup_suffix=".pytest-analyzer.bak",
            verbose_test_output=False,  # Default to quiet mode for validation
        )

    @with_timeout(300)
    def analyze_pytest_output(
        self, output_path: Union[str, Path]
    ) -> List[FixSuggestion]:
        """
        Analyze pytest output from a file and generate fix suggestions.

        Args:
            output_path: Path to the pytest output file

        Returns:
            List of suggested fixes
        """
        # Set memory limits
        limit_memory(self.settings.max_memory_mb)

        # Resolve the output path
        path = Path(output_path)
        if not path.exists():
            logger.error(f"Output file does not exist: {path}")
            return []

        try:
            # Get the appropriate extractor for the file type
            extractor = get_extractor(path, self.settings, self.path_resolver)

            # Extract failures
            failures = extractor.extract_failures(path)

            # Limit the number of failures to analyze
            if len(failures) > self.settings.max_failures:
                logger.warning(
                    f"Found {len(failures)} failures, limiting to {self.settings.max_failures}"
                )
                failures = failures[: self.settings.max_failures]

            # Generate suggestions for each failure
            return self._generate_suggestions(failures)

        except Exception as e:
            logger.error(f"Error analyzing pytest output: {e}")
            return []

    @with_timeout(300)
    def run_pytest_only(
        self,
        test_path: str,
        pytest_args: Optional[List[str]] = None,
        quiet: bool = False,
        progress: Optional[Progress] = None,
        task_id: Optional[TaskID] = None,
    ) -> List[PytestFailure]:
        """
        Run pytest on the given path and return failures without generating suggestions.

        Args:
            test_path: Path to the directory or file to test
            pytest_args: Additional pytest arguments
            quiet: Whether to suppress pytest output
            progress: Optional Progress object for showing progress
            task_id: Optional parent task ID for progress tracking

        Returns:
            List of test failures
        """
        # Set memory limits
        limit_memory(self.settings.max_memory_mb)

        # Add a pytest task if progress is active
        pytest_task_id: Optional[TaskID] = None
        if progress and task_id is not None:
            pytest_task_id = progress.add_task(
                "[cyan]Running pytest...",
                total=None,  # Indeterminate progress
                parent=task_id,
            )

        try:
            # Create a copy of pytest args to avoid modifying the original
            args_copy = list(pytest_args) if pytest_args else []

            # Add quiet-related arguments if needed
            if quiet:
                # Suppress pytest output (using super quiet mode)
                if "-qq" not in args_copy:
                    # First remove any existing -q flags
                    args_copy = [
                        arg for arg in args_copy if arg != "-q" and arg != "--quiet"
                    ]
                    # Add super quiet mode flag
                    args_copy.append("-qq")
                # Add short traceback flag for cleaner output
                if "--tb=short" not in args_copy:
                    args_copy.append("--tb=short")
                # Disable warnings
                if "-W" not in args_copy and "--disable-warnings" not in args_copy:
                    args_copy.append("--disable-warnings")

            # Choose extraction strategy based on settings
            if self.settings.preferred_format == "plugin":
                # Use direct pytest plugin integration
                all_args = [test_path]
                all_args.extend(args_copy)

                failures = collect_failures_with_plugin(all_args)

            elif self.settings.preferred_format == "json":
                # Generate JSON output and parse it
                failures = self._run_and_extract_json(test_path, args_copy)

            elif self.settings.preferred_format == "xml":
                # Generate XML output and parse it
                failures = self._run_and_extract_xml(test_path, args_copy)

            else:
                # Default to JSON format
                failures = self._run_and_extract_json(test_path, args_copy)

            # Update progress if active
            if progress and pytest_task_id is not None:
                progress.update(
                    pytest_task_id,
                    description="[green]Pytest complete!",
                    completed=True,
                )

            return failures

        except Exception as e:
            # Update progress if active
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
        pytest_args: Optional[List[str]] = None,
        quiet: bool = False,
    ) -> List[FixSuggestion]:
        """
        Run pytest on the given path and analyze the output.

        Args:
            test_path: Path to the directory or file to test
            pytest_args: Additional pytest arguments
            quiet: Whether to suppress output and logging

        Returns:
            List of suggested fixes
        """
        # Prepare pytest arguments
        pytest_args = pytest_args or []

        # Import rich components
        from rich.console import Console
        from rich.progress import (
            BarColumn,
            Progress,
            SpinnerColumn,
            TextColumn,
            TimeElapsedColumn,
        )

        # Use the console from CLI if available, or create a new one with force_terminal=True
        try:
            from ..cli.analyzer_cli import console
        except (ImportError, AttributeError):
            # If we can't import the CLI console, create our own with forced terminal
            console = Console(force_terminal=True)

        # Add flags to prevent pytest from capturing output
        if "-s" not in pytest_args and "--capture=no" not in pytest_args:
            pytest_args.append("-s")  # Critical: disable output capturing

        # Optionally disable warnings
        if "--disable-warnings" not in pytest_args:
            pytest_args.append("--disable-warnings")

        if quiet:
            # Even in quiet mode, show minimal progress indicators
            # Make sure quiet mode is reflected in pytest args (using super quiet mode)
            if "-qq" not in pytest_args:
                # First remove any existing -q flags
                pytest_args = [
                    arg for arg in pytest_args if arg != "-q" and arg != "--quiet"
                ]
                # Add super quiet mode flag
                pytest_args.append("-qq")
            # Add short traceback flag for cleaner output
            if "--tb=short" not in pytest_args:
                pytest_args.append("--tb=short")

            # Create minimal progress display
            with Progress(
                SpinnerColumn(),
                TextColumn("[cyan]{task.description}"),
                console=console,
                transient=True,  # Progress bars disappear when done
            ) as progress:
                # Create simplified task list
                main_task_id = progress.add_task("Running tests...", total=2)

                # Run pytest with minimal progress tracking
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
                    # Limit the number of failures to analyze
                    if len(failures) > self.settings.max_failures:
                        failures = failures[: self.settings.max_failures]

                    # Group failures to detect common issues
                    if failures:
                        project_root = (
                            str(self.path_resolver.project_root)
                            if self.path_resolver
                            else None
                        )
                        from .analysis.failure_grouper import group_failures

                        failure_groups = group_failures(failures, project_root)

                        # Show minimal groups info
                        if len(failure_groups) < len(failures):
                            progress.update(
                                main_task_id,
                                description=f"Found {len(failure_groups)} distinct issues...",
                            )

                    # Generate suggestions with minimal progress tracking
                    suggestions = self._generate_suggestions(
                        failures,
                        quiet=quiet,
                        progress=progress,
                        parent_task_id=main_task_id,
                    )

                    progress.update(
                        main_task_id, description="Analysis complete!", completed=True
                    )
                    return suggestions

                except Exception as e:
                    progress.update(
                        main_task_id, description=f"Error: {e}", completed=True
                    )
                    logger.error(f"Error analyzing tests: {e}")
                    return []
        else:
            # Full progress display for normal mode
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TimeElapsedColumn(),
                console=console,
            ) as progress:
                # Create main task
                main_task_id = progress.add_task("[cyan]Running tests...", total=2)

                # Run pytest with progress tracking
                failures = self.run_pytest_only(
                    test_path,
                    pytest_args,
                    quiet=quiet,
                    progress=progress,
                    task_id=main_task_id,
                )

                progress.update(
                    main_task_id, advance=1, description="[cyan]Analyzing failures..."
                )

                try:
                    # Limit the number of failures to analyze
                    if len(failures) > self.settings.max_failures:
                        logger.warning(
                            f"Found {len(failures)} failures, limiting to {self.settings.max_failures}"
                        )
                        failures = failures[: self.settings.max_failures]

                    # Generate suggestions with progress tracking
                    suggestions = self._generate_suggestions(
                        failures,
                        quiet=quiet,
                        progress=progress,
                        parent_task_id=main_task_id,
                    )

                    progress.update(
                        main_task_id,
                        description="[green]Analysis complete!",
                        completed=True,
                    )
                    return suggestions

                except Exception as e:
                    progress.update(
                        main_task_id,
                        description=f"[red]Error analyzing tests: {e}",
                        completed=True,
                    )
                    logger.error(f"Error analyzing tests: {e}")
                    return []

    def _run_and_extract_json(
        self, test_path: str, pytest_args: Optional[List[str]] = None
    ) -> List[PytestFailure]:
        """
        Run pytest with JSON output and extract failures.

        Args:
            test_path: Path to the directory or file to test
            pytest_args: Additional pytest arguments

        Returns:
            List of test failures
        """
        with tempfile.NamedTemporaryFile(suffix=".json") as tmp:
            args = pytest_args or []
            cmd = [
                "pytest",
                test_path,
                "--json-report",
                f"--json-report-file={tmp.name}",
            ]

            # Important: we need to extend args after defining base command to allow
            # custom args to override the defaults if needed
            cmd.extend(args)

            try:
                # Determine if we're in quiet mode
                quiet_mode = "-q" in args or "-qq" in args or "--quiet" in args
                # Determine if we want to show progress (requires -s to avoid pytest capturing output)
                progress_mode = not quiet_mode and (
                    "-s" in args or "--capture=no" in args
                )

                if quiet_mode:
                    # When in quiet mode, redirect output to devnull
                    with open(os.devnull, "w") as devnull:
                        # Run pytest with a timeout, redirecting output to devnull
                        subprocess.run(
                            cmd,
                            timeout=self.settings.pytest_timeout,
                            check=False,
                            stdout=devnull,
                            stderr=devnull,
                        )
                elif progress_mode:
                    # With progress mode enabled, make sure the output isn't being captured
                    from rich.console import Console

                    console = Console()
                    console.print("[cyan]Running pytest with JSON report...[/cyan]")

                    # Run pytest with normal output, needed for rich progress display
                    result = subprocess.run(
                        cmd, timeout=self.settings.pytest_timeout, check=False
                    )

                    if result.returncode != 0 and not quiet_mode:
                        console.print(
                            f"[yellow]Pytest exited with code {result.returncode}[/yellow]"
                        )
                else:
                    # Run pytest with a timeout, normal output but no special progress display
                    subprocess.run(
                        cmd, timeout=self.settings.pytest_timeout, check=False
                    )

                # Extract failures from JSON output
                extractor = get_extractor(
                    Path(tmp.name), self.settings, self.path_resolver
                )
                return extractor.extract_failures(Path(tmp.name))

            except subprocess.TimeoutExpired:
                logger.error(
                    f"Pytest execution timed out after {self.settings.pytest_timeout} seconds"
                )
                return []

    def _run_and_extract_xml(
        self, test_path: str, pytest_args: Optional[List[str]] = None
    ) -> List[PytestFailure]:
        """
        Run pytest with XML output and extract failures.

        Args:
            test_path: Path to the directory or file to test
            pytest_args: Additional pytest arguments

        Returns:
            List of test failures
        """
        with tempfile.NamedTemporaryFile(suffix=".xml") as tmp:
            args = pytest_args or []
            cmd = ["pytest", test_path, "--junit-xml", tmp.name]

            # Important: we need to extend args after defining base command to allow
            # custom args to override the defaults if needed
            cmd.extend(args)

            try:
                # Determine if we're in quiet mode
                quiet_mode = "-q" in args or "-qq" in args or "--quiet" in args
                # Determine if we want to show progress (requires -s to avoid pytest capturing output)
                progress_mode = not quiet_mode and (
                    "-s" in args or "--capture=no" in args
                )

                if quiet_mode:
                    # When in quiet mode, redirect output to devnull
                    with open(os.devnull, "w") as devnull:
                        # Run pytest with a timeout, redirecting output to devnull
                        subprocess.run(
                            cmd,
                            timeout=self.settings.pytest_timeout,
                            check=False,
                            stdout=devnull,
                            stderr=devnull,
                        )
                elif progress_mode:
                    # With progress mode enabled, make sure the output isn't being captured
                    from rich.console import Console

                    console = Console()
                    console.print("[cyan]Running pytest with XML report...[/cyan]")

                    # Run pytest with normal output, needed for rich progress display
                    result = subprocess.run(
                        cmd, timeout=self.settings.pytest_timeout, check=False
                    )

                    if result.returncode != 0 and not quiet_mode:
                        console.print(
                            f"[yellow]Pytest exited with code {result.returncode}[/yellow]"
                        )
                else:
                    # Run pytest with a timeout, normal output but no special progress display
                    subprocess.run(
                        cmd, timeout=self.settings.pytest_timeout, check=False
                    )

                # Extract failures from XML output
                extractor = get_extractor(
                    Path(tmp.name), self.settings, self.path_resolver
                )
                return extractor.extract_failures(Path(tmp.name))

            except subprocess.TimeoutExpired:
                logger.error(
                    f"Pytest execution timed out after {self.settings.pytest_timeout} seconds"
                )
                return []

    def _generate_suggestions(
        self,
        failures: List[PytestFailure],
        quiet: bool = False,
        progress: Optional[Progress] = None,
        parent_task_id: Optional[TaskID] = None,
    ) -> List[FixSuggestion]:
        """
        Generate fix suggestions for the given failures.

        This method combines rule-based and LLM-based suggestions when LLM integration
        is enabled in the settings. When LLM is enabled, it groups similar failures
        to avoid redundant LLM calls.

        :param failures: List of test failures
        :param quiet: Whether to suppress logging output
        :param progress: Optional Progress object for showing progress
        :param parent_task_id: Optional parent task ID for progress tracking
        :return: List of suggested fixes
        """
        all_suggestions = []

        # Add task for rule-based suggestions if progress is active
        rule_task_id: Optional[TaskID] = None
        if progress and parent_task_id is not None:
            rule_task_id = progress.add_task(
                "[cyan]Generating rule-based suggestions...",
                total=len(failures),
                parent=parent_task_id,
            )

        # Generate rule-based suggestions for all failures individually
        for i, failure in enumerate(failures):
            try:
                with ResourceMonitor(max_time_seconds=self.settings.analyzer_timeout):
                    rule_based_suggestions = self.suggester.suggest_fixes(failure)
                    all_suggestions.extend(rule_based_suggestions)

                    # Update progress if active
                    if progress and rule_task_id is not None:
                        progress.update(
                            rule_task_id,
                            advance=1,
                            description=f"[cyan]Rule-based suggestions: {i + 1}/{len(failures)}",
                        )
            except Exception as e:
                logger.error(f"Error generating rule-based suggestions: {e}")

        # Mark rule-based task complete if active
        if progress and rule_task_id is not None:
            progress.update(
                rule_task_id,
                description="[green]Rule-based suggestions complete",
                completed=True,
            )

        # Generate LLM-based suggestions if enabled, grouping similar failures
        if self.llm_suggester and self.settings.use_llm and failures:
            try:
                # Add task for grouping if progress is active
                group_task_id: Optional[TaskID] = None
                if progress and parent_task_id is not None:
                    group_task_id = progress.add_task(
                        "[cyan]Grouping similar failures...",
                        total=1,
                        parent=parent_task_id,
                    )

                # Group similar failures to avoid redundant LLM calls
                project_root = (
                    str(self.path_resolver.project_root) if self.path_resolver else None
                )
                failure_groups = group_failures(failures, project_root)

                # Mark grouping task complete if active
                if progress and group_task_id is not None:
                    progress.update(
                        group_task_id,
                        description=f"[green]Grouped {len(failures)} failures into {len(failure_groups)} distinct groups",
                        completed=True,
                    )

                if not quiet:
                    logger.info(
                        f"Grouped {len(failures)} failures into {len(failure_groups)} distinct groups"
                    )

                # Add task for LLM suggestions if progress is active
                llm_task_id: Optional[TaskID] = None
                if progress and parent_task_id is not None and failure_groups:
                    llm_task_id = progress.add_task(
                        "[cyan]Getting LLM suggestions...",
                        total=len(failure_groups),
                        parent=parent_task_id,
                    )

                # Process each group with a single LLM call
                for i, (fingerprint, group) in enumerate(failure_groups.items()):
                    # Skip empty groups (shouldn't happen, but being defensive)
                    if not group:
                        continue

                    # Select the most representative failure from the group
                    representative = select_representative_failure(group)

                    # Update progress before LLM call if active
                    if progress and llm_task_id is not None:
                        progress.update(
                            llm_task_id,
                            description=f"[cyan]Getting LLM suggestion {i + 1}/{len(failure_groups)}: {representative.test_name}",
                        )

                    if not quiet:
                        logger.info(
                            f"Generating LLM suggestions for group: {fingerprint} ({len(group)} similar failures)"
                        )
                        logger.info(f"Representative test: {representative.test_name}")

                    # Generate suggestions for the representative failure
                    try:
                        with ResourceMonitor(
                            max_time_seconds=self.settings.llm_timeout
                        ):
                            llm_suggestions = self.llm_suggester.suggest_fixes(
                                representative
                            )

                            # Create a FixSuggestion for each failure in the group using the same solution
                            for suggestion in llm_suggestions:
                                # Mark the suggestion as LLM-based
                                if not suggestion.code_changes:
                                    suggestion.code_changes = {}
                                suggestion.code_changes["source"] = "llm"

                                # The original suggestion is for the representative failure
                                all_suggestions.append(suggestion)

                                # For other failures in the group, create similar suggestions
                                for other_failure in group:
                                    if other_failure is not representative:
                                        # Create a new suggestion with the same content but different failure reference
                                        duplicate_suggestion = FixSuggestion(
                                            failure=other_failure,
                                            suggestion=suggestion.suggestion,
                                            explanation=suggestion.explanation,
                                            confidence=suggestion.confidence,
                                            code_changes=dict(suggestion.code_changes)
                                            if suggestion.code_changes
                                            else None,
                                        )
                                        all_suggestions.append(duplicate_suggestion)
                    except Exception as e:
                        logger.error(
                            f"Error generating LLM suggestions for group {fingerprint}: {e}"
                        )

                    # Update progress after LLM call if active
                    if progress and llm_task_id is not None:
                        progress.advance(llm_task_id)

                # Mark LLM task complete if active
                if progress and llm_task_id is not None:
                    progress.update(
                        llm_task_id,
                        description="[green]LLM suggestions complete",
                        completed=True,
                    )

            except Exception as e:
                logger.error(f"Error during failure grouping: {e}")

        # Sort suggestions by confidence (highest first)
        all_suggestions.sort(key=lambda s: s.confidence, reverse=True)

        # Limit to max_suggestions per failure if specified
        if self.settings.max_suggestions_per_failure > 0:
            # Group suggestions by failure
            suggestions_by_failure = {}
            for suggestion in all_suggestions:
                failure_id = suggestion.failure.test_name
                if failure_id not in suggestions_by_failure:
                    suggestions_by_failure[failure_id] = []
                suggestions_by_failure[failure_id].append(suggestion)

            # Limit each group and rebuild the list
            limited_suggestions = []
            for failure_id, suggestions in suggestions_by_failure.items():
                limited_suggestions.extend(
                    suggestions[: self.settings.max_suggestions_per_failure]
                )
            return limited_suggestions

        return all_suggestions

    def apply_suggestion(self, suggestion: FixSuggestion) -> FixApplicationResult:
        """
        Safely apply a fix suggestion to the target files.

        This method extracts necessary information from the suggestion,
        filters out metadata keys, and uses the FixApplier to apply
        the changes with validation and rollback capability.

        Args:
            suggestion: FixSuggestion to apply

        Returns:
            FixApplicationResult indicating success or failure
        """
        if not hasattr(suggestion, "failure") or not suggestion.failure:
            return FixApplicationResult(
                success=False,
                message="Cannot apply fix: Missing original failure information.",
                applied_files=[],
                rolled_back_files=[],
            )

        if not suggestion.code_changes:
            return FixApplicationResult(
                success=False,
                message="Cannot apply fix: No code changes provided in suggestion.",
                applied_files=[],
                rolled_back_files=[],
            )

        # Filter code_changes to include only file paths (not metadata)
        code_changes_to_apply = {}
        for key, value in suggestion.code_changes.items():
            # Skip metadata keys like 'source' and 'fingerprint'
            if not isinstance(key, str) or ("/" not in key and "\\" not in key):
                continue
            # Skip empty values
            if not value:
                continue
            # Include valid file paths with content
            code_changes_to_apply[key] = value

        if not code_changes_to_apply:
            return FixApplicationResult(
                success=False,
                message="Cannot apply fix: No valid file changes found in suggestion.",
                applied_files=[],
                rolled_back_files=[],
            )

        # Determine which tests to run for validation
        tests_to_validate = []
        if hasattr(suggestion, "validation_tests") and suggestion.validation_tests:
            tests_to_validate = suggestion.validation_tests
        elif hasattr(suggestion.failure, "test_name") and suggestion.failure.test_name:
            # Use the original failing test for validation
            tests_to_validate = [suggestion.failure.test_name]
        else:
            logger.warning(
                "Could not determine specific tests for validation. Proceeding without test validation."
            )

        # Log the application attempt
        logger.info(
            f"Attempting to apply fix for failure: {getattr(suggestion.failure, 'test_name', 'Unknown Test')}"
        )
        logger.info(f"Modifying files: {list(code_changes_to_apply.keys())}")
        logger.info(f"Validating with tests: {tests_to_validate}")

        # Apply the fix (using quiet test output by default)
        result = self.fix_applier.apply_fix(
            code_changes_to_apply,
            tests_to_validate,
            verbose_test_output=False,  # Use quiet mode for validation tests
        )

        # Log the result
        if result.success:
            logger.info(
                f"Successfully applied fix to: {[str(p) for p in result.applied_files]}"
            )
        else:
            logger.error(f"Failed to apply fix: {result.message}")
            if result.rolled_back_files:
                logger.info(
                    f"Rolled back changes in: {[str(p) for p in result.rolled_back_files]}"
                )

        return result
