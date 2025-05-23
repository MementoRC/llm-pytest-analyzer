"""
Main window for the Pytest Analyzer GUI.

This module contains the MainWindow class that serves as the primary
user interface for the Pytest Analyzer GUI.
"""

import logging
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import QSettings, QSize, Qt, pyqtSlot
from PyQt6.QtGui import QAction, QKeySequence, QShortcut
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

# Views will be imported lazily when needed
from .views.test_execution_progress_view import TestExecutionProgressView  # Always needed

if TYPE_CHECKING:
    from .app import PytestAnalyzerApp

# Configure logging
logger = logging.getLogger(__name__)


class LazyTabWidget(QTabWidget):
    """A tab widget that creates tabs only when they are first accessed."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lazy_tabs = {}  # tab_index: (title, factory_func)
        self._created_tabs = set()  # track which tabs have been created
        self.currentChanged.connect(self._on_tab_changed)

    def add_lazy_tab(self, factory_func, title: str) -> int:
        """Add a tab that will be created lazily when first accessed."""
        tab_index = self.addTab(QWidget(), title)  # Add placeholder widget
        self._lazy_tabs[tab_index] = (title, factory_func)
        return tab_index

    def _on_tab_changed(self, index: int):
        """Create tab content when tab is first accessed."""
        if index in self._lazy_tabs and index not in self._created_tabs:
            title, factory_func = self._lazy_tabs[index]
            try:
                widget = factory_func()
                self.removeTab(index)  # Remove placeholder
                self.insertTab(index, widget, title)
                self.setCurrentIndex(index)  # Restore selection
                self._created_tabs.add(index)
                logger.debug(f"Lazily created tab: {title}")
            except Exception as e:
                logger.error(f"Failed to create lazy tab '{title}': {e}")

    def get_widget(self, index: int):
        """Get widget at index, creating it if necessary."""
        if index in self._lazy_tabs and index not in self._created_tabs:
            self._on_tab_changed(index)
        return self.widget(index)


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
        # Defer service creation until needed
        self._analyzer_service = None
        self._test_results_model = None

        # Track lazy-loaded views
        self._file_selection_view = None
        self._test_discovery_view = None
        self._test_results_view = None
        self._test_output_view = None

        # Set window properties
        self.setWindowTitle("Pytest Analyzer")
        self.resize(1200, 800)
        self.setMinimumSize(800, 600)

        # Set window icon and properties for better UX
        self.setWindowRole("pytest-analyzer-main")

        # Enable window state saving
        self.setObjectName("MainWindow")

        # Initialize UI components
        self._init_ui()
        self._create_actions()
        self._create_menus()
        self._create_toolbars()
        self._create_statusbar()

        # Restore window state if available
        self._restore_state()

        # Setup keyboard shortcuts
        self._setup_shortcuts()

        logger.info("MainWindow initialized")

    def _setup_shortcuts(self) -> None:
        """Setup keyboard shortcuts for better accessibility."""
        # Tab navigation shortcuts
        next_tab_shortcut = QShortcut(QKeySequence("Ctrl+Tab"), self)
        next_tab_shortcut.activated.connect(self._next_tab)

        prev_tab_shortcut = QShortcut(QKeySequence("Ctrl+Shift+Tab"), self)
        prev_tab_shortcut.activated.connect(self._prev_tab)

        # Selection tabs shortcuts
        tab1_shortcut = QShortcut(QKeySequence("Ctrl+1"), self)
        tab1_shortcut.activated.connect(lambda: self.selection_tabs.setCurrentIndex(0))

        tab2_shortcut = QShortcut(QKeySequence("Ctrl+2"), self)
        tab2_shortcut.activated.connect(lambda: self.selection_tabs.setCurrentIndex(1))

        # Analysis tabs shortcuts
        results_shortcut = QShortcut(QKeySequence("Ctrl+3"), self)
        results_shortcut.activated.connect(lambda: self.analysis_tabs.setCurrentIndex(0))

        output_shortcut = QShortcut(QKeySequence("Ctrl+4"), self)
        output_shortcut.activated.connect(lambda: self.analysis_tabs.setCurrentIndex(1))

        # Refresh/reload shortcut
        refresh_shortcut = QShortcut(QKeySequence("F5"), self)
        refresh_shortcut.activated.connect(self._refresh_current_view)

        logger.debug("Keyboard shortcuts configured")

    def _next_tab(self) -> None:
        """Navigate to next tab in current tab widget."""
        focused_widget = self.focusWidget()
        if hasattr(focused_widget, "parent"):
            # Find which tab widget has focus and navigate
            parent = focused_widget
            while parent:
                if isinstance(parent, (QTabWidget, LazyTabWidget)):
                    current = parent.currentIndex()
                    next_index = (current + 1) % parent.count()
                    parent.setCurrentIndex(next_index)
                    break
                parent = parent.parent()

    def _prev_tab(self) -> None:
        """Navigate to previous tab in current tab widget."""
        focused_widget = self.focusWidget()
        if hasattr(focused_widget, "parent"):
            parent = focused_widget
            while parent:
                if isinstance(parent, (QTabWidget, LazyTabWidget)):
                    current = parent.currentIndex()
                    prev_index = (current - 1) % parent.count()
                    parent.setCurrentIndex(prev_index)
                    break
                parent = parent.parent()

    def _refresh_current_view(self) -> None:
        """Refresh the currently active view."""
        # This will be connected by the main controller
        logger.debug("Refresh requested via keyboard shortcut")

    def update_recent_projects_menu(self, recent_paths: list) -> None:
        """Update the recent projects menu with the given paths."""
        if not self.recent_projects_menu:
            return

        # Clear existing actions
        self.recent_projects_menu.clear()

        if not recent_paths:
            self.recent_projects_menu.setEnabled(False)
            return

        self.recent_projects_menu.setEnabled(True)

        # Add actions for each recent project
        for i, path in enumerate(recent_paths[:10]):  # Limit to 10 recent projects
            if path.exists():
                action = QAction(f"&{i + 1} {path.name}", self)
                action.setStatusTip(f"Open project: {path}")
                action.setData(path)  # Store path in action data
                action.triggered.connect(
                    lambda checked, p=path: self._on_recent_project_selected(p)
                )
                self.recent_projects_menu.addAction(action)

        if self.recent_projects_menu.actions():
            self.recent_projects_menu.addSeparator()
            clear_action = QAction("&Clear Recent Projects", self)
            clear_action.triggered.connect(self._on_clear_recent_projects)
            self.recent_projects_menu.addAction(clear_action)

    def _on_recent_project_selected(self, path) -> None:
        """Handle recent project selection."""
        # This will be connected by the main controller via a signal
        logger.debug(f"Recent project selected: {path}")

    def _on_clear_recent_projects(self) -> None:
        """Handle clear recent projects action."""
        # This will be connected by the main controller via a signal
        logger.debug("Clear recent projects requested")

    @property
    def analyzer_service(self):
        """Lazy-loaded analyzer service."""
        if self._analyzer_service is None:
            self._analyzer_service = PytestAnalyzerService(settings=self.app.core_settings)
            logger.debug("Created analyzer service")
        return self._analyzer_service

    @property
    def test_results_model(self):
        """Lazy-loaded test results model."""
        if self._test_results_model is None:
            self._test_results_model = TestResultsModel()
            logger.debug("Created test results model")
        return self._test_results_model

    def _create_file_selection_view(self):
        """Factory function for file selection view."""
        if self._file_selection_view is None:
            from .views.file_selection_view import FileSelectionView

            self._file_selection_view = FileSelectionView()
            logger.debug("Created file selection view")
        return self._file_selection_view

    def _create_test_discovery_view(self):
        """Factory function for test discovery view."""
        if self._test_discovery_view is None:
            from .views.test_discovery_view import TestDiscoveryView

            self._test_discovery_view = TestDiscoveryView()
            logger.debug("Created test discovery view")
        return self._test_discovery_view

    def _create_test_results_view(self):
        """Factory function for test results view."""
        if self._test_results_view is None:
            from .views.test_results_view import TestResultsView

            self._test_results_view = TestResultsView()
            self._test_results_view.set_results_model(self.test_results_model)
            logger.debug("Created test results view")
        return self._test_results_view

    def _create_test_output_view(self):
        """Factory function for test output view."""
        if self._test_output_view is None:
            from .views.test_output_view import TestOutputView

            self._test_output_view = TestOutputView()
            logger.debug("Created test output view")
        return self._test_output_view

    @property
    def file_selection_view(self):
        """Get file selection view, creating if needed."""
        return self._create_file_selection_view()

    @property
    def test_discovery_view(self):
        """Get test discovery view, creating if needed."""
        return self._create_test_discovery_view()

    @property
    def test_results_view(self):
        """Get test results view, creating if needed."""
        return self._create_test_results_view()

    @property
    def test_output_view(self):
        """Get test output view, creating if needed."""
        return self._create_test_output_view()

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

        # Create lazy TabWidget for selection views
        self.selection_tabs = LazyTabWidget()
        self.selection_tabs.add_lazy_tab(self._create_file_selection_view, "Select Files/Reports")
        self.selection_tabs.add_lazy_tab(self._create_test_discovery_view, "Discover Tests")

        self.test_selection_layout.addWidget(self.selection_tabs)

        # Create a QTabWidget for the analysis area (results and output)
        self.analysis_widget = QWidget()
        self.analysis_layout = QVBoxLayout(self.analysis_widget)
        self.analysis_layout.setContentsMargins(0, 0, 0, 0)

        # Create lazy TabWidget for analysis views
        self.analysis_tabs = LazyTabWidget()
        self.analysis_tabs.add_lazy_tab(self._create_test_results_view, "Test Results")
        self.analysis_tabs.add_lazy_tab(self._create_test_output_view, "Live Test Output")

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
        self.open_action = QAction("&Open", self)
        self.open_action.setShortcut(QKeySequence.StandardKey.Open)
        self.open_action.setStatusTip("Open a test file or directory")
        # self.open_action.triggered.connect(self.on_open) # Now handled by MainController

        # Project actions
        self.open_project_action = QAction("Open &Project...", self)
        self.open_project_action.setShortcut(QKeySequence("Ctrl+Shift+O"))
        self.open_project_action.setStatusTip("Open or select a project")

        self.new_project_action = QAction("&New Project...", self)
        self.new_project_action.setShortcut(QKeySequence("Ctrl+Shift+N"))
        self.new_project_action.setStatusTip("Create a new project")

        self.recent_projects_menu = None  # Will be created in _create_menus

        # Session actions
        self.manage_sessions_action = QAction("&Manage Sessions...", self)
        self.manage_sessions_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self.manage_sessions_action.setStatusTip("Manage analysis sessions")

        self.new_session_action = QAction("&New Session", self)
        self.new_session_action.setStatusTip("Create a new analysis session")

        self.save_session_action = QAction("&Save Session", self)
        self.save_session_action.setShortcut(QKeySequence.StandardKey.Save)
        self.save_session_action.setStatusTip("Save current session")

        self.exit_action = QAction("E&xit", self)
        self.exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        self.exit_action.setStatusTip("Exit the application")
        self.exit_action.triggered.connect(self.close)

        # Edit actions
        self.settings_action = QAction("&Settings", self)
        self.settings_action.setShortcut(QKeySequence("Ctrl+,"))
        self.settings_action.setStatusTip("Edit application settings")
        # self.settings_action.triggered.connect(self.on_settings) # Now handled by MainController

        # Tools actions
        self.run_tests_action = QAction("&Run Tests", self)
        self.run_tests_action.setShortcut(QKeySequence("F5"))
        self.run_tests_action.setStatusTip("Run the selected tests")
        # self.run_tests_action.triggered.connect(self.on_run_tests) # Now handled by MainController

        self.analyze_action = QAction("&Analyze", self)
        self.analyze_action.setShortcut(QKeySequence("F6"))
        self.analyze_action.setStatusTip("Analyze test failures")
        # self.analyze_action.triggered.connect(self.on_analyze) # Now handled by MainController

        # Report actions
        self.generate_report_action = QAction("&Generate Report...", self)
        self.generate_report_action.setShortcut(QKeySequence("Ctrl+R"))
        self.generate_report_action.setStatusTip("Generate a comprehensive analysis report")

        self.quick_html_report_action = QAction("Quick &HTML Report", self)
        self.quick_html_report_action.setStatusTip("Generate a quick HTML report")

        self.export_pdf_action = QAction("Export to &PDF...", self)
        self.export_pdf_action.setStatusTip("Export results to PDF format")

        self.export_json_action = QAction("Export to &JSON...", self)
        self.export_json_action.setStatusTip("Export results to JSON format")

        self.export_csv_action = QAction("Export to &CSV...", self)
        self.export_csv_action.setStatusTip("Export results to CSV format")

        # Help actions
        self.about_action = QAction("&About", self)
        self.about_action.setShortcut(QKeySequence("F1"))
        self.about_action.setStatusTip("Show information about Pytest Analyzer")
        # self.about_action.triggered.connect(self.on_about) # Now handled by MainController

    def _create_menus(self) -> None:
        """Create the application menus."""
        self.file_menu = self.menuBar().addMenu("&File")

        # Project submenu
        self.project_menu = self.file_menu.addMenu("&Project")
        self.project_menu.addAction(self.new_project_action)
        self.project_menu.addAction(self.open_project_action)
        self.project_menu.addSeparator()

        # Recent projects submenu
        self.recent_projects_menu = self.project_menu.addMenu("&Recent Projects")
        self.recent_projects_menu.setEnabled(
            False
        )  # Will be enabled when there are recent projects

        self.file_menu.addSeparator()

        # Session submenu
        self.session_menu = self.file_menu.addMenu("&Session")
        self.session_menu.addAction(self.new_session_action)
        self.session_menu.addAction(self.save_session_action)
        self.session_menu.addSeparator()
        self.session_menu.addAction(self.manage_sessions_action)

        self.file_menu.addSeparator()
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

        # Reports menu
        self.reports_menu = self.menuBar().addMenu("&Reports")
        self.reports_menu.addAction(self.generate_report_action)
        self.reports_menu.addAction(self.quick_html_report_action)
        self.reports_menu.addSeparator()

        # Export submenu
        self.export_menu = self.reports_menu.addMenu("&Export")
        self.export_menu.addAction(self.export_pdf_action)
        self.export_menu.addAction(self.export_json_action)
        self.export_menu.addAction(self.export_csv_action)

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
        self.main_toolbar.addAction(self.generate_report_action)
        self.main_toolbar.addSeparator()
        self.main_toolbar.addAction(self.settings_action)

        self.addToolBar(self.main_toolbar)

    def _create_statusbar(self) -> None:
        """Create the application status bar."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Main status label
        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label)

        # Add permanent widgets for useful information
        self.progress_label = QLabel("")
        self.status_bar.addPermanentWidget(self.progress_label)

        # Test count indicator
        self.test_count_label = QLabel("Tests: 0")
        self.status_bar.addPermanentWidget(self.test_count_label)

        # LLM status indicator
        self.llm_status_label = QLabel("LLM: Not configured")
        self.status_bar.addPermanentWidget(self.llm_status_label)

        # Memory usage indicator (optional)
        self.memory_label = QLabel("")
        self.status_bar.addPermanentWidget(self.memory_label)

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
