"""
Main window for the Pytest Analyzer GUI.

This module contains the MainWindow class that serves as the primary
user interface for the Pytest Analyzer GUI.
"""

import logging
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import QSettings, QSize, Qt, pyqtSlot
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ..core.analyzer_service import PytestAnalyzerService
from .models.test_results_model import (
    TestResultsModel,
)
from .views.file_selection_view import FileSelectionView
from .views.test_discovery_view import TestDiscoveryView
from .views.test_execution_progress_view import TestExecutionProgressView  # Added
from .views.test_output_view import TestOutputView  # Added
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
        self.analyzer_service = PytestAnalyzerService(settings=app.core_settings)
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
        main_layout.setSpacing(5)  # Added some spacing

        # Create main splitter
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Create a container for the left panel (selection views)
        self.test_selection_widget = QWidget()
        self.test_selection_layout = QVBoxLayout(self.test_selection_widget)
        self.test_selection_layout.setContentsMargins(0, 0, 0, 0)
        self.test_selection_widget.setMinimumWidth(350)  # Adjusted min width

        # Create TabWidget for selection views
        self.selection_tabs = QTabWidget()

        # Create file selection view
        self.file_selection_view = FileSelectionView()
        self.selection_tabs.addTab(self.file_selection_view, "Select Files/Reports")

        # Create test discovery view
        self.test_discovery_view = TestDiscoveryView()
        self.selection_tabs.addTab(self.test_discovery_view, "Discover Tests")

        self.test_selection_layout.addWidget(self.selection_tabs)

        # Create test results view
        self.test_results_view = TestResultsView()
        self.test_results_view.set_results_model(self.test_results_model)
        # Connections for test_selected and group_selected will be handled by MainController

        # Create a QTabWidget for the analysis area (results and output)
        self.analysis_widget = QWidget()
        self.analysis_layout = QVBoxLayout(self.analysis_widget)
        self.analysis_layout.setContentsMargins(0, 0, 0, 0)

        self.analysis_tabs = QTabWidget()
        self.analysis_tabs.addTab(self.test_results_view, "Test Results")

        # Create test output view and add it as a tab
        self.test_output_view = TestOutputView()
        self.analysis_tabs.addTab(self.test_output_view, "Live Test Output")

        self.analysis_layout.addWidget(self.analysis_tabs)

        # Add widgets to splitter
        self.main_splitter.addWidget(self.test_selection_widget)
        self.main_splitter.addWidget(self.analysis_widget)

        # Set splitter proportions
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 3)

        # Add splitter to main layout
        main_layout.addWidget(self.main_splitter, 1)  # Give splitter stretch factor

        # Create Test Execution Progress View
        self.test_execution_progress_view = TestExecutionProgressView()
        self.test_execution_progress_view.setObjectName("TestExecutionProgressView")
        # Initially hidden, controller will manage visibility
        self.test_execution_progress_view.hide()
        main_layout.addWidget(self.test_execution_progress_view)

    def _create_actions(self) -> None:
        """Create actions for menus and toolbars."""
        # File actions
        self.open_action = QAction("Open", self)
        self.open_action.setStatusTip("Open a test file or directory")
        # self.open_action.triggered.connect(self.on_open) # Now handled by MainController

        self.exit_action = QAction("Exit", self)
        self.exit_action.setStatusTip("Exit the application")
        self.exit_action.triggered.connect(self.close)

        # Edit actions
        self.settings_action = QAction("Settings", self)
        self.settings_action.setStatusTip("Edit application settings")
        # self.settings_action.triggered.connect(self.on_settings) # Now handled by MainController

        # Tools actions
        self.run_tests_action = QAction("Run Tests", self)
        self.run_tests_action.setStatusTip("Run the selected tests")
        # self.run_tests_action.triggered.connect(self.on_run_tests) # Now handled by MainController

        self.analyze_action = QAction("Analyze", self)
        self.analyze_action.setStatusTip("Analyze test failures")
        # self.analyze_action.triggered.connect(self.on_analyze) # Now handled by MainController

        # Help actions
        self.about_action = QAction("About", self)
        self.about_action.setStatusTip("Show information about Pytest Analyzer")
        # self.about_action.triggered.connect(self.on_about) # Now handled by MainController

    def _create_menus(self) -> None:
        """Create the application menus."""
        self.file_menu = self.menuBar().addMenu("&File")
        self.file_menu.addAction(self.open_action)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.exit_action)

        self.edit_menu = self.menuBar().addMenu("&Edit")
        self.edit_menu.addAction(self.settings_action)

        self.view_menu = self.menuBar().addMenu("&View")  # Placeholder for future view options

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

        self.llm_status_label = QLabel("LLM: Not configured")  # Placeholder
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
            if isinstance(sizes, (list, tuple)) and all(
                isinstance(size, (int, str)) for size in sizes
            ):
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

    # Removed slot handlers like on_open, on_file_selected, on_settings, etc.
    # These are now managed by their respective controllers via MainController.
    # MainWindow now primarily focuses on UI structure and action definitions.
    # Direct signal connections from UI elements (e.g., file_selection_view.file_selected)
    # are also removed as they are set up in MainController._connect_signals.

    # Example: on_test_selected and on_group_selected were connected directly
    # from test_results_view. These will now be connected in MainController
    # to the TestResultsController.
    # For clarity, removing the placeholder slots from MainWindow that are now controller responsibilities.
    # The QActions (e.g., self.open_action) are still defined here, but their `triggered`
    # signals are connected to controller methods in MainController.

    # Keeping on_about as it's simple and directly uses self.app.applicationVersion()
    # Alternatively, this too could be moved to a dedicated controller if desired.
    @pyqtSlot()
    def on_settings(self) -> None:
        """Handle the Settings action - temporary backward compatibility for tests."""
        QMessageBox.information(
            self, "Settings", "Settings dialog will be implemented in a future task."
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
