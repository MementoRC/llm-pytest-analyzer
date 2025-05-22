import logging

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from ..models.test_results_model import TestGroup, TestResult, TestResultsModel
from .base_controller import BaseController

logger = logging.getLogger(__name__)


class TestResultsController(BaseController):
    """Manages interactions with the test results view and model."""

    status_message_updated = pyqtSignal(str)

    def __init__(self, test_results_model: TestResultsModel, parent: QObject = None):
        super().__init__(parent)
        self.test_results_model = test_results_model
        # No direct interaction with TestResultsModel needed here for now,
        # as selection primarily updates details view which is handled by TestResultsView itself.
        # This controller is for reacting to selections if other parts of app need to know.

    @pyqtSlot(TestResult)
    def on_test_selected(self, test: TestResult) -> None:
        """
        Handle test selection from the test results view.

        Args:
            test: Selected test result
        """
        self.logger.debug(f"Test selected: {test.name}")
        self.status_message_updated.emit(f"Selected test: {test.name}")
        # Further logic can be added here if other components need to react to test selection.

    @pyqtSlot(TestGroup)
    def on_group_selected(self, group: TestGroup) -> None:
        """
        Handle group selection from the test results view.

        Args:
            group: Selected test group
        """
        self.logger.debug(f"Group selected: {group.name}")
        self.status_message_updated.emit(f"Selected group: {group.name} ({len(group.tests)} tests)")
        # Further logic for group selection.
