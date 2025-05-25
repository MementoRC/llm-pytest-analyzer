import logging
import re
from typing import List, Optional

from PySide6.QtGui import (
    QAction,
    QColor,
    QFont,
    QGuiApplication,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QLabel,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


# Basic Python Traceback Highlighter (can be expanded)
class PythonTracebackHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        # logger.debug("PythonTracebackHighlighter: Initializing.") # Can be noisy if many documents
        self.highlighting_rules = []

        # Rule for "File /path/to/file.py, line 123, in func_name"
        file_line_format = QTextCharFormat()
        file_line_format.setForeground(QColor("#0000FF"))  # Blue
        self.highlighting_rules.append((r"^\s*File \"([^\"]+)\", line \d+", file_line_format))

        # Rule for lines starting with common error types
        error_format = QTextCharFormat()
        error_format.setForeground(QColor("#FF0000"))  # Red
        error_format.setFontWeight(QFont.Weight.Bold)
        self.highlighting_rules.append((r"^\s*\w*Error:", error_format))
        self.highlighting_rules.append((r"^\s*\w*Exception:", error_format))
        self.highlighting_rules.append((r"^\s*raise\s+\w+", error_format))

        # Rule for "Traceback (most recent call last):"
        traceback_format = QTextCharFormat()
        traceback_format.setForeground(QColor("#FF00FF"))  # Magenta
        traceback_format.setFontWeight(QFont.Weight.Bold)
        self.highlighting_rules.append((r"^Traceback \(most recent call last\):", traceback_format))

        # Rule for indented lines (potential code snippets in tracebacks)
        indented_code_format = QTextCharFormat()
        indented_code_format.setForeground(QColor("#555555"))  # Dark Gray
        # Matches lines starting with at least one space
        self.highlighting_rules.append((r"^\s+.+", indented_code_format))

    def highlightBlock(self, text: str) -> None:
        # This logs for every block, can be very verbose.
        # logger.debug(f"PythonTracebackHighlighter: Highlighting block starting with: '{text[:30]}...'")
        for pattern, style_format in self.highlighting_rules:
            # Use re.finditer to find all occurrences of the pattern in the block
            for match in re.finditer(pattern, text):
                start, end = match.span()
                self.setFormat(start, end - start, style_format)


class TestOutputView(QWidget):
    """
    Widget for displaying live test execution output.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        logger.debug("TestOutputView: Initializing.")
        self._autoscroll = True
        self._raw_lines: List[str] = []
        self._init_ui()
        self._highlighter = PythonTracebackHighlighter(self.output_edit.document())
        logger.debug("TestOutputView: Initialization complete.")

    def _init_ui(self) -> None:
        logger.debug("TestOutputView: Initializing UI.")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # Toolbar
        self.toolbar = QToolBar()
        layout.addWidget(self.toolbar)

        self.autoscroll_checkbox = QCheckBox("Autoscroll")
        self.autoscroll_checkbox.setChecked(self._autoscroll)
        self.autoscroll_checkbox.toggled.connect(self._on_autoscroll_toggled)
        self.toolbar.addWidget(self.autoscroll_checkbox)

        self.toolbar.addSeparator()

        self.clear_action = QAction("Clear", self)
        self.clear_action.triggered.connect(self.clear_output)
        self.toolbar.addAction(self.clear_action)

        self.copy_action = QAction("Copy", self)
        self.copy_action.triggered.connect(self.copy_output)
        self.toolbar.addAction(self.copy_action)

        self.toolbar.addSeparator()

        self.toolbar.addWidget(QLabel("Filter:"))
        self.filter_combo = QComboBox()
        self.filter_combo.addItem("All Output")
        self.filter_combo.addItem("Errors Only")
        self.filter_combo.setEnabled(True)
        self.filter_combo.currentIndexChanged.connect(self._on_filter_changed)
        self.toolbar.addWidget(self.filter_combo)

        # Output Text Edit
        self.output_edit = QTextEdit()
        self.output_edit.setReadOnly(True)
        font = QFont("Monospace")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(10)  # Adjust as needed
        self.output_edit.setFont(font)
        self.output_edit.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self.output_edit, 1)
        logger.debug("TestOutputView: UI initialized.")

    def _is_error_line(self, text: str) -> bool:
        """Checks if a line is considered an error line for filtering."""
        # Patterns that indicate an error or part of a traceback
        error_patterns = [
            r"^\s*File \"[^\"]+\", line \d+",  # File path in traceback
            r"^\s*\w*Error:",  # Error messages (e.g., AssertionError:)
            r"^\s*\w*Exception:",  # Exception messages
            r"^\s*raise\s+\w+",  # Raise statements
            r"^Traceback \(most recent call last\):",  # Traceback header
        ]
        return any(re.search(pattern, text) for pattern in error_patterns)

    def append_output(self, text: str) -> None:
        """Appends text to the output view.
        This method should be called from the GUI thread.
        Assumes `text` is a single line (ends with newline or is last line).
        """
        logger.debug(f"TestOutputView: Appending output (first 30 chars): '{text[:30].strip()}'")
        self._raw_lines.append(text)

        current_filter_index = self.filter_combo.currentIndex()
        should_append = False
        if current_filter_index == 0:  # All Output
            should_append = True
        elif current_filter_index == 1:  # Errors Only
            if self._is_error_line(text):
                should_append = True

        if should_append:
            current_scrollbar = self.output_edit.verticalScrollBar()
            at_bottom = (
                not current_scrollbar.isVisible()
                or current_scrollbar.value() == current_scrollbar.maximum()
                or current_scrollbar.maximum() == 0
            )

            self.output_edit.moveCursor(QTextCursor.MoveOperation.End)
            self.output_edit.insertPlainText(text)

            if self._autoscroll and at_bottom:  # at_bottom defined in original code
                # logger.debug("TestOutputView: Autoscrolling to ensure cursor visible.") # Can be noisy
                self.output_edit.ensureCursorVisible()

    def _on_filter_changed(self, index: int) -> None:
        """Handles changes in the filter selection."""
        filter_text = self.filter_combo.itemText(index)
        logger.debug(f"TestOutputView: Filter changed. Index: {index}, Text: '{filter_text}'.")
        self.output_edit.clear()

        # Try to preserve scroll position if not autoscrolling
        # This is tricky because content length changes. For simplicity,
        # if autoscroll is on, we just scroll to end. If off, user can manually scroll.
        # A more sophisticated approach would map old scroll position to new.

        for line in self._raw_lines:
            should_append = False
            if index == 0:  # All Output
                should_append = True
            elif index == 1:  # Errors Only
                if self._is_error_line(line):
                    should_append = True

            if should_append:
                # No need to move cursor if appending sequentially after clear
                self.output_edit.insertPlainText(line)

        if self._autoscroll:
            logger.debug("TestOutputView: Autoscrolling after filter change.")
            self.output_edit.ensureCursorVisible()
        logger.debug("TestOutputView: Output re-filtered and displayed.")

    def clear_output(self) -> None:
        logger.debug("TestOutputView: Clearing output.")
        self.output_edit.clear()
        self._raw_lines.clear()
        logger.debug("TestOutputView: Output cleared.")

    def copy_output(self) -> None:
        logger.debug("TestOutputView: Copying output to clipboard.")
        clipboard = QGuiApplication.clipboard()
        if clipboard:
            clipboard.setText(self.output_edit.toPlainText())
            logger.debug("TestOutputView: Output copied.")
        else:
            logger.warning("Could not access clipboard for TestOutputView.")

    def _on_autoscroll_toggled(self, checked: bool) -> None:
        logger.debug(f"TestOutputView: Autoscroll toggled. New state: {checked}.")
        self._autoscroll = checked
        if checked:
            logger.debug("TestOutputView: Autoscroll enabled, ensuring cursor visible.")
            self.output_edit.ensureCursorVisible()
