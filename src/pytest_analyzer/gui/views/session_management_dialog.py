"""
Session management dialog for the Pytest Analyzer GUI.

This module contains the dialog for managing analysis sessions including
creation, loading, deletion, and import/export functionality.
"""

import logging
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..models.session import SessionData, SessionManager, SessionMetadata

logger = logging.getLogger(__name__)


class SessionManagementDialog(QDialog):
    """Dialog for managing analysis sessions."""

    session_selected = Signal(str)  # session_id
    session_created = Signal(SessionData)

    def __init__(self, session_manager: SessionManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.session_manager = session_manager
        self.selected_session_id: Optional[str] = None

        self.setWindowTitle("Session Management")
        self.setModal(True)
        self.resize(800, 600)

        self._init_ui()
        self._load_sessions()
        self._connect_signals()

    def _init_ui(self) -> None:
        """Initialize the UI components."""
        layout = QVBoxLayout(self)

        # Create main splitter
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(main_splitter)

        # Left panel - Session list
        left_panel = self._create_session_list_panel()
        main_splitter.addWidget(left_panel)

        # Right panel - Session details
        right_panel = self._create_session_details_panel()
        main_splitter.addWidget(right_panel)

        # Set splitter proportions
        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 2)

        # Dialog buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Apply
        )

        # Customize button text
        self.load_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        self.load_button.setText("Load Session")
        self.load_button.setEnabled(False)

        self.apply_button = self.button_box.button(QDialogButtonBox.StandardButton.Apply)
        self.apply_button.setText("Save Changes")
        self.apply_button.setEnabled(False)

        layout.addWidget(self.button_box)

    def _create_session_list_panel(self) -> QWidget:
        """Create the session list panel."""
        panel = QGroupBox("Sessions")
        layout = QVBoxLayout(panel)

        # Sessions list
        self.sessions_list = QListView()
        self.sessions_model = QStandardItemModel()
        self.sessions_list.setModel(self.sessions_model)
        layout.addWidget(self.sessions_list)

        # Action buttons
        actions_layout = QHBoxLayout()

        self.new_session_btn = QPushButton("New Session")
        self.delete_session_btn = QPushButton("Delete")
        self.delete_session_btn.setEnabled(False)

        self.import_session_btn = QPushButton("Import...")
        self.export_session_btn = QPushButton("Export...")
        self.export_session_btn.setEnabled(False)

        actions_layout.addWidget(self.new_session_btn)
        actions_layout.addWidget(self.delete_session_btn)
        actions_layout.addStretch()
        actions_layout.addWidget(self.import_session_btn)
        actions_layout.addWidget(self.export_session_btn)

        layout.addLayout(actions_layout)

        return panel

    def _create_session_details_panel(self) -> QWidget:
        """Create the session details panel."""
        panel = QGroupBox("Session Details")
        layout = QVBoxLayout(panel)

        # Basic info
        info_layout = QVBoxLayout()

        # Name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Name:"))
        self.session_name_edit = QLineEdit()
        name_layout.addWidget(self.session_name_edit)
        info_layout.addLayout(name_layout)

        # Description
        info_layout.addWidget(QLabel("Description:"))
        self.session_description_edit = QTextEdit()
        self.session_description_edit.setMaximumHeight(80)
        info_layout.addWidget(self.session_description_edit)

        # Metadata display
        self.metadata_label = QLabel("No session selected")
        self.metadata_label.setStyleSheet("color: gray; font-style: italic;")
        info_layout.addWidget(self.metadata_label)

        layout.addLayout(info_layout)

        # Session statistics
        stats_group = QGroupBox("Statistics")
        stats_layout = QVBoxLayout(stats_group)

        self.stats_label = QLabel("No data available")
        stats_layout.addWidget(self.stats_label)

        layout.addWidget(stats_group)

        # Bookmarks section
        bookmarks_group = QGroupBox("Bookmarks")
        bookmarks_layout = QVBoxLayout(bookmarks_group)

        self.bookmarks_list = QListView()
        self.bookmarks_model = QStandardItemModel()
        self.bookmarks_list.setModel(self.bookmarks_model)
        bookmarks_layout.addWidget(self.bookmarks_list)

        layout.addWidget(bookmarks_group)

        return panel

    def _connect_signals(self) -> None:
        """Connect UI signals."""
        self.sessions_list.clicked.connect(self._on_session_selected)
        self.sessions_list.doubleClicked.connect(self._on_session_double_clicked)

        self.new_session_btn.clicked.connect(self._on_new_session)
        self.delete_session_btn.clicked.connect(self._on_delete_session)
        self.import_session_btn.clicked.connect(self._on_import_session)
        self.export_session_btn.clicked.connect(self._on_export_session)

        self.session_name_edit.textChanged.connect(self._on_details_changed)
        self.session_description_edit.textChanged.connect(self._on_details_changed)

        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.apply_button.clicked.connect(self._on_apply_changes)

    def _load_sessions(self) -> None:
        """Load and display available sessions."""
        self.sessions_model.clear()
        self.sessions_model.setHorizontalHeaderLabels(["Session"])

        sessions = self.session_manager.list_sessions()

        for session_metadata in sessions:
            item = QStandardItem(session_metadata.name)
            item.setData(session_metadata, Qt.ItemDataRole.UserRole)
            item.setToolTip(
                f"Created: {session_metadata.created_at.strftime('%Y-%m-%d %H:%M')}\n"
                f"Modified: {session_metadata.last_modified.strftime('%Y-%m-%d %H:%M')}\n"
                f"Description: {session_metadata.description or 'No description'}"
            )

            self.sessions_model.appendRow(item)

    @Slot()
    def _on_session_selected(self) -> None:
        """Handle session selection."""
        indexes = self.sessions_list.selectedIndexes()
        if not indexes:
            self._clear_details()
            return

        item = self.sessions_model.itemFromIndex(indexes[0])
        if not item:
            self._clear_details()
            return

        session_metadata = item.data(Qt.ItemDataRole.UserRole)
        if session_metadata:
            self._display_session_details(session_metadata)

    @Slot()
    def _on_session_double_clicked(self) -> None:
        """Handle double-click on session."""
        if self.selected_session_id:
            self.accept()

    @Slot()
    def _on_new_session(self) -> None:
        """Handle new session creation."""
        dialog = NewSessionDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            session = self.session_manager.create_new_session(
                name=dialog.session_name,
                description=dialog.session_description,
            )

            self._load_sessions()  # Refresh list
            self.session_created.emit(session)

    @Slot()
    def _on_delete_session(self) -> None:
        """Handle session deletion."""
        if not self.selected_session_id:
            return

        # Get session name for confirmation
        session_name = "selected session"
        indexes = self.sessions_list.selectedIndexes()
        if indexes:
            item = self.sessions_model.itemFromIndex(indexes[0])
            if item:
                session_metadata = item.data(Qt.ItemDataRole.UserRole)
                if session_metadata:
                    session_name = session_metadata.name

        # Confirm deletion
        reply = QMessageBox.question(
            self,
            "Delete Session",
            f"Are you sure you want to delete '{session_name}'?\n\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            if self.session_manager.delete_session(self.selected_session_id):
                self._load_sessions()  # Refresh list
                self._clear_details()
                QMessageBox.information(self, "Success", "Session deleted successfully.")
            else:
                QMessageBox.warning(self, "Error", "Failed to delete session.")

    @Slot()
    def _on_import_session(self) -> None:
        """Handle session import."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Session", str(Path.home()), "JSON Files (*.json);;All Files (*)"
        )

        if file_path:
            try:
                session = self.session_manager.import_session(Path(file_path))
                if session:
                    self._load_sessions()  # Refresh list
                    QMessageBox.information(self, "Success", "Session imported successfully.")
                else:
                    QMessageBox.warning(self, "Error", "Failed to import session.")
            except Exception as e:
                QMessageBox.critical(self, "Import Error", f"Failed to import session:\n\n{e}")

    @Slot()
    def _on_export_session(self) -> None:
        """Handle session export."""
        if not self.selected_session_id:
            return

        # Load the session for export
        session = self.session_manager.load_session(self.selected_session_id)
        if not session:
            QMessageBox.warning(self, "Error", "Failed to load session for export.")
            return

        # Get export file path
        default_name = f"{session.metadata.name}.json"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Session",
            str(Path.home() / default_name),
            "JSON Files (*.json);;All Files (*)",
        )

        if file_path:
            try:
                if self.session_manager.export_session(session, Path(file_path)):
                    QMessageBox.information(self, "Success", "Session exported successfully.")
                else:
                    QMessageBox.warning(self, "Error", "Failed to export session.")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to export session:\n\n{e}")

    def _display_session_details(self, session_metadata: SessionMetadata) -> None:
        """Display details for the selected session."""
        self.selected_session_id = session_metadata.id

        # Update UI elements
        self.session_name_edit.setText(session_metadata.name)
        self.session_description_edit.setText(session_metadata.description)

        # Update metadata display
        metadata_text = (
            f"ID: {session_metadata.id}\n"
            f"Created: {session_metadata.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Modified: {session_metadata.last_modified.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Project: {session_metadata.project_path or 'None'}\n"
            f"Tags: {', '.join(session_metadata.tags) if session_metadata.tags else 'None'}"
        )
        self.metadata_label.setText(metadata_text)

        # Try to load full session data for statistics
        try:
            session_data = self.session_manager.load_session(session_metadata.id)
            if session_data:
                self._update_session_statistics(session_data)
                self._update_bookmarks_display(session_data)
        except Exception as e:
            logger.warning(f"Failed to load session data for display: {e}")
            self.stats_label.setText("Failed to load session statistics")

        # Enable relevant buttons
        self.load_button.setEnabled(True)
        self.delete_session_btn.setEnabled(True)
        self.export_session_btn.setEnabled(True)

    def _update_session_statistics(self, session_data: SessionData) -> None:
        """Update session statistics display."""
        test_count = len(session_data.test_results)
        bookmark_count = len(session_data.bookmarks)
        history_count = len(session_data.analysis_history)

        # Count test statuses
        passed_count = sum(1 for tr in session_data.test_results if tr.status.name == "PASSED")
        failed_count = sum(1 for tr in session_data.test_results if tr.status.name == "FAILED")
        error_count = sum(1 for tr in session_data.test_results if tr.status.name == "ERROR")

        stats_text = (
            f"Tests: {test_count} total\n"
            f"  • Passed: {passed_count}\n"
            f"  • Failed: {failed_count}\n"
            f"  • Errors: {error_count}\n"
            f"Bookmarks: {bookmark_count}\n"
            f"Analysis History: {history_count} entries\n"
            f"Workflow State: {session_data.workflow_state}"
        )

        self.stats_label.setText(stats_text)

    def _update_bookmarks_display(self, session_data: SessionData) -> None:
        """Update bookmarks display."""
        self.bookmarks_model.clear()

        for bookmark in session_data.bookmarks:
            item = QStandardItem(f"{bookmark.test_name} ({bookmark.bookmark_type})")
            item.setToolTip(
                f"Type: {bookmark.bookmark_type}\n"
                f"Created: {bookmark.created_at.strftime('%Y-%m-%d %H:%M')}\n"
                f"Description: {bookmark.description or 'No description'}\n"
                f"Notes: {bookmark.notes or 'No notes'}"
            )
            self.bookmarks_model.appendRow(item)

    def _clear_details(self) -> None:
        """Clear session details display."""
        self.selected_session_id = None

        self.session_name_edit.clear()
        self.session_description_edit.clear()
        self.metadata_label.setText("No session selected")
        self.stats_label.setText("No data available")

        self.bookmarks_model.clear()

        # Disable buttons
        self.load_button.setEnabled(False)
        self.delete_session_btn.setEnabled(False)
        self.export_session_btn.setEnabled(False)
        self.apply_button.setEnabled(False)

    @Slot()
    def _on_details_changed(self) -> None:
        """Handle changes to session details."""
        self.apply_button.setEnabled(self.selected_session_id is not None)

    @Slot()
    def _on_apply_changes(self) -> None:
        """Apply changes to session metadata."""
        if not self.selected_session_id:
            return

        # This would require loading the session, updating metadata, and saving
        # For now, we'll just show a message
        QMessageBox.information(
            self,
            "Apply Changes",
            "Session metadata changes would be applied here.\n\n"
            "This feature requires integration with the session manager.",
        )
        self.apply_button.setEnabled(False)

    def accept(self) -> None:
        """Accept dialog and emit selected session."""
        if self.selected_session_id:
            self.session_selected.emit(self.selected_session_id)
        super().accept()


class NewSessionDialog(QDialog):
    """Dialog for creating new sessions."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.session_name: str = ""
        self.session_description: str = ""

        self.setWindowTitle("New Session")
        self.setModal(True)
        self.resize(400, 200)

        self._init_ui()

    def _init_ui(self) -> None:
        """Initialize UI components."""
        layout = QVBoxLayout(self)

        # Session name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Session Name:"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Enter session name...")
        name_layout.addWidget(self.name_edit)
        layout.addLayout(name_layout)

        # Session description
        layout.addWidget(QLabel("Description:"))
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(80)
        self.description_edit.setPlaceholderText("Optional description...")
        layout.addWidget(self.description_edit)

        # Dialog buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        layout.addWidget(self.button_box)

        # Connect signals
        self.name_edit.textChanged.connect(self._update_ok_button)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

    def _update_ok_button(self) -> None:
        """Update OK button state based on input."""
        has_name = bool(self.name_edit.text().strip())
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(has_name)

    def accept(self) -> None:
        """Accept dialog and capture input."""
        self.session_name = self.name_edit.text().strip()
        self.session_description = self.description_edit.toPlainText().strip()
        super().accept()
