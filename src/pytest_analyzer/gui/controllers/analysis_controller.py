import logging

from PyQt6.QtCore import QObject, pyqtSlot
from PyQt6.QtWidgets import QMessageBox

from ...core.analyzer_service import PytestAnalyzerService
from ..models.test_results_model import TestResultsModel
from .base_controller import BaseController

logger = logging.getLogger(__name__)


class AnalysisController(BaseController):
    """Handles test execution and analysis workflows."""

    def __init__(
        self,
        analyzer_service: PytestAnalyzerService,
        test_results_model: TestResultsModel,
        parent: QObject = None,
    ):
        super().__init__(parent)
        self.analyzer_service = analyzer_service
        self.test_results_model = test_results_model

    @pyqtSlot()
    def on_run_tests(self) -> None:
        """Handle the Run Tests action."""
        self.logger.info("Run Tests action triggered.")
        # Will be implemented with proper test execution
        QMessageBox.information(
            None, "Run Tests", "Test execution will be implemented in a future task."
        )
        # Example future logic:
        # selected_file = self.test_results_model.source_file # Or from another source
        # if selected_file and selected_file.suffix == ".py":
        #     failures = self.analyzer_service.run_pytest_only(str(selected_file))
        #     # Convert PytestFailure to TestResult and update model
        # else:
        #     QMessageBox.warning(None, "Run Tests", "Please select a Python test file to run.")

    @pyqtSlot()
    def on_analyze(self) -> None:
        """Handle the Analyze action."""
        self.logger.info("Analyze action triggered.")
        # Will be implemented with proper analysis
        QMessageBox.information(
            None, "Analyze", "Test analysis will be implemented in a future task."
        )
        # Example future logic:
        # failures_to_analyze = [] # Get PytestFailure objects from TestResultsModel
        # if self.test_results_model.results:
        #     for tr_result in self.test_results_model.results:
        #         if tr_result.is_failed or tr_result.is_error:
        #             # This needs a proper conversion or storage of PytestFailure
        #             # For now, this is a conceptual placeholder
        #             pass # Convert TestResult back to PytestFailure or use stored ones
        #
        # if failures_to_analyze:
        #    suggestions = self.analyzer_service._generate_suggestions(failures_to_analyze)
        #    # Update UI with suggestions
        # else:
        #    QMessageBox.information(None, "Analyze", "No failures to analyze.")
