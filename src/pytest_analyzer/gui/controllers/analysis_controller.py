import logging
from typing import TYPE_CHECKING, Any, List, Optional

from PyQt6.QtCore import QObject, pyqtSlot
from PyQt6.QtWidgets import QMessageBox

from ...core.analyzer_service import PytestAnalyzerService
from ...core.models.pytest_failure import FixSuggestion, PytestFailure
from ..models.test_results_model import (
    AnalysisStatus,  # Added AnalysisStatus
    TestResultsModel,
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

        source_path = self.test_results_model.source_file
        source_type = self.test_results_model.source_type

        if source_path and (source_type == "py" or source_type == "directory"):
            self.logger.info(f"Preparing to run tests for: {source_path} (type: {source_type})")

            # Clear previous run results from the model before starting a new run
            # This ensures that the UI reflects that a new set of results is pending.
            # The FileController might have already cleared it if a new file/dir was selected.
            # If running tests on an already loaded report, this explicit clear is good.
            # However, if source_file is from a report, this action might be confusing.
            # Let's assume "Run Tests" always implies a fresh execution based on source_file.
            # The model's set_results will replace old results anyway.
            # For clarity, we can emit a status that tests are running.

            args = (str(source_path),)  # test_path for run_pytest_only
            kwargs = {"quiet": True}  # Progress and task_id will be added by TaskManager

            task_id = self.submit_background_task(
                callable_task=self.analyzer_service.run_pytest_only,
                args=args,
                kwargs=kwargs,
                use_progress_bridge=True,
                # Assign a custom task identifier if needed for _handle_task_completion
                # task_id_prefix="run_tests_"
            )
            if task_id:
                self.logger.info(f"Run tests task submitted with ID: {task_id} for {source_path}")
                # MainController's global signal handlers will show "Task started..."
            else:
                QMessageBox.warning(
                    None, "Run Tests", f"Failed to submit test execution task for {source_path}."
                )

        else:
            QMessageBox.warning(
                None,
                "Run Tests",
                "Please select a Python test file or directory first (e.g., via File menu or File Selection tab).",
            )
            self.logger.warning(
                "Run tests action: No valid Python file or directory selected in the model."
            )

    @pyqtSlot()
    def on_analyze(self) -> None:
        """Handle the Analyze action by running analysis in the background."""
        self.logger.info("Analyze action triggered.")
        if not self.task_manager:
            QMessageBox.critical(None, "Error", "TaskManager not available.")
            return

        failures_to_analyze = self.test_results_model.get_pytest_failures_for_analysis()

        if not failures_to_analyze:
            QMessageBox.information(
                None,
                "Analyze",
                "No failed or errored tests found in the current results to analyze.",
            )
            self.logger.info("Analyze action: No failures to analyze.")
            return

        self.logger.info(f"Preparing to analyze {len(failures_to_analyze)} failures.")

        # Update status for tests being analyzed
        for pf_failure in failures_to_analyze:
            self.test_results_model.update_test_data(
                test_name=pf_failure.test_name, analysis_status=AnalysisStatus.ANALYSIS_PENDING
            )

        args = (failures_to_analyze,)
        kwargs = {
            "quiet": True,  # Suppress terminal output from service if any
            "use_async": self.analyzer_service.use_async,
        }

        task_id = self.submit_background_task(
            callable_task=self.analyzer_service._generate_suggestions,
            args=args,
            kwargs=kwargs,
            use_progress_bridge=True,
            # task_id_prefix="analyze_failures_"
        )

        if task_id:
            self.logger.info(f"Analysis task submitted with ID: {task_id}")
        else:
            QMessageBox.warning(None, "Analyze", "Failed to submit analysis task.")
            # Revert status for tests that were marked PENDING
            for pf_failure in failures_to_analyze:
                self.test_results_model.update_test_data(
                    test_name=pf_failure.test_name,
                    analysis_status=AnalysisStatus.NOT_ANALYZED,  # Or ANALYSIS_FAILED if preferred
                )

    @pyqtSlot(str, object)
    def _handle_task_completion(self, task_id: str, result: Any) -> None:
        """Handle completion of tasks initiated by this controller."""
        self.logger.info(
            f"Task {task_id} completed in AnalysisController. Result type: {type(result)}"
        )

        # TODO: A more robust way to identify task origin if multiple task types are submitted
        # by this controller. For now, relying on result type.

        if isinstance(result, list) and (not result or isinstance(result[0], PytestFailure)):
            # Result from run_pytest_only (List[PytestFailure])
            pytest_failures: List[PytestFailure] = result
            self.logger.info(
                f"Test run task {task_id} completed with {len(pytest_failures)} failures."
            )

            source_path = self.test_results_model.source_file
            run_source_type = self.test_results_model.source_type  # "py" or "directory"

            if not source_path:
                self.logger.error(
                    f"Source path not found in model for completed task {task_id}. Cannot load results."
                )
                QMessageBox.warning(
                    None,
                    "Test Run Error",
                    "Could not determine source of test run to load results.",
                )
                return

            self.test_results_model.load_test_run_results(
                pytest_failures, source_path, f"{run_source_type}_run"
            )

            num_results = len(self.test_results_model.results)
            if not pytest_failures:  # No failures from the run
                QMessageBox.information(
                    None,
                    "Tests Run",
                    f"Tests executed from '{source_path.name}'. No failures reported.",
                )
            else:
                QMessageBox.information(
                    None,
                    "Tests Run",
                    f"Tests executed from '{source_path.name}'. Found {num_results} failures/errors.",
                )

        elif isinstance(result, list) and (not result or isinstance(result[0], FixSuggestion)):
            # Result from _generate_suggestions (List[FixSuggestion])
            suggestions: List[FixSuggestion] = result
            self.logger.info(
                f"Analysis task {task_id} completed with {len(suggestions)} suggestions."
            )

            # Group suggestions by test name
            suggestions_by_test_name: dict[str, List[FixSuggestion]] = {}
            for sugg in suggestions:
                test_name = sugg.failure.test_name
                if test_name not in suggestions_by_test_name:
                    suggestions_by_test_name[test_name] = []
                suggestions_by_test_name[test_name].append(sugg)

            # Update model for tests that were part of the analysis
            # (those that were ANALYSIS_PENDING or identified by get_pytest_failures_for_analysis)
            processed_test_names = set(suggestions_by_test_name.keys())

            for test_result in self.test_results_model.results:
                if test_result.analysis_status == AnalysisStatus.ANALYSIS_PENDING:
                    suggs_for_this_test = suggestions_by_test_name.get(test_result.name, [])
                    new_status = (
                        AnalysisStatus.SUGGESTIONS_AVAILABLE
                        if suggs_for_this_test
                        else AnalysisStatus.ANALYZED_NO_SUGGESTIONS
                    )
                    self.test_results_model.update_test_data(
                        test_name=test_result.name,
                        suggestions=suggs_for_this_test,
                        analysis_status=new_status,
                    )
                    if test_result.name in processed_test_names:
                        processed_test_names.remove(test_result.name)

            if (
                processed_test_names
            ):  # Suggestions for tests not marked PENDING (should not happen ideally)
                self.logger.warning(
                    f"Received suggestions for tests not marked as PENDING: {processed_test_names}"
                )

            QMessageBox.information(
                None,
                "Analysis Complete",
                f"Analysis finished. Received {len(suggestions)} suggestions for {len(suggestions_by_test_name)} tests.",
            )
        else:
            self.logger.warning(
                f"Task {task_id} completed with unhandled result type: {type(result)}"
            )

    @pyqtSlot(str, str)
    def _handle_task_failure(self, task_id: str, error_message: str) -> None:
        """Handle failure of tasks initiated by this controller."""
        self.logger.error(
            f"AnalysisController received failure for task {task_id}: {error_message.splitlines()[0]}"
        )
        # Check if this failed task was an analysis task.
        # This is tricky without storing task metadata (e.g. type of task, items being processed).
        # For now, assume any failure might impact tests that were ANALYSIS_PENDING.

        # Revert status for tests that were ANALYSIS_PENDING
        # This is a broad stroke; ideally, we'd know which task failed.
        # If a run_tests task fails, ANALYSIS_PENDING tests are unaffected.
        # If an analyze_failures task fails, then update.
        # Heuristic: if there are any ANALYSIS_PENDING tests, assume the failed task was analysis.
        # This could be improved by inspecting task_id if we add prefixes, or by the MainController
        # passing more context about the failed task if the signal supported it.

        updated_to_failed = False
        for test_result in self.test_results_model.results:
            if test_result.analysis_status == AnalysisStatus.ANALYSIS_PENDING:
                self.test_results_model.update_test_data(
                    test_name=test_result.name, analysis_status=AnalysisStatus.ANALYSIS_FAILED
                )
                updated_to_failed = True

        if updated_to_failed:
            self.logger.info(
                "Set status to ANALYSIS_FAILED for tests that were ANALYSIS_PENDING due to task failure."
            )
        # The global handler in MainController already shows a QMessageBox.
