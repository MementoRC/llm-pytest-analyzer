"""
Implementation of the analyzer state machine.

This module provides a state machine implementation for the pytest analyzer
workflow, modeling the sequential processes of extracting, analyzing,
suggesting fixes, and applying them.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Union

from rich.progress import Progress, TaskID

from ..utils.path_resolver import PathResolver
from ..utils.settings import Settings
from .analysis.failure_analyzer import FailureAnalyzer
from .analysis.failure_grouper import group_failures
from .analysis.fix_applier import FixApplicationResult, FixApplier
from .analysis.fix_suggester import FixSuggester
from .analysis.llm_suggester import LLMSuggester
from .llm.llm_service_protocol import LLMServiceProtocol
from .models.pytest_failure import FixSuggestion, PytestFailure
from .state_machine.base import (
    BaseStateMachine,
    create_state,
    create_transition,
)

logger = logging.getLogger(__name__)


class AnalyzerState(str, Enum):
    """States in the analyzer state machine."""

    INITIALIZING = "initializing"
    """Initial state - preparing resources."""

    EXTRACTING = "extracting"
    """Extracting test failures from pytest output."""

    ANALYZING = "analyzing"
    """Analyzing test failures."""

    SUGGESTING = "suggesting"
    """Generating fix suggestions."""

    APPLYING = "applying"
    """Applying fixes to source code."""

    COMPLETED = "completed"
    """Analysis workflow completed successfully."""

    ERROR = "error"
    """Analysis workflow failed with an error."""


class AnalyzerEvent(str, Enum):
    """Events that can trigger state transitions in the analyzer."""

    INITIALIZE = "initialize"
    """Initialize the analyzer with settings."""

    START_EXTRACTION = "start_extraction"
    """Start extracting test failures."""

    START_ANALYSIS = "start_analysis"
    """Start analyzing test failures."""

    START_SUGGESTIONS = "start_suggestions"
    """Start generating fix suggestions."""

    START_APPLICATION = "start_application"
    """Start applying fixes."""

    COMPLETE = "complete"
    """Complete the current process."""

    ERROR = "error"
    """An error occurred."""

    RESET = "reset"
    """Reset the state machine."""


@dataclass
class AnalyzerContext:
    """Context data for the analyzer state machine."""

    # Configuration
    settings: Settings
    path_resolver: PathResolver
    llm_service: Optional[LLMServiceProtocol] = None

    # Analysis components
    analyzer: Optional[FailureAnalyzer] = None
    suggester: Optional[FixSuggester] = None
    llm_suggester: Optional[LLMSuggester] = None
    fix_applier: Optional[FixApplier] = None

    # Input/output paths
    test_path: Optional[str] = None
    output_path: Optional[Union[str, Path]] = None
    pytest_args: List[str] = field(default_factory=list)

    # Progress tracking
    progress: Optional[Progress] = None
    quiet: bool = False
    main_task_id: Optional[TaskID] = None

    # Analysis data
    failures: List[PytestFailure] = field(default_factory=list)
    failure_groups: Dict[str, List[PytestFailure]] = field(default_factory=dict)
    suggestions: List[FixSuggestion] = field(default_factory=list)
    application_results: List[FixApplicationResult] = field(default_factory=list)

    # Error tracking
    error: Optional[Exception] = None
    error_state: Optional[str] = None
    error_message: Optional[str] = None


class AnalyzerStateMachine(BaseStateMachine[AnalyzerContext, AnalyzerEvent]):
    """
    State machine for the pytest analyzer workflow.

    This state machine models the workflow of extracting test failures,
    analyzing them, generating fix suggestions, and applying fixes.
    """

    def __init__(self, context: AnalyzerContext):
        """
        Initialize the analyzer state machine.

        Args:
            context: The analyzer context
        """
        super().__init__(context)

        # Define states
        self._define_states()

        # Define transitions
        self._define_transitions()

    def _define_states(self) -> None:
        """Define all states in the analyzer state machine."""

        # Initializing state
        self.add_state(
            create_state(
                AnalyzerState.INITIALIZING,
                on_enter_action=self._on_enter_initializing,
                on_exit_action=self._on_exit_initializing,
            ),
            is_initial=True,
        )

        # Extracting state
        self.add_state(
            create_state(
                AnalyzerState.EXTRACTING,
                on_enter_action=self._on_enter_extracting,
                on_exit_action=self._on_exit_extracting,
            )
        )

        # Analyzing state
        self.add_state(
            create_state(
                AnalyzerState.ANALYZING,
                on_enter_action=self._on_enter_analyzing,
                on_exit_action=self._on_exit_analyzing,
            )
        )

        # Suggesting state
        self.add_state(
            create_state(
                AnalyzerState.SUGGESTING,
                on_enter_action=self._on_enter_suggesting,
                on_exit_action=self._on_exit_suggesting,
            )
        )

        # Applying state
        self.add_state(
            create_state(
                AnalyzerState.APPLYING,
                on_enter_action=self._on_enter_applying,
                on_exit_action=self._on_exit_applying,
            )
        )

        # Completed state
        self.add_state(
            create_state(
                AnalyzerState.COMPLETED,
                on_enter_action=self._on_enter_completed,
                on_exit_action=self._on_exit_completed,
            )
        )

        # Error state
        self.add_state(
            create_state(
                AnalyzerState.ERROR,
                on_enter_action=self._on_enter_error,
                on_exit_action=self._on_exit_error,
            )
        )

    def _define_transitions(self) -> None:
        """Define all transitions in the analyzer state machine."""

        # From Initializing state
        self.add_transition(
            create_transition(
                AnalyzerState.INITIALIZING,
                AnalyzerState.EXTRACTING,
                AnalyzerEvent.START_EXTRACTION,
                guard=self._guard_can_extract,
                action=self._action_prepare_extraction,
            )
        )

        # From Extracting state
        self.add_transition(
            create_transition(
                AnalyzerState.EXTRACTING,
                AnalyzerState.ANALYZING,
                AnalyzerEvent.START_ANALYSIS,
                guard=self._guard_has_failures,
                action=self._action_prepare_analysis,
            )
        )
        self.add_transition(
            create_transition(
                AnalyzerState.EXTRACTING,
                AnalyzerState.COMPLETED,
                AnalyzerEvent.COMPLETE,
                guard=self._guard_no_failures,
            )
        )

        # From Analyzing state
        self.add_transition(
            create_transition(
                AnalyzerState.ANALYZING,
                AnalyzerState.SUGGESTING,
                AnalyzerEvent.START_SUGGESTIONS,
                guard=self._guard_can_suggest,
                action=self._action_prepare_suggestions,
            )
        )

        # From Suggesting state
        self.add_transition(
            create_transition(
                AnalyzerState.SUGGESTING,
                AnalyzerState.APPLYING,
                AnalyzerEvent.START_APPLICATION,
                guard=self._guard_has_suggestions,
                action=self._action_prepare_application,
            )
        )
        self.add_transition(
            create_transition(
                AnalyzerState.SUGGESTING,
                AnalyzerState.COMPLETED,
                AnalyzerEvent.COMPLETE,
                guard=self._guard_no_suggestions,
            )
        )

        # From Applying state
        self.add_transition(
            create_transition(
                AnalyzerState.APPLYING,
                AnalyzerState.COMPLETED,
                AnalyzerEvent.COMPLETE,
            )
        )

        # Error transitions from all states
        for state in [
            AnalyzerState.INITIALIZING,
            AnalyzerState.EXTRACTING,
            AnalyzerState.ANALYZING,
            AnalyzerState.SUGGESTING,
            AnalyzerState.APPLYING,
        ]:
            self.add_transition(
                create_transition(
                    state,
                    AnalyzerState.ERROR,
                    AnalyzerEvent.ERROR,
                    action=self._action_handle_error,
                )
            )

        # Reset transitions from terminal states
        for state in [AnalyzerState.COMPLETED, AnalyzerState.ERROR]:
            self.add_transition(
                create_transition(
                    state,
                    AnalyzerState.INITIALIZING,
                    AnalyzerEvent.RESET,
                    action=self._action_reset,
                )
            )

    # State entry/exit actions

    def _on_enter_initializing(self, context: AnalyzerContext) -> None:
        """Actions when entering the initializing state."""
        logger.debug("Entering initializing state")

        # Initialize components
        if not context.analyzer:
            context.analyzer = FailureAnalyzer(
                max_suggestions=context.settings.max_suggestions
            )

        if not context.suggester:
            context.suggester = FixSuggester(
                min_confidence=context.settings.min_confidence
            )

        # Initialize LLM service and suggester if enabled
        if context.settings.use_llm and not context.llm_suggester:
            if context.llm_service:
                context.llm_suggester = LLMSuggester(
                    llm_service=context.llm_service,
                    min_confidence=context.settings.min_confidence,
                    timeout_seconds=context.settings.llm_timeout,
                )

        # Initialize fix applier
        if not context.fix_applier:
            context.fix_applier = FixApplier(
                project_root=context.settings.project_root,
                backup_suffix=".pytest-analyzer.bak",
                verbose_test_output=False,  # Default to quiet mode for validation
            )

        # Update progress if active
        if context.progress and context.main_task_id is not None:
            context.progress.update(
                context.main_task_id,
                description="[cyan]Initializing analyzer...",
            )

    def _on_exit_initializing(self, context: AnalyzerContext) -> None:
        """Actions when exiting the initializing state."""
        logger.debug("Exiting initializing state")

    def _on_enter_extracting(self, context: AnalyzerContext) -> None:
        """Actions when entering the extracting state."""
        logger.debug("Entering extracting state")

        # Update progress if active
        if context.progress and context.main_task_id is not None:
            context.progress.update(
                context.main_task_id,
                description="[cyan]Extracting test failures...",
            )

    def _on_exit_extracting(self, context: AnalyzerContext) -> None:
        """Actions when exiting the extracting state."""
        logger.debug("Exiting extracting state")

    def _on_enter_analyzing(self, context: AnalyzerContext) -> None:
        """Actions when entering the analyzing state."""
        logger.debug("Entering analyzing state")

        # Update progress if active
        if context.progress and context.main_task_id is not None:
            context.progress.update(
                context.main_task_id,
                description="[cyan]Analyzing failures...",
            )

    def _on_exit_analyzing(self, context: AnalyzerContext) -> None:
        """Actions when exiting the analyzing state."""
        logger.debug("Exiting analyzing state")

    def _on_enter_suggesting(self, context: AnalyzerContext) -> None:
        """Actions when entering the suggesting state."""
        logger.debug("Entering suggesting state")

        # Update progress if active
        if context.progress and context.main_task_id is not None:
            context.progress.update(
                context.main_task_id,
                description="[cyan]Generating fix suggestions...",
            )

    def _on_exit_suggesting(self, context: AnalyzerContext) -> None:
        """Actions when exiting the suggesting state."""
        logger.debug("Exiting suggesting state")

    def _on_enter_applying(self, context: AnalyzerContext) -> None:
        """Actions when entering the applying state."""
        logger.debug("Entering applying state")

        # Update progress if active
        if context.progress and context.main_task_id is not None:
            context.progress.update(
                context.main_task_id,
                description="[cyan]Applying fixes...",
            )

    def _on_exit_applying(self, context: AnalyzerContext) -> None:
        """Actions when exiting the applying state."""
        logger.debug("Exiting applying state")

    def _on_enter_completed(self, context: AnalyzerContext) -> None:
        """Actions when entering the completed state."""
        logger.debug("Entering completed state")

        # Update progress if active
        if context.progress and context.main_task_id is not None:
            context.progress.update(
                context.main_task_id,
                description="[green]Analysis complete!",
                completed=True,
            )

    def _on_exit_completed(self, context: AnalyzerContext) -> None:
        """Actions when exiting the completed state."""
        logger.debug("Exiting completed state")

    def _on_enter_error(self, context: AnalyzerContext) -> None:
        """Actions when entering the error state."""
        logger.debug(f"Entering error state: {context.error_message}")

        # Log the error
        if context.error:
            logger.error(f"Error in state {context.error_state}: {context.error}")

        # Update progress if active
        if context.progress and context.main_task_id is not None:
            error_msg = context.error_message or "Unknown error"
            context.progress.update(
                context.main_task_id,
                description=f"[red]Error: {error_msg}",
                completed=True,
            )

    def _on_exit_error(self, context: AnalyzerContext) -> None:
        """Actions when exiting the error state."""
        logger.debug("Exiting error state")

        # Clear error state
        context.error = None
        context.error_state = None
        context.error_message = None

    # Guard conditions

    def _guard_can_extract(
        self, context: AnalyzerContext, event: Optional[AnalyzerEvent]
    ) -> bool:
        """Check if extraction can begin."""
        # Need either a test path or an output path
        return bool(context.test_path or context.output_path)

    def _guard_has_failures(
        self, context: AnalyzerContext, event: Optional[AnalyzerEvent]
    ) -> bool:
        """Check if there are failures to analyze."""
        return len(context.failures) > 0

    def _guard_no_failures(
        self, context: AnalyzerContext, event: Optional[AnalyzerEvent]
    ) -> bool:
        """Check if there are no failures."""
        return len(context.failures) == 0

    def _guard_can_suggest(
        self, context: AnalyzerContext, event: Optional[AnalyzerEvent]
    ) -> bool:
        """Check if suggestions can be generated."""
        return len(context.failures) > 0 and bool(context.suggester)

    def _guard_has_suggestions(
        self, context: AnalyzerContext, event: Optional[AnalyzerEvent]
    ) -> bool:
        """Check if there are suggestions to apply."""
        return len(context.suggestions) > 0 and bool(context.fix_applier)

    def _guard_no_suggestions(
        self, context: AnalyzerContext, event: Optional[AnalyzerEvent]
    ) -> bool:
        """Check if there are no suggestions."""
        return len(context.suggestions) == 0

    # Transition actions

    def _action_prepare_extraction(
        self, context: AnalyzerContext, event: Optional[AnalyzerEvent]
    ) -> None:
        """Prepare for failure extraction."""
        logger.debug("Preparing for failure extraction")

        # Clear previous failures
        context.failures = []

    def _action_prepare_analysis(
        self, context: AnalyzerContext, event: Optional[AnalyzerEvent]
    ) -> None:
        """Prepare for failure analysis."""
        logger.debug("Preparing for failure analysis")

        # Limit the number of failures to analyze if needed
        if len(context.failures) > context.settings.max_failures:
            logger.warning(
                f"Found {len(context.failures)} failures, limiting to {context.settings.max_failures}"
            )
            context.failures = context.failures[: context.settings.max_failures]

    def _action_prepare_suggestions(
        self, context: AnalyzerContext, event: Optional[AnalyzerEvent]
    ) -> None:
        """Prepare for generating suggestions."""
        logger.debug("Preparing for generating suggestions")

        # Clear previous suggestions
        context.suggestions = []

        # Group failures if using LLM
        if context.settings.use_llm and context.llm_suggester:
            project_root = (
                str(context.path_resolver.project_root)
                if context.path_resolver
                else None
            )
            context.failure_groups = group_failures(context.failures, project_root)

            if not context.quiet:
                logger.info(
                    f"Grouped {len(context.failures)} failures into {len(context.failure_groups)} distinct groups"
                )

    def _action_prepare_application(
        self, context: AnalyzerContext, event: Optional[AnalyzerEvent]
    ) -> None:
        """Prepare for applying fixes."""
        logger.debug("Preparing for applying fixes")

        # Clear previous application results
        context.application_results = []

    def _action_handle_error(
        self, context: AnalyzerContext, event: Optional[AnalyzerEvent]
    ) -> None:
        """Handle transition to error state."""
        if not context.error_state:
            context.error_state = self.current_state_name

    def _action_reset(
        self, context: AnalyzerContext, event: Optional[AnalyzerEvent]
    ) -> None:
        """Reset the state machine context."""
        logger.debug("Resetting analyzer state machine")

        # Clear all analysis data
        context.failures = []
        context.failure_groups = {}
        context.suggestions = []
        context.application_results = []
        context.error = None
        context.error_state = None
        context.error_message = None

    # Public methods

    def setup(
        self,
        test_path: Optional[str] = None,
        output_path: Optional[Union[str, Path]] = None,
        pytest_args: Optional[List[str]] = None,
        progress: Optional[Progress] = None,
        quiet: bool = False,
        main_task_id: Optional[TaskID] = None,
    ) -> None:
        """
        Set up the analyzer with input parameters.

        Args:
            test_path: Path to the test file or directory
            output_path: Path to the pytest output file
            pytest_args: Additional pytest arguments
            progress: Progress object for tracking
            quiet: Whether to suppress output
            main_task_id: Task ID for the main progress task
        """
        context = self.context
        context.test_path = test_path
        context.output_path = output_path
        context.pytest_args = pytest_args or []
        context.progress = progress
        context.quiet = quiet
        context.main_task_id = main_task_id

        # Start extraction if we have required parameters
        if (
            self.current_state_name == AnalyzerState.INITIALIZING
            and self._guard_can_extract(context, None)
        ):
            self.trigger(AnalyzerEvent.START_EXTRACTION)

    def set_error(self, error: Exception, message: str = None) -> None:
        """
        Set an error in the analyzer.

        Args:
            error: The exception that occurred
            message: Optional error message
        """
        context = self.context
        context.error = error
        context.error_message = message or str(error)
        context.error_state = self.current_state_name

        # Transition to error state
        self.trigger(AnalyzerEvent.ERROR)

    def get_suggestions(self) -> List[FixSuggestion]:
        """
        Get the generated fix suggestions.

        Returns:
            List of fix suggestions
        """
        return self.context.suggestions

    def get_failures(self) -> List[PytestFailure]:
        """
        Get the extracted test failures.

        Returns:
            List of test failures
        """
        return self.context.failures

    def get_application_results(self) -> List[FixApplicationResult]:
        """
        Get the results of applying fixes.

        Returns:
            List of fix application results
        """
        return self.context.application_results

    def is_completed(self) -> bool:
        """
        Check if the analyzer has completed.

        Returns:
            True if the analyzer is in the completed state
        """
        return self.current_state_name == AnalyzerState.COMPLETED

    def is_error(self) -> bool:
        """
        Check if the analyzer has encountered an error.

        Returns:
            True if the analyzer is in the error state
        """
        return self.current_state_name == AnalyzerState.ERROR

    def get_error(self) -> Optional[Exception]:
        """
        Get the error that occurred, if any.

        Returns:
            The exception that occurred, or None if no error
        """
        return self.context.error
