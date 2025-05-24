import logging
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from PyQt6.QtCore import QObject, pyqtSlot
from PyQt6.QtWidgets import QMessageBox

from ...core.analysis.failure_grouper import extract_failure_fingerprint
from ...core.analyzer_service import PytestAnalyzerService
from ...core.models.pytest_failure import FixSuggestion, PytestFailure
from ..models.test_results_model import (
    AnalysisStatus,
    TestResult,
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
        self.logger.debug(
            f"AnalysisController: Initializing with service: {analyzer_service}, model: {test_results_model}, task_manager: {task_manager}"
        )
        self.analyzer_service = analyzer_service
        self.test_results_model = test_results_model
        self.suggestion_cache: Dict[str, Tuple[float, List[FixSuggestion]]] = {}
        self.project_root_for_fingerprint: Optional[str] = None
        if self.analyzer_service.path_resolver:  # Ensure path_resolver exists
            self.project_root_for_fingerprint = str(
                self.analyzer_service.path_resolver.project_root
            )
            self.logger.debug(
                f"AnalysisController: Set project_root_for_fingerprint: {self.project_root_for_fingerprint}"
            )

        # Connect to task manager signals if specific handling is needed here
        if self.task_manager:
            self.task_manager.task_completed.connect(self._handle_task_completion)
            self.task_manager.task_failed.connect(self._handle_task_failure)
            self.logger.debug("AnalysisController: Connected to TaskManager signals.")
            # Progress is handled globally by MainController for now, or can be specific here too
        else:
            self.logger.debug("AnalysisController: No TaskManager provided.")
        self.logger.debug("AnalysisController: Initialization complete.")

    @pyqtSlot()
    def on_run_tests(self) -> None:
        """Handle the Run Tests action by running tests in the background."""
        self.logger.debug("AnalysisController: on_run_tests triggered.")
        self.logger.info("Run Tests action triggered.")
        if not self.task_manager:
            self.logger.error("AnalysisController: TaskManager not available for on_run_tests.")
            QMessageBox.critical(None, "Error", "TaskManager not available.")
            return

        source_path = self.test_results_model.source_file
        source_type = self.test_results_model.source_type
        self.logger.debug(
            f"AnalysisController: Retrieved from model - source_path: {source_path}, source_type: {source_type}"
        )

        if source_path and (source_type == "py" or source_type == "directory"):
            self.logger.info(f"Preparing to run tests for: {source_path} (type: {source_type})")
            self.logger.debug("AnalysisController: Valid source path and type for running tests.")

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
            self.logger.debug(f"AnalysisController: Task args: {args}, kwargs: {kwargs}")

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
                self.logger.debug(f"AnalysisController: Test run task submitted, ID: {task_id}")
                # MainController's global signal handlers will show "Task started..."
            else:
                self.logger.error(
                    f"AnalysisController: Failed to submit test execution task for {source_path}."
                )
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
                "AnalysisController: Run tests action: No valid Python file or directory selected in the model."
            )
        self.logger.debug("AnalysisController: on_run_tests finished.")

    @pyqtSlot()
    def on_analyze(self) -> None:
        """Handle the Analyze action by running analysis in the background."""
        self.logger.debug("AnalysisController: on_analyze triggered.")
        self.logger.info("Analyze action triggered.")
        if not self.task_manager:
            self.logger.error("AnalysisController: TaskManager not available for on_analyze.")
            QMessageBox.critical(None, "Error", "TaskManager not available.")
            return

        # Check if LLM suggester is configured
        suggester = self.analyzer_service.llm_suggester
        if not suggester._llm_request_func and not suggester._async_llm_request_func:
            self.logger.warning(
                "AnalysisController: LLM suggester not configured (no request func)."
            )
            QMessageBox.warning(
                None,
                "LLM Not Configured",
                "The Language Model (LLM) for generating suggestions is not configured.\n"
                "Please set the LLM provider and API key in the Settings.",
            )
            self.logger.warning("Analysis aborted: LLM suggester not configured.")
            return

        all_failures_for_analysis = self.test_results_model.get_pytest_failures_for_analysis()

        if not all_failures_for_analysis:
            QMessageBox.information(
                None,
                "Analyze",
                "No failed or errored tests found in the current results to analyze.",
            )
            self.logger.info("Analyze action: No failures to analyze.")
            return

        self.logger.info(f"Preparing to analyze {len(all_failures_for_analysis)} failures.")

        failures_to_submit_for_llm: List[PytestFailure] = []
        cached_suggestion_count = 0

        if self.analyzer_service.settings.llm_cache_enabled:
            current_time = time.time()
            cache_ttl = self.analyzer_service.settings.llm_cache_ttl_seconds
            for pf_failure in all_failures_for_analysis:
                fingerprint = extract_failure_fingerprint(
                    pf_failure, self.project_root_for_fingerprint
                )
                if fingerprint in self.suggestion_cache:
                    timestamp, cached_suggestions = self.suggestion_cache[fingerprint]
                    if (current_time - timestamp) < cache_ttl:
                        self.logger.info(
                            f"Cache hit (valid TTL) for failure {pf_failure.test_name} (fingerprint: {fingerprint[:8]}...)."
                        )
                        self.test_results_model.update_test_data(
                            test_name=pf_failure.test_name,
                            suggestions=cached_suggestions,
                            analysis_status=AnalysisStatus.SUGGESTIONS_AVAILABLE
                            if cached_suggestions
                            else AnalysisStatus.ANALYZED_NO_SUGGESTIONS,
                        )
                        cached_suggestion_count += 1
                    else:
                        self.logger.info(
                            f"Cache hit (expired TTL) for failure {pf_failure.test_name}. Will re-fetch."
                        )
                        del self.suggestion_cache[fingerprint]  # Remove expired entry
                        failures_to_submit_for_llm.append(pf_failure)
                        self.test_results_model.update_test_data(
                            test_name=pf_failure.test_name,
                            analysis_status=AnalysisStatus.ANALYSIS_PENDING,
                        )
                else:  # Not in cache
                    failures_to_submit_for_llm.append(pf_failure)
                    self.test_results_model.update_test_data(
                        test_name=pf_failure.test_name,
                        analysis_status=AnalysisStatus.ANALYSIS_PENDING,
                    )
            self.logger.info(f"{cached_suggestion_count} failures served from valid cache.")
        else:  # Cache disabled
            failures_to_submit_for_llm = all_failures_for_analysis
            for pf_failure in failures_to_submit_for_llm:
                self.test_results_model.update_test_data(
                    test_name=pf_failure.test_name, analysis_status=AnalysisStatus.ANALYSIS_PENDING
                )

        if not failures_to_submit_for_llm:
            QMessageBox.information(
                None,
                "Analysis Complete",
                "All failures were resolved from the cache. No new LLM analysis needed.",
            )
            self.logger.info("All failures resolved from cache. No LLM task submitted.")
            return

        self.logger.info(f"Submitting {len(failures_to_submit_for_llm)} failures for LLM analysis.")

        args = (failures_to_submit_for_llm,)
        kwargs = {
            "quiet": True,  # Suppress terminal output from service if any
            "use_async": self.analyzer_service.use_async,
        }

        task_id = self.submit_background_task(
            callable_task=self.analyzer_service._generate_suggestions,
            args=args,
            kwargs=kwargs,
            use_progress_bridge=True,
            description=f"Analyzing {len(failures_to_submit_for_llm)} test failures with LLM...",
        )

        if task_id:
            self.logger.info(f"LLM Analysis task submitted with ID: {task_id}")
        else:
            QMessageBox.warning(None, "Analyze", "Failed to submit LLM analysis task.")
            # Revert status for tests that were marked PENDING
            for pf_failure in failures_to_submit_for_llm:
                self.test_results_model.update_test_data(
                    test_name=pf_failure.test_name,
                    analysis_status=AnalysisStatus.ANALYSIS_FAILED,
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
            processed_test_names = set()

            for test_name, suggs_for_this_test in suggestions_by_test_name.items():
                processed_test_names.add(test_name)
                new_status = (
                    AnalysisStatus.SUGGESTIONS_AVAILABLE
                    if suggs_for_this_test
                    else AnalysisStatus.ANALYZED_NO_SUGGESTIONS
                )
                self.test_results_model.update_test_data(
                    test_name=test_name,
                    suggestions=suggs_for_this_test,
                    analysis_status=new_status,
                )
                # Add to cache
                if self.analyzer_service.settings.llm_cache_enabled and suggs_for_this_test:
                    original_failure = next(
                        (
                            f.failure
                            for f in suggs_for_this_test
                            if f.failure.test_name == test_name
                        ),
                        None,
                    )
                    if original_failure:
                        fingerprint = extract_failure_fingerprint(
                            original_failure, self.project_root_for_fingerprint
                        )
                        self.suggestion_cache[fingerprint] = (time.time(), suggs_for_this_test)
                        self.logger.info(
                            f"Stored suggestions for {test_name} (fingerprint: {fingerprint[:8]}...) in cache with TTL."
                        )

            for test_result_in_model in self.test_results_model.results:
                if test_result_in_model.analysis_status == AnalysisStatus.ANALYSIS_PENDING:
                    if test_result_in_model.name not in processed_test_names:
                        self.logger.warning(
                            f"Test {test_result_in_model.name} was PENDING but no suggestions received. Marking as NO_SUGGESTIONS."
                        )
                        self.test_results_model.update_test_data(
                            test_name=test_result_in_model.name,
                            suggestions=[],
                            analysis_status=AnalysisStatus.ANALYZED_NO_SUGGESTIONS,
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

    @pyqtSlot(TestResult)
    def on_analyze_single_test(self, test_result_to_analyze: TestResult) -> None:
        """Handle request to analyze a single test."""
        self.logger.info(f"Single test analysis requested for: {test_result_to_analyze.name}")
        if not self.task_manager:
            QMessageBox.critical(
                None, "Error", "TaskManager not available for single test analysis."
            )
            return

        suggester = self.analyzer_service.llm_suggester
        if not suggester._llm_request_func and not suggester._async_llm_request_func:
            QMessageBox.warning(
                None,
                "LLM Not Configured",
                "The Language Model (LLM) for generating suggestions is not configured.\n"
                "Please set the LLM provider and API key in the Settings.",
            )
            self.logger.warning("Single test analysis aborted: LLM suggester not configured.")
            return

        if (
            not (test_result_to_analyze.is_failed or test_result_to_analyze.is_error)
            or not test_result_to_analyze.failure_details
        ):
            QMessageBox.warning(
                None,
                "Analyze Test",
                f"Test '{test_result_to_analyze.name}' is not a failure or has no details.",
            )
            self.logger.warning(
                f"Cannot analyze test {test_result_to_analyze.name}: not a failure or no details."
            )
            # Optionally reset status if it was PENDING from a failed attempt
            if test_result_to_analyze.analysis_status == AnalysisStatus.ANALYSIS_PENDING:
                self.test_results_model.update_test_data(
                    test_name=test_result_to_analyze.name,
                    analysis_status=AnalysisStatus.NOT_ANALYZED,
                )
            return

        # Convert TestResult to PytestFailure
        pf_failure = PytestFailure(
            test_name=test_result_to_analyze.name,
            test_file=str(test_result_to_analyze.file_path)
            if test_result_to_analyze.file_path
            else "",
            error_type=test_result_to_analyze.failure_details.error_type,
            error_message=test_result_to_analyze.failure_details.message,
            traceback=test_result_to_analyze.failure_details.traceback,
            line_number=test_result_to_analyze.failure_details.line_number,
            # relevant_code and raw_output_section are not in TestResult, keep as None
        )

        self.logger.info(f"Submitting single test {pf_failure.test_name} for LLM analysis.")
        self.test_results_model.update_test_data(
            test_name=pf_failure.test_name, analysis_status=AnalysisStatus.ANALYSIS_PENDING
        )

        args = ([pf_failure],)  # _generate_suggestions expects a list of PytestFailure
        kwargs = {
            "quiet": True,
            "use_async": self.analyzer_service.use_async,
        }

        task_id = self.submit_background_task(
            callable_task=self.analyzer_service._generate_suggestions,
            args=args,
            kwargs=kwargs,
            use_progress_bridge=True,  # Can be True, progress will be for 1 item
            description=f"Analyzing test {pf_failure.test_name} with LLM...",
            # task_id_prefix=f"analyze_single_{pf_failure.test_name}_" # Optional for specific handling
        )

        if task_id:
            self.logger.info(
                f"Single test LLM Analysis task submitted with ID: {task_id} for {pf_failure.test_name}"
            )
        else:
            QMessageBox.warning(
                None,
                "Analyze Test",
                f"Failed to submit LLM analysis task for {pf_failure.test_name}.",
            )
            self.test_results_model.update_test_data(
                test_name=pf_failure.test_name,
                analysis_status=AnalysisStatus.ANALYSIS_FAILED,
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
