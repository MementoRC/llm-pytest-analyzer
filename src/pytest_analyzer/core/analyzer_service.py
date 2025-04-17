import logging
import os
import subprocess
import tempfile
import asyncio
from pathlib import Path
from typing import List, Optional, Dict, Any, Union, Tuple, Type, TypeVar, Generic, cast
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from rich.progress import Progress, TaskID

from .models.pytest_failure import PytestFailure, FixSuggestion
from .extraction.extractor_factory import get_extractor
from .extraction.pytest_plugin import collect_failures_with_plugin
from .analysis.failure_analyzer import FailureAnalyzer
from .analysis.llm_suggester import LLMSuggester
from .analysis.failure_grouper import group_failures, select_representative_failure
from .analysis.fix_applier import FixApplier, FixApplicationResult
from ..utils.resource_manager import (
    with_timeout, async_with_timeout, limit_memory,
    ResourceMonitor, AsyncResourceMonitor, performance_tracker
)
from ..utils.settings import Settings
from ..utils.path_resolver import PathResolver

logger = logging.getLogger(__name__)


# --- State Machine Implementation ---

# Type variable for the state class
S = TypeVar('S', bound='State')

# Custom exception hierarchy
class PytestAnalyzerError(Exception):
    """Base exception class for pytest-analyzer states."""

class InitializationError(PytestAnalyzerError):
    """Raised during initialization errors."""

class FailureGroupingError(PytestAnalyzerError):
    """Raised when failing to group failures."""

class RepresentativeSelectionError(PytestAnalyzerError):
    """Raised when failing to select representative failures."""

class BatchProcessingError(PytestAnalyzerError):
    """Raised during batch processing issues."""

class PostProcessingError(PytestAnalyzerError):
    """Raised during post-processing issues."""

class State(ABC):
    """Base class for all states in the state machine."""

    def __init__(self, context: 'Context'):
        self.context = context

    @abstractmethod
    async def run(self) -> None:
        """Execute the state's logic."""
        pass

    async def handle_error(self, error: Exception) -> None:
        """
        Handle error that occurred during state execution.
        By default, transitions to ErrorState but can be overridden.

        Args:
            error: The exception that was raised
        """
        if isinstance(error, PytestAnalyzerError):
            self.context.log_error(f"{error.__class__.__name__}: {error}")
        else:
            self.context.log_error(f"Unexpected error in {self.__class__.__name__}: {error}")

        await self.context.transition_to(ErrorState)

class Context:
    """
    Context for the state machine, containing all shared data and dependencies.
    Manages state transitions and provides helper methods for common operations.
    """

    def __init__(self,
                 failures: List[PytestFailure],
                 quiet: bool,
                 progress: Optional[Progress],
                 parent_task_id: Optional[TaskID],
                 path_resolver,
                 settings,
                 llm_suggester,
                 logger,
                 performance_tracker):
        # Validate essential dependencies
        if logger is None:
            raise ValueError("Logger must not be None")
        if settings is None:
            raise ValueError("Settings must not be None")
        if llm_suggester is None:
            raise ValueError("LLM suggester must not be None")

        # Inputs and dependencies
        self.failures = failures
        self.quiet = quiet
        self.progress = progress
        self.parent_task_id = parent_task_id
        self.path_resolver = path_resolver
        self.settings = settings
        self.llm_suggester = llm_suggester
        self.logger = cast(logging.Logger, logger)
        self.performance_tracker = performance_tracker

        # State data
        self.all_suggestions: List[FixSuggestion] = []
        self.failure_groups: Dict[str, List[PytestFailure]] = {}
        self.representative_failures: List[PytestFailure] = []
        self.group_mapping: Dict[str, List[PytestFailure]] = {}

        # Progress tracking
        self.progress_tasks: Dict[str, TaskID] = {}

        # Current state
        self.state: Optional[State] = None
        self.execution_complete = False
        self.execution_complete_event = asyncio.Event()
        self.final_error: Optional[Exception] = None

    async def transition_to(self, state_cls: Type[S]) -> None:
        """
        Transition to a new state and run it.

        Args:
            state_cls: The state class to transition to
        """
        self.state = state_cls(self)
        self.log_debug(f"Transitioning to {state_cls.__name__}")
        try:
            await self.state.run()
        except Exception as e:
            if self.state:
                await self.state.handle_error(e)
            else:
                self.log_error(f"Error transitioning to {state_cls.__name__}: {e}")
                self.final_error = e
                self.mark_execution_complete()

    def mark_execution_complete(self) -> None:
        """Mark execution as complete and signal waiting tasks."""
        self.execution_complete = True
        self.execution_complete_event.set()

    def log_debug(self, message: str) -> None:
        """Log a debug message."""
        self.logger.debug(message)

    def log_info(self, message: str) -> None:
        """Log an info message if not in quiet mode."""
        if not self.quiet:
            self.logger.info(message)

    def log_error(self, message: str) -> None:
        """Log an error message."""
        self.logger.error(message)

    def log_warning(self, message: str) -> None:
        """Log a warning message."""
        self.logger.warning(message)

    def create_progress_task(self, key: str, description: str, **kwargs) -> Optional[TaskID]:
        """
        Create a progress task and store its ID for later reference.

        Args:
            key: Key to identify the task
            description: Task description
            **kwargs: Additional progress task arguments

        Returns:
            Task ID or None if progress tracking is disabled
        """
        if self.progress and self.parent_task_id is not None:
            # Set default parent task ID if not provided in kwargs
            if 'parent' not in kwargs:
                kwargs['parent'] = self.parent_task_id

            task_id = self.progress.add_task(description, **kwargs)
            self.progress_tasks[key] = task_id
            return task_id
        return None

    def update_progress(self, key: str, description: str = None, completed: bool = False, **kwargs) -> None:
        """
        Update a progress task by its key.

        Args:
            key: The task key
            description: New description (optional)
            completed: Whether to mark the task as completed
            **kwargs: Additional progress.update arguments
        """
        if self.progress and key in self.progress_tasks:
            task_id = self.progress_tasks[key]
            update_kwargs = {}

            if description:
                update_kwargs['description'] = description
            if completed:
                update_kwargs['completed'] = True

            update_kwargs |= kwargs

            self.progress.update(task_id, **update_kwargs)

    def cleanup_progress_tasks(self) -> None:
        """Mark all progress tasks as completed to ensure clean UI."""
        if self.progress:
            for key, task_id in self.progress_tasks.items():
                try:
                    # Check if task still exists before updating
                    if self.progress.get_task(task_id):
                        self.progress.update(task_id, completed=True)
                except Exception as e:
                    self.log_debug(f"Error cleaning up progress task {key}: {e}")

    def mark_llm_async(self, suggestion: FixSuggestion) -> FixSuggestion:
        """
        Mark a suggestion as coming from asynchronous LLM processing.

        Args:
            suggestion: The suggestion to mark

        Returns:
            The marked suggestion (for chaining)
        """
        if not suggestion.code_changes:
            suggestion.code_changes = {}
        suggestion.code_changes['source'] = 'llm_async'
        return suggestion

    @asynccontextmanager
    async def track_performance(self, operation_name: str):
        """Context manager for tracking performance of an operation."""
        async with self.performance_tracker.async_track(operation_name):
            yield


class Initialize(State):
    """Initial state that sets up progress tracking."""

    async def run(self) -> None:
        # Return early if there are no failures to analyze
        if not self.context.failures:
            self.context.cleanup_progress_tasks()  # Defensive cleanup even though no tasks were created
            self.context.mark_execution_complete()
            return

        try:
            # Add task for LLM-based suggestions
            self.context.create_progress_task(
                'llm',
                "[cyan]Generating async LLM-based suggestions...",
                total=len(self.context.failures)
            )

            # Transition to the grouping state
            await self.context.transition_to(GroupFailures)

        except Exception as e:
            raise InitializationError(f"Failed to initialize suggestion generation: {e}") from e


class GroupFailures(State):
    """Groups similar failures to reduce redundant LLM calls."""

    async def run(self) -> None:
        # Add task for grouping
        self.context.create_progress_task(
            'grouping',
            "[cyan]Grouping similar failures...",
            total=1
        )

        try:
            # Group similar failures
            async with self.context.track_performance("async_failure_grouping"):
                project_root = str(self.context.path_resolver.project_root) if self.context.path_resolver else None
                self.context.failure_groups = group_failures(self.context.failures, project_root)

            # Update progress
            self.context.update_progress(
                'grouping',
                f"[green]Grouped {len(self.context.failures)} into {len(self.context.failure_groups)} distinct groups",
                completed=True
            )

            # Log grouping result
            self.context.log_info(
                f"Grouped {len(self.context.failures)} failures into {len(self.context.failure_groups)} distinct groups"
            )

            # Transition to the next state if we have groups
            if self.context.failure_groups:
                await self.context.transition_to(PrepareRepresentatives)
            else:
                # Skip to post-processing if no groups were found
                self.context.log_info("No failure groups found, skipping to post-processing")
                await self.context.transition_to(PostProcess)

        except Exception as e:
            raise FailureGroupingError(f"Error grouping failures: {e}") from e


class PrepareRepresentatives(State):
    """Prepares representative failures for batch processing."""

    async def run(self) -> None:
        try:
            # Prepare representatives from each group
            for fingerprint, group in self.context.failure_groups.items():
                if not group:
                    continue

                representative = select_representative_failure(group)
                self.context.representative_failures.append(representative)
                self.context.group_mapping[representative.test_name] = group

            # Add task for batch processing
            self.context.create_progress_task(
                'batch_processing',
                f"[cyan]Processing {len(self.context.representative_failures)} failure groups in parallel...",
                total=1
            )

            # Log processing start with resource usage warning
            self.context.log_info(
                f"Processing {len(self.context.representative_failures)} failure groups with "
                f"batch_size={self.context.settings.batch_size}, "
                f"concurrency={self.context.settings.max_concurrency}. "
                "Note: High values may impact system resources and LLM backend performance."
            )

            # Transition to batch processing
            await self.context.transition_to(BatchProcess)

        except Exception as e:
            raise RepresentativeSelectionError(f"Error preparing representative failures: {e}") from e


class BatchProcess(State):
    """Processes representative failures in batches to generate suggestions."""

    async def run(self) -> None:
        try:
            async with self.context.track_performance("batch_process_failures"):
                # Start resource monitoring with timeout
                async with AsyncResourceMonitor(max_time_seconds=self.context.settings.llm_timeout):
                    # Get suggestions for all representatives
                    suggestions_by_test = await self.context.llm_suggester.batch_suggest_fixes(
                        self.context.representative_failures
                    )

                    # Process suggestions for all groups
                    for test_name, suggestions in suggestions_by_test.items():
                        group = self.context.group_mapping.get(test_name, [])
                        if not group:
                            continue

                        # Get the representative failure
                        representative = next((f for f in group if f.test_name == test_name), None)

                        if representative and suggestions:
                            # Process all suggestions for this group
                            await self._process_suggestions_for_group(representative, group, suggestions)

            # Update progress
            self.context.update_progress(
                'batch_processing',
                f"[green]Completed processing {len(self.context.representative_failures)} failure groups",
                completed=True
            )

            # Transition to post-processing
            await self.context.transition_to(PostProcess)

        except asyncio.TimeoutError as e:
            self.context.log_warning(
                f"Batch processing timed out after {self.context.settings.llm_timeout} seconds. "
                f"Consider adjusting the timeout or reducing batch size/concurrency."
            )
            raise BatchProcessingError("LLM request timed out") from e
        except Exception as e:
            raise BatchProcessingError(f"Error in batch processing: {e}") from e

    async def _process_suggestions_for_group(
        self,
        representative: PytestFailure,
        group: List[PytestFailure],
        suggestions: List[FixSuggestion]
    ) -> None:
        """
        Process suggestions for a group of failures.

        Args:
            representative: The representative failure
            group: The group of failures
            suggestions: The suggestions for the representative
        """
        for suggestion in suggestions:
            # Add marked suggestion for the representative
            self.context.all_suggestions.append(
                self.context.mark_llm_async(suggestion)
            )

            # Create duplicate suggestions for other failures in the group
            for other_failure in group:
                if other_failure is not representative:
                    duplicate_suggestion = FixSuggestion(
                        failure=other_failure,
                        suggestion=suggestion.suggestion,
                        explanation=suggestion.explanation,
                        confidence=suggestion.confidence,
                        code_changes=dict(suggestion.code_changes) if suggestion.code_changes else None
                    )
                    # Add marked duplicate suggestion
                    self.context.all_suggestions.append(
                        self.context.mark_llm_async(duplicate_suggestion)
                    )


class PostProcess(State):
    """Post-processes suggestions (sorting and limiting)."""

    async def run(self) -> None:
        try:
            async with self.context.track_performance("async_post_processing"):
                # Sort suggestions by confidence
                self.context.all_suggestions.sort(key=lambda s: s.confidence, reverse=True)

                # Limit suggestions per failure if specified
                if self.context.settings.max_suggestions_per_failure > 0:
                    self._limit_suggestions_per_failure()

            # Mark execution as complete
            self.context.mark_execution_complete()

        except Exception as e:
            raise PostProcessingError(f"Error in post-processing: {e}") from e

    def _limit_suggestions_per_failure(self) -> None:
        """Limit the number of suggestions per failure."""
        # Group suggestions by failure
        suggestions_by_failure = {}
        for suggestion in self.context.all_suggestions:
            failure_id = suggestion.failure.test_name
            if failure_id not in suggestions_by_failure:
                suggestions_by_failure[failure_id] = []
            suggestions_by_failure[failure_id].append(suggestion)

        # Limit each group and rebuild the list
        limited_suggestions = []
        for suggestions in suggestions_by_failure.values():
            limited_suggestions.extend(
                suggestions[:self.context.settings.max_suggestions_per_failure]
            )

        # Update the suggestions list
        self.context.all_suggestions = limited_suggestions


class ErrorState(State):
    """
    Handles error conditions and performs cleanup.

    This state is transitioned to when an error occurs in any other state.
    It ensures all resources are properly cleaned up and progress tasks are completed.
    """

    async def run(self) -> None:
        # Ensure all progress tasks are cleaned up
        self.context.cleanup_progress_tasks()

        # Log that we're in error state
        self.context.log_warning("Error encountered during async suggestion generation. Moving to post-processing with partial results.")

        # Transition to post-processing to handle whatever results we have so far
        await self.context.transition_to(PostProcess)

# --- End State Machine Implementation ---


class PytestAnalyzerService:
    """
    Main service for analyzing pytest test failures.

    This class coordinates the extraction and analysis of test failures,
    using different strategies based on the input type and settings.
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        llm_client: Optional[Any] = None,
        use_async: bool = False,
        batch_size: int = 5,
        max_concurrency: int = 10,
    ):
        """
        Initialize the test analyzer service.

        :param settings: Settings object
        :param llm_client: Optional client for language model API
        :param use_async: Whether to use async processing when possible
        :param batch_size: Number of failures to process in each batch
        :param max_concurrency: Maximum number of concurrent LLM requests
        """
        self.settings = settings or Settings()
        self.settings.use_llm = True  # Force LLM usage
        self.path_resolver = PathResolver(self.settings.project_root)
        self.analyzer = FailureAnalyzer(max_suggestions=self.settings.max_suggestions)

        # Async-related settings
        self.use_async = use_async
        self.batch_size = batch_size
        self.max_concurrency = max_concurrency

        # Check Git compatibility early on
        from ..utils.git_manager import confirm_git_setup
        self.git_available = False
        if self.settings.check_git:
            project_root = str(self.path_resolver.project_root)
            self.git_available = confirm_git_setup(project_root)
            logger.info(f"Git integration {'enabled' if self.git_available else 'disabled'}")

        # Always initialize LLM suggester - no rule-based suggester
        self.llm_suggester = LLMSuggester(
            llm_client=llm_client,
            min_confidence=self.settings.min_confidence,
            timeout_seconds=self.settings.llm_timeout,
            batch_size=batch_size,
            max_concurrency=max_concurrency
        )

        # Initialize fix applier for applying suggestions
        if self.git_available:
            from ..utils.git_fix_applier import GitFixApplier
            self.fix_applier = GitFixApplier(
                project_root=self.settings.project_root,
                verbose_test_output=False  # Default to quiet mode for validation
            )
        else:
            # Fallback to traditional file backup approach
            self.fix_applier = FixApplier(
                project_root=self.settings.project_root,
                backup_suffix=".pytest-analyzer.bak",
                verbose_test_output=False  # Default to quiet mode for validation
            )

        # Create our own event loop if running in async mode
        if self.use_async:
            try:
                asyncio.get_event_loop()
            except RuntimeError:
                # Create a new event loop if one doesn't exist
                asyncio.set_event_loop(asyncio.new_event_loop())

        logger.info(f"Async processing: {'enabled' if self.use_async else 'disabled'}")
        logger.info(f"Batch size: {self.batch_size}, Max concurrency: {self.max_concurrency}")

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
            # Get the appropriate extractor for the file type
            extractor = get_extractor(path, self.settings, self.path_resolver)

            # Extract failures
            failures = extractor.extract_failures(path)

            # Limit the number of failures to analyze
            if len(failures) > self.settings.max_failures:
                logger.warning(f"Found {len(failures)} failures, limiting to {self.settings.max_failures}")
                failures = failures[:self.settings.max_failures]

            # Generate suggestions for each failure
            return self._generate_suggestions(failures, use_async=self.use_async)

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
        task_id: Optional[TaskID] = None
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
                parent=task_id
            )

        try:
            # Create a copy of pytest args to avoid modifying the original
            args_copy = list(pytest_args) if pytest_args else []

            # Add quiet-related arguments if needed
            if quiet:
                # Suppress pytest output (using super quiet mode)
                if '-qq' not in args_copy:
                    # First remove any existing -q flags
                    args_copy = [arg for arg in args_copy if arg != '-q' and arg != '--quiet']
                    # Add super quiet mode flag
                    args_copy.append('-qq')
                # Add short traceback flag for cleaner output
                if '--tb=short' not in args_copy:
                    args_copy.append('--tb=short')
                # Disable warnings
                if '-W' not in args_copy and '--disable-warnings' not in args_copy:
                    args_copy.append('--disable-warnings')

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
                progress.update(pytest_task_id, description="[green]Pytest complete!", completed=True)

            return failures

        except Exception as e:
            # Update progress if active
            if progress and pytest_task_id is not None:
                progress.update(pytest_task_id, description=f"[red]Pytest failed: {e}", completed=True)

            logger.error(f"Error running tests: {e}")
            return []

    @with_timeout(300)
    def run_and_analyze(
        self,
        test_path: str,
        pytest_args: Optional[List[str]] = None,
        quiet: bool = False,
        use_async: Optional[bool] = None
    ) -> List[FixSuggestion]:
        """
        Run pytest on the given path and analyze the output.

        Args:
            test_path: Path to the directory or file to test
            pytest_args: Additional pytest arguments
            quiet: Whether to suppress output and logging
            use_async: Whether to use async processing (defaults to self.use_async)

        Returns:
            List of suggested fixes
        """
        # Prepare pytest arguments
        pytest_args = pytest_args or []

        # Import rich components
        from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
        from rich.console import Console

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
                pytest_args = [arg for arg in pytest_args if arg != '-q' and arg != '--quiet']
                # Add super quiet mode flag
                pytest_args.append("-qq")
            # Add short traceback flag for cleaner output
            if '--tb=short' not in pytest_args:
                pytest_args.append('--tb=short')

            # Create minimal progress display
            with Progress(
                SpinnerColumn(),
                TextColumn("[cyan]{task.description}"),
                console=console,
                transient=True  # Progress bars disappear when done
            ) as progress:
                # Create simplified task list
                main_task_id = progress.add_task("Running tests...", total=2)

                # Run pytest with minimal progress tracking
                failures = self.run_pytest_only(
                    test_path,
                    pytest_args,
                    quiet=quiet,
                    progress=progress,
                    task_id=main_task_id
                )

                progress.update(main_task_id, advance=1, description="Analyzing failures...")

                try:
                    # Limit the number of failures to analyze
                    if len(failures) > self.settings.max_failures:
                        failures = failures[:self.settings.max_failures]

                    # Group failures to detect common issues
                    if failures:
                        project_root = str(self.path_resolver.project_root) if self.path_resolver else None
                        from .analysis.failure_grouper import group_failures
                        failure_groups = group_failures(failures, project_root)

                        # Show minimal groups info
                        if len(failure_groups) < len(failures):
                            progress.update(main_task_id, description=f"Found {len(failure_groups)} distinct issues...")

                    # Generate suggestions with minimal progress tracking
                    suggestions = self._generate_suggestions(
                        failures,
                        quiet=quiet,
                        progress=progress,
                        parent_task_id=main_task_id,
                        use_async=use_async
                    )

                    progress.update(main_task_id, description="Analysis complete!", completed=True)
                    return suggestions

                except Exception as e:
                    progress.update(main_task_id, description=f"Error: {e}", completed=True)
                    logger.error(f"Error analyzing tests: {e}")
                    return []
        else:
            # Full progress display for normal mode
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TimeElapsedColumn(),
                console=console
            ) as progress:
                # Create main task
                main_task_id = progress.add_task("[cyan]Running tests...", total=2)

                # Run pytest with progress tracking
                failures = self.run_pytest_only(
                    test_path,
                    pytest_args,
                    quiet=quiet,
                    progress=progress,
                    task_id=main_task_id
                )

                progress.update(main_task_id, advance=1, description="[cyan]Analyzing failures...")

                try:
                    # Limit the number of failures to analyze
                    if len(failures) > self.settings.max_failures:
                        logger.warning(f"Found {len(failures)} failures, limiting to {self.settings.max_failures}")
                        failures = failures[:self.settings.max_failures]

                    # Generate suggestions with progress tracking
                    suggestions = self._generate_suggestions(
                        failures,
                        quiet=quiet,
                        progress=progress,
                        parent_task_id=main_task_id,
                        use_async=use_async
                    )

                    progress.update(main_task_id, description="[green]Analysis complete!", completed=True)
                    return suggestions

                except Exception as e:
                    progress.update(main_task_id, description=f"[red]Error analyzing tests: {e}", completed=True)
                    logger.error(f"Error analyzing tests: {e}")
                    return []

    def _run_and_extract_json(self, test_path: str, pytest_args: Optional[List[str]] = None) -> List[PytestFailure]:
        """
        Run pytest with JSON output and extract failures.

        Args:
            test_path: Path to the directory or file to test
            pytest_args: Additional pytest arguments

        Returns:
            List of test failures
        """
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as tmp:
            json_report_path = tmp.name # Store path before closing

        try:
            args = pytest_args or []
            cmd = ['pytest', test_path, '--json-report', f'--json-report-file={json_report_path}']

            # Important: we need to extend args after defining base command to allow
            # custom args to override the defaults if needed
            cmd.extend(args)

            # Determine if we're in quiet mode
            quiet_mode = '-q' in args or '-qq' in args or '--quiet' in args
            # Determine if we want to show progress (requires -s to avoid pytest capturing output)
            progress_mode = not quiet_mode and ('-s' in args or '--capture=no' in args)

            if quiet_mode:
                # When in quiet mode, redirect output to devnull
                with open(os.devnull, 'w') as devnull:
                    # Run pytest with a timeout, redirecting output to devnull
                    subprocess.run(
                        cmd,
                        timeout=self.settings.pytest_timeout,
                        check=False,
                        stdout=devnull,
                        stderr=devnull
                    )
            elif progress_mode:
                # With progress mode enabled, make sure the output isn't being captured
                from rich.console import Console
                console = Console()
                console.print("[cyan]Running pytest with JSON report...[/cyan]")

                # Run pytest with normal output, needed for rich progress display
                result = subprocess.run(
                    cmd,
                    timeout=self.settings.pytest_timeout,
                    check=False
                )

                if result.returncode != 0 and not quiet_mode:
                    console.print(f"[yellow]Pytest exited with code {result.returncode}[/yellow]")
            else:
                # Run pytest with a timeout, normal output but no special progress display
                subprocess.run(cmd, timeout=self.settings.pytest_timeout, check=False)

            # Extract failures from JSON output
            extractor = get_extractor(Path(json_report_path), self.settings, self.path_resolver)
            return extractor.extract_failures(Path(json_report_path))

        except subprocess.TimeoutExpired:
            logger.error(f"Pytest execution timed out after {self.settings.pytest_timeout} seconds")
            return []
        finally:
            # Ensure temporary file is deleted
            if os.path.exists(json_report_path):
                os.remove(json_report_path)


    def _run_and_extract_xml(self, test_path: str, pytest_args: Optional[List[str]] = None) -> List[PytestFailure]:
        """
        Run pytest with XML output and extract failures.

        Args:
            test_path: Path to the directory or file to test
            pytest_args: Additional pytest arguments

        Returns:
            List of test failures
        """
        with tempfile.NamedTemporaryFile(suffix='.xml', delete=False) as tmp:
            xml_report_path = tmp.name # Store path before closing

        try:
            args = pytest_args or []
            cmd = ['pytest', test_path, f'--junit-xml={xml_report_path}']

            # Important: we need to extend args after defining base command to allow
            # custom args to override the defaults if needed
            cmd.extend(args)

            # Determine if we're in quiet mode
            quiet_mode = '-q' in args or '-qq' in args or '--quiet' in args
            # Determine if we want to show progress (requires -s to avoid pytest capturing output)
            progress_mode = not quiet_mode and ('-s' in args or '--capture=no' in args)

            if quiet_mode:
                # When in quiet mode, redirect output to devnull
                with open(os.devnull, 'w') as devnull:
                    # Run pytest with a timeout, redirecting output to devnull
                    subprocess.run(
                        cmd,
                        timeout=self.settings.pytest_timeout,
                        check=False,
                        stdout=devnull,
                        stderr=devnull
                    )
            elif progress_mode:
                # With progress mode enabled, make sure the output isn't being captured
                from rich.console import Console
                console = Console()
                console.print("[cyan]Running pytest with XML report...[/cyan]")

                # Run pytest with normal output, needed for rich progress display
                result = subprocess.run(
                    cmd,
                    timeout=self.settings.pytest_timeout,
                    check=False
                )

                if result.returncode != 0 and not quiet_mode:
                    console.print(f"[yellow]Pytest exited with code {result.returncode}[/yellow]")
            else:
                # Run pytest with a timeout, normal output but no special progress display
                subprocess.run(cmd, timeout=self.settings.pytest_timeout, check=False)

            # Extract failures from XML output
            extractor = get_extractor(Path(xml_report_path), self.settings, self.path_resolver)
            return extractor.extract_failures(Path(xml_report_path))

        except subprocess.TimeoutExpired:
            logger.error(f"Pytest execution timed out after {self.settings.pytest_timeout} seconds")
            return []
        finally:
            # Ensure temporary file is deleted
            if os.path.exists(xml_report_path):
                os.remove(xml_report_path)

    def _generate_suggestions(
        self,
        failures: List[PytestFailure],
        quiet: bool = False,
        progress: Optional[Progress] = None,
        parent_task_id: Optional[TaskID] = None,
        use_async: Optional[bool] = None
    ) -> List[FixSuggestion]:
        """
        Generate fix suggestions for the given failures using LLM-based approach.

        This method uses LLM to generate suggestions for test failures.
        It groups similar failures to avoid redundant LLM calls for efficiency.

        :param failures: List of test failures
        :param quiet: Whether to suppress logging output
        :param progress: Optional Progress object for showing progress
        :param parent_task_id: Optional parent task ID for progress tracking
        :param use_async: Override for async processing setting (defaults to self.use_async)
        :return: List of suggested fixes
        """
        with performance_tracker.track("generate_suggestions"):
            # Determine whether to use async processing
            should_use_async = self.use_async if use_async is None else use_async

            # Use async processing if enabled
            if should_use_async:
                # Run the async version and get results from the event loop
                try:
                    loop = asyncio.get_event_loop()
                    return loop.run_until_complete(
                        self._async_generate_suggestions(
                            failures=failures,
                            quiet=quiet,
                            progress=progress,
                            parent_task_id=parent_task_id
                        )
                    )
                except Exception as e:
                    logger.error(f"Error in async suggestions generation, falling back to sync: {e}")
                    should_use_async = False  # Fall back to synchronous processing

            # Use synchronous processing
            if not should_use_async:
                return self._sync_generate_suggestions(
                    failures=failures,
                    quiet=quiet,
                    progress=progress,
                    parent_task_id=parent_task_id
                )
            # Add a default return in case logic fails (should not happen)
            return []

    def _sync_generate_suggestions(
        self,
        failures: List[PytestFailure],
        quiet: bool = False,
        progress: Optional[Progress] = None,
        parent_task_id: Optional[TaskID] = None
    ) -> List[FixSuggestion]:
        """
        Generate fix suggestions synchronously for the given failures.

        :param failures: List of test failures
        :param quiet: Whether to suppress logging output
        :param progress: Optional Progress object for showing progress
        :param parent_task_id: Optional parent task ID for progress tracking
        :return: List of suggested fixes
        """
        with performance_tracker.track("sync_generate_suggestions"):
            all_suggestions = []

            # Return early if there are no failures to analyze
            if not failures:
                return all_suggestions

            # Add task for LLM-based suggestions if progress is active
            llm_task_id: Optional[TaskID] = None
            # Note: Re-initializing llm_task_id here, as it might be set later
            # if failure_groups exist.

            # Group similar failures to avoid redundant LLM calls
            try:
                # Add task for grouping if progress is active
                group_task_id: Optional[TaskID] = None
                if progress and parent_task_id is not None:
                    group_task_id = progress.add_task(
                        "[cyan]Grouping similar failures...",
                        total=1,
                        parent=parent_task_id
                    )

                with performance_tracker.track("failure_grouping"):
                    # Group similar failures to avoid redundant LLM calls
                    project_root = str(self.path_resolver.project_root) if self.path_resolver else None
                    failure_groups = group_failures(failures, project_root)

                # Mark grouping task complete if active
                if progress and group_task_id is not None:
                    progress.update(
                        group_task_id,
                        description=f"[green]Grouped {len(failures)} failures into {len(failure_groups)} distinct groups",
                        completed=True
                    )

                if not quiet:
                    logger.info(f"Grouped {len(failures)} failures into {len(failure_groups)} distinct groups")

                # Add task for LLM suggestions if progress is active and groups exist
                if progress and parent_task_id is not None and failure_groups:
                    llm_task_id = progress.add_task(
                        "[cyan]Getting LLM suggestions...",
                        total=len(failure_groups),
                        parent=parent_task_id
                    )

                with performance_tracker.track("process_failure_groups"):
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
                                description=f"[cyan]Getting LLM suggestion {i+1}/{len(failure_groups)}: {representative.test_name}"
                            )

                        if not quiet:
                            logger.info(f"Generating LLM suggestions for group: {fingerprint} ({len(group)} similar failures)")
                            logger.info(f"Representative test: {representative.test_name}")

                        # Generate suggestions for the representative failure
                        try:
                            with performance_tracker.track(f"llm_suggestion_{i}"):
                                with ResourceMonitor(max_time_seconds=self.settings.llm_timeout):
                                    llm_suggestions = self.llm_suggester.suggest_fixes(representative)

                                    # Create a FixSuggestion for each failure in the group using the same solution
                                    for suggestion in llm_suggestions:
                                        # Mark the suggestion as LLM-based
                                        if not suggestion.code_changes:
                                            suggestion.code_changes = {}
                                        suggestion.code_changes['source'] = 'llm'

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
                                                    code_changes=dict(suggestion.code_changes) if suggestion.code_changes else None
                                                )
                                                all_suggestions.append(duplicate_suggestion)
                        except Exception as e:
                            logger.error(f"Error generating LLM suggestions for group {fingerprint}: {e}")

                        # Update progress after LLM call if active
                        if progress and llm_task_id is not None:
                            progress.advance(llm_task_id)

                # Mark LLM task complete if active
                if progress and llm_task_id is not None:
                    progress.update(
                        llm_task_id,
                        description="[green]LLM suggestions complete",
                        completed=True
                    )

            except Exception as e:
                logger.error(f"Error during failure grouping: {e}")

            with performance_tracker.track("post_processing"):
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
                            suggestions[:self.settings.max_suggestions_per_failure]
                        )
                    return limited_suggestions

            return all_suggestions

    @async_with_timeout(300)
    async def _async_generate_suggestions(
        self,
        failures: List[PytestFailure],
        quiet: bool = False,
        progress: Optional[Progress] = None,
        parent_task_id: Optional[TaskID] = None
    ) -> List[FixSuggestion]:
        """
        Generate fix suggestions asynchronously for the given failures.

        This method processes multiple failure groups in parallel for better performance.
        It uses a state machine approach for clear separation of concerns and improved
        error handling.

        Args:
            failures: List of test failures
            quiet: Whether to suppress logging output
            progress: Optional Progress object for showing progress
            parent_task_id: Optional parent task ID for progress tracking

        Returns:
            List of suggested fixes

        Note:
            The method has a timeout of 300 seconds. If the process takes longer,
            it will be interrupted and partial results may be returned.
        """
        async with performance_tracker.async_track("async_generate_suggestions"):
            # Create state machine context
            context = Context(
                failures=failures,
                quiet=quiet,
                progress=progress,
                parent_task_id=parent_task_id,
                path_resolver=self.path_resolver,
                settings=self.settings,
                llm_suggester=self.llm_suggester,
                logger=logger, # Use module-level logger
                performance_tracker=performance_tracker # Use global tracker
            )

            try:
                # Start the state machine
                await context.transition_to(Initialize)

                # Wait for execution to complete using the event
                await context.execution_complete_event.wait()

                # If there was an error, log it
                if context.final_error:
                    logger.error(f"State machine execution failed: {context.final_error}")

            except asyncio.TimeoutError:
                # Handle timeout from the async_with_timeout decorator
                logger.warning(
                    f"Async suggestion generation timed out after 300 seconds. "
                    f"Returning partial results. Consider adjusting parameters."
                )
                # Ensure progress tasks are cleaned up
                context.cleanup_progress_tasks()

            except Exception as e:
                # Handle any uncaught exceptions
                logger.error(f"Unhandled error in async suggestion generation: {e}")
                context.cleanup_progress_tasks()

            # Return results from context (even if partial due to errors)
            return context.all_suggestions

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
        with performance_tracker.track("apply_suggestion"):
            if not hasattr(suggestion, 'failure') or not suggestion.failure:
                return FixApplicationResult(
                    success=False,
                    message="Cannot apply fix: Missing original failure information.",
                    applied_files=[],
                    rolled_back_files=[]
                )

            if not suggestion.code_changes:
                return FixApplicationResult(
                    success=False,
                    message="Cannot apply fix: No code changes provided in suggestion.",
                    applied_files=[],
                    rolled_back_files=[]
                )

            # Filter code_changes to include only file paths (not metadata)
            code_changes_to_apply = {}
            for key, value in suggestion.code_changes.items():
                # Skip metadata keys like 'source' and 'fingerprint'
                # Check if key looks like a file path (contains path separators)
                # This is a heuristic and might need refinement based on actual keys
                if isinstance(key, str) and ('/' in key or '\\' in key):
                     # Skip empty values
                    if not value:
                        continue
                    # Include valid file paths with content
                    code_changes_to_apply[key] = value
                else:
                    # Log skipped keys for debugging if needed
                    # logger.debug(f"Skipping non-file key in code_changes: {key}")
                    pass


            if not code_changes_to_apply:
                return FixApplicationResult(
                    success=False,
                    message="Cannot apply fix: No valid file changes found in suggestion.",
                    applied_files=[],
                    rolled_back_files=[]
                )

            # Determine which tests to run for validation
            tests_to_validate = []
            if hasattr(suggestion, 'validation_tests') and suggestion.validation_tests:
                tests_to_validate = suggestion.validation_tests
            elif hasattr(suggestion.failure, 'test_name') and suggestion.failure.test_name:
                # Use the original failing test for validation
                tests_to_validate = [suggestion.failure.test_name]
            else:
                logger.warning("Could not determine specific tests for validation. Proceeding without test validation.")

            # Log the application attempt
            logger.info(f"Attempting to apply fix for failure: {getattr(suggestion.failure, 'test_name', 'Unknown Test')}")
            logger.info(f"Modifying files: {list(code_changes_to_apply.keys())}")
            logger.info(f"Validating with tests: {tests_to_validate}")

            # Apply the fix (using quiet test output by default)
            with performance_tracker.track("fix_application"):
                result = self.fix_applier.apply_fix(
                    code_changes_to_apply,
                    tests_to_validate,
                    verbose_test_output=False  # Use quiet mode for validation tests
                )

            # Log the result
            if result.success:
                logger.info(f"Successfully applied fix to: {[str(p) for p in result.applied_files]}")
            else:
                logger.error(f"Failed to apply fix: {result.message}")
                if result.rolled_back_files:
                    logger.info(f"Rolled back changes in: {[str(p) for p in result.rolled_back_files]}")

            return result

    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics for all operations performed by the analyzer.

        This method returns detailed metrics about the performance of various
        operations, including timing information and success rates.

        Returns:
            Dictionary of performance metrics
        """
        return performance_tracker.get_metrics()

    def generate_performance_report(self) -> str:
        """
        Generate a human-readable performance report.

        This method returns a formatted string with performance metrics
        for all operations performed by the analyzer.

        Returns:
            Formatted string with performance report
        """
        return performance_tracker.report()

    def reset_performance_metrics(self) -> None:
        """
        Reset all performance metrics.

        This method clears all tracked performance metrics,
        which can be useful between different runs.
        """
        performance_tracker.reset()
