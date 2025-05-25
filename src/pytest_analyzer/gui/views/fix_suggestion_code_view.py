import difflib
import html
import logging
from typing import Optional

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
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
    between files, toggling between original and fixed code, and a side-by-side diff view.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._current_fix_suggestion: Optional[FixSuggestion] = None
        self._code_change_set: Optional[CodeChangeSet] = None
        self._current_code_change_item: Optional[CodeChangeItem] = None

        # Single view state
        self._showing_fixed_code: bool = True

        # Diff view state
        self._diff_view_mode_active: bool = False
        self._original_scroll_handler_active: bool = True
        self._fixed_scroll_handler_active: bool = True

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

        # View Mode Toggle Action (replaces/enhances diff_toggle_button logic)
        self._view_mode_action = QAction("Show Diff View", self)
        self._view_mode_action.triggered.connect(self._toggle_view_mode)
        self.toolbar.addAction(self._view_mode_action)

        # This checkbox is now specific to the single view mode
        self.single_view_diff_toggle_button = QCheckBox("Show Fixed Code")
        self.single_view_diff_toggle_button.setChecked(self._showing_fixed_code)
        self.single_view_diff_toggle_button.toggled.connect(self._on_diff_toggle_changed)
        self.toolbar.addWidget(self.single_view_diff_toggle_button)
        self._update_view_mode_action_state()  # Set initial text/tooltip

        # Content Area using QStackedWidget
        self._stacked_widget = QStackedWidget()
        # main_layout.addWidget(self._stacked_widget, 1) # Will be added after info_groupbox

        # Suggestion Info Panel (common to both views, so placed outside stack or duplicated)
        self.info_groupbox = QGroupBox("Suggestion Details")
        info_layout = QFormLayout(self.info_groupbox)

        self.confidence_label = QLabel()
        self.explanation_text = QTextEdit()
        self.explanation_text.setReadOnly(True)
        self.explanation_text.setFixedHeight(80)

        info_layout.addRow("Confidence:", self.confidence_label)
        info_layout.addRow("Explanation:", self.explanation_text)
        main_layout.addWidget(self.info_groupbox)  # Add info groupbox first
        main_layout.addWidget(
            self._stacked_widget, 1
        )  # Then add stacked widget, taking remaining space

        self._init_single_view_ui()
        self._init_diff_view_ui()

        self._stacked_widget.addWidget(self._single_view_widget)
        self._stacked_widget.addWidget(self._diff_view_widget)

        self.clear()

    def _init_single_view_ui(self) -> None:
        self._single_view_widget = QWidget()
        single_view_layout = QVBoxLayout(self._single_view_widget)
        single_view_layout.setContentsMargins(0, 0, 0, 0)

        self.code_editor = QTextEdit()
        self.code_editor.setReadOnly(True)
        font = QFont("monospace")
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.code_editor.setFont(font)
        single_view_layout.addWidget(self.code_editor, 1)

    def _init_diff_view_ui(self) -> None:
        self._diff_view_widget = QWidget()
        diff_view_layout = QVBoxLayout(self._diff_view_widget)
        diff_view_layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        monospace_font = QFont("monospace")
        monospace_font.setStyleHint(QFont.StyleHint.Monospace)

        # Original Code Pane
        original_pane_widget = QWidget()
        original_pane_layout = QVBoxLayout(original_pane_widget)
        original_pane_layout.setContentsMargins(0, 0, 0, 0)
        original_pane_layout.addWidget(QLabel("Original Code:"))
        self._original_code_editor_diff = QTextEdit()
        self._original_code_editor_diff.setReadOnly(True)
        self._original_code_editor_diff.setFont(monospace_font)
        self._original_code_editor_diff.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        original_pane_layout.addWidget(self._original_code_editor_diff)
        splitter.addWidget(original_pane_widget)

        # Fixed Code Pane
        fixed_pane_widget = QWidget()
        fixed_pane_layout = QVBoxLayout(fixed_pane_widget)
        fixed_pane_layout.setContentsMargins(0, 0, 0, 0)
        fixed_pane_layout.addWidget(QLabel("Fixed Code:"))
        self._fixed_code_editor_diff = QTextEdit()
        self._fixed_code_editor_diff.setReadOnly(True)
        self._fixed_code_editor_diff.setFont(monospace_font)
        self._fixed_code_editor_diff.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        fixed_pane_layout.addWidget(self._fixed_code_editor_diff)
        splitter.addWidget(fixed_pane_widget)

        splitter.setSizes(
            [
                self.width() // 2 if self.width() > 0 else 200,
                self.width() // 2 if self.width() > 0 else 200,
            ]
        )  # Initial equal split
        diff_view_layout.addWidget(splitter)

        # Connect scrollbars
        self._original_code_editor_diff.verticalScrollBar().valueChanged.connect(
            self._on_original_scroll_changed
        )
        self._fixed_code_editor_diff.verticalScrollBar().valueChanged.connect(
            self._on_fixed_scroll_changed
        )

    def _update_view_mode_action_state(self) -> None:
        if self._diff_view_mode_active:
            self._view_mode_action.setText("Show Single View")
            self._view_mode_action.setToolTip("Switch to a single code panel view")
            self.single_view_diff_toggle_button.hide()
        else:
            self._view_mode_action.setText("Show Diff View")
            self._view_mode_action.setToolTip("Switch to a side-by-side diff view")
            self.single_view_diff_toggle_button.show()

        # Ensure the checkbox state reflects the single view's internal state
        self.single_view_diff_toggle_button.setChecked(self._showing_fixed_code)

    @Slot()
    def _toggle_view_mode(self) -> None:
        self._diff_view_mode_active = not self._diff_view_mode_active
        if self._diff_view_mode_active:
            self._stacked_widget.setCurrentWidget(self._diff_view_widget)
        else:
            self._stacked_widget.setCurrentWidget(self._single_view_widget)
        self._update_view_mode_action_state()
        self._load_code_for_current_item()  # Reload content in the new view

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

        self._view_mode_action.setEnabled(False)  # Disable by default, enable if items allow

        if self._code_change_set.parsing_error and not self._code_change_set.items:
            error_message = f"Error parsing code changes: {self._code_change_set.parsing_error}"
            self.code_editor.setPlainText(error_message)
            self._original_code_editor_diff.setPlainText(error_message)
            self._fixed_code_editor_diff.setPlainText(error_message)
            self._disable_controls_for_error_or_no_code()
            return

        if not self._code_change_set.items:
            no_code_message = "No parsable code changes available for this suggestion."
            if isinstance(self._code_change_set.raw_code_changes, str):
                no_code_message = f"Suggested code snippet (no specific file path):\n\n{self._code_change_set.raw_code_changes}"
            elif self._code_change_set.parsing_error:
                no_code_message = (
                    f"Problem parsing code changes. Details: {self._code_change_set.parsing_error}"
                )

            self.code_editor.setPlainText(no_code_message)
            self._original_code_editor_diff.setPlainText(no_code_message)
            self._fixed_code_editor_diff.setPlainText(no_code_message)
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
            # setCurrentIndex will trigger _on_file_selected if index changes
            # or if it's already 0, _on_file_selected needs to be called manually.
            current_idx = self.file_selector_combo.currentIndex()
            if (
                current_idx == 0
            ):  # and self.file_selector_combo.count() == 1: # Simpler: always call if index is 0
                self._on_file_selected(0)  # Manually trigger if current index is already 0
            else:
                self.file_selector_combo.setCurrentIndex(0)
        else:  # Should be caught by "if not self._code_change_set.items:"
            self.clear()

    def _disable_controls_for_error_or_no_code(self):
        self.file_selector_label.hide()
        self.file_selector_combo.hide()
        self.single_view_diff_toggle_button.setEnabled(False)
        self.single_view_diff_toggle_button.setChecked(True)
        self._view_mode_action.setEnabled(False)
        if self._diff_view_mode_active:  # Switch back to single view if in diff mode
            self._diff_view_mode_active = False
            self._stacked_widget.setCurrentWidget(self._single_view_widget)
            self._update_view_mode_action_state()

    @Slot(int)
    def _on_file_selected(self, index: int) -> None:
        if (
            index < 0
            or not self._code_change_set
            or not self._code_change_set.items
            or index >= len(self._code_change_set.items)
        ):
            self._current_code_change_item = None
            # self.code_editor.clear() # Avoid clearing if just switching between valid items
            # self.single_view_diff_toggle_button.setEnabled(False)
            if index < 0:  # Combo is empty or selection cleared
                self.code_editor.clear()
                self._original_code_editor_diff.clear()
                self._fixed_code_editor_diff.clear()
                self.single_view_diff_toggle_button.setEnabled(False)
                self._view_mode_action.setEnabled(False)
            return

        self._current_code_change_item = self.file_selector_combo.itemData(index)
        self._load_code_for_current_item()

    @Slot(bool)
    def _on_diff_toggle_changed(self, checked: bool) -> None:
        # This is for the single_view_diff_toggle_button (checkbox)
        self._showing_fixed_code = checked
        if not self._diff_view_mode_active:  # Only reload if in single view mode
            self._load_code_for_current_item()

    def _load_code_for_current_item(self) -> None:
        if not self._current_code_change_item:
            self.code_editor.clear()
            self._original_code_editor_diff.clear()
            self._fixed_code_editor_diff.clear()
            self.single_view_diff_toggle_button.setEnabled(False)
            self._view_mode_action.setEnabled(False)
            return

        item = self._current_code_change_item
        can_diff = item.is_diff_available and item.original_code is not None
        self._view_mode_action.setEnabled(can_diff)  # Enable/disable diff view action

        if item.error_message:
            error_msg = f"Error loading this change: {item.error_message}\n\nFile: {item.file_path}"
            self.code_editor.setPlainText(error_msg)
            self._original_code_editor_diff.setPlainText(error_msg)
            self._fixed_code_editor_diff.setPlainText(error_msg)
            self.single_view_diff_toggle_button.setEnabled(False)
            self.single_view_diff_toggle_button.setChecked(True)  # Reset
            # If in diff mode but this item has an error, view mode action might be disabled
            # or user can manually switch back. If can_diff is false, it's already disabled.
            # _update_view_mode_action_state() will be called below if not erroring.
            return

        self._update_view_mode_action_state()  # Ensure button text and checkbox visibility are correct

        if self._diff_view_mode_active:
            if can_diff:
                self._display_diff(item.original_code, item.fixed_code)
            else:
                # Diff mode selected, but this item can't be diffed.
                # This case should ideally be prevented by disabling the diff view action if !can_diff
                self._original_code_editor_diff.setPlainText(
                    "Original code not available for diff or diff view not applicable."
                )
                self._fixed_code_editor_diff.setPlainText(item.fixed_code)
        else:  # Single view mode
            self.single_view_diff_toggle_button.setEnabled(item.is_diff_available)

            current_text_for_toggle = (
                "Show Fixed Code" if self._showing_fixed_code else "Show Original Code"
            )
            if not item.is_diff_available:
                self._showing_fixed_code = True  # Force show fixed if no original
                current_text_for_toggle = "Show Fixed Code (Original N/A)"

            self.single_view_diff_toggle_button.setText(current_text_for_toggle)
            self.single_view_diff_toggle_button.setChecked(self._showing_fixed_code)

            if self._showing_fixed_code or not item.is_diff_available:
                self.code_editor.setPlainText(item.fixed_code)
            else:
                self.code_editor.setPlainText(item.original_code or "")

    def _display_diff(self, original_code: str, fixed_code: str):
        original_lines = original_code.splitlines()
        fixed_lines = fixed_code.splitlines()
        # Use autojunk=False to prevent difflib from treating common lines as junk,
        # which can be useful for code diffs where structure might be similar.
        matcher = difflib.SequenceMatcher(None, original_lines, fixed_lines, autojunk=False)

        original_html_lines = []
        fixed_html_lines = []

        # Basic styling for pre tags to ensure consistent line height and monospace font
        pre_style = (
            "white-space: pre; margin: 0; padding: 0; font-family: monospace; font-size: 9pt;"
        )
        # Calculate width for line numbers
        max_total_lines = max(len(original_lines), len(fixed_lines))
        line_num_width = len(str(max_total_lines)) if max_total_lines > 0 else 1

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "replace":
                num_orig_lines_in_op = i2 - i1
                num_fixed_lines_in_op = j2 - j1
                max_sub_lines = max(num_orig_lines_in_op, num_fixed_lines_in_op)

                for k in range(max_sub_lines):
                    # Original side
                    if k < num_orig_lines_in_op:
                        line_num_str = str(i1 + k + 1).rjust(line_num_width)
                        line_text = html.escape(original_lines[i1 + k])
                        original_html_lines.append(
                            f"<div style='background-color:#ffe8e8;'><pre style='{pre_style}'>{line_num_str} {line_text}</pre></div>"
                        )  # Light red
                    else:  # Pad fixed side (if original had fewer lines in this replace op)
                        original_html_lines.append(
                            f"<div style='background-color:#ffe8e8;'><pre style='{pre_style}'>{' '.rjust(line_num_width)} </pre></div>"
                        )

                    # Fixed side
                    if k < num_fixed_lines_in_op:
                        line_num_str = str(j1 + k + 1).rjust(line_num_width)
                        line_text = html.escape(fixed_lines[j1 + k])
                        fixed_html_lines.append(
                            f"<div style='background-color:#e8ffe8;'><pre style='{pre_style}'>{line_num_str} {line_text}</pre></div>"
                        )  # Light green
                    else:  # Pad original side (if fixed had fewer lines in this replace op)
                        fixed_html_lines.append(
                            f"<div style='background-color:#e8ffe8;'><pre style='{pre_style}'>{' '.rjust(line_num_width)} </pre></div>"
                        )

            elif tag == "delete":
                for k_orig in range(i1, i2):
                    line_num_str = str(k_orig + 1).rjust(line_num_width)
                    line_text = html.escape(original_lines[k_orig])
                    original_html_lines.append(
                        f"<div style='background-color:#ffdddd;'><pre style='{pre_style}'>{line_num_str} {line_text}</pre></div>"
                    )  # Reddish
                    fixed_html_lines.append(
                        f"<div style='background-color:#ffdddd;'><pre style='{pre_style}'>{' '.rjust(line_num_width)} </pre></div>"
                    )  # Placeholder on fixed side

            elif tag == "insert":
                for k_fixed in range(j1, j2):
                    original_html_lines.append(
                        f"<div style='background-color:#ddffdd;'><pre style='{pre_style}'>{' '.rjust(line_num_width)} </pre></div>"
                    )  # Placeholder on original side
                    line_num_str = str(k_fixed + 1).rjust(line_num_width)
                    line_text = html.escape(fixed_lines[k_fixed])
                    fixed_html_lines.append(
                        f"<div style='background-color:#ddffdd;'><pre style='{pre_style}'>{line_num_str} {line_text}</pre></div>"
                    )  # Greenish

            elif tag == "equal":
                for k_orig, k_fixed in zip(range(i1, i2), range(j1, j2)):
                    orig_line_num_str = str(k_orig + 1).rjust(line_num_width)
                    orig_line_text = html.escape(original_lines[k_orig])
                    original_html_lines.append(
                        f"<div><pre style='{pre_style}'>{orig_line_num_str} {orig_line_text}</pre></div>"
                    )

                    fixed_line_num_str = str(k_fixed + 1).rjust(line_num_width)
                    fixed_line_text = html.escape(fixed_lines[k_fixed])
                    fixed_html_lines.append(
                        f"<div><pre style='{pre_style}'>{fixed_line_num_str} {fixed_line_text}</pre></div>"
                    )

        # Temporarily disable scroll handlers to prevent feedback loop during setHtml
        self._original_scroll_handler_active = False
        self._fixed_scroll_handler_active = False

        self._original_code_editor_diff.setHtml("".join(original_html_lines))
        self._fixed_code_editor_diff.setHtml("".join(fixed_html_lines))

        # Re-enable scroll handlers
        self._original_scroll_handler_active = True
        self._fixed_scroll_handler_active = True

    @Slot(int)
    def _on_original_scroll_changed(self, value: int):
        if not self._original_scroll_handler_active or not self._diff_view_mode_active:
            return
        self._fixed_scroll_handler_active = False
        self._fixed_code_editor_diff.verticalScrollBar().setValue(value)
        self._fixed_scroll_handler_active = True

    @Slot(int)
    def _on_fixed_scroll_changed(self, value: int):
        if not self._fixed_scroll_handler_active or not self._diff_view_mode_active:
            return
        self._original_scroll_handler_active = False
        self._original_code_editor_diff.verticalScrollBar().setValue(value)
        self._original_scroll_handler_active = True

    def clear(self) -> None:
        self._current_fix_suggestion = None
        self._code_change_set = None
        self._current_code_change_item = None

        self._showing_fixed_code = True  # Reset single view toggle state
        # self._diff_view_mode_active = False # Reset by _disable_controls or explicitly later

        self.file_selector_combo.blockSignals(True)
        self.file_selector_combo.clear()
        self.file_selector_combo.blockSignals(False)

        self._disable_controls_for_error_or_no_code()  # This will also handle view mode action

        self.confidence_label.setText("N/A")
        self.explanation_text.clear()

        self.code_editor.clear()
        self._original_code_editor_diff.clear()
        self._fixed_code_editor_diff.clear()

        # Set placeholder text
        placeholder_text = "Select a suggestion with code changes to view details."
        self.code_editor.setPlainText(placeholder_text)
        self._original_code_editor_diff.setPlainText(placeholder_text)
        self._fixed_code_editor_diff.setPlainText(placeholder_text)

        # Reset single view checkbox text and state
        self.single_view_diff_toggle_button.setText("Show Fixed Code")
        self.single_view_diff_toggle_button.setChecked(self._showing_fixed_code)

        # Ensure stack is on single view and view mode action is updated
        if self._stacked_widget.currentWidget() != self._single_view_widget:
            self._stacked_widget.setCurrentWidget(self._single_view_widget)
        self._diff_view_mode_active = (
            False  # Explicitly set after potential changes in _disable_controls
        )
        self._update_view_mode_action_state()
