import asyncio
import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from rich.progress import TaskID

from pytest_analyzer.core.analysis.llm_suggester import LLMSuggester

# Import domain entities from the correct location
from pytest_analyzer.core.domain.entities.fix_suggestion import FixSuggestion
from pytest_analyzer.core.domain.entities.pytest_failure import PytestFailure

# Import state machine components
from pytest_analyzer.core.orchestration.analyzer_orchestrator import (
    BatchProcess,
    Context,
    ErrorState,
    FailureGroupingError,
    GroupFailures,
    Initialize,
    PostProcess,
    PrepareRepresentatives,
)
from pytest_analyzer.core.progress.progress_manager import (
    RichProgressManager,  # Import the actual class
)
from pytest_analyzer.utils.path_resolver import PathResolver
from pytest_analyzer.utils.resource_manager import PerformanceTracker
from pytest_analyzer.utils.settings import Settings

# --- Fixtures ---


@pytest.fixture
def mock_logger():
    """Fixture for a mocked logger."""
    return MagicMock(spec=logging.Logger)


@pytest.fixture
def mock_performance_tracker():
    """Fixture for a mocked performance tracker."""
    tracker = MagicMock(spec=PerformanceTracker)
    # Mock the async_track context manager
    mock_context_manager = AsyncMock()
    mock_context_manager.__aenter__.return_value = None  # Simulate entering the context
    mock_context_manager.__aexit__.return_value = None  # Simulate exiting the context
    tracker.async_track.return_value = mock_context_manager
    return tracker


@pytest.fixture
def mock_path_resolver():
    """Fixture for a mocked path resolver."""
    resolver = MagicMock(spec=PathResolver)
    resolver.project_root = "/fake/project"
    return resolver


@pytest.fixture
def mock_settings():
    """Fixture for default settings."""
    settings = Settings()
    settings.llm_timeout = 10
    settings.max_suggestions_per_failure = 3
    # These properties aren't available in Settings, but we need them for tests
    # Add them as attributes directly for the mock settings object
    settings.batch_size = 2
    settings.max_concurrency = 2
    return settings


@pytest.fixture
def mock_llm_suggester():
    """Fixture for a mocked LLM suggester."""
    suggester = MagicMock(spec=LLMSuggester)
    suggester.batch_suggest_fixes = AsyncMock()
    return suggester


@pytest.fixture
def mock_progress_manager():
    """Fixture for a mocked RichProgressManager."""
    manager = MagicMock(spec=RichProgressManager)
    # Mock methods used by the states
    manager.create_task = MagicMock(return_value=TaskID(1))  # Return a dummy TaskID
    manager.update_task = MagicMock()
    manager.cleanup_tasks = MagicMock()
    return manager


@pytest.fixture
def sample_failures():
    """Fixture for a list of sample PytestFailure objects."""
    # Ensure failures have unique IDs for group mapping
    return [
        PytestFailure.create(
            test_name=f"test_func_{i}",
            file_path=Path(f"file_{i}.py"),
            failure_message=f"msg {i}",
            error_type="AssertionError",
            traceback=[f"tb {i}"],
            line_number=i + 1,
            function_name=f"test_func_{i}",
            class_name=None,
        )
        for i in range(5)
    ]


@pytest.fixture
def test_context(
    sample_failures,
    mock_logger,
    mock_performance_tracker,
    mock_path_resolver,
    mock_settings,
    mock_llm_suggester,
    mock_progress_manager,  # Use the progress manager fixture
):
    """Factory fixture to create a Context object for testing."""

    def _create_context(
        failures=sample_failures,
        quiet=False,
        # Pass the mocked progress manager directly
        progress_manager=mock_progress_manager,
    ):
        return Context(
            failures=failures,
            quiet=quiet,
            progress_manager=progress_manager,  # Use the passed manager
            path_resolver=mock_path_resolver,
            settings=mock_settings,
            llm_suggester=mock_llm_suggester,
            logger=mock_logger,
            performance_tracker=mock_performance_tracker,
        )

    return _create_context


# --- State Tests ---


@pytest.mark.asyncio
async def test_initialize_state_success(test_context, mock_progress_manager):
    """Test Initialize state successfully transitions to GroupFailures."""
    context = test_context()
    initialize_state = Initialize(context)

    # Mock transition_to to prevent actual transition but record call
    context.transition_to = AsyncMock()

    await initialize_state.run()

    # Verify progress task was created using the manager
    mock_progress_manager.create_task.assert_called_once_with(
        "llm",
        "[cyan]Generating async LLM-based suggestions...",
        total=len(context.failures),
    )
    # Verify transition to GroupFailures
    context.transition_to.assert_awaited_once_with(GroupFailures)


@pytest.mark.asyncio
async def test_initialize_state_no_failures(test_context, mock_progress_manager):
    """Test Initialize state completes immediately with no failures."""
    context = test_context(failures=[])
    initialize_state = Initialize(context)
    context.transition_to = AsyncMock()  # Mock transition
    context.mark_execution_complete = MagicMock()  # Mock completion marker

    await initialize_state.run()

    # Verify no progress task was created
    mock_progress_manager.create_task.assert_not_called()
    # Verify no transition occurred
    context.transition_to.assert_not_awaited()
    # Verify execution was marked complete
    context.mark_execution_complete.assert_called_once()
    # Verify cleanup was called on the manager
    mock_progress_manager.cleanup_tasks.assert_called_once()


@pytest.mark.asyncio
async def test_initialize_state_error(test_context, mock_progress_manager):
    """Test Initialize state handles errors and transitions to ErrorState."""
    context = test_context()

    # Simulate error during progress task creation
    mock_progress_manager.create_task.side_effect = ValueError("Progress error")

    # Start the state machine (this will call transition_to internally)
    await context.transition_to(Initialize)

    # Verify that we ended up in PostProcess (ErrorState transitions to PostProcess)
    assert isinstance(context.state, PostProcess)
    # Verify error was logged (InitializationError during state transition)
    context.logger.error.assert_called_once()
    # Verify warning was logged (from ErrorState)
    context.logger.warning.assert_called_once()


@pytest.mark.asyncio
async def test_group_failures_state_success(test_context, mock_progress_manager):
    """Test GroupFailures state successfully groups and transitions."""
    context = test_context()
    group_state = GroupFailures(context)
    context.transition_to = AsyncMock()  # Mock transition

    # Mock the actual grouping function
    with patch(
        "pytest_analyzer.core.orchestration.analyzer_orchestrator.group_failures"
    ) as mock_group:
        mock_group.return_value = {
            "group1": [context.failures[0]],
            "group2": context.failures[1:],
        }
        await group_state.run()

    # Verify progress task creation and update using the manager
    mock_progress_manager.create_task.assert_called_once_with(
        "grouping", "[cyan]Grouping similar failures...", total=1
    )
    mock_progress_manager.update_task.assert_called_once_with(
        "grouping",  # Use the task key
        description="[green]Grouped 5 into 2 distinct groups",
        completed=True,
    )
    # Verify grouping function was called
    mock_group.assert_called_once_with(
        context.failures, str(context.path_resolver.project_root)
    )
    # Verify context is updated
    assert len(context.failure_groups) == 2
    # Verify transition to PrepareRepresentatives
    context.transition_to.assert_awaited_once_with(PrepareRepresentatives)


@pytest.mark.asyncio
async def test_group_failures_state_no_groups(test_context, mock_progress_manager):
    """Test GroupFailures state transitions to PostProcess if no groups found."""
    context = test_context()
    group_state = GroupFailures(context)
    context.transition_to = AsyncMock()

    with patch(
        "pytest_analyzer.core.orchestration.analyzer_orchestrator.group_failures"
    ) as mock_group:
        mock_group.return_value = {}  # Simulate no groups found
        await group_state.run()

    # Verify progress update indicates 0 groups
    mock_progress_manager.update_task.assert_called_once_with(
        "grouping",  # Use the task key
        description="[green]Grouped 5 into 0 distinct groups",
        completed=True,
    )
    # Verify context is updated
    assert len(context.failure_groups) == 0
    # Verify transition to PostProcess
    context.transition_to.assert_awaited_once_with(PostProcess)


@pytest.mark.asyncio
async def test_group_failures_state_error(test_context, mock_progress_manager):
    """Test GroupFailures state handles errors."""
    context = test_context()
    group_state = GroupFailures(context)
    context.transition_to = AsyncMock()

    with patch(
        "pytest_analyzer.core.orchestration.analyzer_orchestrator.group_failures"
    ) as mock_group:
        mock_group.side_effect = ValueError("Grouping failed")
        await group_state.run()

    # Verify error logging (implicitly tested via handle_error)
    context.logger.error.assert_called_once()
    # Verify transition to ErrorState (implicitly tested via handle_error)
    context.transition_to.assert_awaited_once_with(ErrorState)


@pytest.mark.asyncio
async def test_prepare_representatives_state_success(
    test_context, mock_progress_manager
):
    """Test PrepareRepresentatives state successfully prepares and transitions."""
    context = test_context()
    # Pre-populate groups using failure IDs as keys
    context.failure_groups = {
        context.failures[0].id: [context.failures[0]],
        context.failures[1].id: context.failures[1:],
    }
    prepare_state = PrepareRepresentatives(context)
    context.transition_to = AsyncMock()

    # Mock select_representative_failure
    with patch(
        "pytest_analyzer.core.orchestration.analyzer_orchestrator.select_representative_failure"
    ) as mock_select:
        # Return the first element of each group as representative
        mock_select.side_effect = lambda group: group[0]
        await prepare_state.run()

    # Verify representatives are selected
    assert len(context.representative_failures) == 2
    assert context.representative_failures[0] == context.failures[0]
    assert (
        context.representative_failures[1] == context.failures[1]
    )  # First of the second group
    # Verify group mapping is correct (using representative ID as key)
    assert context.group_mapping[context.failures[0].id] == [context.failures[0]]
    assert context.group_mapping[context.failures[1].id] == context.failures[1:]
    # Verify progress task creation using the manager
    mock_progress_manager.create_task.assert_called_once_with(
        "batch_processing",
        f"[cyan]Processing {len(context.representative_failures)} failure groups in parallel...",
        total=len(
            context.representative_failures
        ),  # Total is number of representatives
    )
    # Verify transition to BatchProcess
    context.transition_to.assert_awaited_once_with(BatchProcess)


@pytest.mark.asyncio
async def test_prepare_representatives_state_error(test_context):
    """Test PrepareRepresentatives state handles errors."""
    context = test_context()
    context.failure_groups = {context.failures[0].id: [context.failures[0]]}
    prepare_state = PrepareRepresentatives(context)
    context.transition_to = AsyncMock()

    with patch(
        "pytest_analyzer.core.orchestration.analyzer_orchestrator.select_representative_failure"
    ) as mock_select:
        mock_select.side_effect = ValueError("Selection failed")
        await prepare_state.run()

    # Verify error logging and transition to ErrorState (implicitly tested via handle_error)
    context.logger.error.assert_called_once()
    context.transition_to.assert_awaited_once_with(ErrorState)


@pytest.mark.asyncio
async def test_batch_process_state_success(
    test_context, mock_llm_suggester, mock_progress_manager
):
    """Test BatchProcess state successfully processes batches and transitions."""
    context = test_context()
    # Pre-populate representatives and mapping using failure IDs
    rep1 = context.failures[0]
    rep2 = context.failures[1]
    group1 = [rep1]
    group2 = [rep2, context.failures[2]]
    context.representative_failures = [rep1, rep2]
    context.group_mapping = {rep1.id: group1, rep2.id: group2}

    batch_state = BatchProcess(context)
    context.transition_to = AsyncMock()

    # Mock LLM response (using FixSuggestion.create)
    suggestion1 = FixSuggestion.create(
        failure_id=rep1.id,
        suggestion_text="Fix 1",
        confidence=0.9,
        code_changes=["file_0.py: fixed code 1"],
        metadata={"initial": "data"},
    )
    suggestion2 = FixSuggestion.create(
        failure_id=rep2.id,
        suggestion_text="Fix 2",
        confidence=0.8,
        code_changes=["file_1.py: fixed code 2"],
    )
    mock_llm_suggester.batch_suggest_fixes.return_value = {
        rep1.id: [suggestion1],
        rep2.id: [suggestion2],
    }

    await batch_state.run()

    # Verify LLM suggester was called
    mock_llm_suggester.batch_suggest_fixes.assert_awaited_once_with(
        context.representative_failures
    )
    # Verify suggestions are added to context (original + duplicates)
    # 1 for group1 (rep1), 2 for group2 (rep2 + failures[2]) = 3 total
    assert len(context.all_suggestions) == 3

    # Check suggestion details and marking (order might vary before post-processing sort)
    # Find the suggestions by the failure ID they are linked to
    sug_for_f0 = next(s for s in context.all_suggestions if s.failure_id == rep1.id)
    sug_for_f1 = next(s for s in context.all_suggestions if s.failure_id == rep2.id)
    sug_for_f2 = next(
        s for s in context.all_suggestions if s.failure_id == context.failures[2].id
    )

    assert sug_for_f0.suggestion_text == "Fix 1"
    assert sug_for_f0.confidence == 0.9
    assert sug_for_f0.metadata.get("source") == "llm_async"
    assert "initial" in sug_for_f0.metadata  # Check original metadata is kept

    assert sug_for_f1.suggestion_text == "Fix 2"
    assert sug_for_f1.confidence == 0.8
    assert sug_for_f1.metadata.get("source") == "llm_async"

    assert sug_for_f2.suggestion_text == "Fix 2"  # Duplicate suggestion text
    assert sug_for_f2.confidence == 0.8  # Duplicate confidence
    assert sug_for_f2.id != sug_for_f1.id  # Ensure it's a new FixSuggestion entity

    # Verify progress update was called using the manager
    # create_task was called in PrepareRepresentatives, update_task is called here
    mock_progress_manager.update_task.assert_any_call(
        "batch_processing", advance=1
    )  # Called for each representative
    mock_progress_manager.update_task.assert_called_with(  # Final update
        "batch_processing",
        description=f"[green]Completed processing {len(context.representative_failures)} failure groups",
        completed=True,
    )

    # Verify transition to PostProcess
    context.transition_to.assert_awaited_once_with(PostProcess)


@pytest.mark.asyncio
async def test_batch_process_state_timeout(test_context, mock_llm_suggester):
    """Test BatchProcess state handles timeout errors."""
    context = test_context()
    rep_failure = context.failures[0]
    context.representative_failures = [rep_failure]
    context.group_mapping = {rep_failure.id: [rep_failure]}
    batch_state = BatchProcess(context)
    context.transition_to = AsyncMock()

    # Simulate timeout
    mock_llm_suggester.batch_suggest_fixes.side_effect = asyncio.TimeoutError(
        "LLM timed out"
    )

    await batch_state.run()

    # Verify warning log
    context.logger.warning.assert_called_once_with(
        f"Batch processing timed out after {context.settings.llm_timeout} seconds. "
        "Consider adjusting the timeout or reducing batch size/concurrency."
    )
    # Verify error log from handle_error
    context.logger.error.assert_called_once_with(
        "BatchProcessingError: LLM request timed out"
    )
    # Verify transition to ErrorState (implicitly tested via handle_error)
    context.transition_to.assert_awaited_once_with(ErrorState)


@pytest.mark.asyncio
async def test_batch_process_state_generic_error(test_context, mock_llm_suggester):
    """Test BatchProcess state handles generic errors during processing."""
    context = test_context()
    rep_failure = context.failures[0]
    context.representative_failures = [rep_failure]
    context.group_mapping = {rep_failure.id: [rep_failure]}
    batch_state = BatchProcess(context)
    context.transition_to = AsyncMock()

    # Simulate generic error from LLM suggester
    error_message = "Something broke"
    mock_llm_suggester.batch_suggest_fixes.side_effect = ValueError(error_message)

    await batch_state.run()

    # Verify error log from handle_error
    context.logger.error.assert_called_once_with(
        f"BatchProcessingError: Error in batch processing: {error_message}"
    )
    # Verify transition to ErrorState (implicitly tested via handle_error)
    context.transition_to.assert_awaited_once_with(ErrorState)


@pytest.mark.asyncio
async def test_post_process_state_success(test_context):
    """Test PostProcess state successfully sorts and limits suggestions."""
    context = test_context()
    # Pre-populate suggestions (unsorted, more than limit)
    f1 = context.failures[0]
    f2 = context.failures[1]
    context.all_suggestions = [
        FixSuggestion.create(
            failure_id=f1.id, suggestion_text="S1 Low", confidence=0.5
        ),
        FixSuggestion.create(
            failure_id=f2.id, suggestion_text="S2 High", confidence=0.9
        ),
        FixSuggestion.create(
            failure_id=f1.id, suggestion_text="S1 High", confidence=0.95
        ),
        FixSuggestion.create(
            failure_id=f1.id, suggestion_text="S1 Mid", confidence=0.7
        ),
        FixSuggestion.create(
            failure_id=f2.id, suggestion_text="S2 Low", confidence=0.4
        ),
        FixSuggestion.create(
            failure_id=f1.id, suggestion_text="S1 Lowest", confidence=0.2
        ),  # Exceeds limit for f1
    ]
    context.settings.max_suggestions_per_failure = 3  # Set limit

    post_process_state = PostProcess(context)
    context.mark_execution_complete = MagicMock()  # Mock completion marker

    await post_process_state.run()

    # Verify suggestions are sorted by confidence (desc) and limited per failure
    assert len(context.all_suggestions) == 5  # 3 for f1, 2 for f2
    # Check order and content (after sorting)
    # Get suggestions for f1 and f2 separately and check their counts and order
    sugs_f1 = sorted(
        [s for s in context.all_suggestions if s.failure_id == f1.id],
        key=lambda s: s.confidence,
        reverse=True,
    )
    sugs_f2 = sorted(
        [s for s in context.all_suggestions if s.failure_id == f2.id],
        key=lambda s: s.confidence,
        reverse=True,
    )

    assert len(sugs_f1) == 3
    assert sugs_f1[0].suggestion_text == "S1 High"
    assert sugs_f1[1].suggestion_text == "S1 Mid"
    assert sugs_f1[2].suggestion_text == "S1 Low"

    assert len(sugs_f2) == 2
    assert sugs_f2[0].suggestion_text == "S2 High"
    assert sugs_f2[1].suggestion_text == "S2 Low"

    # Verify execution marked complete
    context.mark_execution_complete.assert_called_once()


@pytest.mark.asyncio
async def test_post_process_state_no_limit(test_context):
    """Test PostProcess state works correctly when no limit is set."""
    context = test_context()
    context.all_suggestions = [
        FixSuggestion.create(
            failure_id=context.failures[0].id, suggestion_text="S1 Low", confidence=0.5
        ),
        FixSuggestion.create(
            failure_id=context.failures[1].id, suggestion_text="S2 High", confidence=0.9
        ),
    ]
    context.settings.max_suggestions_per_failure = 0  # No limit

    post_process_state = PostProcess(context)
    context.mark_execution_complete = MagicMock()

    await post_process_state.run()

    # Verify suggestions are sorted but not limited
    assert len(context.all_suggestions) == 2
    final_suggestions = sorted(
        context.all_suggestions, key=lambda s: s.confidence, reverse=True
    )
    assert final_suggestions[0].suggestion_text == "S2 High"
    assert final_suggestions[1].suggestion_text == "S1 Low"
    context.mark_execution_complete.assert_called_once()


@pytest.mark.asyncio
async def test_post_process_state_error(test_context):
    """Test PostProcess state handles errors."""
    context = test_context()
    post_process_state = PostProcess(context)
    context.transition_to = AsyncMock()

    # Directly patch the context's track_performance method to raise an error
    with patch.object(
        context, "track_performance", side_effect=Exception("Test error")
    ):
        await post_process_state.run()

    # Verify error logging and transition to ErrorState
    context.logger.error.assert_called_once_with(
        "PostProcessingError: Error in post-processing: Test error"
    )
    context.transition_to.assert_awaited_once_with(ErrorState)


@pytest.mark.asyncio
async def test_error_state_run(test_context, mock_progress_manager):
    """Test ErrorState cleans up and transitions to PostProcess."""
    context = test_context()
    error_state = ErrorState(context)
    context.transition_to = AsyncMock()

    await error_state.run()

    # Verify cleanup was called on the manager
    mock_progress_manager.cleanup_tasks.assert_called_once()
    # Verify warning log
    context.logger.warning.assert_called_once_with(
        "Error encountered during async suggestion generation. "
        "Moving to post-processing with partial results."
    )
    # Verify transition to PostProcess
    context.transition_to.assert_awaited_once_with(PostProcess)


@pytest.mark.asyncio
async def test_state_handle_error_default(test_context):
    """Test the default handle_error transitions to ErrorState."""
    context = test_context()
    # Use Initialize as a sample state
    state = Initialize(context)
    context.transition_to = AsyncMock()  # Mock transition

    error = ValueError("Generic error")
    await state.handle_error(error)

    # Verify error logging format for non-OrchestrationError
    context.logger.error.assert_called_once_with(
        f"Unexpected error in Initialize: {error}"
    )
    # Verify transition to ErrorState
    context.transition_to.assert_awaited_once_with(ErrorState)


@pytest.mark.asyncio
async def test_state_handle_error_custom_exception(test_context):
    """Test handle_error logs custom OrchestrationError correctly."""
    context = test_context()
    state = GroupFailures(context)  # Use a state that can raise custom errors
    context.transition_to = AsyncMock()

    error = FailureGroupingError("Specific grouping issue")
    await state.handle_error(error)

    # Verify specific error logging format for OrchestrationError
    context.logger.error.assert_called_once_with(f"FailureGroupingError: {error}")
    # Verify transition to ErrorState
    context.transition_to.assert_awaited_once_with(ErrorState)


# --- Full Flow Tests ---


@pytest.mark.asyncio
async def test_full_flow_success(test_context, mock_llm_suggester, sample_failures):
    """Test the complete state machine flow successfully."""
    context = test_context()

    # Mock grouping and selection
    rep_failure = sample_failures[0]  # Assume first is representative after grouping
    # Simulate grouping into one group
    mock_failure_groups = {rep_failure.id: sample_failures}

    # Mock LLM response for the representative failure (using FixSuggestion.create)
    suggestion = FixSuggestion.create(
        failure_id=rep_failure.id,
        suggestion_text="Fix it",
        confidence=0.9,
        code_changes=["file_0.py: fixed"],
    )
    mock_llm_suggester.batch_suggest_fixes.return_value = {rep_failure.id: [suggestion]}

    with (
        patch(
            "pytest_analyzer.core.orchestration.analyzer_orchestrator.group_failures"
        ) as mock_group,
        patch(
            "pytest_analyzer.core.orchestration.analyzer_orchestrator.select_representative_failure"
        ) as mock_select,
    ):
        mock_group.return_value = mock_failure_groups
        mock_select.return_value = rep_failure

        # Start the state machine
        await context.transition_to(Initialize)

        # Wait for completion
        await context.execution_complete_event.wait()

    # Verify final state
    assert isinstance(context.state, PostProcess)  # Should end in PostProcess
    assert context.execution_complete is True
    assert context.final_error is None
    # Verify suggestions (one for each original failure, based on the representative)
    assert len(context.all_suggestions) == len(sample_failures)
    # Sort before checking content due to potential limiting/reordering in PostProcess
    # Check that each original failure ID has exactly one suggestion linked to it
    suggestions_by_failure_id = {s.failure_id: s for s in context.all_suggestions}
    assert len(suggestions_by_failure_id) == len(sample_failures)

    for original_failure in sample_failures:
        sug = suggestions_by_failure_id.get(original_failure.id)
        assert sug is not None
        assert sug.suggestion_text == "Fix it"
        assert sug.confidence == 0.9
        assert sug.metadata.get("source") == "llm_async"
        # Check that the suggestion is linked to the correct failure ID
        assert sug.failure_id == original_failure.id


@pytest.mark.asyncio
async def test_full_flow_no_failures(test_context):
    """Test the flow completes correctly with no initial failures."""
    context = test_context(failures=[])

    # Start the state machine
    await context.transition_to(Initialize)

    # Wait for completion (should be immediate)
    await context.execution_complete_event.wait()

    # Verify final state
    # The state remains Initialize because run() returns early before transitioning
    assert isinstance(context.state, Initialize)
    assert context.execution_complete is True
    assert context.final_error is None
    assert len(context.all_suggestions) == 0
    # Verify cleanup was called
    context.progress_manager.cleanup_tasks.assert_called_once()


@pytest.mark.asyncio
async def test_full_flow_error_in_batch_process(
    test_context, mock_llm_suggester, sample_failures
):
    """Test the flow handles an error during BatchProcess and completes."""
    context = test_context()

    # Mock grouping and selection
    rep_failure = sample_failures[0]
    mock_failure_groups = {rep_failure.id: sample_failures}

    with (
        patch(
            "pytest_analyzer.core.orchestration.analyzer_orchestrator.group_failures"
        ) as mock_group,
        patch(
            "pytest_analyzer.core.orchestration.analyzer_orchestrator.select_representative_failure"
        ) as mock_select,
    ):
        mock_group.return_value = mock_failure_groups
        mock_select.return_value = rep_failure

        # Simulate error during LLM call
        error_message = "LLM API failed"
        mock_llm_suggester.batch_suggest_fixes.side_effect = ValueError(error_message)

        # Start the state machine
        await context.transition_to(Initialize)

        # Wait for completion
        await context.execution_complete_event.wait()

    # Verify final state is PostProcess (after ErrorState)
    assert isinstance(context.state, PostProcess)
    assert context.execution_complete is True
    # Check logs for error messages
    # The error should be logged by the state's handle_error method
    context.logger.error.assert_called_once_with(
        f"BatchProcessingError: Error in batch processing: {error_message}"
    )
    # Verify no suggestions were added because the error happened before processing results
    assert len(context.all_suggestions) == 0
    # Verify cleanup was called by ErrorState
    context.progress_manager.cleanup_tasks.assert_called_once()
