"""
Asynchronous state machine for orchestrating the failure analysis process.

This module defines the states, context, and transitions for a robust,
asynchronous pipeline that processes test failures, groups them, generates
suggestions using LLMs, and post-processes the results.
"""

import abc
import asyncio
import dataclasses
import logging
import uuid
from typing import Any, Dict, List, Optional, Type

from ...utils.path_resolver import PathResolver
from ...utils.resource_manager import AsyncResourceMonitor, PerformanceTracker
from ...utils.settings import Settings
from ..analysis.failure_grouper import group_failures, select_representative_failure
from ..analysis.llm_suggester import LLMSuggester
from ..domain.entities.fix_suggestion import FixSuggestion
from ..domain.entities.pytest_failure import PytestFailure
from ..progress.progress_manager import RichProgressManager

logger = logging.getLogger(__name__)


# --- Custom Errors ---
class OrchestrationError(Exception):
    """Base exception for state machine orchestration errors."""


class InitializationError(OrchestrationError):
    """Error during initialization state."""


class FailureGroupingError(OrchestrationError):
    """Error during failure grouping state."""


class RepresentativeSelectionError(OrchestrationError):
    """Error during representative selection state."""


class BatchProcessingError(OrchestrationError):
    """Error during batch processing of failures state."""


class PostProcessingError(OrchestrationError):
    """Error during post-processing state."""


# --- State Machine Core ---


class State(abc.ABC):
    """Abstract base class for a state in the state machine."""

    def __init__(self, context: "Context"):
        self.context = context

    @abc.abstractmethod
    async def _run(self) -> None:
        """Contains the specific logic for the state."""
        raise NotImplementedError

    async def run(self) -> None:
        """
        Executes the state's logic with centralized error handling.
        This should be called by the context, not overridden.
        """
        try:
            await self._run()
        except Exception as e:
            await self.handle_error(e)

    async def handle_error(self, error: Exception) -> None:
        """
        Handles errors that occur within the state's run logic.
        Logs the error and transitions to the ErrorState.
        """
        if isinstance(error, OrchestrationError):
            self.context.logger.error(f"{type(error).__name__}: {error}")
        else:
            self.context.logger.error(
                f"Unexpected error in {type(self).__name__}: {error}"
            )

        self.context.final_error = error
        await self.context.transition_to(ErrorState)


class Context:
    """
    Holds the shared state and data for the state machine.
    Also acts as the runner for the state machine.
    """

    def __init__(
        self,
        failures: List[PytestFailure],
        quiet: bool,
        progress_manager: RichProgressManager,
        path_resolver: PathResolver,
        settings: Settings,
        llm_suggester: LLMSuggester,
        logger: logging.Logger,
        performance_tracker: PerformanceTracker,
    ):
        self.failures = failures
        self.quiet = quiet
        self.progress_manager = progress_manager
        self.path_resolver = path_resolver
        self.settings = settings
        self.llm_suggester = llm_suggester
        self.logger = logger
        self.performance_tracker = performance_tracker

        self.state: Optional[State] = None
        self.execution_complete_event = asyncio.Event()
        self.execution_complete = False
        self.final_error: Optional[Exception] = None

        # Data passed between states
        self.failure_groups: Dict[str, List[PytestFailure]] = {}
        self.representative_failures: List[PytestFailure] = []
        self.group_mapping: Dict[str, List[PytestFailure]] = {}
        self.all_suggestions: List[FixSuggestion] = []

    async def transition_to(self, state_class: Type[State]) -> None:
        """Transitions the context to a new state and runs it."""
        self.state = state_class(self)
        await self.state.run()

    def mark_execution_complete(self) -> None:
        """Marks the execution as complete and signals the event."""
        self.execution_complete = True
        self.execution_complete_event.set()

    def track_performance(self, name: str) -> Any:
        """Helper to track performance of a code block."""
        return self.performance_tracker.async_track(name)


# --- State Implementations ---


class Initialize(State):
    """Initial state: sets up progress bars and checks for failures."""

    async def _run(self) -> None:
        async with self.context.track_performance("initialize"):
            if not self.context.failures:
                self.context.logger.info("No failures to analyze.")
                self.context.progress_manager.cleanup_tasks()
                self.context.mark_execution_complete()
                return

            self.context.progress_manager.create_task(
                "llm",
                "[cyan]Generating async LLM-based suggestions...",
                total=len(self.context.failures),
            )
        await self.context.transition_to(GroupFailures)


class GroupFailures(State):
    """Groups similar failures together to reduce redundant analysis."""

    async def _run(self) -> None:
        task_key = "grouping"
        self.context.progress_manager.create_task(
            task_key, "[cyan]Grouping similar failures...", total=1
        )
        async with self.context.track_performance("group_failures"):
            try:
                self.context.failure_groups = group_failures(
                    self.context.failures, str(self.context.path_resolver.project_root)
                )
                num_groups = len(self.context.failure_groups)
                self.context.progress_manager.update_task(
                    task_key,
                    description=f"[green]Grouped {len(self.context.failures)} into {num_groups} distinct groups",
                    completed=True,
                )
            except Exception as e:
                raise FailureGroupingError(f"Failed to group failures: {e}") from e

        if not self.context.failure_groups:
            await self.context.transition_to(PostProcess)
        else:
            await self.context.transition_to(PrepareRepresentatives)


class PrepareRepresentatives(State):
    """Selects a representative failure from each group for analysis."""

    async def _run(self) -> None:
        task_key = "batch_processing"
        async with self.context.track_performance("prepare_representatives"):
            try:
                for group in self.context.failure_groups.values():
                    representative = select_representative_failure(group)
                    self.context.representative_failures.append(representative)
                    self.context.group_mapping[representative.id] = group
            except Exception as e:
                raise RepresentativeSelectionError(
                    f"Failed to select representatives: {e}"
                ) from e

        self.context.progress_manager.create_task(
            task_key,
            f"[cyan]Processing {len(self.context.representative_failures)} failure groups in parallel...",
            total=len(self.context.representative_failures),
        )
        await self.context.transition_to(BatchProcess)


class BatchProcess(State):
    """Processes failure groups in batches to generate suggestions via LLM."""

    async def _run(self) -> None:
        task_key = "batch_processing"
        try:
            async with AsyncResourceMonitor(
                max_time_seconds=self.context.settings.llm_timeout
            ):
                async with self.context.track_performance("batch_process_llm"):
                    results = await self.context.llm_suggester.batch_suggest_fixes(
                        self.context.representative_failures
                    )

                    for rep_id, suggestions in results.items():
                        group = self.context.group_mapping.get(rep_id)
                        if not group:
                            continue

                        for original_failure in group:
                            for suggestion in suggestions:
                                new_suggestion = dataclasses.replace(
                                    suggestion,
                                    id=str(uuid.uuid4()),
                                    failure_id=original_failure.id,
                                )
                                new_suggestion.metadata["source"] = "llm_async"
                                self.context.all_suggestions.append(new_suggestion)

                        self.context.progress_manager.update_task(task_key, advance=1)

        except asyncio.TimeoutError:
            msg = (
                f"Batch processing timed out after {self.context.settings.llm_timeout} seconds. "
                "Consider adjusting the timeout or reducing batch size/concurrency."
            )
            self.context.logger.warning(msg)
            raise BatchProcessingError("LLM request timed out") from None
        except Exception as e:
            raise BatchProcessingError(f"Error in batch processing: {e}") from e

        self.context.progress_manager.update_task(
            task_key,
            description=f"[green]Completed processing {len(self.context.representative_failures)} failure groups",
            completed=True,
        )
        await self.context.transition_to(PostProcess)


class PostProcess(State):
    """Final state: sorts and filters suggestions before finishing."""

    async def _run(self) -> None:
        try:
            async with self.context.track_performance("post_process"):
                limit = self.context.settings.max_suggestions_per_failure
                if limit > 0:
                    suggestions_by_failure: Dict[str, List[FixSuggestion]] = {}
                    for s in self.context.all_suggestions:
                        suggestions_by_failure.setdefault(s.failure_id, []).append(s)

                    final_suggestions = []
                    for _, suggestions in suggestions_by_failure.items():
                        sorted_suggestions = sorted(
                            suggestions, key=lambda s: s.confidence, reverse=True
                        )
                        final_suggestions.extend(sorted_suggestions[:limit])
                    self.context.all_suggestions = final_suggestions
                else:
                    # Sort all suggestions by confidence if no per-failure limit
                    self.context.all_suggestions.sort(
                        key=lambda s: s.confidence, reverse=True
                    )
        except Exception as e:
            raise PostProcessingError(f"Error in post-processing: {e}") from e
        finally:
            self.context.mark_execution_complete()


class ErrorState(State):
    """A terminal state for handling errors, allowing graceful shutdown."""

    async def _run(self) -> None:
        self.context.logger.warning(
            "Error encountered during async suggestion generation. "
            "Moving to post-processing with partial results."
        )
        self.context.progress_manager.cleanup_tasks()
        await self.context.transition_to(PostProcess)


# --- Orchestrator Implementation ---


class AnalyzerOrchestrator:
    """
    Main orchestrator that manages the state machine for failure analysis.
    This class provides the main interface for running the analysis pipeline.
    Implements the Orchestrator protocol expected by PytestAnalyzerService.
    """

    def __init__(
        self,
        path_resolver: PathResolver,
        settings: Settings,
        llm_suggester: LLMSuggester,
    ):
        self.path_resolver = path_resolver
        self.settings = settings
        self.llm_suggester = llm_suggester
        self.logger = logging.getLogger(__name__)
        self.context: Optional[Context] = None

    async def generate_suggestions(
        self,
        failures: List[PytestFailure],
        quiet: bool = False,
        progress: Optional[Any] = None,
        parent_task_id: Optional[Any] = None,
    ) -> List[FixSuggestion]:
        """
        Generate suggestions for a list of failures.
        This method implements the Orchestrator protocol.
        """
        from ...utils.resource_manager import PerformanceTracker
        from ..progress.progress_manager import RichProgressManager

        # Create runtime dependencies
        performance_tracker = PerformanceTracker()
        progress_manager = RichProgressManager(
            progress=progress, parent_task_id=parent_task_id, quiet=quiet
        )

        # Create context for this analysis
        self.context = Context(
            failures=failures,
            quiet=quiet,
            progress_manager=progress_manager,
            path_resolver=self.path_resolver,
            settings=self.settings,
            llm_suggester=self.llm_suggester,
            logger=self.logger,
            performance_tracker=performance_tracker,
        )

        # Run the state machine analysis
        return await self.run_analysis()

    def _create_context(
        self,
        failures: List[PytestFailure],
        quiet: bool,
        progress_manager: RichProgressManager,
        performance_tracker: PerformanceTracker,
    ) -> Context:
        """Create a new context for analysis."""
        return Context(
            failures=failures,
            quiet=quiet,
            progress_manager=progress_manager,
            path_resolver=self.path_resolver,
            settings=self.settings,
            llm_suggester=self.llm_suggester,
            logger=self.logger,
            performance_tracker=performance_tracker,
        )

    async def run_analysis(self) -> List[FixSuggestion]:
        """
        Run the complete analysis pipeline and return suggestions.

        Returns:
            List of fix suggestions generated by the analysis pipeline.
        """
        if self.context is None:
            raise RuntimeError(
                "Context not initialized. Call generate_suggestions first."
            )

        # Start the state machine
        await self.context.transition_to(Initialize)

        # Wait for completion
        await self.context.execution_complete_event.wait()

        # Return the generated suggestions
        return self.context.all_suggestions

    def get_suggestions(self) -> List[FixSuggestion]:
        """
        Get the current suggestions from the analysis.

        Returns:
            List of fix suggestions.
        """
        return self.context.all_suggestions

    def is_complete(self) -> bool:
        """
        Check if the analysis is complete.

        Returns:
            True if the analysis has finished, False otherwise.
        """
        return self.context.execution_complete

    def has_error(self) -> Optional[Exception]:
        """
        Check if there was an error during analysis.

        Returns:
            The error exception if there was one, None otherwise.
        """
        return self.context.final_error
