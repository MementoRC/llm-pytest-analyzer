"""
Session controller for managing session operations in the Pytest Analyzer GUI.

This module contains the SessionController class that handles session-related
operations including creation, loading, saving, and bookmark management.
"""

import logging
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QMessageBox

from ..models.session import SessionData, SessionManager
from ..views.session_management_dialog import SessionManagementDialog
from .base_controller import BaseController

logger = logging.getLogger(__name__)


class SessionController(BaseController):
    """Handles session management operations."""

    session_changed = Signal(SessionData)
    session_saved = Signal(str)  # session_id
    session_loaded = Signal(SessionData)
    bookmark_added = Signal(str, str)  # test_name, bookmark_type
    bookmark_removed = Signal(str)  # test_name
    status_message_updated = Signal(str)

    def __init__(self, sessions_dir: Optional[Path] = None, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.session_manager = SessionManager(sessions_dir, self)

        # Connect session manager signals
        self.session_manager.session_saved.connect(self._on_session_saved)
        self.session_manager.session_loaded.connect(self._on_session_loaded)
        self.session_manager.bookmark_added.connect(self._on_bookmark_added)
        self.session_manager.bookmark_removed.connect(self._on_bookmark_removed)

    @property
    def current_session(self) -> Optional[SessionData]:
        """Get the current session."""
        return self.session_manager.current_session

    @Slot()
    def show_session_management(self) -> None:
        """Show the session management dialog."""
        dialog = SessionManagementDialog(self.session_manager)
        dialog.session_selected.connect(self._on_dialog_session_selected)
        dialog.session_created.connect(self._on_dialog_session_created)

        if dialog.exec():
            self.logger.info("Session management dialog completed")
        else:
            self.logger.info("Session management dialog cancelled")

    @Slot(str, str, str)
    def create_new_session(
        self, name: str = "", description: str = "", project_path: str = ""
    ) -> None:
        """Create a new session."""
        try:
            project_path_obj = Path(project_path) if project_path else None
            session = self.session_manager.create_new_session(name, description, project_path_obj)

            self.status_message_updated.emit(f"Created new session: {session.metadata.name}")
            self.session_changed.emit(session)
            self.logger.info(f"Created new session: {session.metadata.name}")

        except Exception as e:
            error_msg = f"Failed to create session: {e}"
            self.logger.error(error_msg)
            self.status_message_updated.emit(error_msg)

            # Show error dialog
            QMessageBox.warning(None, "Session Error", f"Failed to create new session:\n\n{e}")

    @Slot(str)
    def load_session(self, session_id: str) -> None:
        """Load a session by ID."""
        try:
            session = self.session_manager.load_session(session_id)
            if session:
                self.status_message_updated.emit(f"Loaded session: {session.metadata.name}")
                self.session_changed.emit(session)
                self.logger.info(f"Loaded session: {session.metadata.name}")
            else:
                error_msg = "Failed to load session"
                self.status_message_updated.emit(error_msg)
                self.logger.error(f"Failed to load session: {session_id}")

        except Exception as e:
            error_msg = f"Failed to load session: {e}"
            self.logger.error(error_msg)
            self.status_message_updated.emit(error_msg)

            # Show error dialog
            QMessageBox.warning(None, "Session Error", f"Failed to load session:\n\n{e}")

    @Slot()
    def save_current_session(self) -> None:
        """Save the current session."""
        try:
            if self.session_manager.save_session():
                session_name = (
                    self.current_session.metadata.name if self.current_session else "session"
                )
                self.status_message_updated.emit(f"Saved session: {session_name}")
                self.logger.info(f"Saved current session: {session_name}")
            else:
                error_msg = "Failed to save session"
                self.status_message_updated.emit(error_msg)
                self.logger.error("Failed to save current session")

        except Exception as e:
            error_msg = f"Failed to save session: {e}"
            self.logger.error(error_msg)
            self.status_message_updated.emit(error_msg)

    @Slot(str)
    def delete_session(self, session_id: str) -> None:
        """Delete a session."""
        try:
            if self.session_manager.delete_session(session_id):
                self.status_message_updated.emit("Session deleted successfully")
                self.logger.info(f"Deleted session: {session_id}")
            else:
                error_msg = "Failed to delete session"
                self.status_message_updated.emit(error_msg)
                self.logger.error(f"Failed to delete session: {session_id}")

        except Exception as e:
            error_msg = f"Failed to delete session: {e}"
            self.logger.error(error_msg)
            self.status_message_updated.emit(error_msg)

    @Slot(str)
    def export_session(self, export_path: str) -> None:
        """Export the current session."""
        if not self.current_session:
            self.status_message_updated.emit("No session to export")
            return

        try:
            if self.session_manager.export_session(self.current_session, Path(export_path)):
                self.status_message_updated.emit(f"Session exported to: {export_path}")
                self.logger.info(f"Exported session to: {export_path}")
            else:
                error_msg = "Failed to export session"
                self.status_message_updated.emit(error_msg)
                self.logger.error(f"Failed to export session to: {export_path}")

        except Exception as e:
            error_msg = f"Failed to export session: {e}"
            self.logger.error(error_msg)
            self.status_message_updated.emit(error_msg)

    @Slot(str)
    def import_session(self, import_path: str) -> None:
        """Import a session from file."""
        try:
            session = self.session_manager.import_session(Path(import_path))
            if session:
                self.status_message_updated.emit(f"Imported session: {session.metadata.name}")
                self.session_changed.emit(session)
                self.logger.info(f"Imported session: {session.metadata.name}")
            else:
                error_msg = "Failed to import session"
                self.status_message_updated.emit(error_msg)
                self.logger.error(f"Failed to import session from: {import_path}")

        except Exception as e:
            error_msg = f"Failed to import session: {e}"
            self.logger.error(error_msg)
            self.status_message_updated.emit(error_msg)

    @Slot(str, str, str, str)
    def add_bookmark(
        self,
        test_name: str,
        bookmark_type: str = "important",
        description: str = "",
        notes: str = "",
    ) -> None:
        """Add a bookmark for a test."""
        try:
            if not self.current_session:
                # Create a new session if none exists
                self.create_new_session(
                    "Auto-created Session", "Automatically created for bookmarks"
                )

            self.session_manager.add_bookmark(
                test_name=test_name,
                bookmark_type=bookmark_type,
                description=description,
                notes=notes,
            )

            self.status_message_updated.emit(f"Added bookmark for: {test_name}")
            self.bookmark_added.emit(test_name, bookmark_type)
            self.logger.info(f"Added bookmark for test: {test_name}")

        except Exception as e:
            error_msg = f"Failed to add bookmark: {e}"
            self.logger.error(error_msg)
            self.status_message_updated.emit(error_msg)

    @Slot(str)
    def remove_bookmark(self, test_name: str) -> None:
        """Remove a bookmark for a test."""
        try:
            if self.session_manager.remove_bookmark(test_name):
                self.status_message_updated.emit(f"Removed bookmark for: {test_name}")
                self.bookmark_removed.emit(test_name)
                self.logger.info(f"Removed bookmark for test: {test_name}")
            else:
                self.logger.info(f"No bookmark found for test: {test_name}")

        except Exception as e:
            error_msg = f"Failed to remove bookmark: {e}"
            self.logger.error(error_msg)
            self.status_message_updated.emit(error_msg)

    @Slot(str, str, int, str)
    def add_analysis_history_entry(
        self, test_name: str, analysis_type: str, suggestions_count: int, status: str
    ) -> None:
        """Add an analysis history entry."""
        try:
            if not self.current_session:
                # Create a new session if none exists
                self.create_new_session(
                    "Auto-created Session", "Automatically created for analysis history"
                )

            self.session_manager.add_analysis_history_entry(
                test_name=test_name,
                analysis_type=analysis_type,
                suggestions_count=suggestions_count,
                status=status,
            )

            self.logger.debug(f"Added analysis history entry for test: {test_name}")

        except Exception as e:
            self.logger.error(f"Failed to add analysis history entry: {e}")

    @Slot(list)
    def update_session_with_test_results(self, test_results: List) -> None:
        """Update the current session with test results."""
        try:
            if not self.current_session:
                # Create a new session if none exists
                self.create_new_session(
                    "Auto-created Session", "Automatically created for test results"
                )

            # Update test results in current session
            if self.current_session:
                self.current_session.test_results = test_results

                # Auto-save if enabled
                if self.session_manager._auto_save_enabled:
                    self.session_manager.save_session()

                self.logger.info(f"Updated session with {len(test_results)} test results")

        except Exception as e:
            self.logger.error(f"Failed to update session with test results: {e}")

    @Slot(str)
    def update_workflow_state(self, workflow_state: str) -> None:
        """Update the workflow state in the current session."""
        try:
            if self.current_session:
                self.current_session.workflow_state = workflow_state

                # Auto-save if enabled
                if self.session_manager._auto_save_enabled:
                    self.session_manager.save_session()

                self.logger.debug(f"Updated workflow state to: {workflow_state}")

        except Exception as e:
            self.logger.error(f"Failed to update workflow state: {e}")

    @Slot(str, str, str)
    def update_session_metadata(
        self, name: str = None, description: str = None, tags: str = None
    ) -> None:
        """Update current session metadata."""
        try:
            tags_list = tags.split(",") if tags else None
            if self.session_manager.update_session_metadata(name, description, tags_list):
                self.status_message_updated.emit("Session metadata updated")
                self.logger.info("Updated session metadata")
            else:
                self.logger.warning("No current session to update metadata")

        except Exception as e:
            error_msg = f"Failed to update session metadata: {e}"
            self.logger.error(error_msg)
            self.status_message_updated.emit(error_msg)

    def get_bookmarks_for_test(self, test_name: str) -> List:
        """Get bookmarks for a specific test."""
        try:
            return self.session_manager.get_bookmarks_for_test(test_name)
        except Exception as e:
            self.logger.error(f"Failed to get bookmarks for test {test_name}: {e}")
            return []

    def get_analysis_history_for_test(self, test_name: str) -> List:
        """Get analysis history for a specific test."""
        try:
            return self.session_manager.get_analysis_history_for_test(test_name)
        except Exception as e:
            self.logger.error(f"Failed to get analysis history for test {test_name}: {e}")
            return []

    def set_auto_save(self, enabled: bool) -> None:
        """Enable or disable automatic saving."""
        self.session_manager.set_auto_save(enabled)

    def list_available_sessions(self) -> List:
        """Get a list of available sessions."""
        try:
            return self.session_manager.list_sessions()
        except Exception as e:
            self.logger.error(f"Failed to list sessions: {e}")
            return []

    def _on_session_saved(self, session_id: str) -> None:
        """Handle session saved signal."""
        self.session_saved.emit(session_id)

    def _on_session_loaded(self, session_data: SessionData) -> None:
        """Handle session loaded signal."""
        self.session_loaded.emit(session_data)

    def _on_bookmark_added(self, bookmark) -> None:
        """Handle bookmark added signal."""
        # bookmark is a SessionBookmark object
        self.bookmark_added.emit(bookmark.test_name, bookmark.bookmark_type)

    def _on_bookmark_removed(self, test_name: str) -> None:
        """Handle bookmark removed signal."""
        self.bookmark_removed.emit(test_name)

    def _on_dialog_session_selected(self, session_id: str) -> None:
        """Handle session selection from dialog."""
        self.load_session(session_id)

    def _on_dialog_session_created(self, session_data: SessionData) -> None:
        """Handle session creation from dialog."""
        self.session_changed.emit(session_data)
