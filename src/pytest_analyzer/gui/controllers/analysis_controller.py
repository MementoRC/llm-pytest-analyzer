import logging
from typing import TYPE_CHECKING, Any, List, Optional

from PyQt6.QtCore import QObject, pyqtSlot
from PyQt6.QtWidgets import QMessageBox

from ...core.analyzer_service import PytestAnalyzerService
from ...core.models.pytest_failure import FixSuggestion, PytestFailure  # Added FixSuggestion
from ..models.test_results_model import (  # Added TestResult, TestStatus
    TestFailureDetails,
    TestResult,
    TestResultsModel,
    TestStatus,
)
from .base_controller import BaseController

if TYPE_CHECKING:
    from ..background.task_manager import TaskManager


logger = logging.getLogger(__name__)


class AnalysisController(BaseController):
    """Handles test execution and analysis workflows."""

    def __init__(
        self,
        analyzer_service: PytestAnalyzerService,
        test_results_model: TestResultsModel,
        parent: Optional[QObject] = None,
        task_manager: Optional["TaskManager"] = None,  # Added task_manager
    ):
        super().__init__(parent, task_manager=task_manager)  # Pass to base
        self.analyzer_service = analyzer_service
        self.test_results_model = test_results_model

        # Connect to task manager signals if specific handling is needed here
        if self.task_manager:
            self.task_manager.task_completed.connect(self._handle_task_completion)
            self.task_manager.task_failed.connect(self._handle_task_failure)
            # Progress is handled globally by MainController for now, or can be specific here too

    @pyqtSlot()
    def on_run_tests(self) -> None:
        """Handle the Run Tests action by running tests in the background."""
        self.logger.info("Run Tests action triggered.")
        if not self.task_manager:
            QMessageBox.critical(None, "Error", "TaskManager not available.")
            return

        selected_file = self.test_results_model.source_file
        if selected_file and selected_file.suffix == ".py":
            self.logger.info(f"Preparing to run tests for: {selected_file}")
            # Args for analyzer_service.run_pytest_only:
            # test_path: str, pytest_args: Optional[List[str]] = None, quiet: bool = False,
            # progress: Optional[Progress] = None, task_id: Optional[TaskID] = None

            # For now, no extra pytest_args and quiet=True for background execution
            args = (str(selected_file),)
            kwargs = {"quiet": True}  # Progress and task_id will be added by TaskManager

            task_id = self.submit_background_task(
                callable_task=self.analyzer_service.run_pytest_only,
                args=args,
                kwargs=kwargs,
                use_progress_bridge=True,
            )
            if task_id:
                self.logger.info(f"Run tests task submitted with ID: {task_id}")
                # Status update will be handled by MainController's global signal handlers
            else:
                QMessageBox.warning(None, "Run Tests", "Failed to submit test execution task.")

        else:
            QMessageBox.warning(
                None,
                "Run Tests",
                "Please select a Python test file to run from a loaded report, or implement direct file selection for running tests.",
            )
            self.logger.warning(
                "Run tests action: No valid Python file selected or source_file not set."
            )

    @pyqtSlot()
    def on_analyze(self) -> None:
        """Handle the Analyze action by running analysis in the background."""
        self.logger.info("Analyze action triggered.")
        if not self.task_manager:
            QMessageBox.critical(None, "Error", "TaskManager not available.")
            return

        # Convert TestResult objects with failures/errors to PytestFailure objects
        # This requires TestResult to store enough info, or to have access to original PytestFailure
        # For now, this is a conceptual placeholder. Assume we can get/construct PytestFailure list.

        failures_to_analyze: List[PytestFailure] = []
        if self.test_results_model.results:
            for tr_result in self.test_results_model.results:
                if tr_result.is_failed or tr_result.is_error:
                    # This is a simplified conversion. Real conversion needs more details.
                    # A proper solution would be to store original PytestFailure objects
                    # or have a robust way to reconstruct them.
                    pf = PytestFailure(
                        test_name=tr_result.name,
                        error_message=tr_result.failure_details.message
                        if tr_result.failure_details
                        else "Unknown error",
                        traceback=tr_result.failure_details.traceback
                        if tr_result.failure_details
                        else "",
                        file_path=str(tr_result.file_path) if tr_result.file_path else None,
                        line_number=tr_result.failure_details.line_number
                        if tr_result.failure_details
                        and tr_result.failure_details.line_number is not None
                        else 0,
                    )
                    failures_to_analyze.append(pf)

        if not failures_to_analyze:
            QMessageBox.information(
                None,
                "Analyze",
                "No failed or errored tests found in the current results to analyze.",
            )
            self.logger.info("Analyze action: No failures to analyze.")
            return

        self.logger.info(f"Preparing to analyze {len(failures_to_analyze)} failures.")
        # Args for analyzer_service._generate_suggestions:
        # failures: List[PytestFailure], quiet: bool = False,
        # progress: Optional[Progress] = None, parent_task_id: Optional[TaskID] = None,
        # use_async: Optional[bool] = None

        args = (failures_to_analyze,)
        kwargs = {
            "quiet": True,
            "use_async": self.analyzer_service.use_async,
        }  # Progress and parent_task_id by TaskManager

        task_id = self.submit_background_task(
            callable_task=self.analyzer_service._generate_suggestions,  # Or _async_generate_suggestions
            args=args,
            kwargs=kwargs,
            use_progress_bridge=True,
        )

        if task_id:
            self.logger.info(f"Analysis task submitted with ID: {task_id}")
        else:
            QMessageBox.warning(None, "Analyze", "Failed to submit analysis task.")

    @pyqtSlot(str, object)
    def _handle_task_completion(self, task_id: str, result: Any) -> None:
        """Handle completion of tasks initiated by this controller."""
        self.logger.info(
            f"Task {task_id} completed in AnalysisController. Result type: {type(result)}"
        )

        # Determine if it was a run_tests task or analyze task based on result type or stored task info
        if isinstance(result, list) and all(isinstance(item, PytestFailure) for item in result):
            # Likely result from run_pytest_only
            self.logger.info(f"Test run task {task_id} completed with {len(result)} failures.")
            # Convert PytestFailure list to TestResult list and update model
            test_results: List[TestResult] = []
            for pf_failure in result:
                status = TestStatus.FAILED  # Assuming run_pytest_only returns only failures
                # This needs a more robust mapping if run_pytest_only returns other statuses
                # For now, this is a simplification.
                # A better approach: analyzer_service.run_pytest_only should return richer status info.
                # Or, it should return TestResult objects directly if used by GUI.
                # Let's assume it returns PytestFailure, and we map them.

                # Simplified status mapping
                if "AssertionError" in pf_failure.error_message:  # Basic heuristic
                    status = TestStatus.FAILED
                elif pf_failure.error_message:  # Any error message implies error/failure
                    status = TestStatus.ERROR
                else:  # Should not happen if it's a failure list
                    status = TestStatus.UNKNOWN

                failure_details = None
                if status in (TestStatus.FAILED, TestStatus.ERROR):
                    failure_details = TestFailureDetails(
                        message=pf_failure.error_message,
                        traceback=pf_failure.traceback,
                        file_path=pf_failure.file_path,
                        line_number=pf_failure.line_number,
                    )

                tr = TestResult(
                    name=pf_failure.test_name,
                    status=status,
                    duration=0.0,  # run_pytest_only doesn't provide this easily for individual tests
                    file_path=pf_failure.file_path,
                    failure_details=failure_details,
                )
                test_results.append(tr)

            # Assuming the source_file is still relevant or set it to where tests were run
            source_file = (
                self.test_results_model.source_file
            )  # This might be incorrect if tests run on a dir
            source_type = "runtime_py"  # Indicate these are from a direct run
            self.test_results_model.set_results(test_results, source_file, source_type)
            QMessageBox.information(
                None,
                "Tests Run",
                f"Tests executed. Found {len(test_results)} results (mapped from failures).",
            )

        elif isinstance(result, list) and all(isinstance(item, FixSuggestion) for item in result):
            # Likely result from _generate_suggestions
            self.logger.info(f"Analysis task {task_id} completed with {len(result)} suggestions.")
            # TODO: Integrate suggestions into the TestResultsModel and UI
            # This might involve updating TestGroup or TestResult with suggestions.
            # For now, just a message.
            QMessageBox.information(
                None, "Analysis Complete", f"Analysis finished. Received {len(result)} suggestions."
            )
            # Example: self.test_results_model.set_suggestions(result) - needs new model method

        else:
            self.logger.info(f"Task {task_id} completed with unhandled result type: {type(result)}")

    @pyqtSlot(str, str)
    def _handle_task_failure(self, task_id: str, error_message: str) -> None:
        """Handle failure of tasks initiated by this controller."""
        # Global handler in MainController already shows a QMessageBox.
        # This is for any specific cleanup or state change in AnalysisController.
        self.logger.error(
            f"AnalysisController received failure for task {task_id}: {error_message.splitlines()[0]}"
        )
        # No specific action here beyond what MainController does, for now.
