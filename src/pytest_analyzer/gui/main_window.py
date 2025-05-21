"""
Main window for the Pytest Analyzer GUI.

This module contains the MainWindow class that serves as the primary
user interface for the Pytest Analyzer GUI.
"""

import sys
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QSplitter, QToolBar, QStatusBar, QMessageBox,
    QFileDialog, QAction, QMenu, QLabel
)
from PyQt6.QtCore import Qt, QSize, QSettings, pyqtSlot
from PyQt6.QtGui import QIcon

from ..core.analyzer_service import PytestAnalyzerService
from ..utils.settings import Settings

# Configure logging
logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """
    Main window for the Pytest Analyzer GUI.
    
    This window contains all the primary UI components for analyzing
    test failures and managing fixes.
    """
    
    def __init__(self, app: 'PytestAnalyzerApp'):
        """
        Initialize the main window.
        
        Args:
            app: The PytestAnalyzerApp instance
        """
        super().__init__()
        
        self.app = app
        self.analyzer_service = PytestAnalyzerService()
        
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
        
        # Create placeholder widgets for now
        # These will be replaced with actual UI components in future tasks
        self.test_selection_widget = QWidget()
        self.test_selection_widget.setMinimumWidth(250)
        self.test_selection_layout = QVBoxLayout(self.test_selection_widget)
        self.test_selection_layout.addWidget(QLabel("Test Selection Panel (Placeholder)"))
        
        self.analysis_widget = QWidget()
        self.analysis_layout = QVBoxLayout(self.analysis_widget)
        self.analysis_layout.addWidget(QLabel("Analysis Panel (Placeholder)"))
        
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
            self.main_splitter.setSizes(settings.value("mainwindow/splitterSizes"))
    
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
        # Show file dialog to select a test file or directory
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Test File",
            str(self.app.core_settings.project_root),
            "Python Files (*.py);;All Files (*)"
        )
        
        if file_path:
            self.status_label.setText(f"Selected file: {file_path}")
            logger.info(f"Selected file: {file_path}")
    
    @pyqtSlot()
    def on_settings(self) -> None:
        """Handle the Settings action."""
        # Will be implemented with a proper settings dialog
        QMessageBox.information(
            self,
            "Settings",
            "Settings dialog will be implemented in a future task."
        )
    
    @pyqtSlot()
    def on_run_tests(self) -> None:
        """Handle the Run Tests action."""
        # Will be implemented with proper test execution
        QMessageBox.information(
            self,
            "Run Tests",
            "Test execution will be implemented in a future task."
        )
    
    @pyqtSlot()
    def on_analyze(self) -> None:
        """Handle the Analyze action."""
        # Will be implemented with proper analysis
        QMessageBox.information(
            self,
            "Analyze",
            "Test analysis will be implemented in a future task."
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
            """
        )