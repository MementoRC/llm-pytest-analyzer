import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, pyqtSlot
from PyQt6.QtWidgets import QFileDialog, QMessageBox

from .analysis_controller import AnalysisController
from .base_controller import BaseController
from .file_controller import FileController
from .settings_controller import SettingsController
from .test_results_controller import TestResultsController

if TYPE_CHECKING:
    from ...core.analyzer_service import PytestAnalyzerService
    from ...utils.settings import Settings as CoreSettings
    from ..app import PytestAnalyzerApp
    from ..main_window import MainWindow
    from ..models.test_results_model import TestResultsModel
    from ..views.file_selection_view import FileSelectionView
    from ..views.test_results_view import TestResultsView

logger = logging.getLogger(__name__)


class MainController(BaseController):
    """Main orchestration controller for the GUI."""

    def __init__(self, main_window: "MainWindow", app: "PytestAnalyzerApp", parent: QObject = None):
        super().__init__(parent)
        self.main_window = main_window
        self.app = app
        self.core_settings: CoreSettings = app.core_settings
        self.analyzer_service: PytestAnalyzerService = main_window.analyzer_service
        self.test_results_model: TestResultsModel = main_window.test_results_model

        # Initialize sub-controllers
        self.file_controller = FileController(self.test_results_model, parent=self)
        self.test_results_controller = TestResultsController(self.test_results_model, parent=self)
        self.analysis_controller = AnalysisController(
            self.analyzer_service, self.test_results_model, parent=self
        )
        self.settings_controller = SettingsController(parent=self)

        self._connect_signals()
        self.logger.info("MainController initialized and signals connected.")

    def _connect_signals(self) -> None:
        """Connect signals and slots between components."""
        # --- MainWindow Actions to Controllers ---
        self.main_window.open_action.triggered.connect(self.on_open)
        self.main_window.about_action.triggered.connect(self.on_about)
        self.main_window.exit_action.triggered.connect(self.main_window.close)  # Can remain direct

        self.main_window.run_tests_action.triggered.connect(self.analysis_controller.on_run_tests)
        self.main_window.analyze_action.triggered.connect(self.analysis_controller.on_analyze)
        self.main_window.settings_action.triggered.connect(self.settings_controller.on_settings)

        # --- View Signals to Controllers ---
        # FileSelectionView -> FileController
        file_selection_view: FileSelectionView = self.main_window.file_selection_view
        file_selection_view.file_selected.connect(self.file_controller.on_file_selected)
        file_selection_view.report_type_changed.connect(self.file_controller.on_report_type_changed)

        # TestResultsView -> TestResultsController
        test_results_view: TestResultsView = self.main_window.test_results_view
        test_results_view.test_selected.connect(self.test_results_controller.on_test_selected)
        test_results_view.group_selected.connect(self.test_results_controller.on_group_selected)

        # --- Controller Signals to Model/View Updates ---
        # FileController -> TestResultsModel
        self.file_controller.results_loaded.connect(self.test_results_model.set_results)
        # FileController -> MainWindow Status Label
        self.file_controller.status_message_updated.connect(self.main_window.status_label.setText)

        # TestResultsController -> MainWindow Status Label
        self.test_results_controller.status_message_updated.connect(
            self.main_window.status_label.setText
        )

    @pyqtSlot()
    def on_open(self) -> None:
        """Handle the Open action from MainWindow."""
        self.logger.info("Open action triggered.")
        file_path_str, _ = QFileDialog.getOpenFileName(
            self.main_window,  # Parent for the dialog
            "Open File",
            str(self.core_settings.project_root),  # Default directory
            "Python Files (*.py);;JSON Files (*.json);;XML Files (*.xml);;All Files (*)",
        )

        if file_path_str:
            path = Path(file_path_str)
            self.logger.info(f"File dialog selected: {path}")
            # Delegate to FileController to handle the selection
            self.file_controller.on_file_selected(path)
        else:
            self.logger.info("File dialog cancelled.")

    @pyqtSlot()
    def on_about(self) -> None:
        """Handle the About action from MainWindow."""
        self.logger.info("About action triggered.")
        QMessageBox.about(
            self.main_window,  # Parent for the dialog
            "About Pytest Analyzer",
            f"""<b>Pytest Analyzer</b> v{self.app.applicationVersion()}
            <p>A tool for analyzing pytest test failures and suggesting fixes.</p>
            <p>Created by MementoRC</p>
            """,
        )
