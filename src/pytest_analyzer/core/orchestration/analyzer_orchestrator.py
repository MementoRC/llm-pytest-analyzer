import asyncio
import logging
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional, Type, TypeVar

from rich.progress import Progress, TaskID

from ...utils.path_resolver import PathResolver
from ...utils.resource_manager import AsyncResourceMonitor, performance_tracker
from ...utils.settings import Settings
from ..analysis.failure_grouper import group_failures, select_representative_failure
from ..analysis.llm_suggester import LLMSuggester
from ..domain.entities.fix_suggestion import FixSuggestion
from ..domain.entities.pytest_failure import PytestFailure
from ..interfaces.protocols import Orchestrator, ProgressManager
from ..progress.progress_manager import RichProgressManager

logger = logging.getLogger(__name__)

# Type variable for the state class
S = TypeVar("S", bound="State")


# Custom exception hierarchy
class OrchestrationError(Exception):
    """Base exception class for orchestrator states."""


class InitializationError(OrchestrationError):
    """Raised during initialization errors."""


class FailureGroupingError(OrchestrationError):
    """Raised when failing to group failures."""


class RepresentativeSelectionError(OrchestrationError):
    """Raised when failing to select representative failures."""


class BatchProcessingError(OrchestrationError):
    """Raised during batch processing issues."""


class PostProcessingError(OrchestrationError):
    """Raised during post-processing issues."""


class State(ABC):
    """Base class for all states in the state machine."""

    def __init__(self, context: "Context"):
        self.context = context

    @abstractmethod
    async def run(self) -> None:
        """Execute the state's logic."""
        pass

    async def handle_error(self, error: Exception) -> None:
        """
        Handle error that occurred during state execution.
        By default, transitions to ErrorState but can be overridden.
        """
        if isinstance(error, OrchestrationError):
            self.context.log_error(f"{error.__class__.__name__}: {error}")
        else:
            self.context.log_error(
                f"Unexpected error in {self.__class__.__name__}: {error}"
            )
        await self.context.transition_to(ErrorState)


class Context:
    """
    Context for the state machine, containing all shared data and dependencies.
    """

    def __init__(
        self,
        failures: List[PytestFailure],
        quiet: bool,
        progress_manager: ProgressManager,
        path_resolver: PathResolver,
        settings: Settings,
        llm_suggester: LLMSuggester,
        logger: logging.Logger,
        performance_tracker: Any,
    ):
        self.failures = failures
        self.quiet = quiet
        self.progress_manager = progress_manager
        self.path_resolver = path_resolver
        self.settings = settings
        self.llm_suggester = llm_suggester
        self.logger = logger
        self.performance_tracker = performance_tracker

        self.all_suggestions: List[FixSuggestion] = []
        self.failure_groups: Dict[str, List[PytestFailure]] = {}
        self.representative_failures: List[PytestFailure] = []
        self.group_mapping: Dict[str, List[PytestFailure]] = {}

        self.state: Optional[State] = None
        self.execution_complete = False
        self.execution_complete_event = asyncio.Event()
        self.final_error: Optional[Exception] = None

    async def transition_to(self, state_cls: Type[S]) -> None:
        """Transition to a new state and run it."""
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
        self.logger.debug(message)

    def log_info(self, message: str) -> None:
        if not self.quiet:
            self.logger.info(message)

    def log_error(self, message: str) -> None:
        self.logger.error(message)

    def log_warning(self, message: str) -> None:
        self.logger.warning(message)

    def mark_llm_async(self, suggestion: FixSuggestion) -> FixSuggestion:
        """Mark a suggestion as coming from asynchronous LLM processing."""
        # Add source to metadata instead of code_changes
        suggestion.add_metadata("source", "llm_async")
        return suggestion

    @asynccontextmanager
    async def track_performance(self, operation_name: str):
        """Context manager for tracking performance of an operation."""
        async with self.performance_tracker.async_track(operation_name):
            yield


class Initialize(State):
    """Initial state that sets up progress tracking."""

    async def run(self) -> None:
        if not self.context.failures:
            self.context.progress_manager.cleanup_tasks()
            self.context.mark_execution_complete()
            return
        try:
            self.context.progress_manager.create_task(
                "llm",
                "[cyan]Generating async LLM-based suggestions...",
                total=len(self.context.failures),
            )
            await self.context.transition_to(GroupFailures)
        except Exception as e:
            raise InitializationError(
                f"Failed to initialize suggestion generation: {e}"
            ) from e


class GroupFailures(State):
    """Groups similar failures to reduce redundant LLM calls."""

    async def run(self) -> None:
        self.context.progress_manager.create_task(
            "grouping", "[cyan]Grouping similar failures...", total=1
        )
        try:
            async with self.context.track_performance("async_failure_grouping"):
                project_root = (
                    str(self.context.path_resolver.project_root)
                    if self.context.path_resolver
                    else None
                )
                self.context.failure_groups = group_failures(
                    self.context.failures, project_root
                )
            self.context.progress_manager.update_task(
                "grouping",
                f"[green]Grouped {len(self.context.failures)} into {len(self.context.failure_groups)} distinct groups",
                completed=True,
            )
            self.context.log_info(
                f"Grouped {len(self.context.failures)} failures into {len(self.context.failure_groups)} distinct groups"
            )
            if self.context.failure_groups:
                await self.context.transition_to(PrepareRepresentatives)
            else:
                self.context.log_info(
                    "No failure groups found, skipping to post-processing"
                )
                await self.context.transition_to(PostProcess)
        except Exception as e:
            raise FailureGroupingError(f"Error grouping failures: {e}") from e


class PrepareRepresentatives(State):
    """Prepares representative failures for batch processing."""

    async def run(self) -> None:
        try:
            for fingerprint, group in self.context.failure_groups.items():
                if not group:
                    continue
                representative = select_representative_failure(group)
                if representative is None:
                    continue
                self.context.representative_failures.append(representative)
                # Store mapping from representative failure ID to the full group
                self.context.group_mapping[representative.id] = group

            self.context.progress_manager.create_task(
                "batch_processing",
                f"[cyan]Processing {len(self.context.representative_failures)} failure groups in parallel...",
                total=len(
                    self.context.representative_failures
                ),  # Total should be number of representatives
            )
            self.context.log_info(
                f"Processing {len(self.context.representative_failures)} failure groups with "
                f"batch_size={self.context.settings.batch_size}, "
                f"concurrency={self.context.settings.max_concurrency}. "
                "Note: High values may impact system resources and LLM backend performance."
            )
            await self.context.transition_to(BatchProcess)
        except Exception as e:
            raise RepresentativeSelectionError(
                f"Error preparing representative failures: {e}"
            ) from e


class BatchProcess(State):
    """Processes representative failures in batches to generate suggestions."""

    async def run(self) -> None:
        try:
            async with self.context.track_performance("batch_process_failures"):
                async with AsyncResourceMonitor(
                    max_time_seconds=self.context.settings.llm_timeout
                ):
                    # batch_suggest_fixes returns Dict[str, List[FixSuggestion]] where key is failure_id
                    suggestions_by_failure_id = (
                        await self.context.llm_suggester.batch_suggest_fixes(
                            self.context.representative_failures
                        )
                    )

                    processed_count = 0
                    for representative in self.context.representative_failures:
                        suggestions = suggestions_by_failure_id.get(
                            representative.id, []
                        )
                        group = self.context.group_mapping.get(representative.id, [])

                        if suggestions and group:
                            await self._process_suggestions_for_group(
                                representative, group, suggestions
                            )
                        processed_count += 1
                        self.context.progress_manager.update_task(
                            "batch_processing", advance=1
                        )

            self.context.progress_manager.update_task(
                "batch_processing",
                f"[green]Completed processing {len(self.context.representative_failures)} failure groups",
                completed=True,
            )
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
        suggestions: List[FixSuggestion],  # Suggestions are for the representative
    ) -> None:
        """Distribute suggestions from the representative to all failures in the group."""
        for suggestion in suggestions:
            # Add the original suggestion for the representative
            self.context.all_suggestions.append(self.context.mark_llm_async(suggestion))

            # Create duplicates for other failures in the group
            for other_failure in group:
                if other_failure.id != representative.id:  # Use ID for comparison
                    # Create a new suggestion entity for the duplicate
                    duplicate_suggestion = FixSuggestion.create(
                        failure_id=other_failure.id,  # Link to the other failure's ID
                        suggestion_text=suggestion.suggestion_text,
                        confidence=suggestion.confidence,
                        explanation=suggestion.explanation,
                        code_changes=list(suggestion.code_changes),  # Copy the list
                        alternative_approaches=list(
                            suggestion.alternative_approaches
                        ),  # Copy the list
                        metadata=dict(suggestion.metadata),  # Copy the dict
                    )
                    self.context.all_suggestions.append(
                        self.context.mark_llm_async(duplicate_suggestion)
                    )


class PostProcess(State):
    """Post-processes suggestions (sorting and limiting)."""

    async def run(self) -> None:
        try:
            async with self.context.track_performance("async_post_processing"):
                # Sort by confidence (descending)
                self.context.all_suggestions.sort(
                    key=lambda s: s.confidence, reverse=True
                )
                if self.context.settings.max_suggestions_per_failure > 0:
                    self._limit_suggestions_per_failure()
            self.context.mark_execution_complete()
        except Exception as e:
            raise PostProcessingError(f"Error in post-processing: {e}") from e

    def _limit_suggestions_per_failure(self) -> None:
        suggestions_by_failure_id: Dict[str, List[FixSuggestion]] = {}
        for suggestion in self.context.all_suggestions:
            failure_id = suggestion.failure_id  # Use failure_id
            if failure_id not in suggestions_by_failure_id:
                suggestions_by_failure_id[failure_id] = []
            suggestions_by_failure_id[failure_id].append(suggestion)

        limited_suggestions = []
        for suggestions in suggestions_by_failure_id.values():
            # Suggestions are already sorted by confidence from the previous step
            limited_suggestions.extend(
                suggestions[: self.context.settings.max_suggestions_per_failure]
            )
        self.context.all_suggestions = limited_suggestions


class ErrorState(State):
    """Handles error conditions and performs cleanup."""

    async def run(self) -> None:
        self.context.progress_manager.cleanup_tasks()
        self.context.log_warning(
            "Error encountered during async suggestion generation. Moving to post-processing with partial results."
        )
        # Transition to PostProcess to allow cleanup and return partial results
        await self.context.transition_to(PostProcess)


class AnalyzerOrchestrator(Orchestrator):
    """Orchestrates the analysis process using a state machine."""

    def __init__(
        self,
        path_resolver: PathResolver,
        settings: Settings,
        llm_suggester: LLMSuggester,
    ):
        self.path_resolver = path_resolver
        self.settings = settings
        self.llm_suggester = llm_suggester

    async def generate_suggestions(
        self,
        failures: List[PytestFailure],
        quiet: bool = False,
        progress: Optional[Progress] = None,
        parent_task_id: Optional[TaskID] = None,
    ) -> List[FixSuggestion]:
        async with performance_tracker.async_track("async_generate_suggestions"):
            # RichProgressManager requires a rich.Progress instance, which is optional here.
            # If not provided, it operates in a 'quiet' mode where tasks are not added/updated.
            # The Context needs a ProgressManager instance regardless.
            progress_manager = RichProgressManager(progress, parent_task_id, quiet)
            context = Context(
                failures=failures,
                quiet=quiet,
                progress_manager=progress_manager,
                path_resolver=self.path_resolver,
                settings=self.settings,
                llm_suggester=self.llm_suggester,
                logger=logger,
                performance_tracker=performance_tracker,
            )
            try:
                await context.transition_to(Initialize)
                # Wait for the state machine execution to complete
                await context.execution_complete_event.wait()
                if context.final_error:
                    # Re-raise the final error if one occurred, after cleanup
                    raise context.final_error
            except asyncio.TimeoutError:
                logger.warning(
                    "Async suggestion generation timed out. Returning partial results."
                )
                # Cleanup tasks if timeout happens outside the state machine's error handling
                context.progress_manager.cleanup_tasks()
            except Exception as e:
                # Catch any unhandled exceptions from the state machine or orchestrator itself
                logger.error(f"Unhandled error in async suggestion generation: {e}")
                context.progress_manager.cleanup_tasks()
                # Decide whether to re-raise or return partial results.
                # For now, let's return partial results and log the error.
                # raise e # Option to re-raise
            return context.all_suggestions
