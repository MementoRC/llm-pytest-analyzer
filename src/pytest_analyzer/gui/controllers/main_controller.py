import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import QObject, pyqtSlot
from PyQt6.QtWidgets import QFileDialog, QMessageBox

from ..background.task_manager import TaskManager  # Added import
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
        # Initialize TaskManager first as it's needed by BaseController's __init__
        self.task_manager = TaskManager(parent=self)
        # Call super().__init__ once, passing the task_manager
        super().__init__(parent, task_manager=self.task_manager)

        # Assign other MainController specific attributes
        self.main_window = main_window
        self.app = app
        self.core_settings: CoreSettings = app.core_settings
        self.analyzer_service: PytestAnalyzerService = main_window.analyzer_service
        self.test_results_model: TestResultsModel = main_window.test_results_model

        # Initialize sub-controllers, passing TaskManager
        # BaseController's __init__ for these sub-controllers will correctly receive the task_manager
        self.file_controller = FileController(
            self.test_results_model, parent=self, task_manager=self.task_manager
        )
        self.test_results_controller = TestResultsController(
            self.test_results_model, parent=self, task_manager=self.task_manager
        )
        self.analysis_controller = AnalysisController(
            self.analyzer_service,
            self.test_results_model,
            parent=self,
            task_manager=self.task_manager,
        )
        self.settings_controller = SettingsController(
            parent=self, task_manager=self.task_manager
        )  # Assuming it might need it

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

        # --- TaskManager Global Signals to MainWindow Status Updates ---
        self.task_manager.task_started.connect(self._on_global_task_started)
        self.task_manager.task_progress.connect(self._on_global_task_progress)
        self.task_manager.task_completed.connect(self._on_global_task_completed)
        self.task_manager.task_failed.connect(self._on_global_task_failed)

    @pyqtSlot(str, str)
    def _on_global_task_started(self, task_id: str, description: str) -> None:
        self.main_window.status_label.setText(f"Task started: {description} ({task_id[:8]}...).")
        # Optionally, show a global progress bar or indicator

    @pyqtSlot(str, int, str)
    def _on_global_task_progress(self, task_id: str, percentage: int, message: str) -> None:
        self.main_window.status_label.setText(
            f"Progress ({task_id[:8]}...): {percentage}% - {message}"
        )
        # Optionally, update a global progress bar

    @pyqtSlot(str, object)
    def _on_global_task_completed(self, task_id: str, result: Any) -> None:
        # Result is often not directly shown in status bar, but controller handles it.
        self.main_window.status_label.setText(f"Task completed: {task_id[:8]}...")
        # Optionally, hide global progress bar

    @pyqtSlot(str, str)
    def _on_global_task_failed(self, task_id: str, error_message: str) -> None:
        self.main_window.status_label.setText(f"Task failed: {task_id[:8]}...")
        QMessageBox.warning(
            self.main_window,
            "Task Error",
            f"A background task failed ({task_id[:8]}):\n\n{error_message.splitlines()[0]}",  # Show first line
        )
        # Optionally, hide global progress bar, show error icon

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
