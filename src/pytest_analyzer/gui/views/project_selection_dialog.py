"""
Project selection dialog for the Pytest Analyzer GUI.

This module contains the dialog for selecting, creating, and managing projects.
"""

import logging
from pathlib import Path
from typing import List, Optional

from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..models.project import Project, ProjectManager

logger = logging.getLogger(__name__)


class ProjectSelectionDialog(QDialog):
    """Dialog for selecting and managing projects."""

    project_selected = pyqtSignal(Project)

    def __init__(self, project_manager: ProjectManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.project_manager = project_manager
        self.selected_project: Optional[Project] = None

        self.setWindowTitle("Project Selection")
        self.setModal(True)
        self.resize(700, 500)

        self._init_ui()
        self._load_recent_projects()
        self._connect_signals()

    def _init_ui(self) -> None:
        """Initialize the UI components."""
        layout = QVBoxLayout(self)

        # Recent Projects Section
        recent_group = QGroupBox("Recent Projects")
        recent_layout = QVBoxLayout(recent_group)

        self.recent_list = QListView()
        self.recent_model = QStandardItemModel()
        self.recent_list.setModel(self.recent_model)
        recent_layout.addWidget(self.recent_list)

        # Project Actions
        actions_layout = QHBoxLayout()

        self.open_project_btn = QPushButton("Open Project...")
        self.create_project_btn = QPushButton("Create New Project...")
        self.discover_projects_btn = QPushButton("Discover Projects...")

        actions_layout.addWidget(self.open_project_btn)
        actions_layout.addWidget(self.create_project_btn)
        actions_layout.addWidget(self.discover_projects_btn)
        actions_layout.addStretch()

        recent_layout.addLayout(actions_layout)
        layout.addWidget(recent_group)

        # Project Details Section
        details_group = QGroupBox("Project Details")
        details_layout = QVBoxLayout(details_group)

        # Project info display
        info_layout = QVBoxLayout()

        self.project_name_label = QLabel("No project selected")
        self.project_name_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        info_layout.addWidget(self.project_name_label)

        self.project_path_label = QLabel("")
        self.project_path_label.setStyleSheet("color: gray;")
        info_layout.addWidget(self.project_path_label)

        self.project_description = QTextEdit()
        self.project_description.setMaximumHeight(60)
        self.project_description.setPlaceholderText("Project description...")
        info_layout.addWidget(self.project_description)

        details_layout.addLayout(info_layout)
        layout.addWidget(details_group)

        # Dialog buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        layout.addWidget(self.button_box)

    def _connect_signals(self) -> None:
        """Connect UI signals."""
        self.recent_list.clicked.connect(self._on_recent_project_selected)
        self.recent_list.doubleClicked.connect(self._on_recent_project_double_clicked)

        self.open_project_btn.clicked.connect(self._on_open_project)
        self.create_project_btn.clicked.connect(self._on_create_project)
        self.discover_projects_btn.clicked.connect(self._on_discover_projects)

        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        self.project_description.textChanged.connect(self._on_description_changed)

    def _load_recent_projects(self) -> None:
        """Load and display recent projects."""
        self.recent_model.clear()

        recent_paths = self.project_manager.get_recent_projects()

        for project_path in recent_paths:
            if project_path.exists():
                try:
                    # Load project to get metadata
                    project = Project.load_config(project_path)

                    item = QStandardItem(f"{project.name}")
                    item.setData(project, Qt.ItemDataRole.UserRole)
                    item.setToolTip(f"{project.path}\n{project.metadata.description}")

                    # Add status indicators
                    if not project.is_valid_project():
                        item.setText(f"{project.name} (Invalid)")
                        item.setEnabled(False)

                    self.recent_model.appendRow(item)

                except Exception as e:
                    logger.error(f"Failed to load project {project_path}: {e}")

    @pyqtSlot()
    def _on_recent_project_selected(self) -> None:
        """Handle recent project selection."""
        indexes = self.recent_list.selectedIndexes()
        if not indexes:
            self._clear_selection()
            return

        item = self.recent_model.itemFromIndex(indexes[0])
        if not item or not item.isEnabled():
            self._clear_selection()
            return

        project = item.data(Qt.ItemDataRole.UserRole)
        if project:
            self._select_project(project)

    @pyqtSlot()
    def _on_recent_project_double_clicked(self) -> None:
        """Handle double-click on recent project."""
        if self.selected_project:
            self.accept()

    @pyqtSlot()
    def _on_open_project(self) -> None:
        """Handle open project button click."""
        project_dir = QFileDialog.getExistingDirectory(
            self,
            "Select Project Directory",
            str(Path.home()),
        )

        if project_dir:
            try:
                project = Project.load_config(Path(project_dir))
                self._select_project(project)

                # Add to recent projects model
                self._add_project_to_recent_model(project)

            except Exception as e:
                logger.error(f"Failed to open project {project_dir}: {e}")

    @pyqtSlot()
    def _on_create_project(self) -> None:
        """Handle create project button click."""
        dialog = CreateProjectDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                project = self.project_manager.create_project(
                    dialog.project_path, dialog.project_name
                )
                self._select_project(project)
                self._add_project_to_recent_model(project)

            except Exception as e:
                logger.error(f"Failed to create project: {e}")

    @pyqtSlot()
    def _on_discover_projects(self) -> None:
        """Handle discover projects button click."""
        root_dir = QFileDialog.getExistingDirectory(
            self,
            "Select Root Directory to Search",
            str(Path.home()),
        )

        if root_dir:
            try:
                discovered = self.project_manager.discover_projects(Path(root_dir))

                if discovered:
                    dialog = DiscoveredProjectsDialog(discovered, self)
                    if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_path:
                        project = Project.load_config(dialog.selected_path)
                        self._select_project(project)
                        self._add_project_to_recent_model(project)
                else:
                    # Show message about no projects found
                    pass

            except Exception as e:
                logger.error(f"Failed to discover projects: {e}")

    def _select_project(self, project: Project) -> None:
        """Select a project and update UI."""
        self.selected_project = project

        self.project_name_label.setText(project.name)
        self.project_path_label.setText(str(project.path))
        self.project_description.setText(project.metadata.description)

        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)

    def _clear_selection(self) -> None:
        """Clear project selection."""
        self.selected_project = None

        self.project_name_label.setText("No project selected")
        self.project_path_label.setText("")
        self.project_description.clear()

        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)

    def _add_project_to_recent_model(self, project: Project) -> None:
        """Add project to recent projects model."""
        # Check if already exists
        for row in range(self.recent_model.rowCount()):
            item = self.recent_model.item(row)
            existing_project = item.data(Qt.ItemDataRole.UserRole)
            if existing_project and existing_project.path == project.path:
                return

        # Add new item
        item = QStandardItem(project.name)
        item.setData(project, Qt.ItemDataRole.UserRole)
        item.setToolTip(f"{project.path}\n{project.metadata.description}")
        self.recent_model.insertRow(0, item)

    @pyqtSlot()
    def _on_description_changed(self) -> None:
        """Handle description text changes."""
        if self.selected_project:
            self.selected_project.metadata.description = self.project_description.toPlainText()

    def accept(self) -> None:
        """Accept dialog and emit selected project."""
        if self.selected_project:
            # Save any changes to description
            if hasattr(self.selected_project, "metadata"):
                self.selected_project.metadata.description = self.project_description.toPlainText()

            self.project_selected.emit(self.selected_project)
        super().accept()


class CreateProjectDialog(QDialog):
    """Dialog for creating new projects."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.project_path: Optional[Path] = None
        self.project_name: str = ""

        self.setWindowTitle("Create New Project")
        self.setModal(True)
        self.resize(500, 200)

        self._init_ui()

    def _init_ui(self) -> None:
        """Initialize UI components."""
        layout = QVBoxLayout(self)

        # Project name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Project Name:"))
        self.name_edit = QLineEdit()
        name_layout.addWidget(self.name_edit)
        layout.addLayout(name_layout)

        # Project location
        location_layout = QHBoxLayout()
        location_layout.addWidget(QLabel("Location:"))
        self.location_edit = QLineEdit()
        self.location_edit.setReadOnly(True)
        location_layout.addWidget(self.location_edit)

        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self._browse_location)
        location_layout.addWidget(self.browse_btn)
        layout.addLayout(location_layout)

        # Full path display
        self.full_path_label = QLabel("")
        self.full_path_label.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(self.full_path_label)

        # Dialog buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        layout.addWidget(self.button_box)

        # Connect signals
        self.name_edit.textChanged.connect(self._update_path)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

    @pyqtSlot()
    def _browse_location(self) -> None:
        """Browse for project location."""
        location = QFileDialog.getExistingDirectory(
            self,
            "Select Project Parent Directory",
            str(Path.home()),
        )

        if location:
            self.location_edit.setText(location)
            self._update_path()

    def _update_path(self) -> None:
        """Update full path display and validation."""
        name = self.name_edit.text().strip()
        location = self.location_edit.text().strip()

        if name and location:
            self.project_path = Path(location) / name
            self.project_name = name
            self.full_path_label.setText(f"Full path: {self.project_path}")

            # Check if path already exists
            if self.project_path.exists():
                self.full_path_label.setText(f"Warning: {self.project_path} already exists")
                self.full_path_label.setStyleSheet("color: orange; font-style: italic;")
            else:
                self.full_path_label.setStyleSheet("color: gray; font-style: italic;")

            self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)
        else:
            self.full_path_label.setText("")
            self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)


class DiscoveredProjectsDialog(QDialog):
    """Dialog for selecting from discovered projects."""

    def __init__(self, discovered_paths: List[Path], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.discovered_paths = discovered_paths
        self.selected_path: Optional[Path] = None

        self.setWindowTitle("Discovered Projects")
        self.setModal(True)
        self.resize(600, 400)

        self._init_ui()

    def _init_ui(self) -> None:
        """Initialize UI components."""
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(f"Found {len(self.discovered_paths)} potential projects:"))

        self.projects_list = QListView()
        self.projects_model = QStandardItemModel()
        self.projects_list.setModel(self.projects_model)
        layout.addWidget(self.projects_list)

        # Populate list
        for path in self.discovered_paths:
            item = QStandardItem(str(path))
            item.setData(path, Qt.ItemDataRole.UserRole)
            self.projects_model.appendRow(item)

        # Dialog buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        layout.addWidget(self.button_box)

        # Connect signals
        self.projects_list.clicked.connect(self._on_project_selected)
        self.projects_list.doubleClicked.connect(self.accept)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

    @pyqtSlot()
    def _on_project_selected(self) -> None:
        """Handle project selection."""
        indexes = self.projects_list.selectedIndexes()
        if indexes:
            item = self.projects_model.itemFromIndex(indexes[0])
            self.selected_path = item.data(Qt.ItemDataRole.UserRole)
            self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)
