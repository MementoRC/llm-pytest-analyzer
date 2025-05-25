"""
Analysis results view component for the Pytest Analyzer GUI.

This module contains the AnalysisResultsView widget for displaying
LLM analysis results for test failures.
"""

import hashlib
import logging
from html import escape
from typing import Dict, Optional

from PyQt6.QtCore import QUrl, pyqtSignal, pyqtSlot
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

from ...core.models.pytest_failure import FixSuggestion  # Ensure this is imported
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
    view_code_requested = pyqtSignal(FixSuggestion)  # New signal

    def __init__(self, model: TestResultsModel, parent: Optional[QWidget] = None):
        super().__init__(parent)
        logger.debug("AnalysisResultsView: Initializing.")
        self.results_model = model
        self.current_test: Optional[TestResult] = None
        self._html_cache: Dict[str, str] = {}
        self._cache_max_size = 100

        self._init_ui()
        self._connect_signals()
        self.text_browser.anchorClicked.connect(self._on_anchor_clicked)
        logger.debug("AnalysisResultsView: Initialization complete.")

    def _init_ui(self) -> None:
        logger.debug("AnalysisResultsView: Initializing UI.")
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
        logger.debug("AnalysisResultsView: UI initialized.")

    def _connect_signals(self) -> None:
        if self.results_model:
            logger.debug(
                "AnalysisResultsView: Connecting to TestResultsModel signals (suggestions_updated, analysis_status_updated)."
            )
            self.results_model.suggestions_updated.connect(self._on_model_data_updated)
            self.results_model.analysis_status_updated.connect(self._on_model_data_updated)
        else:
            logger.warning(
                "AnalysisResultsView: _connect_signals called but results_model is None."
            )

    @pyqtSlot(str)
    def _on_model_data_updated(self, updated_test_name: str) -> None:
        logger.debug(
            f"AnalysisResultsView: _on_model_data_updated signal received for test: '{updated_test_name}'."
        )
        if self.current_test and self.current_test.name == updated_test_name:
            logger.debug(
                f"AnalysisResultsView: Current test '{updated_test_name}' matches updated test. Refreshing view."
            )
            updated_test_object = next(
                (tr for tr in self.results_model.results if tr.name == updated_test_name), None
            )
            if updated_test_object:
                self.update_view_for_test(updated_test_object)
            else:
                logger.warning(
                    f"AnalysisResultsView: Test '{updated_test_name}' not found in model after update signal."
                )
        else:
            logger.debug(
                f"AnalysisResultsView: Updated test '{updated_test_name}' is not the current test ('{self.current_test.name if self.current_test else 'None'}'). No view refresh."
            )

    @pyqtSlot(QUrl)
    def _on_anchor_clicked(self, url: QUrl) -> None:
        scheme = url.scheme()
        logger.debug(
            f"AnalysisResultsView: Anchor clicked. URL: '{url.toString()}', Scheme: '{scheme}'."
        )
        if scheme == "viewcode":
            if self.current_test and self.current_test.suggestions:
                try:
                    suggestion_index = int(url.path())
                    logger.debug(
                        f"AnalysisResultsView: 'viewcode' anchor clicked for suggestion index: {suggestion_index}."
                    )
                    if 0 <= suggestion_index < len(self.current_test.suggestions):
                        fix_suggestion = self.current_test.suggestions[suggestion_index]
                        if fix_suggestion.code_changes is not None:
                            logger.info(
                                f"View code requested for suggestion {suggestion_index} of test {self.current_test.name}. Emitting view_code_requested signal."
                            )
                            self.view_code_requested.emit(fix_suggestion)
                        else:
                            logger.warning(
                                f"View code clicked for suggestion {suggestion_index} but it has no code_changes (was None)."
                            )
                    else:
                        logger.warning(f"Invalid suggestion index from anchor: {suggestion_index}")
                except ValueError:
                    logger.error(f"Could not parse suggestion index from anchor: {url.path()}")
            else:
                logger.warning(
                    "AnalysisResultsView: 'viewcode' anchor clicked, but no current test or suggestions available."
                )
        # else: default Qt handling for external links

    def update_view_for_test(self, test_result: Optional[TestResult]) -> None:
        test_name = test_result.name if test_result else "None"
        logger.debug(f"AnalysisResultsView: update_view_for_test called for test: '{test_name}'.")
        self.current_test = test_result

        if not self.current_test:
            self.clear_view_content()
            self.status_label.setText("No test selected or test has no failure details.")
            self._update_button_states()
            logger.debug("AnalysisResultsView: View cleared, no test selected.")
            return

        if not (self.current_test.is_failed or self.current_test.is_error):
            self.clear_view_content()
            status_text = f"Test '{self.current_test.short_name}' is not a failure/error. No analysis to display."
            self.status_label.setText(status_text)
            self._update_button_states()
            logger.debug(f"AnalysisResultsView: {status_text}")
            return

        self.status_label.setText(f"Analysis for: {self.current_test.short_name}")
        logger.debug(
            f"AnalysisResultsView: Generating HTML content for '{self.current_test.short_name}'."
        )
        html_content = self._generate_html_content(self.current_test)
        self.text_browser.setHtml(html_content)
        self._update_button_states()
        logger.debug(
            f"AnalysisResultsView: View updated for test '{self.current_test.short_name}'."
        )

    def _get_cache_key(self, test_result: TestResult) -> str:
        """Generate a cache key for the test result HTML."""
        # Create hash from test name, status, and suggestions
        content = f"{test_result.name}:{test_result.analysis_status.name}"
        if test_result.suggestions:
            suggestions_str = "|".join(
                [
                    f"{s.suggestion}:{s.confidence}:{s.explanation or ''}"
                    for s in test_result.suggestions
                ]
            )
            content += f":{suggestions_str}"

        return hashlib.md5(content.encode()).hexdigest()

    def _generate_html_content(self, test_result: TestResult) -> str:
        cache_key = self._get_cache_key(test_result)
        if cache_key in self._html_cache:
            logger.debug(
                f"AnalysisResultsView: Using cached HTML for test: {test_result.name}, cache key: {cache_key}."
            )
            return self._html_cache[cache_key]

        logger.debug(
            f"AnalysisResultsView: No cache hit for test: {test_result.name}. Generating new HTML."
        )
        html_content = self._generate_html_content_impl(test_result)

        if len(self._html_cache) >= self._cache_max_size:
            oldest_key = next(iter(self._html_cache))
            del self._html_cache[oldest_key]
            logger.debug(
                f"AnalysisResultsView: Cache full. Evicted oldest entry (key: {oldest_key})."
            )

        self._html_cache[cache_key] = html_content
        logger.debug(
            f"AnalysisResultsView: Cached new HTML for test: {test_result.name}, cache key: {cache_key}."
        )
        return html_content

    def _generate_html_content_impl(self, test_result: TestResult) -> str:
        logger.debug(
            f"AnalysisResultsView: _generate_html_content_impl for test: '{test_result.name}', Status: {test_result.analysis_status.name}, Suggestions: {len(test_result.suggestions)}."
        )
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

                    if fix_suggestion.code_changes is not None:
                        html_parts.append(
                            f'<p><a href="viewcode:{i}" style="text-decoration: none; background-color: #007bff; color: white; padding: 5px 10px; border-radius: 3px; font-size: 0.9em;">View Code Changes in Editor</a></p>'
                        )
                        # Removed the <pre> block for direct code_changes display to avoid redundancy.
                        # The user will now click the link to see it in FixSuggestionCodeView.

                    html_parts.append("</div>")  # suggestion-block
        else:
            html_parts.append(
                f"<p>Unknown analysis status: {status.name if status else 'None'}</p>"
            )

        return "".join(html_parts)  # html_parts defined in original code

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
        logger.debug(
            f"AnalysisResultsView: Updating button states. Reanalyze: {self.reanalyze_button.isEnabled()}, Copy: {self.copy_button.isEnabled()}, Clear: {self.clear_button.isEnabled()}."
        )

    @pyqtSlot()
    def _on_reanalyze_clicked(self) -> None:
        if self.current_test:
            logger.info(
                f"AnalysisResultsView: Re-analyze button clicked for test: {self.current_test.name}. Emitting reanalyze_requested signal."
            )
            self.reanalyze_requested.emit(self.current_test)
            self.status_label.setText(f"Re-analyzing {self.current_test.short_name}...")
        else:
            logger.warning(
                "AnalysisResultsView: Re-analyze button clicked, but no current test selected."
            )

    @pyqtSlot()
    def _on_copy_clicked(self) -> None:
        logger.debug("AnalysisResultsView: Copy HTML button clicked.")
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(self.text_browser.toHtml())
            logger.info("Analysis HTML content copied to clipboard.")
        else:
            logger.warning("Could not access clipboard for AnalysisResultsView.")

    def clear_view_content(self) -> None:
        logger.debug("AnalysisResultsView: Clearing view content (text browser and status label).")
        self.text_browser.clear()
        self.status_label.setText("Analysis view cleared.")

    def clear_view(self) -> None:
        logger.debug("AnalysisResultsView: Clearing entire view (current_test, content, buttons).")
        self.current_test = None
        self.clear_view_content()
        self.status_label.setText("Select a failed test to see analysis.")
        self._update_button_states()
        logger.debug("AnalysisResultsView: View fully cleared.")
