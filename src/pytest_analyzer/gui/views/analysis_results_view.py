"""
Analysis results view component for the Pytest Analyzer GUI.

This module contains the AnalysisResultsView widget for displaying
LLM analysis results for test failures.
"""

import logging
from html import escape
from typing import Optional

from PyQt6.QtCore import pyqtSignal, pyqtSlot
from PyQt6.QtGui import (  # QDesktopServices imported as per user spec
    QAction,
)
from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QStyle,
    QTextBrowser,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ..models.test_results_model import (
    AnalysisStatus,
    TestResult,
    TestResultsModel,
)

logger = logging.getLogger(__name__)


class AnalysisResultsView(QWidget):
    """
    Widget for displaying LLM analysis results for a selected test failure.
    """

    reanalyze_requested = pyqtSignal(TestResult)

    def __init__(self, model: TestResultsModel, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.results_model = model
        self.current_test: Optional[TestResult] = None

        self._init_ui()
        self._connect_signals()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # Toolbar
        self.toolbar = QToolBar()
        layout.addWidget(self.toolbar)

        self.reanalyze_button = QAction(
            QApplication.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload),
            "Re-analyze",
            self,
        )
        self.reanalyze_button.triggered.connect(self._on_reanalyze_clicked)
        self.toolbar.addAction(self.reanalyze_button)

        self.toolbar.addSeparator()

        self.copy_button = QAction(
            QApplication.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogContentsView),
            "Copy HTML",
            self,
        )
        self.copy_button.triggered.connect(self._on_copy_clicked)
        self.toolbar.addAction(self.copy_button)

        self.clear_button = QAction(
            QApplication.style().standardIcon(QStyle.StandardPixmap.SP_DialogCloseButton),
            "Clear View",
            self,
        )
        self.clear_button.triggered.connect(self.clear_view)  # Directly connect to clear_view
        self.toolbar.addAction(self.clear_button)

        # Status Label
        self.status_label = QLabel("Select a failed test to see analysis.")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        # Content Display
        self.text_browser = QTextBrowser()
        self.text_browser.setOpenExternalLinks(True)  # For any external links if ever needed
        self.text_browser.setReadOnly(True)
        layout.addWidget(self.text_browser, 1)

        self.update_view_for_test(None)  # Initial state

    def _connect_signals(self) -> None:
        # Ensure results_model is not None before connecting
        if self.results_model:
            self.results_model.suggestions_updated.connect(self._on_model_data_updated)
            self.results_model.analysis_status_updated.connect(self._on_model_data_updated)

    @pyqtSlot(str)
    def _on_model_data_updated(self, updated_test_name: str) -> None:
        if self.current_test and self.current_test.name == updated_test_name:
            logger.debug(
                f"AnalysisResultsView: Model data updated for current test '{updated_test_name}', refreshing view."
            )
            # Re-fetch the test result from the model to ensure we have the latest data
            updated_test_object = next(
                (tr for tr in self.results_model.results if tr.name == updated_test_name), None
            )
            self.update_view_for_test(updated_test_object)

    def update_view_for_test(self, test_result: Optional[TestResult]) -> None:
        self.current_test = test_result

        if not self.current_test:
            self.clear_view_content()
            self.status_label.setText("No test selected or test has no failure details.")
            self._update_button_states()
            return

        if not (self.current_test.is_failed or self.current_test.is_error):
            self.clear_view_content()
            self.status_label.setText(
                f"Test '{self.current_test.short_name}' is not a failure/error. No analysis to display."
            )
            self._update_button_states()
            return

        self.status_label.setText(f"Analysis for: {self.current_test.short_name}")
        html_content = self._generate_html_content(self.current_test)
        self.text_browser.setHtml(html_content)
        self._update_button_states()

    def _generate_html_content(self, test_result: TestResult) -> str:
        # Basic CSS
        css = """
        <style>
            body { font-size: 9pt; background-color: #ffffff; color: #000000; } /* Base for light theme */
            h3 { margin-top: 0.5em; margin-bottom: 0.3em; color: #1E1E1E; }
            .suggestion-block { border: 1px solid #cccccc; padding: 10px; margin-bottom: 15px; border-radius: 5px; background-color: #f9f9f9; }
            .suggestion-header { font-weight: bold; margin-bottom: 5px; color: #333333; }
            .confidence-text { font-style: italic; color: #333333; }
            .confidence-bar-container { width: 100px; height: 12px; background-color: #e0e0e0; border-radius: 3px; display: inline-block; vertical-align: middle; margin-left: 8px; overflow: hidden;}
            .confidence-bar { height: 100%; } /* Color set dynamically */
            pre {
                background-color: #282c34; /* Darker background for code */
                color: #abb2bf; /* Light text for dark background */
                border: 1px solid #444851;
                padding: 10px;
                border-radius: 4px;
                overflow-x: auto;
                white-space: pre;
                font-family: Consolas, "Courier New", monospace;
                font-size: 8.5pt;
            }
            details > summary { cursor: pointer; font-weight: bold; color: #007bff; margin-bottom: 5px;}
            details > summary:hover { text-decoration: underline; }
            details[open] > summary { margin-bottom: 8px; }
            .status-message { padding: 10px; border-radius: 5px; margin-bottom:10px; font-weight: bold; }
            .status-analyzing { background-color: #fff3cd; color: #856404; border: 1px solid #ffeeba; }
            .status-no-suggestions { background-color: #e9ecef; color: #495057; border: 1px solid #ced4da; }
            .status-failed { background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
            .status-not-analyzed { background-color: #cce5ff; color: #004085; border: 1px solid #b8daff; }
        </style>
        """
        # TODO: Add dark theme detection and alternative CSS
        # For now, this is a light-theme oriented CSS.
        # A simple way for QTextBrowser to somewhat follow system theme for basic text/background:
        # palette = self.text_browser.palette()
        # body_bg_color = palette.color(palette.Role.Base).name()
        # body_text_color = palette.color(palette.Role.Text).name()
        # css = css.replace("background-color: #ffffff;", f"background-color: {body_bg_color};")
        # css = css.replace("color: #000000;", f"color: {body_text_color};")

        html_parts = [css]
        html_parts.append(f"<h3>{escape(test_result.short_name)}</h3>")

        status = test_result.analysis_status
        suggestions = test_result.suggestions

        if status == AnalysisStatus.NOT_ANALYZED:
            html_parts.append(
                "<div class='status-message status-not-analyzed'>This test has not been analyzed yet. Use the 'Analyze' option or the 'Re-analyze' button.</div>"
            )
        elif status == AnalysisStatus.ANALYSIS_PENDING:
            html_parts.append(
                f"<div class='status-message status-analyzing'>Analyzing {escape(test_result.short_name)}... Please wait.</div>"
            )
        elif status == AnalysisStatus.ANALYSIS_FAILED:
            html_parts.append(
                f"<div class='status-message status-failed'>Analysis failed for {escape(test_result.short_name)}. Check logs for details.</div>"
            )
        elif status == AnalysisStatus.ANALYZED_NO_SUGGESTIONS:
            html_parts.append(
                f"<div class='status-message status-no-suggestions'>Analysis complete. No specific suggestions found for {escape(test_result.short_name)}.</div>"
            )
        elif status == AnalysisStatus.SUGGESTIONS_AVAILABLE:
            if not suggestions:
                html_parts.append(
                    f"<div class='status-message status-no-suggestions'>Analysis complete. No suggestions available for {escape(test_result.short_name)} (status inconsistency).</div>"
                )
            else:
                html_parts.append(
                    f"<p><strong>Analysis Results for {escape(test_result.short_name)}:</strong></p>"
                )
                for i, fix_suggestion in enumerate(suggestions):
                    html_parts.append("<div class='suggestion-block'>")
                    html_parts.append(f"<div class='suggestion-header'>Suggestion {i + 1}:</div>")

                    confidence_percent = int(fix_suggestion.confidence * 100)
                    confidence_color = self._get_confidence_color(fix_suggestion.confidence)
                    html_parts.append(
                        f"<p><span class='confidence-text'>Confidence: {confidence_percent}%</span>"
                    )
                    html_parts.append("<span class='confidence-bar-container'>")
                    html_parts.append(
                        f"<div class='confidence-bar' style='width: {confidence_percent}%; background-color: {confidence_color};'></div>"
                    )
                    html_parts.append("</span></p>")

                    escaped_suggestion = escape(fix_suggestion.suggestion).replace("\n", "<br>")
                    html_parts.append(f"<p>{escaped_suggestion}</p>")

                    if fix_suggestion.explanation:
                        escaped_explanation = escape(fix_suggestion.explanation).replace(
                            "\n", "<br>"
                        )
                        html_parts.append("<details><summary>Explanation</summary>")
                        html_parts.append(f"<p>{escaped_explanation}</p></details>")

                    if fix_suggestion.code_changes:
                        html_parts.append("<details open><summary>Suggested Code Changes</summary>")
                        # Assuming code_changes is Dict[str, str] or str
                        if isinstance(fix_suggestion.code_changes, dict):
                            for file_path, code_diff in fix_suggestion.code_changes.items():
                                html_parts.append(f"<p><em>File: {escape(file_path)}</em></p>")
                                html_parts.append(
                                    f"<pre><code>{escape(str(code_diff))}</code></pre>"
                                )
                        else:  # Treat as single block of text
                            html_parts.append(
                                f"<pre><code>{escape(str(fix_suggestion.code_changes))}</code></pre>"
                            )
                        html_parts.append("</details>")
                    html_parts.append("</div>")  # suggestion-block
        else:
            html_parts.append(
                f"<p>Unknown analysis status: {status.name if status else 'None'}</p>"
            )

        return "".join(html_parts)

    def _get_confidence_color(self, confidence: float) -> str:
        if confidence > 0.8:
            return "#4CAF50"  # Green
        if confidence > 0.5:
            return "#FFC107"  # Amber
        return "#F44336"  # Red

    def _update_button_states(self) -> None:
        can_reanalyze = False
        can_copy_clear = bool(self.text_browser.toPlainText())

        if self.current_test and (self.current_test.is_failed or self.current_test.is_error):
            is_analyzing = self.current_test.analysis_status == AnalysisStatus.ANALYSIS_PENDING
            can_reanalyze = not is_analyzing

        self.reanalyze_button.setEnabled(can_reanalyze)
        self.copy_button.setEnabled(can_copy_clear)
        self.clear_button.setEnabled(can_copy_clear)

    @pyqtSlot()
    def _on_reanalyze_clicked(self) -> None:
        if self.current_test:
            logger.info(f"Re-analyze requested for test: {self.current_test.name}")
            self.reanalyze_requested.emit(self.current_test)
            # Optionally, update status label immediately
            self.status_label.setText(f"Re-analyzing {self.current_test.short_name}...")
            # The model update will eventually refresh the full view.

    @pyqtSlot()
    def _on_copy_clicked(self) -> None:
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(self.text_browser.toHtml())  # Copy as HTML
            logger.info("Analysis HTML content copied to clipboard.")
        else:
            logger.warning("Could not access clipboard for AnalysisResultsView.")

    def clear_view_content(self) -> None:
        self.text_browser.clear()
        self.status_label.setText("Analysis view cleared.")

    def clear_view(self) -> None:
        self.current_test = None
        self.clear_view_content()
        self.status_label.setText("Select a failed test to see analysis.")
        self._update_button_states()
