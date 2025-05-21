"""
Main window for the Pytest Analyzer GUI.

This module contains the MainWindow class that serves as the primary
user interface for the Pytest Analyzer GUI.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import QSettings, QSize, Qt, pyqtSlot
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ..core.analyzer_service import PytestAnalyzerService
from .models.test_results_model import (
    TestFailureDetails,
    TestGroup,
    TestResult,
    TestResultsModel,
    TestStatus,
)
from .views.file_selection_view import FileSelectionView
from .views.test_results_view import TestResultsView

if TYPE_CHECKING:
    from .app import PytestAnalyzerApp

# Configure logging
logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """
    Main window for the Pytest Analyzer GUI.

    This window contains all the primary UI components for analyzing
    test failures and managing fixes.
    """

    def __init__(self, app: "PytestAnalyzerApp"):
        """
        Initialize the main window.

        Args:
            app: The PytestAnalyzerApp instance
        """
        super().__init__()

        self.app = app
        self.analyzer_service = PytestAnalyzerService()
        self.test_results_model = TestResultsModel()

        # Set window properties
        self.setWindowTitle("Pytest Analyzer")
        self.resize(1200, 800)

        # Initialize UI components
        self._init_ui()
        self._create_actions()
        self._create_menus()
        self._create_toolbars()
        self._create_statusbar()

        # Restore window state if available
        self._restore_state()

        logger.info("MainWindow initialized")

    def _init_ui(self) -> None:
        """Initialize the UI components."""
        # Create main widget and layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        # Main layout
        main_layout = QVBoxLayout(self.central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(0)

        # Create main splitter
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Create file selection view
        self.file_selection_view = FileSelectionView()
        self.file_selection_view.setMinimumWidth(300)
        self.file_selection_view.file_selected.connect(self.on_file_selected)
        self.file_selection_view.report_type_changed.connect(
            self.on_report_type_changed
        )

        # Create a container for the file selection view
        self.test_selection_widget = QWidget()
        self.test_selection_layout = QVBoxLayout(self.test_selection_widget)
        self.test_selection_layout.setContentsMargins(0, 0, 0, 0)
        self.test_selection_layout.addWidget(self.file_selection_view)

        # Create test results view
        self.test_results_view = TestResultsView()
        self.test_results_view.set_results_model(self.test_results_model)
        self.test_results_view.test_selected.connect(self.on_test_selected)
        self.test_results_view.group_selected.connect(self.on_group_selected)

        # Create a container for the test results view
        self.analysis_widget = QWidget()
        self.analysis_layout = QVBoxLayout(self.analysis_widget)
        self.analysis_layout.setContentsMargins(0, 0, 0, 0)
        self.analysis_layout.addWidget(self.test_results_view)

        # Add widgets to splitter
        self.main_splitter.addWidget(self.test_selection_widget)
        self.main_splitter.addWidget(self.analysis_widget)

        # Set splitter proportions
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 3)

        # Add splitter to main layout
        main_layout.addWidget(self.main_splitter)

    def _create_actions(self) -> None:
        """Create actions for menus and toolbars."""
        # File actions
        self.open_action = QAction("Open", self)
        self.open_action.setStatusTip("Open a test file or directory")
        self.open_action.triggered.connect(self.on_open)

        self.exit_action = QAction("Exit", self)
        self.exit_action.setStatusTip("Exit the application")
        self.exit_action.triggered.connect(self.close)

        # Edit actions
        self.settings_action = QAction("Settings", self)
        self.settings_action.setStatusTip("Edit application settings")
        self.settings_action.triggered.connect(self.on_settings)

        # Tools actions
        self.run_tests_action = QAction("Run Tests", self)
        self.run_tests_action.setStatusTip("Run the selected tests")
        self.run_tests_action.triggered.connect(self.on_run_tests)

        self.analyze_action = QAction("Analyze", self)
        self.analyze_action.setStatusTip("Analyze test failures")
        self.analyze_action.triggered.connect(self.on_analyze)

        # Help actions
        self.about_action = QAction("About", self)
        self.about_action.setStatusTip("Show information about Pytest Analyzer")
        self.about_action.triggered.connect(self.on_about)

    def _create_menus(self) -> None:
        """Create the application menus."""
        # File menu
        self.file_menu = self.menuBar().addMenu("&File")
        self.file_menu.addAction(self.open_action)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.exit_action)

        # Edit menu
        self.edit_menu = self.menuBar().addMenu("&Edit")
        self.edit_menu.addAction(self.settings_action)

        # View menu
        self.view_menu = self.menuBar().addMenu("&View")

        # Tools menu
        self.tools_menu = self.menuBar().addMenu("&Tools")
        self.tools_menu.addAction(self.run_tests_action)
        self.tools_menu.addAction(self.analyze_action)

        # Help menu
        self.help_menu = self.menuBar().addMenu("&Help")
        self.help_menu.addAction(self.about_action)

    def _create_toolbars(self) -> None:
        """Create the application toolbars."""
        self.main_toolbar = QToolBar("Main")
        self.main_toolbar.setMovable(False)
        self.main_toolbar.setIconSize(QSize(24, 24))

        self.main_toolbar.addAction(self.open_action)
        self.main_toolbar.addAction(self.run_tests_action)
        self.main_toolbar.addAction(self.analyze_action)
        self.main_toolbar.addSeparator()
        self.main_toolbar.addAction(self.settings_action)

        self.addToolBar(self.main_toolbar)

    def _create_statusbar(self) -> None:
        """Create the application status bar."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label)

        self.llm_status_label = QLabel("LLM: Not configured")
        self.status_bar.addPermanentWidget(self.llm_status_label)

    def _restore_state(self) -> None:
        """Restore window state from settings."""
        settings = QSettings()

        if settings.contains("mainwindow/geometry"):
            self.restoreGeometry(settings.value("mainwindow/geometry"))

        if settings.contains("mainwindow/windowState"):
            self.restoreState(settings.value("mainwindow/windowState"))

        if settings.contains("mainwindow/splitterSizes"):
            # Convert the splitter sizes to integers
            sizes = settings.value("mainwindow/splitterSizes")
            if isinstance(sizes, (list, tuple)) and all(isinstance(size, (int, str)) for size in sizes):
                # Convert any string values to integers
                int_sizes = [int(size) if isinstance(size, str) else size for size in sizes]
                self.main_splitter.setSizes(int_sizes)

    def closeEvent(self, event: Any) -> None:
        """
        Handle the window close event.

        Args:
            event: Close event
        """
        # Save window state
        settings = QSettings()
        settings.setValue("mainwindow/geometry", self.saveGeometry())
        settings.setValue("mainwindow/windowState", self.saveState())
        settings.setValue("mainwindow/splitterSizes", self.main_splitter.sizes())

        # Accept the close event
        event.accept()

    @pyqtSlot()
    def on_open(self) -> None:
        """Handle the Open action."""
        # Show file dialog to select various file types
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open File",
            str(self.app.core_settings.project_root),
            "Python Files (*.py);;JSON Files (*.json);;XML Files (*.xml);;All Files (*)",
        )

        if file_path:
            path = Path(file_path)
            self.status_label.setText(f"Selected file: {file_path}")
            logger.info(f"Selected file: {file_path}")

            # Process the selected file based on its type
            self.on_file_selected(path)

    @pyqtSlot(Path)
    def on_file_selected(self, path: Path) -> None:
        """
        Handle file selection from the file selection view.

        Args:
            path: Path to the selected file
        """
        file_type = path.suffix.lower()

        if file_type == ".py":
            self.status_label.setText(f"Selected test file: {path.name}")
            # Load the test file for analysis
            self._load_test_file(path)
        elif file_type == ".json":
            self.status_label.setText(f"Selected JSON report: {path.name}")
            # Load the JSON report for analysis
            self._load_json_report(path)
        elif file_type == ".xml":
            self.status_label.setText(f"Selected XML report: {path.name}")
            # Load the XML report for analysis
            self._load_xml_report(path)
        else:
            self.status_label.setText(f"Unsupported file type: {path.name}")
            logger.warning(f"Unsupported file type: {file_type}")

    def _load_test_file(self, path: Path) -> None:
        """
        Load test file for analysis.

        Args:
            path: Path to the test file
        """
        # This would typically run the tests in the file
        # For now, just show a message
        QMessageBox.information(
            self,
            "Test File",
            f"Running tests in {path.name} will be implemented in a future task.",
        )

        # Clear existing results
        self.test_results_model.clear()

    def _load_json_report(self, path: Path) -> None:
        """
        Load test results from a JSON report file.

        Args:
            path: Path to the JSON report file
        """
        try:
            # Load the JSON file
            import json

            with open(path, "r") as f:
                data = json.load(f)

            # Process results
            results = []

            # Check for pytest JSON report format
            if "tests" in data:
                # Process each test in the report
                for test_data in data["tests"]:
                    test_result = TestResult(
                        name=test_data.get("nodeid", "Unknown"),
                        status=self._map_test_status(
                            test_data.get("outcome", "unknown")
                        ),
                        duration=test_data.get("duration", 0.0),
                        file_path=Path(test_data.get("path", ""))
                        if "path" in test_data
                        else None,
                    )

                    # Add failure details if the test failed
                    if test_result.status in (TestStatus.FAILED, TestStatus.ERROR):
                        failure_details = TestFailureDetails(
                            message=test_data.get("message", ""),
                            traceback=test_data.get("longrepr", ""),
                        )
                        test_result.failure_details = failure_details

                    results.append(test_result)

            # Update the model
            self.test_results_model.set_results(results, path, "json")

            # Show a success message
            self.status_label.setText(
                f"Loaded {len(results)} test results from {path.name}"
            )
            logger.info(f"Loaded {len(results)} test results from {path}")

        except Exception as e:
            # Show an error message
            QMessageBox.warning(
                self, "Error Loading Report", f"Failed to load JSON report: {str(e)}"
            )
            logger.exception(f"Error loading JSON report {path}: {e}")

    def _load_xml_report(self, path: Path) -> None:
        """
        Load test results from an XML report file.

        Args:
            path: Path to the XML report file
        """
        try:
            # Parse the XML file
            import xml.etree.ElementTree as ET

            tree = ET.parse(path)
            root = tree.getroot()

            # Process results
            results = []

            # Check for JUnit XML format
            if root.tag == "testsuites" or root.tag == "testsuite":
                # Get all testcase elements
                testsuites = (
                    [root] if root.tag == "testsuite" else root.findall("./testsuite")
                )

                for testsuite in testsuites:
                    for testcase in testsuite.findall("./testcase"):
                        # Extract test details
                        name = f"{testcase.get('classname', '')}.{testcase.get('name', '')}"
                        duration = (
                            float(testcase.get("time", "0"))
                            if testcase.get("time")
                            else 0.0
                        )

                        # Determine test status
                        status = TestStatus.PASSED
                        failure_details = None

                        # Check for failure or error
                        failure = testcase.find("./failure")
                        error = testcase.find("./error")
                        skipped = testcase.find("./skipped")

                        if failure is not None:
                            status = TestStatus.FAILED
                            failure_details = TestFailureDetails(
                                message=failure.get("message", ""),
                                traceback=failure.text or "",
                            )
                        elif error is not None:
                            status = TestStatus.ERROR
                            failure_details = TestFailureDetails(
                                message=error.get("message", ""),
                                traceback=error.text or "",
                            )
                        elif skipped is not None:
                            status = TestStatus.SKIPPED

                        # Create test result
                        test_result = TestResult(
                            name=name,
                            status=status,
                            duration=duration,
                            file_path=None,  # XML format typically doesn't include file paths
                        )

                        if failure_details:
                            test_result.failure_details = failure_details

                        results.append(test_result)

            # Update the model
            self.test_results_model.set_results(results, path, "xml")

            # Show a success message
            self.status_label.setText(
                f"Loaded {len(results)} test results from {path.name}"
            )
            logger.info(f"Loaded {len(results)} test results from {path}")

        except Exception as e:
            # Show an error message
            QMessageBox.warning(
                self, "Error Loading Report", f"Failed to load XML report: {str(e)}"
            )
            logger.exception(f"Error loading XML report {path}: {e}")

    def _map_test_status(self, status_str: str) -> TestStatus:
        """
        Map a status string to a TestStatus enum value.

        Args:
            status_str: Status string

        Returns:
            TestStatus enum value
        """
        status_map = {
            "passed": TestStatus.PASSED,
            "failed": TestStatus.FAILED,
            "error": TestStatus.ERROR,
            "skipped": TestStatus.SKIPPED,
        }

        return status_map.get(status_str.lower(), TestStatus.UNKNOWN)

    @pyqtSlot(str)
    def on_report_type_changed(self, report_type: str) -> None:
        """
        Handle report type change from the file selection view.

        Args:
            report_type: Type of report ('json' or 'xml')
        """
        logger.debug(f"Report type changed to {report_type}")
        # Update UI elements based on report type

    @pyqtSlot(TestResult)
    def on_test_selected(self, test: TestResult) -> None:
        """
        Handle test selection from the test results view.

        Args:
            test: Selected test result
        """
        logger.debug(f"Test selected: {test.name}")
        # Handle test selection
        # For now, just update the status bar
        self.status_label.setText(f"Selected test: {test.name}")

    @pyqtSlot(TestGroup)
    def on_group_selected(self, group: TestGroup) -> None:
        """
        Handle group selection from the test results view.

        Args:
            group: Selected test group
        """
        logger.debug(f"Group selected: {group.name}")
        # Handle group selection
        # For now, just update the status bar
        self.status_label.setText(
            f"Selected group: {group.name} ({len(group.tests)} tests)"
        )

    @pyqtSlot()
    def on_settings(self) -> None:
        """Handle the Settings action."""
        # Will be implemented with a proper settings dialog
        QMessageBox.information(
            self, "Settings", "Settings dialog will be implemented in a future task."
        )

    @pyqtSlot()
    def on_run_tests(self) -> None:
        """Handle the Run Tests action."""
        # Will be implemented with proper test execution
        QMessageBox.information(
            self, "Run Tests", "Test execution will be implemented in a future task."
        )

    @pyqtSlot()
    def on_analyze(self) -> None:
        """Handle the Analyze action."""
        # Will be implemented with proper analysis
        QMessageBox.information(
            self, "Analyze", "Test analysis will be implemented in a future task."
        )

    @pyqtSlot()
    def on_about(self) -> None:
        """Handle the About action."""
        QMessageBox.about(
            self,
            "About Pytest Analyzer",
            f"""<b>Pytest Analyzer</b> v{self.app.applicationVersion()}
            <p>A tool for analyzing pytest test failures and suggesting fixes.</p>
            <p>Created by MementoRC</p>
            """,
        )
