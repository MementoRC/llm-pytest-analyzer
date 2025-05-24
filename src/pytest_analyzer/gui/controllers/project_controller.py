"""
Project controller for managing project operations in the Pytest Analyzer GUI.

This module contains the ProjectController class that handles project-related
operations including creation, loading, switching, and settings management.
"""

import logging
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QObject, QSettings, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import QMessageBox

from ..models.project import Project, ProjectManager
from ..views.project_selection_dialog import ProjectSelectionDialog
from .base_controller import BaseController

logger = logging.getLogger(__name__)


class ProjectController(BaseController):
    """Handles project management operations."""

    project_changed = pyqtSignal(Project)
    settings_updated = pyqtSignal(object)  # Settings object
    status_message_updated = pyqtSignal(str)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.project_manager = ProjectManager(self)
        self.qsettings = QSettings()

        # Connect project manager signals
        self.project_manager.project_changed.connect(self._on_project_changed)
        self.project_manager.recent_projects_updated.connect(self._save_recent_projects)

        # Load recent projects from QSettings
        self._load_recent_projects()

        # Try to restore last project
        self._restore_last_project()

    @property
    def current_project(self) -> Optional[Project]:
        """Get the current project."""
        return self.project_manager.current_project

    @pyqtSlot()
    def show_project_selection(self) -> None:
        """Show the project selection dialog."""
        dialog = ProjectSelectionDialog(self.project_manager)
        dialog.project_selected.connect(self._on_project_selected)

        if dialog.exec():
            self.logger.info("Project selection completed")
        else:
            self.logger.info("Project selection cancelled")

    @pyqtSlot(Path)
    def open_project(self, project_path: Path) -> None:
        """Open a project from the given path."""
        try:
            project = self.project_manager.open_project(project_path)
            self.status_message_updated.emit(f"Opened project: {project.name}")
            self.logger.info(f"Opened project: {project.name} at {project.path}")

        except Exception as e:
            error_msg = f"Failed to open project: {e}"
            self.logger.error(error_msg)
            self.status_message_updated.emit(error_msg)

            # Show error dialog
            QMessageBox.warning(
                None, "Project Error", f"Failed to open project at {project_path}:\n\n{e}"
            )

    @pyqtSlot(Path, str)
    def create_project(self, project_path: Path, name: str) -> None:
        """Create a new project."""
        try:
            project = self.project_manager.create_project(project_path, name)
            self.status_message_updated.emit(f"Created project: {project.name}")
            self.logger.info(f"Created project: {project.name} at {project.path}")

        except Exception as e:
            error_msg = f"Failed to create project: {e}"
            self.logger.error(error_msg)
            self.status_message_updated.emit(error_msg)

            # Show error dialog
            QMessageBox.warning(None, "Project Error", f"Failed to create project:\n\n{e}")

    @pyqtSlot()
    def save_current_project(self) -> None:
        """Save the current project configuration."""
        if not self.current_project:
            return

        try:
            self.current_project.save_config()
            self.status_message_updated.emit(f"Saved project: {self.current_project.name}")
            self.logger.info(f"Saved project config: {self.current_project.name}")

        except Exception as e:
            error_msg = f"Failed to save project: {e}"
            self.logger.error(error_msg)
            self.status_message_updated.emit(error_msg)

    @pyqtSlot(object)
    def update_project_settings(self, settings) -> None:
        """Update current project settings."""
        if not self.current_project:
            self.logger.warning("No current project to update settings")
            return

        try:
            # Update project settings
            self.current_project.settings = settings

            # Save immediately
            self.current_project.save_config()

            self.logger.info("Updated project settings")
            self.status_message_updated.emit("Project settings updated")

        except Exception as e:
            error_msg = f"Failed to update project settings: {e}"
            self.logger.error(error_msg)
            self.status_message_updated.emit(error_msg)

    def get_recent_projects(self) -> list:
        """Get list of recent project paths."""
        return self.project_manager.get_recent_projects()

    @pyqtSlot(Path)
    def open_recent_project(self, project_path: Path) -> None:
        """Open a recent project."""
        self.open_project(project_path)

    @pyqtSlot()
    def discover_projects(self) -> list:
        """Discover projects in a directory."""
        # This will be called from the UI
        # Implementation is in ProjectSelectionDialog
        pass

    def _on_project_changed(self, project: Project) -> None:
        """Handle project change."""
        try:
            # Save project path as last opened
            self.qsettings.setValue("project/last_opened", str(project.path))

            # Emit signals
            self.project_changed.emit(project)
            self.settings_updated.emit(project.settings)

            self.logger.info(f"Project changed to: {project.name}")

        except Exception as e:
            self.logger.error(f"Error handling project change: {e}")

    def _on_project_selected(self, project: Project) -> None:
        """Handle project selection from dialog."""
        try:
            self.project_manager.set_current_project(project)

        except Exception as e:
            error_msg = f"Failed to select project: {e}"
            self.logger.error(error_msg)
            self.status_message_updated.emit(error_msg)

    def _load_recent_projects(self) -> None:
        """Load recent projects from QSettings."""
        try:
            recent_count = self.qsettings.beginReadArray("project/recent")
            recent_paths = []

            for i in range(recent_count):
                self.qsettings.setArrayIndex(i)
                path_str = self.qsettings.value("path")
                if path_str:
                    path = Path(path_str)
                    if path.exists():
                        recent_paths.append(path)

            self.qsettings.endArray()

            # Update project manager
            self.project_manager._recent_projects = recent_paths
            self.logger.info(f"Loaded {len(recent_paths)} recent projects")

        except Exception as e:
            self.logger.error(f"Failed to load recent projects: {e}")

    def _save_recent_projects(self, recent_paths: list) -> None:
        """Save recent projects to QSettings."""
        try:
            self.qsettings.beginWriteArray("project/recent")

            for i, path in enumerate(recent_paths):
                self.qsettings.setArrayIndex(i)
                self.qsettings.setValue("path", str(path))

            self.qsettings.endArray()
            self.qsettings.sync()

            self.logger.debug(f"Saved {len(recent_paths)} recent projects")

        except Exception as e:
            self.logger.error(f"Failed to save recent projects: {e}")

    def _restore_last_project(self) -> None:
        """Attempt to restore the last opened project."""
        try:
            last_path_str = self.qsettings.value("project/last_opened")
            if last_path_str:
                last_path = Path(last_path_str)
                if last_path.exists():
                    self.open_project(last_path)
                    self.logger.info(f"Restored last project: {last_path}")
                else:
                    self.logger.warning(f"Last project path no longer exists: {last_path}")
            else:
                self.logger.info("No previous project to restore")

        except Exception as e:
            self.logger.error(f"Failed to restore last project: {e}")

    def close_current_project(self) -> None:
        """Close the current project."""
        if self.current_project:
            try:
                # Save before closing
                self.current_project.save_config()

                project_name = self.current_project.name
                self.project_manager._current_project = None

                self.status_message_updated.emit(f"Closed project: {project_name}")
                self.logger.info(f"Closed project: {project_name}")

                # Clear last opened
                self.qsettings.remove("project/last_opened")

            except Exception as e:
                self.logger.error(f"Error closing project: {e}")

    def get_project_info(self) -> dict:
        """Get information about the current project."""
        if not self.current_project:
            return {}

        return {
            "name": self.current_project.name,
            "path": str(self.current_project.path),
            "description": self.current_project.metadata.description,
            "created_at": self.current_project.metadata.created_at.isoformat(),
            "last_accessed": self.current_project.metadata.last_accessed.isoformat(),
            "tags": self.current_project.metadata.tags,
            "test_patterns": self.current_project.metadata.test_patterns,
            "is_valid": self.current_project.is_valid_project(),
        }
