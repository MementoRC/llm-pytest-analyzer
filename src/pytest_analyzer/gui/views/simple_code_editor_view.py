import logging
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QTextEdit, QWidget

logger = logging.getLogger(__name__)


class SimpleCodeEditorView(QTextEdit):
    """
    A simple code editor widget using QTextEdit as fallback when QScintilla is not available.
    Provides basic code viewing functionality with monospace font.
    """

    file_loaded = Signal(Path)
    file_saved = Signal(Path)
    content_changed = Signal()
    status_message = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        """
        Initialize the SimpleCodeEditorView.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._current_file_path: Optional[Path] = None
        self._init_editor_config()
        self.textChanged.connect(self._on_text_changed)

    def _init_editor_config(self) -> None:
        """Initialize the editor's configuration."""
        # Font
        font = QFont()
        font.setFamily("monospace")
        font.setFixedPitch(True)
        font.setPointSize(10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)

        # Set to read-only by default until content is loaded
        self.setReadOnly(True)

        # Enable line wrap mode for better readability
        self.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)

    def _on_text_changed(self) -> None:
        """Handles the textChanged signal."""
        if not self.isReadOnly():
            self.content_changed.emit()

    def load_file(self, file_path: Path) -> bool:
        """
        Loads content from the specified file into the editor.

        Args:
            file_path: The Path object of the file to load.

        Returns:
            True if loading was successful, False otherwise.
        """
        try:
            with file_path.open("r", encoding="utf-8") as f:
                content = f.read()
            self.setPlainText(content)
            self._current_file_path = file_path
            self.setReadOnly(False)  # Allow editing after successful load
            self.file_loaded.emit(file_path)
            self.status_message.emit(f"File '{file_path.name}' loaded successfully.")
            logger.info(f"File loaded: {file_path}")
            return True
        except FileNotFoundError:
            self.status_message.emit(f"Error: File not found '{file_path}'.")
            logger.error(f"File not found: {file_path}")
            return False
        except UnicodeDecodeError:
            self.status_message.emit(f"Error: Could not decode file '{file_path}' as UTF-8.")
            logger.error(f"UnicodeDecodeError for file: {file_path}")
            return False
        except Exception as e:
            self.status_message.emit(f"Error loading file '{file_path}': {e}")
            logger.error(f"Error loading file {file_path}: {e}", exc_info=True)
            return False

    def save_file(self, file_path: Optional[Path] = None) -> bool:
        """
        Saves the editor's content to the specified file.
        If file_path is None, uses the current file path.

        Args:
            file_path: Optional Path object for "Save As" functionality.

        Returns:
            True if saving was successful, False otherwise.
        """
        target_path = file_path or self._current_file_path

        if not target_path:
            self.status_message.emit("Error: No file path specified for saving.")
            logger.error("Save attempt with no file path.")
            return False

        if self.isReadOnly():
            self.status_message.emit(
                f"Error: Cannot save, editor is in read-only mode for '{target_path.name}'."
            )
            logger.warning(f"Attempt to save read-only file: {target_path}")
            return False

        try:
            content = self.toPlainText()
            with target_path.open("w", encoding="utf-8") as f:
                f.write(content)

            self._current_file_path = target_path  # Update current path if saved to a new location
            self.file_saved.emit(target_path)
            self.status_message.emit(f"File '{target_path.name}' saved successfully.")
            logger.info(f"File saved: {target_path}")
            return True
        except Exception as e:
            self.status_message.emit(f"Error saving file '{target_path}': {e}")
            logger.error(f"Error saving file {target_path}: {e}", exc_info=True)
            return False

    def get_content(self) -> str:
        """Returns the current text content of the editor."""
        return self.toPlainText()

    def set_content(
        self, text: str, is_editable: bool = False, file_path: Optional[Path] = None
    ) -> None:
        """
        Sets the editor's text content and editable state.

        Args:
            text: The text content to set.
            is_editable: Whether the editor should be editable.
            file_path: Optional Path object to associate with this content.
        """
        self.setPlainText(text)
        self.setReadOnly(not is_editable)
        self._current_file_path = file_path

        path_name = f"'{file_path.name}'" if file_path else "new content"
        self.status_message.emit(f"Content set for {path_name}. Read-only: {not is_editable}")

    def set_editable(self, editable: bool) -> None:
        """Sets the read-only state of the editor."""
        self.setReadOnly(not editable)
        self.status_message.emit(f"Editor read-only state set to: {not editable}")

    def clear_content(self) -> None:
        """Clears all text from the editor and resets its state."""
        self.clear()
        self._current_file_path = None
        self.setReadOnly(True)  # Default to read-only after clear
        self.status_message.emit("Editor content cleared.")

    def has_unsaved_changes(self) -> bool:
        """Checks if the editor has unsaved modifications."""
        # Simple implementation - could be enhanced with modification tracking
        return not self.isReadOnly() and bool(self.toPlainText().strip())

    @property
    def current_file_path(self) -> Optional[Path]:
        """Returns the path of the file currently loaded in the editor, if any."""
        return self._current_file_path
