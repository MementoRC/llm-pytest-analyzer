# Add after existing imports
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, List

from PyQt6.QtCore import QObject, pyqtSlot
from PyQt6.QtWidgets import QFileDialog, QMessageBox

from ...core.analyzer_service import PytestAnalyzerService
from ..background.task_manager import TaskManager
from ..models.test_results_model import TestResult  # Added import
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
from .report_controller import ReportController
from .session_controller import SessionController
from .settings_controller import SettingsController
from .test_discovery_controller import TestDiscoveryController
from .test_execution_controller import TestExecutionController
from .test_results_controller import TestResultsController

if TYPE_CHECKING:
    from ...utils.settings import Settings as CoreSettings  # type: ignore
    from ..app import PytestAnalyzerApp
    from ..main_window import MainWindow
    from ..models.test_results_model import TestResultsModel

    # Removed TestResult from here if it was, ensure it's imported above for runtime use

logger = logging.getLogger(__name__)


class MainController(BaseController):
    """Main orchestration controller for the GUI."""

    def __init__(self, main_window: "MainWindow", app: "PytestAnalyzerApp", parent: QObject = None):
        # Call super().__init__ first. This ensures that the QObject part of this
        # MainController instance is properly initialized before 'self' is used
        # as a parent for other QObjects. BaseController.__init__ will be called,
        # and its self.task_manager attribute will be initially set to None.
        super().__init__(parent=parent)
        self.logger.debug("MainController: Initializing...")

        # Now, create the TaskManager. 'self' can now be safely used as its parent.
        # This line also sets the 'self.task_manager' attribute (which is defined
        # in BaseController and used by it) to the new TaskManager instance.
        self.task_manager = TaskManager(parent=self)
        self.logger.debug(f"MainController: TaskManager initialized: {self.task_manager}")

        # Assign other MainController specific attributes
        self.main_window = main_window
        self.app = app
        self.core_settings: CoreSettings = app.core_settings
        self.analyzer_service: PytestAnalyzerService = main_window.analyzer_service
        self.test_results_model: TestResultsModel = main_window.test_results_model  # type: ignore
        self.logger.debug(
            f"MainController: Assigned main_window, app, core_settings: {self.core_settings}"
        )
        self.logger.debug(f"MainController: Assigned analyzer_service: {self.analyzer_service}")
        self.logger.debug(f"MainController: Assigned test_results_model: {self.test_results_model}")

        # Initialize sub-controllers, passing TaskManager
        self.logger.debug("MainController: Initializing sub-controllers...")
        self.file_controller = FileController(
            self.test_results_model,
            parent=self,  # type: ignore
        )
        self.logger.debug(f"MainController: FileController initialized: {self.file_controller}")
        self.test_results_controller = TestResultsController(
            self.test_results_model,
            parent=self,  # type: ignore
        )
        self.logger.debug(
            f"MainController: TestResultsController initialized: {self.test_results_controller}"
        )
        self.analysis_controller = AnalysisController(
            self.analyzer_service,
            self.test_results_model,  # type: ignore
            parent=self,
            task_manager=self.task_manager,
        )
        self.logger.debug(
            f"MainController: AnalysisController initialized: {self.analysis_controller}"
        )
        self.settings_controller = SettingsController(
            app=self.app,
            parent=self,  # type: ignore
        )
        self.logger.debug(
            f"MainController: SettingsController initialized: {self.settings_controller}"
        )
        self.project_controller = ProjectController(parent=self)
        self.logger.debug(
            f"MainController: ProjectController initialized: {self.project_controller}"
        )
        self.session_controller = SessionController(parent=self)
        self.logger.debug(
            f"MainController: SessionController initialized: {self.session_controller}"
        )
        self.test_discovery_controller = TestDiscoveryController(
            self.analyzer_service, parent=self, task_manager=self.task_manager
        )
        self.logger.debug(
            f"MainController: TestDiscoveryController initialized: {self.test_discovery_controller}"
        )
        self.test_execution_controller = TestExecutionController(
            progress_view=self.main_window.test_execution_progress_view,  # type: ignore
            output_view=self.main_window.test_output_view,  # type: ignore
            task_manager=self.task_manager,  # type: ignore
            analyzer_service=self.analyzer_service,  # type: ignore
            parent=self,
        )
        self.logger.debug(
            f"MainController: TestExecutionController initialized: {self.test_execution_controller}"
        )
        self.report_controller = ReportController(parent=self.main_window)
        self.logger.debug(f"MainController: ReportController initialized: {self.report_controller}")

        # Initialize Workflow System
        self.logger.debug("MainController: Initializing Workflow System...")
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
        self.logger.debug("MainController: Workflow System initialized.")

        self._connect_signals()
        self.logger.info("MainController initialized and signals connected.")
        self.workflow_state_machine.to_idle()  # Initialize workflow state
        self.logger.debug("MainController: Initialization complete.")

    def _connect_signals(self) -> None:
        """Connect signals and slots between components."""
        self.logger.debug("MainController: Connecting signals...")
        # --- MainWindow Actions to Controllers ---
        self.logger.debug("MainController: Connecting MainWindow actions to controllers...")
        self.main_window.open_action.triggered.connect(self.on_open)  # type: ignore
        self.main_window.about_action.triggered.connect(  # type: ignore
            self.main_window.on_about  # type: ignore
        )
        self.main_window.exit_action.triggered.connect(self.main_window.close)  # type: ignore

        self.main_window.run_tests_action.triggered.connect(self.on_run_tests_action_triggered)  # type: ignore
        self.main_window.analyze_action.triggered.connect(self.analysis_controller.on_analyze)  # type: ignore
        self.main_window.settings_action.triggered.connect(self.settings_controller.on_settings)  # type: ignore

        # Project Management Actions
        self.logger.debug("MainController: Connecting Project Management actions...")
        self.main_window.open_project_action.triggered.connect(
            self.project_controller.show_project_selection
        )  # type: ignore
        self.main_window.new_project_action.triggered.connect(
            self.project_controller.show_project_selection
        )  # type: ignore

        # Session Management Actions
        self.logger.debug("MainController: Connecting Session Management actions...")
        self.main_window.manage_sessions_action.triggered.connect(
            self.session_controller.show_session_management
        )  # type: ignore
        self.main_window.new_session_action.triggered.connect(
            lambda: self.session_controller.create_new_session()
        )  # type: ignore
        self.main_window.save_session_action.triggered.connect(
            self.session_controller.save_current_session
        )  # type: ignore

        # Report Actions
        self.logger.debug("MainController: Connecting Report actions...")
        self.main_window.generate_report_action.triggered.connect(
            self.report_controller.show_report_dialog
        )  # type: ignore
        self.main_window.quick_html_report_action.triggered.connect(self._on_quick_html_report)  # type: ignore
        self.main_window.export_pdf_action.triggered.connect(self._on_export_pdf)  # type: ignore
        self.main_window.export_json_action.triggered.connect(self._on_export_json)  # type: ignore
        self.main_window.export_csv_action.triggered.connect(self._on_export_csv)  # type: ignore

        # --- View Signals to Controllers ---
        self.logger.debug("MainController: Connecting View signals to controllers...")
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
        self.logger.debug("MainController: Connecting Controller signals to Model/View updates...")
        # Connections for FileController's new specific signals
        self.file_controller.report_parsed.connect(self._on_report_parsed_update_models)
        self.file_controller.python_file_opened.connect(self._on_source_selected_for_discovery)
        self.file_controller.python_file_opened.connect(self._on_python_file_opened_for_editor)
        self.file_controller.directory_opened.connect(self._on_source_selected_for_discovery)
        # Status messages are now handled by WorkflowGuide

        # TestDiscoveryController -> TestDiscoveryView
        self.test_discovery_controller.tests_discovered.connect(
            test_discovery_view.update_test_tree
        )
        # Discovery status messages also handled by WorkflowGuide via WorkflowCoordinator

        # --- TaskManager Global Signals (primarily for non-workflow specific status updates) ---
        self.logger.debug("MainController: Connecting TaskManager global signals...")
        self.task_manager.task_started.connect(self._on_global_task_started)  # type: ignore
        self.task_manager.task_progress.connect(self._on_global_task_progress)  # type: ignore
        self.task_manager.task_completed.connect(self._on_global_task_completed)  # type: ignore
        self.task_manager.task_failed.connect(self._on_global_task_failed)  # type: ignore
        self._task_descriptions: dict[str, str] = {}

        # Connect TestExecutionController signal to TestResultsController slot
        self.logger.debug(
            "MainController: Connecting TestExecutionController to TestResultsController..."
        )
        self.test_execution_controller.test_execution_completed.connect(
            self.test_results_controller.auto_load_test_results
        )
        self.test_execution_controller.test_counts_updated.connect(
            self._update_status_bar_test_counts
        )

        # Connect test results model signals to report controller
        self.logger.debug("MainController: Connecting TestResultsModel to ReportController...")
        self.test_results_model.results_updated.connect(
            lambda: self.report_controller.set_test_results(self.test_results_model.results)
        )
        self.test_results_model.suggestions_updated.connect(
            lambda: self.report_controller.set_analysis_results(self._get_analysis_results())
        )

        # SettingsController -> MainController for core settings updates
        self.logger.debug("MainController: Connecting SettingsController to self...")
        self.settings_controller.core_settings_changed.connect(self._on_core_settings_changed)
        self._update_llm_status_label()  # Still relevant as LLM settings are part of core settings

        # ProjectController connections
        self.logger.debug("MainController: Connecting ProjectController signals...")
        self.project_controller.project_changed.connect(self._on_project_changed)
        self.project_controller.settings_updated.connect(self._on_project_settings_updated)
        self.project_controller.status_message_updated.connect(self._update_status_message)

        # Recent projects menu updates
        self.project_controller.project_manager.recent_projects_updated.connect(
            self.main_window.update_recent_projects_menu
        )

        # SessionController connections
        self.logger.debug("MainController: Connecting SessionController signals...")
        self.session_controller.session_changed.connect(self._on_session_changed)
        self.session_controller.status_message_updated.connect(self._update_status_message)
        self.session_controller.bookmark_added.connect(self._on_bookmark_added)
        self.session_controller.bookmark_removed.connect(self._on_bookmark_removed)

        # --- Workflow System Connections ---
        self.logger.debug("MainController: Connecting Workflow System signals...")
        self.workflow_guide.guidance_updated.connect(self._update_status_bar_guidance)
        self.workflow_state_machine.state_changed.connect(self._on_workflow_state_changed)
        self.logger.debug("MainController: Signal connections complete.")

    @pyqtSlot(list, Path, str)
    def _on_report_parsed_update_models(
        self, results: List[TestResult], source_file: Path, source_type: str
    ) -> None:
        """
        Handles parsed test results from a report file (JSON/XML).
        Updates the TestResultsModel and ReportController.
        """
        self.logger.debug(
            f"MainController: _on_report_parsed_update_models called with {len(results)} results, source: {source_file}, type: {source_type}"
        )
        self.logger.info(
            f"Received {len(results)} parsed results from {source_file.name} ({source_type}). Updating models."
        )
        self.test_results_model.set_results(results, source_file, source_type)  # type: ignore # Ensure set_results takes 3 args
        self.logger.debug(
            f"MainController: TestResultsModel.set_results called with {len(results)} items."
        )
        self.report_controller.set_test_results(results)
        self.logger.debug(
            f"MainController: ReportController.set_test_results called with {len(results)} items."
        )
        self.logger.debug("MainController: _on_report_parsed_update_models finished.")

    @pyqtSlot(Path)
    def _on_source_selected_for_discovery(self, source_path: Path) -> None:
        """
        Handles selection of a Python file or directory as a test source.
        Prepares the TestDiscoveryView by clearing any previous test tree.
        """
        self.logger.debug(
            f"MainController: _on_source_selected_for_discovery called with path: {source_path}"
        )
        self.logger.info(
            f"Source selected for discovery: {source_path}. Clearing TestDiscoveryView tree."
        )
        test_discovery_view = self.main_window.test_discovery_view  # type: ignore
        if test_discovery_view:
            # Assuming update_test_tree with an empty list clears the view.
            # This prepares the view for a new discovery action.
            test_discovery_view.update_test_tree([])
            self.logger.debug("MainController: TestDiscoveryView tree cleared.")
        else:
            self.logger.warning("MainController: TestDiscoveryView not available to clear tree.")
        self.logger.debug("MainController: _on_source_selected_for_discovery finished.")

    @pyqtSlot(Path)
    def _on_python_file_opened_for_editor(self, file_path: Path) -> None:
        """
        Handles Python file opening for the code editor.
        Loads the file content into the CodeEditorView and switches to the Code Editor tab.
        """
        self.logger.debug(
            f"MainController: _on_python_file_opened_for_editor called with path: {file_path}"
        )
        self.logger.info(f"Loading Python file into code editor: {file_path}")
        code_editor_view = self.main_window.code_editor_view  # type: ignore
        if code_editor_view:
            success = code_editor_view.load_file(file_path)
            if success:
                # Switch to the Code Editor tab
                # Assuming analysis_tabs is accessible and 2 is the correct index for Code Editor
                if (
                    hasattr(self.main_window, "analysis_tabs")
                    and self.main_window.analysis_tabs is not None
                ):
                    try:
                        self.main_window.analysis_tabs.setCurrentIndex(
                            2
                        )  # Code Editor is the 3rd tab (index 2)
                        self.logger.info(
                            f"File {file_path.name} loaded successfully in code editor and tab switched."
                        )
                    except Exception as e_tab_switch:
                        self.logger.error(
                            f"Error switching to Code Editor tab: {e_tab_switch}", exc_info=True
                        )
                else:
                    self.logger.warning(
                        "analysis_tabs not available on main_window, cannot switch to Code Editor tab."
                    )

                self.logger.debug(
                    f"MainController: File {file_path.name} loaded successfully in code editor."
                )
            else:
                self.logger.error(
                    f"MainController: Failed to load file {file_path.name} in code editor using {type(code_editor_view).__name__}."
                )
        else:
            self.logger.critical(
                "MainController: CodeEditorView component is not available. Cannot load Python file."
            )
            QMessageBox.critical(
                self.main_window,  # type: ignore
                "Code Editor Error",
                "The code editor component could not be loaded. Please check the application logs for more details. Python files cannot be opened for editing.",
            )
        self.logger.debug("MainController: _on_python_file_opened_for_editor finished.")

    def _get_task_description(self, task_id: str) -> str:
        """Retrieves the cached description for a task, or a fallback."""
        desc = self._task_descriptions.get(task_id, task_id[:8])
        self.logger.debug(
            f"MainController: _get_task_description for task_id '{task_id}': '{desc}'"
        )
        return desc

    @pyqtSlot(str, str)
    def _on_global_task_started(self, task_id: str, description: str) -> None:
        self.logger.debug(
            f"MainController: _on_global_task_started - task_id: {task_id}, description: {description}"
        )
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
            status_msg = f"Task started: {description} ({task_id[:8]}...)."
            self.main_window.status_label.setText(status_msg)  # type: ignore
            self.logger.debug(f"MainController: Global task started, status updated: {status_msg}")
        self.logger.debug("MainController: _on_global_task_started finished.")

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
            status_msg = f"Task '{task_desc}' progress: {percentage}% - {message}"
            self.main_window.status_label.setText(status_msg)  # type: ignore
            self.logger.debug(f"MainController: Global task progress, status updated: {status_msg}")
        self.logger.debug("MainController: _on_global_task_progress finished.")

    @pyqtSlot(str, object)
    def _on_global_task_completed(self, task_id: str, result: Any) -> None:
        self.logger.debug(
            f"MainController: _on_global_task_completed - task_id: {task_id}, result type: {type(result)}"
        )
        task_desc = self._get_task_description(task_id)
        self._task_descriptions.pop(task_id, None)
        self.logger.debug(f"MainController: Removed task_id {task_id} from _task_descriptions.")

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
            status_msg = f"Task '{task_desc}' completed."
            self.main_window.status_label.setText(status_msg)  # type: ignore
            self.logger.debug(
                f"MainController: Global task completed, status updated: {status_msg}"
            )
        self.logger.debug("MainController: _on_global_task_completed finished.")

    @pyqtSlot(str, str)
    def _on_global_task_failed(self, task_id: str, error_message: str) -> None:
        self.logger.debug(
            f"MainController: _on_global_task_failed - task_id: {task_id}, error: {error_message.splitlines()[0]}"
        )
        task_desc = self._get_task_description(task_id)
        self._task_descriptions.pop(task_id, None)
        self.logger.debug(f"MainController: Removed task_id {task_id} from _task_descriptions.")

        # WorkflowCoordinator will handle setting ERROR state for workflow tasks.
        # This is a fallback for other tasks or if coordinator doesn't catch it.
        if self.workflow_state_machine.current_state != WorkflowState.ERROR:
            # self.main_window.status_label.setText(f"Task '{task_desc}' failed.") # Workflow guide will show error
            QMessageBox.warning(
                self.main_window,  # type: ignore
                "Task Error",
                f"Task '{task_desc}' failed:\n\n{error_message.splitlines()[0]}",
            )
            self.logger.debug(
                f"MainController: Global task failed, QMessageBox shown for '{task_desc}'."
            )
        self.logger.debug("MainController: _on_global_task_failed finished.")

    @pyqtSlot()
    def on_open(self) -> None:
        """Handle the Open action from MainWindow."""
        self.logger.debug("MainController: on_open triggered.")
        default_dir = (
            str(self.core_settings.project_root) if self.core_settings.project_root else ""
        )  # type: ignore
        self.logger.debug(f"MainController: Default directory for QFileDialog: '{default_dir}'")

        file_path_str, _ = QFileDialog.getOpenFileName(
            self.main_window,  # type: ignore
            "Open File",
            default_dir,
            "Python Files (*.py);;JSON Files (*.json);;XML Files (*.xml);;All Files (*)",
        )

        if file_path_str:
            path = Path(file_path_str)
            self.logger.info(f"File dialog selected: {path}")
            self.logger.debug(
                f"MainController: File selected via dialog: {path}. Calling FileController.on_file_selected."
            )
            # FileController's on_file_selected will emit results_loaded,
            # which WorkflowCoordinator listens to.
            self.file_controller.on_file_selected(path)
        else:
            self.logger.info("File dialog cancelled.")
            self.logger.debug("MainController: File dialog was cancelled by user.")
            # Optionally, if in IDLE state, emit guidance again or do nothing
            if self.workflow_state_machine.current_state == WorkflowState.IDLE:
                self.logger.debug("MainController: Workflow state is IDLE, updating guidance.")
                self.workflow_guide.update_guidance(
                    WorkflowState.IDLE, self.workflow_state_machine.context
                )
        self.logger.debug("MainController: on_open finished.")

    @pyqtSlot()
    def on_run_tests_action_triggered(self) -> None:
        """
        Handles the "Run Tests" action from the main menu.
        It retrieves the currently selected test file or directory from the
        TestResultsModel and instructs the TestExecutionController to start the run.
        """
        self.logger.debug("MainController: on_run_tests_action_triggered.")
        self.logger.info("'Run Tests' action triggered by user.")

        source_path = self.test_results_model.source_file  # type: ignore
        source_type = self.test_results_model.source_type  # type: ignore
        self.logger.debug(
            f"MainController: Retrieved from model - source_path: {source_path}, source_type: {source_type}"
        )

        if source_path and (source_type == "py" or source_type == "directory"):
            self.logger.info(f"Preparing to run tests for: {source_path} (type: {source_type})")  # type: ignore
            test_path_to_run = str(source_path)
            pytest_arguments: List[str] = []  # TODO: Get from settings or UI
            self.logger.debug(
                f"MainController: Test path to run: {test_path_to_run}, Pytest args: {pytest_arguments}"
            )

            task_id = self.test_execution_controller.start_test_run(
                test_path_to_run, pytest_arguments
            )
            if task_id:
                # WorkflowCoordinator will transition state to TESTS_RUNNING
                # and WorkflowGuide will update status.
                self.logger.info(f"Test execution task submitted with ID: {task_id}")
                self.logger.debug(
                    f"MainController: Test execution task submitted to TestExecutionController, task_id: {task_id}"
                )
            else:
                QMessageBox.warning(
                    self.main_window,  # type: ignore
                    "Run Tests Error",
                    f"Failed to submit test execution task for {source_path.name}.",  # type: ignore
                )
                self.logger.error(
                    f"MainController: Failed to get task_id from start_test_run for {source_path.name}"  # type: ignore
                )
                self.workflow_state_machine.to_error(
                    f"Failed to submit test execution task for {source_path.name}",  # type: ignore
                    self.workflow_state_machine.current_state,
                )
                self.logger.debug(
                    "MainController: Workflow state set to ERROR due to task submission failure."
                )
        else:
            QMessageBox.warning(
                self.main_window,  # type: ignore
                "Run Tests",
                "Please select a Python test file or directory first "
                "(e.g., via File menu or File Selection tab).",
            )
            self.logger.warning(
                "MainController: Run tests action: No valid Python file or directory selected in the model."
            )
        self.logger.debug("MainController: on_run_tests_action_triggered finished.")

    def _update_llm_status_label(self) -> None:
        """Updates the LLM status label in the main window's status bar."""
        self.logger.debug("MainController: _update_llm_status_label called.")
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
        self.logger.debug(
            f"MainController: LLM provider: {provider}, API key present: {api_key_present}, model: {model_name}"
        )

        status_text = "LLM: Disabled"
        if provider != "none":  # type: ignore
            if api_key_present:
                status_text = f"LLM: {provider.capitalize()} ({model_name}) - Ready"  # type: ignore
            else:
                status_text = f"LLM: {provider.capitalize()} - API Key Missing"  # type: ignore

        self.main_window.llm_status_label.setText(status_text)  # type: ignore
        self.logger.info(
            f"LLM status label updated: {status_text}"
        )  # Changed to info as it's a significant status
        self.logger.debug("MainController: _update_llm_status_label finished.")

    @pyqtSlot("PyQt_PyObject")  # Argument type hint for CoreSettings
    def _on_core_settings_changed(self, updated_settings: "CoreSettings") -> None:
        """Handles changes to core application settings."""
        self.logger.debug(
            f"MainController: _on_core_settings_changed called with updated_settings: {updated_settings}"
        )
        self.logger.info(
            "Core settings changed. Re-initializing analysis service and clearing cache."
        )

        # self.app.core_settings is already updated by SettingsController before this signal is emitted.
        # updated_settings parameter is the new settings object.
        # We re-initialize services based on self.app.core_settings which should be the same as updated_settings.
        self.analyzer_service = PytestAnalyzerService(settings=self.app.core_settings)
        self.logger.debug(
            f"MainController: Re-initialized PytestAnalyzerService with new settings: {self.app.core_settings}"
        )

        self.analysis_controller.analyzer_service = self.analyzer_service
        self.test_discovery_controller.analyzer_service = self.analyzer_service
        self.test_execution_controller.analyzer_service = self.analyzer_service
        self.logger.debug("MainController: Updated analyzer_service in relevant sub-controllers.")

        if hasattr(self.analysis_controller, "suggestion_cache"):
            self.analysis_controller.suggestion_cache.clear()
            self.logger.info("Analysis suggestion cache cleared.")
            self.logger.debug("MainController: AnalysisController suggestion_cache cleared.")

        self._update_llm_status_label()  # LLM status might have changed
        QMessageBox.information(
            self.main_window,  # type: ignore
            "Settings Changed",
            "Core settings have been updated. Services have been re-initialized.",
        )
        self.logger.debug("MainController: _on_core_settings_changed finished.")

    @pyqtSlot(str, str)
    def _update_status_bar_guidance(self, message: str, tooltip: str) -> None:
        """Updates the main status label with guidance from WorkflowGuide."""
        self.logger.debug(
            f"MainController: _update_status_bar_guidance - message: '{message}', tooltip: '{tooltip}'"
        )
        self.main_window.status_label.setText(message)  # type: ignore
        self.main_window.status_label.setToolTip(tooltip)  # type: ignore
        self.logger.debug("MainController: Status bar guidance updated.")
        self.logger.debug("MainController: _update_status_bar_guidance finished.")

    @pyqtSlot(str, str)
    def _on_workflow_state_changed(self, old_state_str: str, new_state_str: str) -> None:
        """Handles UI updates when the workflow state changes."""
        self.logger.debug(
            f"MainController: _on_workflow_state_changed from '{old_state_str}' to '{new_state_str}'"
        )
        try:
            new_state = WorkflowState(new_state_str)
            self.logger.info(f"Workflow state changed from {old_state_str} to {new_state}")
        except ValueError:
            self.logger.error(f"MainController: Received invalid new state string: {new_state_str}")
            return

        # Enable/disable actions based on the new state
        # File actions
        # self.main_window.open_action is always enabled
        self.logger.debug(f"MainController: Updating UI actions based on new state: {new_state}")

        # Tools actions
        can_run_tests = new_state in [
            WorkflowState.FILE_SELECTED,
            WorkflowState.TESTS_DISCOVERED,
            WorkflowState.RESULTS_AVAILABLE,  # Allow re-run
            WorkflowState.FIXES_APPLIED,  # Allow re-run
        ]
        self.main_window.run_tests_action.setEnabled(can_run_tests)  # type: ignore
        self.logger.debug(f"MainController: 'Run Tests' action enabled: {can_run_tests}")

        can_analyze = (
            new_state == WorkflowState.RESULTS_AVAILABLE
            and self.workflow_state_machine.context.get("failure_count", 0) > 0
        )
        self.main_window.analyze_action.setEnabled(can_analyze)  # type: ignore
        self.logger.debug(
            f"MainController: 'Analyze' action enabled: {can_analyze} (failure_count: {self.workflow_state_machine.context.get('failure_count', 0)})"
        )

        # Add logic for other actions like "Apply Fixes" when FixController is integrated
        # e.g., self.main_window.apply_fixes_action.setEnabled(new_state == WorkflowState.FIXES_AVAILABLE)

        # Update status bar (already handled by WorkflowGuide -> _update_status_bar_guidance)
        # Potentially update other UI elements, e.g., highlighting current step in a visual guide
        self.logger.debug("MainController: _on_workflow_state_changed finished.")

    @pyqtSlot(int, int, int, int)
    def _update_status_bar_test_counts(
        self, passed: int, failed: int, skipped: int, errors: int
    ) -> None:
        """Updates the test count label in the main window's status bar."""
        self.logger.debug(
            f"MainController: _update_status_bar_test_counts called with P:{passed}, F:{failed}, S:{skipped}, E:{errors}"
        )
        if hasattr(self.main_window, "test_count_label"):
            # Format: "Tests: {total} (P:{passed}, F:{failed}, E:{errors}, S:{skipped})"
            # Compact Format: "Tests: {passed}P, {failed}F, {errors}E, {skipped}S"
            total_tests = passed + failed + skipped + errors
            if total_tests == 0 and passed == 0 and failed == 0 and skipped == 0 and errors == 0:
                # This case can mean "reset" or "no tests run yet"
                status_text = "Tests: 0"
            else:
                status_text = f"Tests: {passed}P, {failed}F, {errors}E, {skipped}S"

            self.main_window.test_count_label.setText(status_text)
            self.logger.info(f"Status bar test count updated: {status_text}")
        else:
            self.logger.warning(
                "MainController: main_window.test_count_label not found, cannot update test counts."
            )
        self.logger.debug("MainController: _update_status_bar_test_counts finished.")

    def _on_project_changed(self, project) -> None:
        """Handle project change."""
        self.logger.debug(
            f"MainController: _on_project_changed called with project: {project.name if project else 'None'}"
        )
        from ..models.project import Project

        if isinstance(project, Project):
            # Update window title
            self.main_window.setWindowTitle(f"Pytest Analyzer - {project.name}")
            self.logger.debug(
                f"MainController: Window title updated to 'Pytest Analyzer - {project.name}'"
            )

            # Update core settings to use project settings
            self.core_settings = project.settings
            self.logger.debug(
                f"MainController: Core settings updated from project: {project.settings}"
            )
            self.analyzer_service = PytestAnalyzerService(settings=project.settings)
            self.logger.debug(
                "MainController: PytestAnalyzerService re-initialized with project settings."
            )

            # Update workflow state
            self.workflow_state_machine.transition_to(WorkflowState.IDLE)
            self.logger.debug("MainController: Workflow state transitioned to IDLE.")

            logger.info(f"Project changed to: {project.name}")
        else:
            self.logger.debug(
                "MainController: Project object is not an instance of Project, or is None."
            )
        self.logger.debug("MainController: _on_project_changed finished.")

    def _on_project_settings_updated(self, settings) -> None:
        """Handle project settings update."""
        self.logger.debug(
            f"MainController: _on_project_settings_updated called with settings: {settings}"
        )
        # Update core settings reference
        self.core_settings = settings
        self.logger.debug("MainController: Core settings reference updated.")

        # Recreate analyzer service with new settings
        self.analyzer_service = PytestAnalyzerService(settings=settings)
        self.logger.debug("MainController: PytestAnalyzerService re-initialized with new settings.")

        # Update controllers that depend on settings
        self.analysis_controller.analyzer_service = self.analyzer_service
        self.test_discovery_controller.analyzer_service = self.analyzer_service
        self.test_execution_controller.analyzer_service = self.analyzer_service
        self.logger.debug("MainController: analyzer_service updated in sub-controllers.")

        logger.info("Project settings updated")
        self.logger.debug("MainController: _on_project_settings_updated finished.")

    def _update_status_message(self, message: str) -> None:
        """Update status bar message."""
        self.logger.debug(
            f"MainController: _update_status_message called with message: '{message}'"
        )
        if hasattr(self.main_window, "status_label"):
            self.main_window.status_label.setText(message)
            self.logger.debug("MainController: Status label text updated.")
        else:
            self.logger.debug("MainController: main_window.status_label not found.")
        self.logger.debug("MainController: _update_status_message finished.")

    def _on_session_changed(self, session_data) -> None:
        """Handle session change."""
        self.logger.debug(
            f"MainController: _on_session_changed called with session_data name: {session_data.metadata.name if session_data else 'None'}"
        )
        from ..models.session import SessionData

        if isinstance(session_data, SessionData):
            # Update window title to include session name
            current_title = self.main_window.windowTitle()
            if " - Session:" in current_title:
                base_title = current_title.split(" - Session:")[0]
            else:
                base_title = current_title
            self.logger.debug(
                f"MainController: Current window title: '{current_title}', base title: '{base_title}'"
            )

            new_title = f"{base_title} - Session: {session_data.metadata.name}"
            self.main_window.setWindowTitle(new_title)
            self.logger.debug(f"MainController: Window title updated to '{new_title}'")

            # Update session with current test results if any
            if hasattr(self.test_results_model, "results") and self.test_results_model.results:
                self.logger.debug(
                    f"MainController: Updating session with {len(self.test_results_model.results)} current test results."
                )
                self.session_controller.update_session_with_test_results(
                    self.test_results_model.results
                )
            else:
                self.logger.debug(
                    "MainController: No current test results in model to update session with."
                )

            logger.info(f"Session changed to: {session_data.metadata.name}")
        else:
            self.logger.debug(
                "MainController: session_data is not an instance of SessionData, or is None."
            )
        self.logger.debug("MainController: _on_session_changed finished.")

    def _on_bookmark_added(self, test_name: str, bookmark_type: str) -> None:
        """Handle bookmark addition."""
        self.logger.debug(
            f"MainController: _on_bookmark_added - test_name: {test_name}, type: {bookmark_type}"
        )
        logger.info(f"Bookmark added for test: {test_name} ({bookmark_type})")
        # Could update UI indicators here
        self.logger.debug("MainController: _on_bookmark_added finished.")

    def _on_bookmark_removed(self, test_name: str) -> None:
        """Handle bookmark removal."""
        self.logger.debug(f"MainController: _on_bookmark_removed - test_name: {test_name}")
        logger.info(f"Bookmark removed for test: {test_name}")
        # Could update UI indicators here
        self.logger.debug("MainController: _on_bookmark_removed finished.")

    def _on_quick_html_report(self) -> None:
        """Handle quick HTML report generation."""
        self.logger.debug("MainController: _on_quick_html_report triggered.")
        from ..models.report import ReportFormat, ReportType

        self.report_controller.generate_quick_report(
            report_type=ReportType.SUMMARY, report_format=ReportFormat.HTML
        )
        self.logger.debug(
            "MainController: Called ReportController.generate_quick_report for HTML Summary."
        )
        self.logger.debug("MainController: _on_quick_html_report finished.")

    def _on_export_pdf(self) -> None:
        """Handle PDF export."""
        self.logger.debug("MainController: _on_export_pdf triggered.")
        from ..models.report import ReportFormat

        self.report_controller.export_to_format(ReportFormat.PDF)
        self.logger.debug("MainController: Called ReportController.export_to_format for PDF.")
        self.logger.debug("MainController: _on_export_pdf finished.")

    def _on_export_json(self) -> None:
        """Handle JSON export."""
        self.logger.debug("MainController: _on_export_json triggered.")
        from ..models.report import ReportFormat

        self.report_controller.export_to_format(ReportFormat.JSON)
        self.logger.debug("MainController: Called ReportController.export_to_format for JSON.")
        self.logger.debug("MainController: _on_export_json finished.")

    def _on_export_csv(self) -> None:
        """Handle CSV export."""
        self.logger.debug("MainController: _on_export_csv triggered.")
        from ..models.report import ReportFormat

        self.report_controller.export_to_format(ReportFormat.CSV)
        self.logger.debug("MainController: Called ReportController.export_to_format for CSV.")
        self.logger.debug("MainController: _on_export_csv finished.")

    def _get_analysis_results(self) -> List[Any]:
        """Get analysis results from test results model."""
        self.logger.debug("MainController: _get_analysis_results called.")
        analysis_results = []
        for result in self.test_results_model.results:
            if hasattr(result, "suggestions") and result.suggestions:
                self.logger.debug(f"MainController: Found suggestions for test: {result.name}")
                analysis_results.append(
                    {
                        "test_name": result.name,
                        "suggestions": result.suggestions,
                        "failure_details": getattr(result, "failure_details", None),
                        "analysis_status": getattr(result, "analysis_status", None),
                    }
                )
        self.logger.debug(
            f"MainController: _get_analysis_results returning {len(analysis_results)} items with suggestions."
        )
        return analysis_results

    def cleanup_on_close(self) -> None:
        """Clean up resources when the application is closing."""
        self.logger.debug("MainController: cleanup_on_close called.")
        self.logger.info("MainController cleanup initiated")
        if self.task_manager:
            self.logger.debug("MainController: Calling TaskManager.cleanup_all_tasks().")
            self.task_manager.cleanup_all_tasks()
        self.logger.info("MainController cleanup complete")
        self.logger.debug("MainController: cleanup_on_close finished.")
