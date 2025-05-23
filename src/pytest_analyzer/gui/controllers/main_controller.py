import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, List

from PyQt6.QtCore import QObject, pyqtSlot
from PyQt6.QtWidgets import QFileDialog, QMessageBox

from ...core.analyzer_service import PytestAnalyzerService
from ..background.task_manager import TaskManager
from ..workflow import (
    WorkflowCoordinator,
    WorkflowGuide,
    WorkflowState,
    WorkflowStateMachine,
)
from .analysis_controller import AnalysisController
from .base_controller import BaseController
from .file_controller import FileController
from .project_controller import ProjectController
from .settings_controller import SettingsController
from .test_discovery_controller import TestDiscoveryController
from .test_execution_controller import TestExecutionController
from .test_results_controller import TestResultsController

if TYPE_CHECKING:
    from ...utils.settings import Settings as CoreSettings  # type: ignore
    from ..app import PytestAnalyzerApp
    from ..main_window import MainWindow
    from ..models.test_results_model import TestResultsModel

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
        self.test_results_model: TestResultsModel = main_window.test_results_model  # type: ignore

        # Initialize sub-controllers, passing TaskManager
        self.file_controller = FileController(
            self.test_results_model,
            parent=self,  # type: ignore
        )
        self.test_results_controller = TestResultsController(
            self.test_results_model,
            parent=self,  # type: ignore
        )
        self.analysis_controller = AnalysisController(
            self.analyzer_service,
            self.test_results_model,  # type: ignore
            parent=self,
            task_manager=self.task_manager,
        )
        self.settings_controller = SettingsController(
            app=self.app,
            parent=self,  # type: ignore
        )
        self.project_controller = ProjectController(parent=self)
        self.test_discovery_controller = TestDiscoveryController(
            self.analyzer_service, parent=self, task_manager=self.task_manager
        )
        self.test_execution_controller = TestExecutionController(
            progress_view=self.main_window.test_execution_progress_view,  # type: ignore
            output_view=self.main_window.test_output_view,  # type: ignore
            task_manager=self.task_manager,  # type: ignore
            analyzer_service=self.analyzer_service,  # type: ignore
            parent=self,
        )

        # Initialize Workflow System
        self.workflow_state_machine = WorkflowStateMachine(parent=self)
        self.workflow_guide = WorkflowGuide(parent=self)
        self.workflow_coordinator = WorkflowCoordinator(
            state_machine=self.workflow_state_machine,
            guide=self.workflow_guide,
            file_controller=self.file_controller,
            test_discovery_controller=self.test_discovery_controller,
            test_execution_controller=self.test_execution_controller,
            analysis_controller=self.analysis_controller,
            # fix_controller=self.fix_controller, # Add when available
            task_manager=self.task_manager,  # type: ignore
            parent=self,
        )

        self._connect_signals()
        self.logger.info("MainController initialized and signals connected.")
        self.workflow_state_machine.to_idle()  # Initialize workflow state

    def _connect_signals(self) -> None:
        """Connect signals and slots between components."""
        # --- MainWindow Actions to Controllers ---
        self.main_window.open_action.triggered.connect(self.on_open)  # type: ignore
        self.main_window.about_action.triggered.connect(  # type: ignore
            self.main_window.on_about  # type: ignore
        )
        self.main_window.exit_action.triggered.connect(self.main_window.close)  # type: ignore

        self.main_window.run_tests_action.triggered.connect(self.on_run_tests_action_triggered)  # type: ignore
        self.main_window.analyze_action.triggered.connect(self.analysis_controller.on_analyze)  # type: ignore
        self.main_window.settings_action.triggered.connect(self.settings_controller.on_settings)  # type: ignore

        # Project Management Actions
        self.main_window.open_project_action.triggered.connect(
            self.project_controller.show_project_selection
        )  # type: ignore
        self.main_window.new_project_action.triggered.connect(
            self.project_controller.show_project_selection
        )  # type: ignore

        # --- View Signals to Controllers ---
        file_selection_view = self.main_window.file_selection_view  # type: ignore
        file_selection_view.file_selected.connect(self.file_controller.on_file_selected)
        file_selection_view.report_type_changed.connect(self.file_controller.on_report_type_changed)

        test_results_view = self.main_window.test_results_view  # type: ignore
        test_results_view.test_selected.connect(self.test_results_controller.on_test_selected)
        test_results_view.group_selected.connect(self.test_results_controller.on_group_selected)

        test_discovery_view = self.main_window.test_discovery_view  # type: ignore
        test_discovery_view.discover_tests_requested.connect(
            self.test_discovery_controller.request_discover_tests
        )

        # --- Controller Signals to Model/View Updates (and Workflow Coordinator) ---
        self.file_controller.results_loaded.connect(self.test_results_model.set_results)
        # Status messages are now handled by WorkflowGuide

        # TestDiscoveryController -> TestDiscoveryView
        self.test_discovery_controller.tests_discovered.connect(
            test_discovery_view.update_test_tree
        )
        # Discovery status messages also handled by WorkflowGuide via WorkflowCoordinator

        # --- TaskManager Global Signals (primarily for non-workflow specific status updates) ---
        self.task_manager.task_started.connect(self._on_global_task_started)  # type: ignore
        self.task_manager.task_progress.connect(self._on_global_task_progress)  # type: ignore
        self.task_manager.task_completed.connect(self._on_global_task_completed)  # type: ignore
        self.task_manager.task_failed.connect(self._on_global_task_failed)  # type: ignore
        self._task_descriptions: dict[str, str] = {}

        # Connect TestExecutionController signal to TestResultsController slot
        self.test_execution_controller.test_execution_completed.connect(
            self.test_results_controller.auto_load_test_results
        )

        # SettingsController -> MainController for LLM updates
        self.settings_controller.llm_settings_changed.connect(self._on_llm_settings_changed)
        self._update_llm_status_label()

        # ProjectController connections
        self.project_controller.project_changed.connect(self._on_project_changed)
        self.project_controller.settings_updated.connect(self._on_project_settings_updated)
        self.project_controller.status_message_updated.connect(self._update_status_message)

        # Recent projects menu updates
        self.project_controller.project_manager.recent_projects_updated.connect(
            self.main_window.update_recent_projects_menu
        )

        # --- Workflow System Connections ---
        self.workflow_guide.guidance_updated.connect(self._update_status_bar_guidance)
        self.workflow_state_machine.state_changed.connect(self._on_workflow_state_changed)

    def _get_task_description(self, task_id: str) -> str:
        """Retrieves the cached description for a task, or a fallback."""
        return self._task_descriptions.get(task_id, task_id[:8])

    @pyqtSlot(str, str)
    def _on_global_task_started(self, task_id: str, description: str) -> None:
        self._task_descriptions[task_id] = description
        # WorkflowCoordinator will handle state changes for workflow-related tasks.
        # This global handler can provide generic feedback if not handled by workflow/specific controller.
        if not self.test_execution_controller.is_test_execution_task(
            task_id, description
        ) and self.workflow_state_machine.current_state not in [
            WorkflowState.TESTS_RUNNING,
            WorkflowState.ANALYSIS_RUNNING,
            WorkflowState.TESTS_DISCOVERING,
        ]:
            self.main_window.status_label.setText(  # type: ignore
                f"Task started: {description} ({task_id[:8]}...)."
            )

    @pyqtSlot(str, int, str)
    def _on_global_task_progress(self, task_id: str, percentage: int, message: str) -> None:
        if (
            task_id != self.test_execution_controller._current_task_id
            and self.workflow_state_machine.current_state
            not in [
                WorkflowState.TESTS_RUNNING,
                WorkflowState.ANALYSIS_RUNNING,
                WorkflowState.TESTS_DISCOVERING,
            ]
        ):
            task_desc = self._get_task_description(task_id)
            self.main_window.status_label.setText(  # type: ignore
                f"Task '{task_desc}' progress: {percentage}% - {message}"
            )

    @pyqtSlot(str, object)
    def _on_global_task_completed(self, task_id: str, result: Any) -> None:
        task_desc = self._get_task_description(task_id)
        self._task_descriptions.pop(task_id, None)

        if (
            task_id != self.test_execution_controller._current_task_id
            and self.workflow_state_machine.current_state
            not in [
                WorkflowState.RESULTS_AVAILABLE,
                WorkflowState.FIXES_AVAILABLE,
                WorkflowState.TESTS_DISCOVERED,
            ]
        ):
            # Avoid overriding workflow messages
            self.main_window.status_label.setText(f"Task '{task_desc}' completed.")  # type: ignore

    @pyqtSlot(str, str)
    def _on_global_task_failed(self, task_id: str, error_message: str) -> None:
        task_desc = self._get_task_description(task_id)
        self._task_descriptions.pop(task_id, None)

        # WorkflowCoordinator will handle setting ERROR state for workflow tasks.
        # This is a fallback for other tasks or if coordinator doesn't catch it.
        if self.workflow_state_machine.current_state != WorkflowState.ERROR:
            # self.main_window.status_label.setText(f"Task '{task_desc}' failed.") # Workflow guide will show error
            QMessageBox.warning(
                self.main_window,  # type: ignore
                "Task Error",
                f"Task '{task_desc}' failed:\n\n{error_message.splitlines()[0]}",
            )

    @pyqtSlot()
    def on_open(self) -> None:
        """Handle the Open action from MainWindow."""
        self.logger.info("Open action triggered.")
        default_dir = (
            str(self.core_settings.project_root) if self.core_settings.project_root else ""
        )  # type: ignore

        file_path_str, _ = QFileDialog.getOpenFileName(
            self.main_window,  # type: ignore
            "Open File",
            default_dir,
            "Python Files (*.py);;JSON Files (*.json);;XML Files (*.xml);;All Files (*)",
        )

        if file_path_str:
            path = Path(file_path_str)
            self.logger.info(f"File dialog selected: {path}")
            # FileController's on_file_selected will emit results_loaded,
            # which WorkflowCoordinator listens to.
            self.file_controller.on_file_selected(path)
        else:
            self.logger.info("File dialog cancelled.")
            # Optionally, if in IDLE state, emit guidance again or do nothing
            if self.workflow_state_machine.current_state == WorkflowState.IDLE:
                self.workflow_guide.update_guidance(
                    WorkflowState.IDLE, self.workflow_state_machine.context
                )

    @pyqtSlot()
    def on_run_tests_action_triggered(self) -> None:
        """
        Handles the "Run Tests" action from the main menu.
        It retrieves the currently selected test file or directory from the
        TestResultsModel and instructs the TestExecutionController to start the run.
        """
        self.logger.info("'Run Tests' action triggered by user.")

        source_path = self.test_results_model.source_file  # type: ignore
        source_type = self.test_results_model.source_type  # type: ignore

        if source_path and (source_type == "py" or source_type == "directory"):
            self.logger.info(f"Preparing to run tests for: {source_path} (type: {source_type})")  # type: ignore
            test_path_to_run = str(source_path)
            pytest_arguments: List[str] = []

            task_id = self.test_execution_controller.start_test_run(
                test_path_to_run, pytest_arguments
            )
            if task_id:
                # WorkflowCoordinator will transition state to TESTS_RUNNING
                # and WorkflowGuide will update status.
                self.logger.info(f"Test execution task submitted with ID: {task_id}")
            else:
                QMessageBox.warning(
                    self.main_window,  # type: ignore
                    "Run Tests Error",
                    f"Failed to submit test execution task for {source_path.name}.",  # type: ignore
                )
                self.logger.error(
                    f"Failed to get task_id from start_test_run for {source_path.name}"  # type: ignore
                )
                self.workflow_state_machine.to_error(
                    f"Failed to submit test execution task for {source_path.name}",  # type: ignore
                    self.workflow_state_machine.current_state,
                )
        else:
            QMessageBox.warning(
                self.main_window,  # type: ignore
                "Run Tests",
                "Please select a Python test file or directory first "
                "(e.g., via File menu or File Selection tab).",
            )
            self.logger.warning(
                "Run tests action: No valid Python file or directory selected in the model."
            )

    def _update_llm_status_label(self) -> None:
        """Updates the LLM status label in the main window's status bar."""
        provider = self.core_settings.llm_provider  # type: ignore
        api_key_present = False
        model_name = ""

        if provider == "openai":  # type: ignore
            if self.core_settings.llm_api_key_openai:  # type: ignore
                api_key_present = True
            model_name = self.core_settings.llm_model_openai  # type: ignore
        elif provider == "anthropic":  # type: ignore
            if self.core_settings.llm_api_key_anthropic:  # type: ignore
                api_key_present = True
            model_name = self.core_settings.llm_model_anthropic  # type: ignore

        status_text = "LLM: Disabled"
        if provider != "none":  # type: ignore
            if api_key_present:
                status_text = f"LLM: {provider.capitalize()} ({model_name}) - Ready"  # type: ignore
            else:
                status_text = f"LLM: {provider.capitalize()} - API Key Missing"  # type: ignore

        self.main_window.llm_status_label.setText(status_text)  # type: ignore
        self.logger.debug(f"LLM status label updated: {status_text}")

    @pyqtSlot()
    def _on_llm_settings_changed(self) -> None:
        """Handles changes to LLM settings."""
        self.logger.info(
            "LLM settings changed. Re-initializing analysis service and clearing cache."
        )

        self.analyzer_service = PytestAnalyzerService(settings=self.app.core_settings)  # type: ignore

        self.analysis_controller.analyzer_service = self.analyzer_service
        self.test_discovery_controller.analyzer_service = self.analyzer_service
        self.test_execution_controller.analyzer_service = self.analyzer_service  # type: ignore

        if hasattr(self.analysis_controller, "suggestion_cache"):
            self.analysis_controller.suggestion_cache.clear()
            self.logger.info("Analysis suggestion cache cleared.")

        self._update_llm_status_label()
        QMessageBox.information(
            self.main_window,  # type: ignore
            "Settings Changed",
            "LLM settings have been updated. The analysis service has been re-initialized.",
        )

    @pyqtSlot(str, str)
    def _update_status_bar_guidance(self, message: str, tooltip: str) -> None:
        """Updates the main status label with guidance from WorkflowGuide."""
        self.main_window.status_label.setText(message)  # type: ignore
        self.main_window.status_label.setToolTip(tooltip)  # type: ignore

    @pyqtSlot(str, str)
    def _on_workflow_state_changed(self, old_state_str: str, new_state_str: str) -> None:
        """Handles UI updates when the workflow state changes."""
        try:
            new_state = WorkflowState(new_state_str)
            self.logger.info(f"Workflow state changed from {old_state_str} to {new_state}")
        except ValueError:
            self.logger.error(f"Received invalid new state string: {new_state_str}")
            return

        # Enable/disable actions based on the new state
        # File actions
        # self.main_window.open_action is always enabled

        # Tools actions
        can_run_tests = new_state in [
            WorkflowState.FILE_SELECTED,
            WorkflowState.TESTS_DISCOVERED,
            WorkflowState.RESULTS_AVAILABLE,  # Allow re-run
            WorkflowState.FIXES_APPLIED,  # Allow re-run
        ]
        self.main_window.run_tests_action.setEnabled(can_run_tests)  # type: ignore

        can_analyze = (
            new_state == WorkflowState.RESULTS_AVAILABLE
            and self.workflow_state_machine.context.get("failure_count", 0) > 0
        )
        self.main_window.analyze_action.setEnabled(can_analyze)  # type: ignore

        # Add logic for other actions like "Apply Fixes" when FixController is integrated
        # e.g., self.main_window.apply_fixes_action.setEnabled(new_state == WorkflowState.FIXES_AVAILABLE)

        # Update status bar (already handled by WorkflowGuide -> _update_status_bar_guidance)
        # Potentially update other UI elements, e.g., highlighting current step in a visual guide

    def _on_project_changed(self, project) -> None:
        """Handle project change."""
        from ..models.project import Project

        if isinstance(project, Project):
            # Update window title
            self.main_window.setWindowTitle(f"Pytest Analyzer - {project.name}")

            # Update core settings to use project settings
            self.core_settings = project.settings
            self.analyzer_service = PytestAnalyzerService(settings=project.settings)

            # Update workflow state
            self.workflow_state_machine.transition_to(WorkflowState.IDLE)

            logger.info(f"Project changed to: {project.name}")

    def _on_project_settings_updated(self, settings) -> None:
        """Handle project settings update."""
        # Update core settings reference
        self.core_settings = settings

        # Recreate analyzer service with new settings
        self.analyzer_service = PytestAnalyzerService(settings=settings)

        # Update controllers that depend on settings
        self.analysis_controller.analyzer_service = self.analyzer_service
        self.test_discovery_controller.analyzer_service = self.analyzer_service
        self.test_execution_controller.analyzer_service = self.analyzer_service

        logger.info("Project settings updated")

    def _update_status_message(self, message: str) -> None:
        """Update status bar message."""
        if hasattr(self.main_window, "status_label"):
            self.main_window.status_label.setText(message)
