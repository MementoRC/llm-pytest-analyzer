import logging
from typing import Optional

from PyQt6.QtCore import pyqtSlot
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QSizePolicy,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ...core.models.pytest_failure import FixSuggestion
from ..models.code_change import CodeChangeItem, CodeChangeSet

# from .code_editor_view import CodeEditorView # TODO: Revert to CodeEditorView once QsciScintilla issues are resolved

logger = logging.getLogger(__name__)


class FixSuggestionCodeView(QWidget):
    """
    Widget to display code changes from a FixSuggestion, allowing navigation
    between files and toggling between original and fixed code.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._current_fix_suggestion: Optional[FixSuggestion] = None
        self._code_change_set: Optional[CodeChangeSet] = None
        self._current_code_change_item: Optional[CodeChangeItem] = None
        self._showing_fixed_code: bool = True  # Default to showing fixed code

        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar
        self.toolbar = QToolBar()
        main_layout.addWidget(self.toolbar)

        self.file_selector_label = QLabel("File:")
        self.toolbar.addWidget(self.file_selector_label)
        self.file_selector_combo = QComboBox()
        self.file_selector_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.file_selector_combo.currentIndexChanged.connect(self._on_file_selected)
        self.toolbar.addWidget(self.file_selector_combo)

        self.diff_toggle_button = QCheckBox("Show Fixed Code")
        self.diff_toggle_button.setChecked(self._showing_fixed_code)
        self.diff_toggle_button.toggled.connect(self._on_diff_toggle_changed)
        self.toolbar.addWidget(self.diff_toggle_button)

        # Content Area
        content_layout = QVBoxLayout()
        main_layout.addLayout(content_layout, 1)

        # Suggestion Info Panel
        self.info_groupbox = QGroupBox("Suggestion Details")
        info_layout = QFormLayout(self.info_groupbox)

        self.confidence_label = QLabel()
        self.explanation_text = QTextEdit()
        self.explanation_text.setReadOnly(True)
        self.explanation_text.setFixedHeight(80)  # Initial height

        info_layout.addRow("Confidence:", self.confidence_label)
        info_layout.addRow("Explanation:", self.explanation_text)
        content_layout.addWidget(self.info_groupbox)

        # Code Editor
        # TODO: Revert to CodeEditorView once QsciScintilla issues are resolved
        self.code_editor = QTextEdit()
        self.code_editor.setReadOnly(True)
        font = QFont("monospace")  # Or "Courier", "Consolas", etc.
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.code_editor.setFont(font)
        content_layout.addWidget(self.code_editor, 1)  # Stretch factor for editor

        self.clear()

    def load_fix_suggestion(self, fix_suggestion: Optional[FixSuggestion]) -> None:
        self._current_fix_suggestion = fix_suggestion
        self.file_selector_combo.clear()  # Important to clear before processing

        if not fix_suggestion:
            self.clear()
            return

        self._code_change_set = CodeChangeSet.from_fix_suggestion_changes(
            fix_suggestion.code_changes
        )

        confidence_percent = int(fix_suggestion.confidence * 100)
        self.confidence_label.setText(f"{confidence_percent}%")
        self.explanation_text.setPlainText(fix_suggestion.explanation or "No explanation provided.")

        if self._code_change_set.parsing_error and not self._code_change_set.items:
            # Only show top-level parsing error if there are no items to even attempt to display
            # TODO: Revert to CodeEditorView's set_content method
            self.code_editor.setPlainText(
                f"Error parsing code changes: {self._code_change_set.parsing_error}"
            )
            self._disable_controls_for_error_or_no_code()
            return

        if not self._code_change_set.items:
            if isinstance(self._code_change_set.raw_code_changes, str):
                # TODO: Revert to CodeEditorView's set_content method
                self.code_editor.setPlainText(
                    f"Suggested code snippet (no specific file path):\n\n{self._code_change_set.raw_code_changes}"
                )
            elif (
                self._code_change_set.parsing_error
            ):  # e.g. if input was dict but all items failed to parse
                # TODO: Revert to CodeEditorView's set_content method
                self.code_editor.setPlainText(
                    f"Problem parsing code changes. Details: {self._code_change_set.parsing_error}"
                )
            else:
                # TODO: Revert to CodeEditorView's set_content method
                self.code_editor.setPlainText(
                    "No parsable code changes available for this suggestion."
                )
            self._disable_controls_for_error_or_no_code()
            return

        self.file_selector_label.show()
        self.file_selector_combo.show()

        for i, item in enumerate(self._code_change_set.items):
            display_name = item.file_path.name
            if item.error_message:
                display_name += " (Error)"
            self.file_selector_combo.addItem(display_name, userData=item)

        # self.file_selector_combo.setCurrentIndex(0) should trigger _on_file_selected
        # If only one item and index is already 0, it might not trigger, so ensure load.
        if self.file_selector_combo.count() > 0:
            if self.file_selector_combo.currentIndex() == 0:
                self._on_file_selected(0)  # Manually trigger if current index is already 0
            else:
                self.file_selector_combo.setCurrentIndex(0)
        else:  # Should be caught by "if not self._code_change_set.items:"
            self.clear()

    def _disable_controls_for_error_or_no_code(self):
        self.file_selector_label.hide()
        self.file_selector_combo.hide()
        self.diff_toggle_button.setEnabled(False)
        self.diff_toggle_button.setChecked(True)  # Reset to default

    @pyqtSlot(int)
    def _on_file_selected(self, index: int) -> None:
        if (
            index < 0
            or not self._code_change_set
            or not self._code_change_set.items
            or index >= len(self._code_change_set.items)
        ):
            self._current_code_change_item = None
            # self.code_editor.clear() # Avoid clearing if just switching between valid items
            # self.diff_toggle_button.setEnabled(False)
            if index < 0:  # Only clear if index is truly invalid (e.g. combo is empty)
                # TODO: Revert to CodeEditorView's clear_content method
                self.code_editor.clear()
                self.diff_toggle_button.setEnabled(False)
            return

        self._current_code_change_item = self.file_selector_combo.itemData(index)
        self._load_code_for_current_item()

    @pyqtSlot(bool)
    def _on_diff_toggle_changed(self, checked: bool) -> None:
        self._showing_fixed_code = checked
        self._load_code_for_current_item()

    def _load_code_for_current_item(self) -> None:
        if not self._current_code_change_item:
            # TODO: Revert to CodeEditorView's clear_content method
            self.code_editor.clear()
            self.diff_toggle_button.setEnabled(False)
            return

        item = self._current_code_change_item

        if item.error_message:
            # TODO: Revert to CodeEditorView's set_content method
            self.code_editor.setPlainText(
                f"Error loading this change: {item.error_message}\n\nFile: {item.file_path}"
            )
            self.diff_toggle_button.setEnabled(False)
            self.diff_toggle_button.setChecked(True)  # Reset
            return

        self.diff_toggle_button.setEnabled(item.is_diff_available)

        current_text_for_toggle = (
            "Show Fixed Code" if self._showing_fixed_code else "Show Original Code"
        )
        if not item.is_diff_available:
            self._showing_fixed_code = True  # Force show fixed if no original
            current_text_for_toggle = "Show Fixed Code (Original N/A)"

        self.diff_toggle_button.setText(current_text_for_toggle)
        self.diff_toggle_button.setChecked(self._showing_fixed_code)

        # TODO: Revert to CodeEditorView's set_content method (and handle file_path for syntax highlighting)
        if self._showing_fixed_code or not item.is_diff_available:
            self.code_editor.setPlainText(item.fixed_code)
        else:  # Show original code
            self.code_editor.setPlainText(item.original_code or "")

    def clear(self) -> None:
        self._current_fix_suggestion = None
        self._code_change_set = None
        self._current_code_change_item = None
        self._showing_fixed_code = True

        self.file_selector_combo.blockSignals(True)
        self.file_selector_combo.clear()
        self.file_selector_combo.blockSignals(False)

        self._disable_controls_for_error_or_no_code()

        self.confidence_label.setText("N/A")
        self.explanation_text.clear()
        # TODO: Revert to CodeEditorView's clear_content and set_content methods
        self.code_editor.clear()
        self.code_editor.setPlainText("Select a suggestion with code changes to view details.")

        self.diff_toggle_button.setText("Show Fixed Code")  # Reset text
