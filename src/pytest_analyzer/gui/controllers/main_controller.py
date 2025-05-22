import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, List

from PyQt6.QtCore import QObject, pyqtSlot
from PyQt6.QtWidgets import QFileDialog, QMessageBox

from ...core.analyzer_service import PytestAnalyzerService
from ..background.task_manager import TaskManager
from .analysis_controller import AnalysisController
from .base_controller import BaseController
from .file_controller import FileController
from .settings_controller import SettingsController
from .test_discovery_controller import TestDiscoveryController
from .test_execution_controller import TestExecutionController
from .test_results_controller import TestResultsController

if TYPE_CHECKING:
    from ...utils.settings import Settings as CoreSettings
    from ..app import PytestAnalyzerApp
    from ..main_window import MainWindow
    from ..models.test_results_model import TestResultsModel
    from ..views.file_selection_view import FileSelectionView
    from ..views.test_discovery_view import TestDiscoveryView
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
            app=self.app, parent=self, task_manager=self.task_manager
        )
        self.test_discovery_controller = TestDiscoveryController(
            self.analyzer_service, parent=self, task_manager=self.task_manager
        )
        # Instantiate TestExecutionController
        self.test_execution_controller = TestExecutionController(
            progress_view=self.main_window.test_execution_progress_view,
            output_view=self.main_window.test_output_view,  # Pass the output view
            task_manager=self.task_manager,
            analyzer_service=self.analyzer_service,
            parent=self,
        )

        self._connect_signals()
        self.logger.info("MainController initialized and signals connected.")

    def _connect_signals(self) -> None:
        """Connect signals and slots between components."""
        # --- MainWindow Actions to Controllers ---
        self.main_window.open_action.triggered.connect(self.on_open)
        self.main_window.about_action.triggered.connect(
            self.main_window.on_about
        )  # Can remain direct or move to a controller
        self.main_window.exit_action.triggered.connect(self.main_window.close)

        # self.main_window.run_tests_action.triggered.connect(self.analysis_controller.on_run_tests)
        # Connect Run Tests action to TestExecutionController or a new MainController slot
        self.main_window.run_tests_action.triggered.connect(self.on_run_tests_action_triggered)

        self.main_window.analyze_action.triggered.connect(self.analysis_controller.on_analyze)
        self.main_window.settings_action.triggered.connect(self.settings_controller.on_settings)

        # --- View Signals to Controllers ---
        # FileSelectionView -> FileController
        file_selection_view: FileSelectionView = self.main_window.file_selection_view
        file_selection_view.file_selected.connect(self.file_controller.on_file_selected)
        file_selection_view.report_type_changed.connect(self.file_controller.on_report_type_changed)

        # TestResultsView -> TestResultsController
        test_results_view: TestResultsView = self.main_window.test_results_view
        # These connections were previously in MainWindow, now correctly here
        test_results_view.test_selected.connect(self.test_results_controller.on_test_selected)
        test_results_view.group_selected.connect(self.test_results_controller.on_group_selected)

        test_discovery_view: TestDiscoveryView = self.main_window.test_discovery_view
        test_discovery_view.discover_tests_requested.connect(
            self.test_discovery_controller.request_discover_tests
        )
        # TestDiscoveryView.selection_changed could be connected if needed by a controller

        # --- Controller Signals to Model/View Updates ---
        # FileController -> TestResultsModel
        self.file_controller.results_loaded.connect(self.test_results_model.set_results)
        # FileController -> MainWindow Status Label
        self.file_controller.status_message_updated.connect(self.main_window.status_label.setText)

        # TestResultsController -> MainWindow Status Label
        self.test_results_controller.status_message_updated.connect(
            self.main_window.status_label.setText
        )

        # TestDiscoveryController -> TestDiscoveryView and MainWindow Status
        self.test_discovery_controller.tests_discovered.connect(
            test_discovery_view.update_test_tree
        )
        self.test_discovery_controller.discovery_started.connect(
            lambda msg: self.main_window.status_label.setText(f"Discovery: {msg}")
        )
        self.test_discovery_controller.discovery_finished.connect(
            lambda msg: self.main_window.status_label.setText(f"Discovery: {msg}")
        )

        # --- TaskManager Global Signals to MainWindow Status Updates & TestExecutionController ---
        # TestExecutionController will handle its specific tasks.
        # MainController handles generic status updates for other tasks.
        self.task_manager.task_started.connect(self._on_global_task_started)
        self.task_manager.task_progress.connect(self._on_global_task_progress)
        self.task_manager.task_completed.connect(self._on_global_task_completed)
        self.task_manager.task_failed.connect(self._on_global_task_failed)
        self._task_descriptions: dict[str, str] = {}

        # Connect TestExecutionController signal to TestResultsController slot
        self.test_execution_controller.test_execution_completed.connect(
            self.test_results_controller.auto_load_test_results
        )

        # SettingsController -> MainController for LLM updates
        self.settings_controller.llm_settings_changed.connect(self._on_llm_settings_changed)
        self._update_llm_status_label()  # Initial status update

    def _get_task_description(self, task_id: str) -> str:
        """Retrieves the cached description for a task, or a fallback."""
        return self._task_descriptions.get(task_id, task_id[:8])

    @pyqtSlot(str, str)
    def _on_global_task_started(self, task_id: str, description: str) -> None:
        self._task_descriptions[task_id] = description
        # TestExecutionController also listens to task_started and will manage its view.
        # MainController provides a general status update.
        if not self.test_execution_controller.is_test_execution_task(task_id, description):
            self.main_window.status_label.setText(
                f"Task started: {description} ({task_id[:8]}...)."
            )
        # Else, TestExecutionController is handling the display for this task.

    @pyqtSlot(str, int, str)
    def _on_global_task_progress(self, task_id: str, percentage: int, message: str) -> None:
        # TestExecutionController handles progress for its specific task.
        # MainController provides general status update for other tasks.
        # We need to check if the TestExecutionController is currently tracking this task_id.
        if task_id != self.test_execution_controller._current_task_id:
            task_desc = self._get_task_description(task_id)
            self.main_window.status_label.setText(
                f"Task '{task_desc}' progress: {percentage}% - {message}"
            )
        # Else, TestExecutionController's view is showing progress.

    @pyqtSlot(str, object)
    def _on_global_task_completed(self, task_id: str, result: Any) -> None:
        task_desc = self._get_task_description(task_id)
        self._task_descriptions.pop(task_id, None)  # Clean up cached description

        if (
            task_id != self.test_execution_controller._current_task_id
        ):  # Check if it was handled by TEC
            # If TestExecutionController was tracking it, it would have set _current_task_id to None on completion.
            # So, if _current_task_id is still this task_id, it means TEC's _handle_task_completed hasn't run yet or this is a different task.
            # This logic might need refinement if signal order is an issue.
            # A simpler approach: if it's NOT a test execution task that TEC would have picked up.
            # This requires knowing the description again, or checking if TEC *was* tracking it.
            # For now, let's assume TEC clears its _current_task_id promptly.
            self.main_window.status_label.setText(f"Task '{task_desc}' completed.")

    @pyqtSlot(str, str)
    def _on_global_task_failed(self, task_id: str, error_message: str) -> None:
        task_desc = self._get_task_description(task_id)
        self._task_descriptions.pop(task_id, None)  # Clean up cached description

        if (
            task_id != self.test_execution_controller._current_task_id
        ):  # Check if it was handled by TEC
            self.main_window.status_label.setText(f"Task '{task_desc}' failed.")
            QMessageBox.warning(
                self.main_window,
                "Task Error",
                f"Task '{task_desc}' failed:\n\n{error_message.splitlines()[0]}",
            )

    @pyqtSlot()
    def on_open(self) -> None:
        """Handle the Open action from MainWindow."""
        self.logger.info("Open action triggered.")
        # Use core_settings for default directory if available
        default_dir = str(self.core_settings.project_root) if self.core_settings else ""

        file_path_str, _ = QFileDialog.getOpenFileName(
            self.main_window,
            "Open File",
            default_dir,
            "Python Files (*.py);;JSON Files (*.json);;XML Files (*.xml);;All Files (*)",
        )

        if file_path_str:
            path = Path(file_path_str)
            self.logger.info(f"File dialog selected: {path}")
            self.file_controller.on_file_selected(path)  # Delegate to FileController
        else:
            self.logger.info("File dialog cancelled.")

    @pyqtSlot()
    def on_run_tests_action_triggered(self) -> None:
        """
        Handles the "Run Tests" action from the main menu.
        It retrieves the currently selected test file or directory from the
        TestResultsModel and instructs the TestExecutionController to start the run.
        """
        self.logger.info("'Run Tests' action triggered by user.")

        source_path = self.test_results_model.source_file
        source_type = self.test_results_model.source_type

        if source_path and (source_type == "py" or source_type == "directory"):
            self.logger.info(f"Preparing to run tests for: {source_path} (type: {source_type})")
            test_path_to_run = str(source_path)
            pytest_arguments: List[str] = []  # Placeholder for future UI to set arguments

            # TestExecutionController will show progress and output.
            # Results will be auto-loaded via signal/slot connection.
            task_id = self.test_execution_controller.start_test_run(
                test_path_to_run, pytest_arguments
            )
            if task_id:
                self.main_window.status_label.setText(
                    f"Test execution started for {source_path.name}..."
                )
                self.logger.info(f"Test execution task submitted with ID: {task_id}")
            else:
                # This case should be rare if submit_background_task itself doesn't fail badly
                QMessageBox.warning(
                    self.main_window,
                    "Run Tests Error",
                    f"Failed to submit test execution task for {source_path.name}.",
                )
                self.logger.error(
                    f"Failed to get task_id from start_test_run for {source_path.name}"
                )
        else:
            QMessageBox.warning(
                self.main_window,
                "Run Tests",
                "Please select a Python test file or directory first "
                "(e.g., via File menu or File Selection tab).",
            )
            self.logger.warning(
                "Run tests action: No valid Python file or directory selected in the model."
            )

    def _update_llm_status_label(self) -> None:
        """Updates the LLM status label in the main window's status bar."""
        provider = self.core_settings.llm_provider
        api_key_present = False
        model_name = ""

        if provider == "openai":
            if self.core_settings.llm_api_key_openai:
                api_key_present = True
            model_name = self.core_settings.llm_model_openai
        elif provider == "anthropic":
            if self.core_settings.llm_api_key_anthropic:
                api_key_present = True
            model_name = self.core_settings.llm_model_anthropic

        status_text = "LLM: Disabled"
        if provider != "none":
            if api_key_present:
                status_text = f"LLM: {provider.capitalize()} ({model_name}) - Ready"
            else:
                status_text = f"LLM: {provider.capitalize()} - API Key Missing"

        self.main_window.llm_status_label.setText(status_text)
        self.logger.debug(f"LLM status label updated: {status_text}")

    @pyqtSlot()
    def _on_llm_settings_changed(self) -> None:
        """Handles changes to LLM settings."""
        self.logger.info(
            "LLM settings changed. Re-initializing analysis service and clearing cache."
        )

        self.analyzer_service = PytestAnalyzerService(settings=self.app.core_settings)

        self.analysis_controller.analyzer_service = self.analyzer_service
        self.test_discovery_controller.analyzer_service = self.analyzer_service
        self.test_execution_controller.analyzer_service = self.analyzer_service

        if hasattr(self.analysis_controller, "suggestion_cache"):
            self.analysis_controller.suggestion_cache.clear()
            self.logger.info("Analysis suggestion cache cleared.")

        self._update_llm_status_label()
        QMessageBox.information(
            self.main_window,
            "Settings Changed",
            "LLM settings have been updated. The analysis service has been re-initialized.",
        )
