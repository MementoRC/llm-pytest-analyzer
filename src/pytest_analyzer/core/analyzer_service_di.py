"""
DI-based analyzer service implementation.

This module provides an analyzer service implementation using the DI container
to manage dependencies, improving modularity and testability.
"""

import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Union

from rich.progress import (
    BarColumn,
    Console,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)

from ..utils.path_resolver import PathResolver
from ..utils.resource_manager import ResourceMonitor, limit_memory, with_timeout
from ..utils.settings import Settings
from .analyzer_state_machine import (
    AnalyzerEvent,
    AnalyzerState,
    AnalyzerStateMachine,
)
from .extraction.extractor_factory import get_extractor
from .llm.llm_service_protocol import LLMServiceProtocol
from .models.pytest_failure import FixSuggestion, PytestFailure

logger = logging.getLogger(__name__)


class DIPytestAnalyzerService:
    """
    Main service for analyzing pytest test failures using dependency injection.

    This class leverages the DI container and state machine architecture to coordinate
    the extraction, analysis, and fix suggestion processes with improved
    modularity and testability.
    """

    def __init__(
        self,
        settings: Settings,
        path_resolver: PathResolver,
        state_machine: AnalyzerStateMachine,
        llm_service: Optional[LLMServiceProtocol] = None,
    ):
        """
        Initialize the test analyzer service with injected dependencies.

        Args:
            settings: Settings object
            path_resolver: PathResolver object for resolving paths
            state_machine: The analyzer state machine
            llm_service: Optional LLM service for advanced suggestions
        """
        self.settings = settings
        self.path_resolver = path_resolver
        self.state_machine = state_machine
        self.llm_service = llm_service

        # Get context for convenience
        self.context = state_machine.context

    @with_timeout(300)
    def analyze_pytest_output(self, output_path: Union[str, Path]) -> List[FixSuggestion]:
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
            # Set up the state machine
            self.state_machine.setup(output_path=path)

            # Process the output file
            self._process_output_file(path)

            # Continue through the state machine
            self._continue_analysis()

            # Return suggestions
            if self.state_machine.is_completed():
                return self.state_machine.get_suggestions()
            logger.warning(
                f"Analysis not completed, state: {self.state_machine.current_state_name}"
            )
            return []

        except Exception as e:
            logger.error(f"Error analyzing pytest output: {e}")
            self.state_machine.set_error(e, f"Error analyzing pytest output: {e}")
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
                    args_copy = [arg for arg in args_copy if arg != "-q" and arg != "--quiet"]
                    # Add super quiet mode flag
                    args_copy.append("-qq")
                # Add short traceback flag for cleaner output
                if "--tb=short" not in args_copy:
                    args_copy.append("--tb=short")
                # Disable warnings
                if "-W" not in args_copy and "--disable-warnings" not in args_copy:
                    args_copy.append("--disable-warnings")

            # Set up the state machine
            self.state_machine.setup(
                test_path=test_path,
                pytest_args=args_copy,
                quiet=quiet,
                progress=progress,
                main_task_id=task_id,
            )

            # Extract failures based on preferred format
            failures = self._extract_failures(test_path, args_copy)

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
            self.state_machine.set_error(e, f"Error running tests: {e}")
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
                pytest_args = [arg for arg in pytest_args if arg != "-q" and arg != "--quiet"]
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

                # Set up the state machine
                self.state_machine.setup(
                    test_path=test_path,
                    pytest_args=pytest_args,
                    quiet=quiet,
                    progress=progress,
                    main_task_id=main_task_id,
                )

                # Run pytest and extract failures
                self.run_pytest_only(
                    test_path,
                    pytest_args,
                    quiet=quiet,
                    progress=progress,
                    task_id=main_task_id,
                )

                progress.update(main_task_id, advance=1, description="Analyzing failures...")

                try:
                    # Continue with analysis
                    self._continue_analysis()

                    # Return suggestions based on state machine status
                    if self.state_machine.is_completed():
                        return self.state_machine.get_suggestions()
                    logger.warning(
                        f"Analysis not completed, state: {self.state_machine.current_state_name}"
                    )
                    return []

                except Exception as e:
                    progress.update(main_task_id, description=f"Error: {e}", completed=True)
                    logger.error(f"Error analyzing tests: {e}")
                    self.state_machine.set_error(e, f"Error analyzing tests: {e}")
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

                # Set up the state machine
                self.state_machine.setup(
                    test_path=test_path,
                    pytest_args=pytest_args,
                    quiet=quiet,
                    progress=progress,
                    main_task_id=main_task_id,
                )

                # Run pytest and extract failures
                self.run_pytest_only(
                    test_path,
                    pytest_args,
                    quiet=quiet,
                    progress=progress,
                    task_id=main_task_id,
                )

                progress.update(main_task_id, advance=1, description="[cyan]Analyzing failures...")

                try:
                    # Continue with analysis
                    self._continue_analysis()

                    # Return suggestions based on state machine status
                    if self.state_machine.is_completed():
                        return self.state_machine.get_suggestions()
                    logger.warning(
                        f"Analysis not completed, state: {self.state_machine.current_state_name}"
                    )
                    return []

                except Exception as e:
                    progress.update(
                        main_task_id,
                        description=f"[red]Error analyzing tests: {e}",
                        completed=True,
                    )
                    logger.error(f"Error analyzing tests: {e}")
                    self.state_machine.set_error(e, f"Error analyzing tests: {e}")
                    return []

    def apply_suggestion(self, suggestion: FixSuggestion):
        """
        Apply a fix suggestion to the code.

        Args:
            suggestion: The fix suggestion to apply

        Returns:
            Result of the fix application
        """
        # Delegate to the fix applier in the state machine context
        if self.context.fix_applier:
            return self.context.fix_applier.apply_fix_suggestion(suggestion)
        logger.error("Cannot apply fix: Fix applier not initialized")
        return None

    def _process_output_file(self, output_path: Path) -> None:
        """
        Process a pytest output file to extract failures.

        Args:
            output_path: Path to the pytest output file
        """
        try:
            # Get the appropriate extractor for the file type
            extractor = get_extractor(output_path, self.settings, self.path_resolver)

            # Extract failures
            failures = extractor.extract_failures(output_path)

            # Store failures in the context
            self.context.failures = failures

            # Trigger analysis if we have failures
            if failures:
                self.state_machine.trigger(AnalyzerEvent.START_ANALYSIS)
            else:
                # Complete the workflow if there are no failures
                self.state_machine.trigger(AnalyzerEvent.COMPLETE)

        except Exception as e:
            logger.error(f"Error processing output file: {e}")
            self.state_machine.set_error(e, f"Error processing output file: {e}")

    def _extract_failures(self, test_path: str, pytest_args: List[str]) -> List[PytestFailure]:
        """
        Extract failures from pytest execution.

        Args:
            test_path: Path to the test file or directory
            pytest_args: Additional pytest arguments

        Returns:
            List of test failures
        """
        # Choose extraction strategy based on settings
        try:
            if self.settings.preferred_format == "plugin":
                # Use direct pytest plugin integration
                all_args = [test_path]
                all_args.extend(pytest_args)

                from .extraction.pytest_plugin import collect_failures_with_plugin

                failures = collect_failures_with_plugin(all_args)

            elif self.settings.preferred_format == "json":
                # Generate JSON output and parse it
                failures = self._run_and_extract_json(test_path, pytest_args)

            elif self.settings.preferred_format == "xml":
                # Generate XML output and parse it
                failures = self._run_and_extract_xml(test_path, pytest_args)

            else:
                # Default to JSON format
                failures = self._run_and_extract_json(test_path, pytest_args)

            # Store failures in the context
            self.context.failures = failures

            # Trigger analysis if we have failures
            if failures:
                self.state_machine.trigger(AnalyzerEvent.START_ANALYSIS)
            else:
                # Complete the workflow if there are no failures
                self.state_machine.trigger(AnalyzerEvent.COMPLETE)

            return failures

        except Exception as e:
            logger.error(f"Error extracting failures: {e}")
            self.state_machine.set_error(e, f"Error extracting failures: {e}")
            return []

    def _continue_analysis(self) -> None:
        """
        Continue the analysis process through the state machine.
        """
        # If in the analyzing state, move to suggesting fixes
        if self.state_machine.current_state_name == AnalyzerState.ANALYZING:
            try:
                # Trigger suggestion generation
                self.state_machine.trigger(AnalyzerEvent.START_SUGGESTIONS)

                # Generate suggestions
                if self.state_machine.current_state_name == AnalyzerState.SUGGESTING:
                    self._generate_suggestions()

                    # Move to completed state if we were able to generate suggestions
                    if self.state_machine.current_state_name == AnalyzerState.SUGGESTING:
                        if self.context.suggestions:
                            # If we have suggestions and want to apply them, continue to applying state
                            if self.settings.auto_apply:
                                self.state_machine.trigger(AnalyzerEvent.START_APPLICATION)
                                self._apply_fixes()
                            else:
                                # Otherwise, just complete the workflow
                                self.state_machine.trigger(AnalyzerEvent.COMPLETE)
                        else:
                            # Complete the workflow if there are no suggestions
                            self.state_machine.trigger(AnalyzerEvent.COMPLETE)
            except Exception as e:
                logger.error(f"Error continuing analysis: {e}")
                self.state_machine.set_error(e, f"Error continuing analysis: {e}")

    def _generate_suggestions(self) -> None:
        """
        Generate fix suggestions for the extracted failures.
        """
        all_suggestions = []

        # Generate rule-based suggestions
        if self.context.suggester:
            for failure in self.context.failures:
                try:
                    with ResourceMonitor(max_time_seconds=self.settings.analyzer_timeout):
                        rule_based_suggestions = self.context.suggester.suggest_fixes(failure)
                        all_suggestions.extend(rule_based_suggestions)
                except Exception as e:
                    logger.error(f"Error generating rule-based suggestions: {e}")

        # Generate LLM-based suggestions if enabled
        if self.context.llm_suggester and self.settings.use_llm and self.context.failures:
            try:
                # Process each failure group with LLM
                for fingerprint, group in self.context.failure_groups.items():
                    # Skip empty groups (shouldn't happen, but being defensive)
                    if not group:
                        continue

                    # Select the most representative failure from the group
                    from .analysis.failure_grouper import select_representative_failure

                    representative = select_representative_failure(group)

                    # Generate suggestions for the representative failure
                    try:
                        with ResourceMonitor(max_time_seconds=self.settings.llm_timeout):
                            llm_suggestions = self.context.llm_suggester.suggest_fixes(
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

            except Exception as e:
                logger.error(f"Error during failure grouping: {e}")

        # Sort suggestions by confidence
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
                limited_suggestions.extend(suggestions[: self.settings.max_suggestions_per_failure])
            self.context.suggestions = limited_suggestions
        else:
            self.context.suggestions = all_suggestions

    def _apply_fixes(self) -> None:
        """
        Apply generated fix suggestions.
        """
        application_results = []

        # Apply each suggestion
        for suggestion in self.context.suggestions:
            result = self.apply_suggestion(suggestion)
            if result:
                application_results.append(result)

        # Store application results
        self.context.application_results = application_results

        # Complete the workflow
        self.state_machine.trigger(AnalyzerEvent.COMPLETE)

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
                progress_mode = not quiet_mode and ("-s" in args or "--capture=no" in args)

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
                    console = Console()
                    console.print("[cyan]Running pytest with JSON report...[/cyan]")

                    # Run pytest with normal output, needed for rich progress display
                    result = subprocess.run(cmd, timeout=self.settings.pytest_timeout, check=False)

                    if result.returncode != 0 and not quiet_mode:
                        console.print(
                            f"[yellow]Pytest exited with code {result.returncode}[/yellow]"
                        )
                else:
                    # Run pytest with a timeout, normal output but no special progress display
                    subprocess.run(cmd, timeout=self.settings.pytest_timeout, check=False)

                # Extract failures from JSON output
                extractor = get_extractor(Path(tmp.name), self.settings, self.path_resolver)
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
                progress_mode = not quiet_mode and ("-s" in args or "--capture=no" in args)

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
                    console = Console()
                    console.print("[cyan]Running pytest with XML report...[/cyan]")

                    # Run pytest with normal output, needed for rich progress display
                    result = subprocess.run(cmd, timeout=self.settings.pytest_timeout, check=False)

                    if result.returncode != 0 and not quiet_mode:
                        console.print(
                            f"[yellow]Pytest exited with code {result.returncode}[/yellow]"
                        )
                else:
                    # Run pytest with a timeout, normal output but no special progress display
                    subprocess.run(cmd, timeout=self.settings.pytest_timeout, check=False)

                # Extract failures from XML output
                extractor = get_extractor(Path(tmp.name), self.settings, self.path_resolver)
                return extractor.extract_failures(Path(tmp.name))

            except subprocess.TimeoutExpired:
                logger.error(
                    f"Pytest execution timed out after {self.settings.pytest_timeout} seconds"
                )
                return []
