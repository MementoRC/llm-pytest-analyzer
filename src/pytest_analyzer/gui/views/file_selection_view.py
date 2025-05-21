"""
File selection view component for the Pytest Analyzer GUI.

This module contains the FileSelectionView widget for selecting and
managing test files and reports.
"""

import os
import logging
from pathlib import Path
from typing import Optional, List, Callable, Dict, Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTreeView, QHeaderView, QFileDialog, QTabWidget,
    QRadioButton, QButtonGroup, QGroupBox, QComboBox
)
from PyQt6.QtCore import Qt, QDir, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QIcon

# Configure logging
logger = logging.getLogger(__name__)


class FileSelectionView(QWidget):
    """
    Widget for selecting test files and reports.
    
    This widget provides a UI for selecting various input types:
    - Test files (Python files containing pytest tests)
    - JSON report files
    - XML report files
    - Test output
    """
    
    # Signals
    file_selected = pyqtSignal(Path)
    report_type_changed = pyqtSignal(str)
    
    def __init__(self, parent: Optional[QWidget] = None):
        """
        Initialize the file selection view.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.current_directory = Path.cwd()
        self.selected_file: Optional[Path] = None
        self.selected_report_type = "json"
        
        # Initialize UI
        self._init_ui()
    
    def _init_ui(self) -> None:
        """Initialize the UI components."""
        # Create main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create tab widget for different input types
        self.tabs = QTabWidget()
        
        # Create tabs for different input types
        self.file_tab = self._create_file_tab()
        self.report_tab = self._create_report_tab()
        self.output_tab = self._create_output_tab()
        
        # Add tabs to tab widget
        self.tabs.addTab(self.file_tab, "Test Files")
        self.tabs.addTab(self.report_tab, "Report Files")
        self.tabs.addTab(self.output_tab, "Test Output")
        
        # Connect tab changed signal
        self.tabs.currentChanged.connect(self._on_tab_changed)
        
        # Add tab widget to main layout
        main_layout.addWidget(self.tabs)
    
    def _create_file_tab(self) -> QWidget:
        """
        Create the test files tab.
        
        Returns:
            Widget containing the test files UI
        """
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Directory selection
        dir_layout = QHBoxLayout()
        dir_label = QLabel("Directory:")
        self.dir_combo = QComboBox()
        self.dir_combo.setEditable(True)
        self.dir_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.dir_combo.setCurrentText(str(self.current_directory))
        
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self._on_browse_directory)
        
        dir_layout.addWidget(dir_label)
        dir_layout.addWidget(self.dir_combo, 1)
        dir_layout.addWidget(browse_button)
        
        # File tree
        self.file_model = QStandardItemModel()
        self.file_model.setHorizontalHeaderLabels(["Name", "Path"])
        
        self.file_tree = QTreeView()
        self.file_tree.setModel(self.file_model)
        self.file_tree.setAlternatingRowColors(True)
        self.file_tree.setAnimated(True)
        self.file_tree.setHeaderHidden(False)
        self.file_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.file_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.file_tree.setSelectionBehavior(QTreeView.SelectionBehavior.SelectRows)
        self.file_tree.clicked.connect(self._on_file_clicked)
        
        # Add widgets to layout
        layout.addLayout(dir_layout)
        layout.addWidget(self.file_tree)
        
        # Populate initial tree
        self._populate_file_tree()
        
        return tab
    
    def _create_report_tab(self) -> QWidget:
        """
        Create the report files tab.
        
        Returns:
            Widget containing the report files UI
        """
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Report type selection
        type_group = QGroupBox("Report Type")
        type_layout = QHBoxLayout(type_group)
        
        self.report_type_group = QButtonGroup()
        self.json_radio = QRadioButton("JSON")
        self.xml_radio = QRadioButton("XML")
        
        self.report_type_group.addButton(self.json_radio)
        self.report_type_group.addButton(self.xml_radio)
        
        # Set default
        self.json_radio.setChecked(True)
        
        # Connect signals
        self.json_radio.toggled.connect(
            lambda checked: checked and self._on_report_type_changed("json")
        )
        self.xml_radio.toggled.connect(
            lambda checked: checked and self._on_report_type_changed("xml")
        )
        
        type_layout.addWidget(self.json_radio)
        type_layout.addWidget(self.xml_radio)
        type_layout.addStretch()
        
        # File selection
        file_layout = QHBoxLayout()
        self.report_path_label = QLabel("No report file selected")
        select_button = QPushButton("Select Report File...")
        select_button.clicked.connect(self._on_select_report)
        
        file_layout.addWidget(self.report_path_label, 1)
        file_layout.addWidget(select_button)
        
        # Add widgets to layout
        layout.addWidget(type_group)
        layout.addLayout(file_layout)
        layout.addStretch()
        
        return tab
    
    def _create_output_tab(self) -> QWidget:
        """
        Create the test output tab.
        
        Returns:
            Widget containing the test output UI
        """
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Placeholder message
        msg = QLabel("Paste pytest output here")
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Add widgets to layout
        layout.addWidget(msg)
        
        # Add "Not implemented yet" message for now
        not_implemented = QLabel("This feature is not implemented yet.")
        not_implemented.setAlignment(Qt.AlignmentFlag.AlignCenter)
        not_implemented.setStyleSheet("color: red;")
        layout.addWidget(not_implemented)
        
        layout.addStretch()
        
        return tab
    
    def _populate_file_tree(self) -> None:
        """Populate the file tree with test files from the current directory."""
        self.file_model.clear()
        self.file_model.setHorizontalHeaderLabels(["Name", "Path"])
        
        root_item = self.file_model.invisibleRootItem()
        
        try:
            # Check if directory exists
            if not self.current_directory.exists():
                logger.warning(f"Directory does not exist: {self.current_directory}")
                return
            
            # Get all Python files in the directory
            for path in self.current_directory.glob("**/*.py"):
                if path.is_file():
                    # Check if the file contains pytest tests
                    if self._is_test_file(path):
                        rel_path = path.relative_to(self.current_directory)
                        name_item = QStandardItem(path.name)
                        path_item = QStandardItem(str(rel_path))
                        
                        name_item.setData(str(path), Qt.ItemDataRole.UserRole)
                        path_item.setData(str(path), Qt.ItemDataRole.UserRole)
                        
                        root_item.appendRow([name_item, path_item])
        
        except Exception as e:
            logger.exception(f"Error populating file tree: {e}")
    
    def _is_test_file(self, path: Path) -> bool:
        """
        Check if a file is a pytest test file.
        
        A file is considered a test file if its name starts with 'test_'
        or ends with '_test.py'.
        
        Args:
            path: Path to the file
            
        Returns:
            True if the file is a test file, False otherwise
        """
        name = path.name
        return name.startswith("test_") or name.endswith("_test.py")
    
    @pyqtSlot()
    def _on_browse_directory(self) -> None:
        """Handle the browse directory button click."""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "Select Directory",
            str(self.current_directory)
        )
        
        if dir_path:
            self.current_directory = Path(dir_path)
            self.dir_combo.setCurrentText(str(self.current_directory))
            
            # Add to history if not already present
            if self.dir_combo.findText(str(self.current_directory)) == -1:
                self.dir_combo.addItem(str(self.current_directory))
            
            # Repopulate the file tree
            self._populate_file_tree()
    
    @pyqtSlot()
    def _on_select_report(self) -> None:
        """Handle the select report file button click."""
        file_filter = "JSON Files (*.json)" if self.selected_report_type == "json" else "XML Files (*.xml)"
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Report File",
            str(self.current_directory),
            file_filter
        )
        
        if file_path:
            self.selected_file = Path(file_path)
            self.report_path_label.setText(str(self.selected_file))
            self.file_selected.emit(self.selected_file)
    
    @pyqtSlot(str)
    def _on_report_type_changed(self, report_type: str) -> None:
        """
        Handle report type change.
        
        Args:
            report_type: Type of report ('json' or 'xml')
        """
        self.selected_report_type = report_type
        self.report_type_changed.emit(report_type)
    
    @pyqtSlot(int)
    def _on_tab_changed(self, index: int) -> None:
        """
        Handle tab change.
        
        Args:
            index: Index of the selected tab
        """
        logger.debug(f"Tab changed to index {index}")
    
    @pyqtSlot()
    def _on_file_clicked(self) -> None:
        """Handle file tree item click."""
        indexes = self.file_tree.selectedIndexes()
        if indexes:
            # Get the file path from the first column's user role data
            file_path = indexes[0].data(Qt.ItemDataRole.UserRole)
            if file_path:
                self.selected_file = Path(file_path)
                self.file_selected.emit(self.selected_file)