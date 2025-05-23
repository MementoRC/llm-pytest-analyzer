import logging
from pathlib import Path
from typing import Optional

from PyQt6.Qsci import QsciLexerPython, QsciScintilla
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import QWidget

logger = logging.getLogger(__name__)


class CodeEditorView(QsciScintilla):
    """
    A code editor widget using QScintilla for displaying and editing code,
    primarily Python code.
    """

    file_loaded = pyqtSignal(Path)
    file_saved = pyqtSignal(Path)
    content_changed = pyqtSignal()
    status_message = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        """
        Initialize the CodeEditorView.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._current_file_path: Optional[Path] = None
        self._init_editor_config()
        self.textChanged.connect(self._on_text_changed)
        # Ensure modification status is handled correctly for undo/redo history
        self.modificationChanged.connect(self._on_modification_changed)

    def _init_editor_config(self) -> None:
        """Initialize the QScintilla editor's configuration."""
        # Font
        font = QFont()
        font.setFamily("Monospace")  # Common monospaced font family
        font.setFixedPitch(True)
        font.setPointSize(10)  # A common default size
        self.setFont(font)  # Set font for the editor content area

        # Python Lexer for syntax highlighting
        self._lexer = QsciLexerPython(self)
        self._lexer.setDefaultFont(font)  # Ensure lexer uses the same font
        # Use default lexer colors by not setting them individually.
        # self._lexer.setPaper(QColor("#ffffff")) # Optionally set background
        # self._lexer.setDefaultPaper(QColor("#ffffff")) # Optionally set default background

        self.setLexer(self._lexer)

        # Line Numbers Margin
        self.setMarginsFont(font)  # Font for margin text
        font_metrics = self.fontMetrics()
        # Calculate width needed for up to 5 digits + a little padding
        self.setMarginWidth(0, font_metrics.horizontalAdvance("00000") + 6)
        self.setMarginLineNumbers(0, True)
        self.setMarginsBackgroundColor(QColor("#f0f0f0"))  # Light gray for margins background
        self.setMarginsForegroundColor(QColor("#808080"))  # Gray for line numbers

        # Code Folding Margin (Margin 1)
        self.setFolding(QsciScintilla.FoldStyle.CircledTreeFoldStyle, 1)
        self.setMarginWidth(1, 14)  # Width for folding margin
        self.setMarginSensitivity(1, True)  # Enable clicking on folding margin

        # Define markers for code folding
        self.markerDefine(QsciScintilla.MarkerSymbol.Circle, QsciScintilla.SC_MARKNUM_FOLDEROPEN)
        self.markerDefine(QsciScintilla.MarkerSymbol.CircledPlus, QsciScintilla.SC_MARKNUM_FOLDER)
        self.markerDefine(
            QsciScintilla.MarkerSymbol.CircledMinus, QsciScintilla.SC_MARKNUM_FOLDEROPENMID
        )
        self.markerDefine(QsciScintilla.MarkerSymbol.BoxedPlus, QsciScintilla.SC_MARKNUM_FOLDEREND)
        self.markerDefine(
            QsciScintilla.MarkerSymbol.BoxedMinus, QsciScintilla.SC_MARKNUM_FOLDERMIDTAIL
        )
        self.markerDefine(QsciScintilla.MarkerSymbol.Empty, QsciScintilla.SC_MARKNUM_FOLDERTAIL)
        # Set colors for fold margin itself
        self.setFoldMarginColors(QColor("#f0f0f0"), QColor("#e0e0e0"))

        # Brace Matching
        self.setBraceMatching(QsciScintilla.BraceMatch.SloppyBraceMatch)
        self.setMatchedBraceBackgroundColor(QColor("#b0e0b0"))  # Light green for matched braces
        self.setUnmatchedBraceForegroundColor(QColor("#ff0000"))  # Red for unmatched braces

        # Auto Indentation
        self.setAutoIndent(True)

        # Caret Line Visibility and Styling
        self.setCaretLineVisible(True)
        self.setCaretLineBackgroundColor(QColor("#e8f0e8"))  # Very light green/gray

        # Encoding (UTF-8 by default)
        self.setUtf8(True)

        # Tabs and Indentation Settings
        self.setIndentationsUseTabs(False)  # Use spaces instead of tabs
        self.setTabWidth(4)  # Standard 4 spaces for a tab
        self.setIndentationGuides(True)  # Show indentation guides
        self.setTabIndents(True)  # Tab key indents

        # Auto-completion (basic, can be configured further)
        self.setAutoCompletionSource(QsciScintilla.AutoCompletionSource.AcsAll)
        self.setAutoCompletionCaseSensitivity(False)  # Usually false for convenience
        self.setAutoCompletionThreshold(1)  # Show completion after 1 char

        # Wrap Mode (default to no wrapping)
        self.setWrapMode(QsciScintilla.WrapMode.WrapNone)

        # Set to read-only by default until content is loaded or explicitly made editable
        self.setReadOnly(True)

    def _on_text_changed(self) -> None:
        """Handles the QScintilla textChanged signal."""
        # This signal is emitted for any text change.
        # The content_changed signal is more about user-driven changes to unsaved content.
        # QScintilla's `modificationChanged` is better for tracking "modified" state.
        pass

    def _on_modification_changed(self, modified: bool) -> None:
        """Handles the QScintilla modificationChanged signal."""
        if modified and not self.isReadOnly():
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
            self.setText(content)
            self._current_file_path = file_path
            self.setReadOnly(False)  # Allow editing after successful load
            self.setModified(False)  # Mark as unmodified initially
            self.SendScintilla(
                QsciScintilla.SCI_SETSAVEPOINT
            )  # Mark current state as save point for undo history
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
            content = self.text()
            with target_path.open("w", encoding="utf-8") as f:
                f.write(content)

            self._current_file_path = target_path  # Update current path if saved to a new location
            self.setModified(False)  # Mark as unmodified after save
            self.SendScintilla(QsciScintilla.SCI_SETSAVEPOINT)
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
        return self.text()

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
        self.setText(text)
        self.setReadOnly(not is_editable)
        self.setModified(False)  # New content is initially unmodified
        self.SendScintilla(QsciScintilla.SCI_SETSAVEPOINT)
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
        self.setModified(False)
        self.SendScintilla(QsciScintilla.SCI_SETSAVEPOINT)
        self.status_message.emit("Editor content cleared.")

    def has_unsaved_changes(self) -> bool:
        """Checks if the editor has unsaved modifications."""
        return self.isModified()

    @property
    def current_file_path(self) -> Optional[Path]:
        """Returns the path of the file currently loaded in the editor, if any."""
        return self._current_file_path

    # Basic Search/Replace functionality (can be expanded with dialogs by a controller)
    def find_first(
        self,
        text: str,
        regex: bool,
        case_sensitive: bool,
        whole_word: bool,
        wrap: bool,
        forward: bool = True,
        line: int = -1,
        index: int = -1,
        show: bool = True,
    ) -> bool:
        """Finds the first occurrence of text."""
        return super().findFirst(
            text, regex, case_sensitive, whole_word, wrap, forward, line, index, show
        )

    def find_next(self) -> bool:
        """Finds the next occurrence based on previous findFirst parameters."""
        return super().findNext()

    def find_previous(self) -> bool:
        """Finds the previous occurrence. Note: Relies on findFirst being called with forward=False or managing search parameters externally."""
        # QScintilla's findNext/findPrevious behavior depends on the last findFirst call.
        # For a true "Find Previous" button, it's often better to call findFirst with forward=False.
        # This method is a simple wrapper.
        return super().findPrevious()

    def replace_selected_text(self, replace_text_str: str) -> None:
        """Replaces the currently selected text."""
        if self.hasSelectedText() and not self.isReadOnly():
            super().replaceSelectedText(replace_text_str)
        elif self.isReadOnly():
            self.status_message.emit("Cannot replace text: Editor is read-only.")
        elif not self.hasSelectedText():
            self.status_message.emit("Cannot replace text: No text selected.")

    def replace_all(
        self,
        find_text: str,
        replace_text_str: str,
        regex: bool,
        case_sensitive: bool,
        whole_word: bool,
    ) -> int:
        """
        Replaces all occurrences of text.

        Args:
            find_text: The text to find.
            replace_text_str: The text to replace with.
            regex: Whether find_text is a regular expression.
            case_sensitive: Whether the search is case-sensitive.
            whole_word: Whether to match whole words only.

        Returns:
            The number of replacements made.
        """
        if self.isReadOnly():
            self.status_message.emit("Cannot replace text: Editor is read-only.")
            return 0

        self.beginUndoAction()  # Group all replacements into a single undo action
        count = 0
        line, index = 0, 0
        while True:
            found = self.findFirst(
                find_text, regex, case_sensitive, whole_word, False, True, line, index
            )  # wrap=False
            if found:
                self.replaceSelectedText(replace_text_str)
                # After replacement, get new line and index to continue search from this point
                line, index = self.getCursorPosition()
                count += 1
            else:
                break
        self.endUndoAction()

        if count > 0:
            self.status_message.emit(f"Replaced {count} occurrence(s) of '{find_text}'.")
        else:
            self.status_message.emit(f"No occurrences of '{find_text}' found.")
        return count

    # Undo/Redo are available as self.undo() and self.redo()
    # Standard shortcuts (Ctrl+Z, Ctrl+Y / Cmd+Z, Cmd+Shift+Z) usually work out of the box.
