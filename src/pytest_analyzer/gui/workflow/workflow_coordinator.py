import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, List, Optional

from PyQt6.QtCore import QObject, pyqtSlot

from ...core.models.pytest_failure import PytestFailure
from ..models.test_results_model import (  # Assuming TestResult might be used
    AnalysisStatus,
    TestResult,
)
from .workflow_guide import WorkflowGuide
from .workflow_state_machine import WorkflowState, WorkflowStateMachine

if TYPE_CHECKING:
    from ..background.task_manager import TaskManager
    from ..controllers.analysis_controller import AnalysisController
    from ..controllers.file_controller import FileController
    from ..controllers.test_discovery_controller import TestDiscoveryController
    from ..controllers.test_execution_controller import TestExecutionController


logger = logging.getLogger(__name__)


class WorkflowCoordinator(QObject):
    """
    Central coordinator for the GUI workflow.

    Connects to signals from various controllers and manages state transitions
    in the WorkflowStateMachine. It also triggers updates in the WorkflowGuide.
    """

    def __init__(
        self,
        state_machine: WorkflowStateMachine,
        guide: WorkflowGuide,
        file_controller: "FileController",
        test_discovery_controller: "TestDiscoveryController",
        test_execution_controller: "TestExecutionController",
        analysis_controller: "AnalysisController",
        # fix_controller: Optional["FixController"] = None, # Add when FixController is integrated
        task_manager: "TaskManager",
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self.state_machine = state_machine
        self.guide = guide
        self.file_controller = file_controller
        self.test_discovery_controller = test_discovery_controller
        self.test_execution_controller = test_execution_controller
        self.analysis_controller = analysis_controller
        # self.fix_controller = fix_controller
        self.task_manager = task_manager

        self._connect_signals()
        logger.info("WorkflowCoordinator initialized and signals connected.")

    def _connect_signals(self) -> None:
        # State machine changes trigger guide updates
        self.state_machine.state_changed.connect(self._on_state_changed_update_guide)

        # FileController signals
        self.file_controller.results_loaded.connect(self._handle_results_loaded)  # For reports
        # Need a signal from FileController when a .py file or directory is selected but not yet run
        # For now, using results_loaded with empty list for .py/directory selection
        # A more specific signal like `source_selected_for_run` might be better.

        # TestDiscoveryController signals
        self.test_discovery_controller.discovery_started.connect(self._handle_discovery_started)
        self.test_discovery_controller.tests_discovered.connect(self._handle_tests_discovered)
        self.test_discovery_controller.discovery_finished.connect(
            self._handle_discovery_outcome_message
        )

        # TestExecutionController signals
        # TaskManager's task_started is used by TestExecutionController to show its view.
        # We need to know when a test execution task specifically starts to change workflow state.
        # We can listen to task_manager.task_started and filter by description.
        self.task_manager.task_started.connect(self._handle_task_started_for_workflow)
        self.test_execution_controller.test_execution_completed.connect(
            self._handle_test_execution_completed
        )
        # TaskManager's task_failed is used by TestExecutionController.
        # We also listen to task_manager.task_failed for generic error handling.
        self.task_manager.task_failed.connect(self._handle_task_failed_for_workflow)

        # AnalysisController signals
        # Similar to test execution, we need to know when analysis task starts.
        # AnalysisController.on_analyze() submits a task. We can listen to task_manager.task_started.
        self.analysis_controller.test_results_model.analysis_status_updated.connect(
            self._handle_analysis_status_changed_for_workflow
        )
        # A more direct signal from AnalysisController like `analysis_task_submitted` or `analysis_completed` would be ideal.
        # For now, using task_manager signals and model signals.
        # Let's assume AnalysisController emits signals for completion/failure of analysis.
        # The current AnalysisController._handle_task_completion processes results but doesn't emit a specific "analysis_finished" signal.
        # We will rely on task_manager.task_completed and filter by task description/origin if possible.
        # Or, more robustly, connect to a new signal from AnalysisController if we were to add one.
        # For now, let's assume we can infer from task_completed.

        # Placeholder for FixController signals
        # if self.fix_controller:
        #     self.fix_controller.fix_applied_successfully.connect(self._handle_fix_applied)
        #     self.fix_controller.batch_operation_completed.connect(self._handle_batch_fix_completed)
        #     self.fix_controller.fix_application_failed.connect(self._handle_fix_failed)

        # Connect to AnalysisController's specific signals for suggestions
        # This requires AnalysisController to emit such signals.
        # Let's assume AnalysisController's _handle_task_completion (which processes suggestions)
        # could trigger a state change or emit a signal the coordinator listens to.
        # For now, we'll infer from the model updates or task completion.
        # A direct signal like `suggestions_generated(suggestions: List[FixSuggestion])` from AnalysisController would be best.
        # Let's assume `analysis_controller.test_results_model.suggestions_updated` or similar.
        # The model's `dataChanged` signal is too generic.
        # We'll use the `task_completed` for analysis tasks for now.

    @pyqtSlot(str, str)
    def _on_state_changed_update_guide(self, old_state_val: str, new_state_val: str) -> None:
        try:
            new_state = WorkflowState(new_state_val)
            self.guide.update_guidance(new_state, self.state_machine.context)
        except ValueError:
            logger.error(f"Invalid state value received: {new_state_val}")

    @pyqtSlot(list, Path, str)
    def _handle_results_loaded(
        self, results: List[Any], source_file: Path, source_type: str
    ) -> None:
        """Handles loading of test results from reports or initial selection of .py/dir."""
        if source_type in ("json", "xml"):  # Report loaded
            failure_count = sum(
                1
                for r in results
                if hasattr(r, "status")
                and r.status
                in ("failed", "error", TestResult.TestStatus.FAILED, TestResult.TestStatus.ERROR)
            )
            self.state_machine.to_results_available(
                result_count=len(results),
                failure_count=failure_count,
                file_path=source_file,
                file_type=source_type,
            )
        elif source_type in ("py", "directory"):  # .py file or directory selected
            self.state_machine.to_file_selected(file_path=source_file, file_type=source_type)
            # If it's a .py file, we might auto-trigger discovery or wait for user.
            # For now, just FILE_SELECTED. User can click "Discover" or "Run".

    @pyqtSlot(str)
    def _handle_discovery_started(self, message: str) -> None:
        self.state_machine.to_tests_discovering()

    @pyqtSlot(list)
    def _handle_tests_discovered(self, discovered_tests: list) -> None:
        self.state_machine.to_tests_discovered(test_count=len(discovered_tests))

    @pyqtSlot(str)
    def _handle_discovery_outcome_message(self, message: str) -> None:
        """Handles the discovery_finished signal from TestDiscoveryController."""
        # Check if the message indicates a failure
        if message.lower().startswith("discovery failed") or message.lower().startswith(
            "test discovery failed"
        ):
            # The message from TestDiscoveryController is already formatted for error display
            self.state_machine.to_error(message)
        # If it's a success message (e.g., "Test discovery complete..."),
        # the _handle_tests_discovered slot (connected to tests_discovered signal)
        # should have already handled the state transition. No action needed here for success.

    @pyqtSlot(str, str)
    def _handle_task_started_for_workflow(self, task_id: str, description: str) -> None:
        # Check if it's a test execution task
        if description == self.test_execution_controller.analyzer_service.run_pytest_only.__name__:
            self.state_machine.to_tests_running()
        # Check if it's an analysis task
        elif (
            description == self.analysis_controller.analyzer_service._generate_suggestions.__name__
        ):
            # Need failure_count from context if available (though not used in state transition)
            # current_context = self.state_machine.context # Not needed here
            # failure_count = current_context.get("failure_count", 0) # Get from context # Unused
            self.state_machine.to_analysis_running()
        # Add other task types like applying fixes if FixController was integrated
        # elif self.fix_controller and description == self.fix_controller.applier.apply_fix_suggestion.__name__:
        #     self.state_machine.to_applying_fixes()

    @pyqtSlot(list)  # List[PytestFailure]
    def _handle_test_execution_completed(self, pytest_failures: List[PytestFailure]) -> None:
        # This signal comes from TestExecutionController after its _handle_task_completed.
        # The result (pytest_failures) is already processed by TestResultsController
        # to update the model. We can get counts from the model or the list.
        total_results = self.analysis_controller.test_results_model.rowCount()  # Approximation
        failure_count = len(pytest_failures)
        self.state_machine.to_results_available(
            result_count=total_results,  # This might not be accurate if model isn't fully updated yet
            failure_count=failure_count,
        )

    @pyqtSlot(str, str)
    def _handle_task_failed_for_workflow(self, task_id: str, error_message: str) -> None:
        # This is a generic handler. If a task fails, set workflow to error.
        # Specific controllers might handle their own task failures more gracefully first.
        # We need to identify if the failed task was part of the core workflow.
        # For now, any task failure related to core operations (run, discover, analyze) leads to ERROR state.
        # We can check the current state to see if we were in a running state.
        current_state = self.state_machine.current_state
        critical_states = [
            WorkflowState.TESTS_DISCOVERING,
            WorkflowState.TESTS_RUNNING,
            WorkflowState.ANALYSIS_RUNNING,
            WorkflowState.APPLYING_FIXES,
        ]
        if current_state in critical_states:
            self.state_machine.to_error(
                f"Task failed: {error_message.splitlines()[0]}", previous_state=current_state
            )

    # This is a conceptual slot. AnalysisController needs to be modified to emit such a signal,
    # or we infer this from task_completed for analysis tasks.
    # For now, let's assume task_completed for analysis tasks will be handled by a more generic task handler.
    # The _handle_task_completed in AnalysisController updates the model.
    # We can listen to model changes or have AnalysisController emit a specific signal.
    # Let's refine _handle_task_completed_for_workflow to check task description.

    @pyqtSlot(str, object)
    def _handle_task_completed_for_workflow(self, task_id: str, result: Any) -> None:
        # This is connected to task_manager.task_completed
        # We need to identify if this completed task was an analysis task.
        # The task description might be stored when task_started.
        # This is getting complex; direct signals from controllers are better.
        # For now, let's assume AnalysisController's own _handle_task_completion
        # will eventually lead to a state where we know if fixes are available.
        # This might be by checking the model.

        # If the completed task was `_generate_suggestions`:
        # The result is List[FixSuggestion].
        # This logic is currently in AnalysisController._handle_task_completion.
        # That method updates the model.
        # We need a signal from AnalysisController: `suggestions_ready(count)`
        # Or, the model itself could emit a more specific signal than dataChanged.

        # Let's assume for now that after analysis, if suggestions are found,
        # the AnalysisController or model updates will eventually trigger a UI update,
        # and the user then decides to apply fixes.
        # The transition to FIXES_AVAILABLE should happen when suggestions are populated.

        # A simplified approach: if an analysis task completes successfully,
        # and the model now has suggestions, transition.
        # This requires checking the model state after an analysis task.
        # This is not ideal for the coordinator.
        # The AnalysisController should emit a signal like `analysis_finished_with_suggestions(count)`
        # or `analysis_finished_no_suggestions`.

        # Let's assume AnalysisController's model `analysis_status_changed` can be used.
        pass  # This will be handled by specific task type handlers or model change listeners.

    @pyqtSlot(str)  # test_name
    def _handle_analysis_status_changed_for_workflow(self, test_name: str) -> None:
        # This signal comes from TestResultsModel when a test's analysis status is updated.
        if self.state_machine.current_state != WorkflowState.ANALYSIS_RUNNING:
            # Only process this if we are in the ANALYSIS_RUNNING state.
            # Other state transitions (e.g., task completion) should handle other scenarios.
            return

        test_result_item: Optional[TestResult] = None
        for res in self.analysis_controller.test_results_model.results:
            if res.name == test_name:
                test_result_item = res
                break

        if not test_result_item:
            logger.warning(f"Received analysis status update for unknown test: {test_name}")
            return

        current_analysis_status = test_result_item.analysis_status
        suggestions = test_result_item.suggestions

        # This slot might be called for each test that gets analyzed.
        # We want to transition to FIXES_AVAILABLE if *any* test has suggestions
        # and we are in the ANALYSIS_RUNNING state.
        # The transition should ideally happen once the overall analysis task is complete.
        # However, if we want to react as soon as the first suggestion is available:
        if current_analysis_status == AnalysisStatus.SUGGESTIONS_AVAILABLE and suggestions:
            # To avoid multiple transitions if many tests get suggestions,
            # we could check if we've already transitioned or rely on the analysis task completion.
            # For now, let's assume this signal means at least one suggestion is ready.
            # The state machine's `to_fixes_available` should be idempotent or handle multiple calls.

            # Recalculate total suggestions to pass to the state machine
            all_suggestions_count = 0
            for res_item in self.analysis_controller.test_results_model.results:
                if res_item.suggestions:
                    all_suggestions_count += len(res_item.suggestions)

            if all_suggestions_count > 0:
                # Transition if we are still in ANALYSIS_RUNNING.
                # The state machine itself might prevent redundant transitions.
                self.state_machine.to_fixes_available(suggestion_count=all_suggestions_count)

        # If a test is analyzed and has no suggestions, or analysis failed for it,
        # we don't necessarily change the overall workflow state based on a single test.
        # The overall state change (e.g., to RESULTS_AVAILABLE if all analysis is done with no suggestions)
        # should be triggered by the completion of the analysis *task* (batch).
        # This slot primarily reacts to the *presence* of suggestions to enable the "Fixes Available" state.
        elif current_analysis_status == AnalysisStatus.ANALYZED_NO_SUGGESTIONS:
            # Potentially, if all tests are analyzed and none have suggestions,
            # the analysis task completion handler would transition to an appropriate state.
            pass
        elif current_analysis_status == AnalysisStatus.ANALYSIS_FAILED:
            # Similar to above, individual analysis failure might not change workflow state
            # unless it's a global failure handled by task_failed.
            pass

    # Placeholder for FixController signal handlers
    # def _handle_fix_applied(self, task_id: str, application_result: dict) -> None:
    #     # Assuming single fix application for now
    #     if application_result.get("success"):
    #         # This might be one of many. If it's the last one of a batch, then FIXES_APPLIED.
    #         # For simplicity, let's say any successful apply moves to FIXES_APPLIED.
    #         # A count of applied fixes would be good.
    #         self.state_machine.to_fixes_applied(applied_count=1) # Placeholder count
    #     else:
    #         self.state_machine.to_error(f"Fix application failed: {application_result.get('message')}")

    # def _handle_batch_fix_completed(self, task_id: str, succeeded_count: int, failed_count: int, errors: list) -> None:
    #     if succeeded_count > 0:
    #         self.state_machine.to_fixes_applied(applied_count=succeeded_count)
    #     if failed_count > 0:
    #         # Partial success, but also errors.
    #         # The state machine could go to ERROR or a mixed state.
    #         # For now, if any failed, consider it an error for the batch.
    #         self.state_machine.to_error(f"Batch fix operation completed with {failed_count} failures.")

    # def _handle_fix_failed(self, task_id: str, error_message: str) -> None:
    #     self.state_machine.to_error(f"Fix application failed: {error_message}")

    def reset_workflow(self) -> None:
        """Resets the workflow to the initial IDLE state."""
        logger.info("Workflow reset to IDLE state.")
        self.state_machine.to_idle()

    def get_current_file_path(self) -> Optional[Path]:
        """Utility to get current file_path from context if available."""
        return self.state_machine.context.get("file_path")
