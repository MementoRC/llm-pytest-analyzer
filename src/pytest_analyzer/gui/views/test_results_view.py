"""
Test results view component for the Pytest Analyzer GUI.

This module contains the TestResultsView widget for displaying test results
and visualizing test failures.
"""

import logging
from typing import Any, List, Optional

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QBrush, QColor, QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QSplitter,
    QTableView,
    QTabWidget,
    QTextEdit,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from ...core.models.pytest_failure import FixSuggestion  # For type hint
from ..models.test_results_model import (
    TestGroup,
    TestResult,
    TestResultsModel,
    TestStatus,
)
from . import fix_suggestion_code_view  # Changed import
from .analysis_results_view import AnalysisResultsView

# Configure logging
logger = logging.getLogger(__name__)


class TestResultsTableModel(QAbstractTableModel):
    """Table model for displaying test results."""

    def __init__(self, parent: Optional[QWidget] = None):
        """
        Initialize the table model.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        logger.debug("TestResultsTableModel: Initializing.")
        self.results: List[TestResult] = []
        self.headers = ["Status", "Test Name", "Duration", "File"]
        logger.debug("TestResultsTableModel: Initialization complete.")

    def set_results(self, results: List[TestResult]) -> None:
        """
        Set test results data.

        Args:
            results: List of test results
        """
        logger.debug(f"TestResultsTableModel: Setting results. Count: {len(results)}.")
        self.beginResetModel()
        self.results = results
        self.endResetModel()
        logger.debug("TestResultsTableModel: Results set and model reset.")

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """
        Get the number of rows in the model.

        Args:
            parent: Parent index

        Returns:
            Number of rows
        """
        return len(self.results)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """
        Get the number of columns in the model.

        Args:
            parent: Parent index

        Returns:
            Number of columns
        """
        return len(self.headers)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        """
        Get header data.

        Args:
            section: Section index
            orientation: Header orientation
            role: Data role

        Returns:
            Header data
        """
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.headers[section]

        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        """
        Get data for an index.

        Args:
            index: Item index
            role: Data role

        Returns:
            Item data
        """
        # if index.isValid():
        #    logger.debug(f"TestResultsTableModel: data called. Row: {index.row()}, Col: {index.column()}, Role: {role}.")
        if not index.isValid() or index.row() >= len(self.results):
            return None

        result = self.results[index.row()]
        column = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if column == 0:
                return result.status.name
            if column == 1:
                return result.name
            if column == 2:
                return f"{result.duration:.3f}s"
            if column == 3:
                return str(result.file_path) if result.file_path else ""

        elif role == Qt.ItemDataRole.BackgroundRole:
            if result.status == TestStatus.FAILED:
                return QBrush(QColor(255, 200, 200))
            if result.status == TestStatus.ERROR:
                return QBrush(QColor(255, 150, 150))
            if result.status == TestStatus.PASSED:
                return QBrush(QColor(200, 255, 200))
            if result.status == TestStatus.SKIPPED:
                return QBrush(QColor(200, 200, 255))

        return None


class TestResultsView(QWidget):
    """
    Widget for displaying test results and visualizing failures.

    This widget provides a UI for viewing test results, including:
    - A table of test results
    - Details of selected tests
    - Grouping of related failures
    """

    # Signals
    test_selected = pyqtSignal(TestResult)
    group_selected = pyqtSignal(TestGroup)

    def __init__(self, parent: Optional[QWidget] = None):
        """
        Initialize the test results view.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        logger.debug("TestResultsView: Initializing.")

        self.results_model = TestResultsModel()
        logger.debug("TestResultsView: Default TestResultsModel instantiated.")
        self.results_model.results_updated.connect(self._on_results_updated)
        self.results_model.groups_updated.connect(self._on_groups_updated)
        logger.debug("TestResultsView: Connected to default model signals.")

        self.selected_test: Optional[TestResult] = None
        self.selected_group: Optional[TestGroup] = None

        self.analysis_results_view = AnalysisResultsView(self.results_model, self)
        self.fix_suggestion_code_view = fix_suggestion_code_view.FixSuggestionCodeView(
            self
        )  # Changed instantiation

        self._init_ui()

        # Connect the new signal from AnalysisResultsView
        self.analysis_results_view.view_code_requested.connect(self._on_view_code_requested)
        logger.debug("TestResultsView: Initialization complete.")

    def _init_ui(self) -> None:
        """Initialize the UI components."""
        logger.debug("TestResultsView: Initializing UI components.")
        # Create main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Create summary section
        summary_layout = QHBoxLayout()
        summary_layout.setContentsMargins(5, 5, 5, 5)

        self.summary_label = QLabel("No test results loaded")

        summary_layout.addWidget(self.summary_label)
        summary_layout.addStretch()

        # Create splitter for results and details
        self.main_splitter = QSplitter(Qt.Orientation.Vertical)

        # Create tab widget for different views
        self.tabs = QTabWidget()

        # Create tab for test results table
        self.results_table_model = TestResultsTableModel()
        self.results_table = QTableView()
        self.results_table.setModel(self.results_table_model)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.results_table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.results_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.results_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.results_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self.results_table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        self.results_table.setColumnWidth(0, 80)
        self.results_table.setColumnWidth(2, 100)
        self.results_table.verticalHeader().setVisible(False)

        # Create tab for grouped failures
        self.groups_model = QStandardItemModel()
        self.groups_model.setHorizontalHeaderLabels(["Group", "Count", "Root Cause"])

        self.groups_tree = QTreeView()
        self.groups_tree.setModel(self.groups_model)
        self.groups_tree.setAlternatingRowColors(True)
        self.groups_tree.setHeaderHidden(False)
        self.groups_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.groups_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.groups_tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        # Add tabs
        self.tabs.addTab(self.results_table, "All Tests")
        self.tabs.addTab(self.groups_tree, "Grouped Failures")

        # Create details section
        self.details_widget = QWidget()
        details_layout = QVBoxLayout(self.details_widget)
        details_layout.setContentsMargins(0, 0, 0, 0)

        # Details tab widget
        self.details_tabs = QTabWidget()

        # Failure details tab
        self.failure_details = QTextEdit()
        self.failure_details.setReadOnly(True)

        # Traceback tab
        self.traceback_details = QTextEdit()
        self.traceback_details.setReadOnly(True)
        self.traceback_details.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)

        # Add tabs to details tab widget
        self.details_tabs.addTab(self.failure_details, "Failure Details")
        self.details_tabs.addTab(self.traceback_details, "Traceback")
        self.details_tabs.addTab(self.analysis_results_view, "Analysis")
        self.details_tabs.addTab(self.fix_suggestion_code_view, "Code Preview")  # New tab

        # Add details tab widget to details layout
        details_layout.addWidget(self.details_tabs)

        # Add widgets to splitter
        self.main_splitter.addWidget(self.tabs)
        self.main_splitter.addWidget(self.details_widget)

        # Set splitter proportions
        self.main_splitter.setStretchFactor(0, 2)
        self.main_splitter.setStretchFactor(1, 1)

        # Connect signals
        self.results_table.selectionModel().selectionChanged.connect(
            self._on_test_selection_changed
        )
        self.groups_tree.selectionModel().selectionChanged.connect(self._on_group_selection_changed)

        # Add widgets to main layout
        main_layout.addLayout(summary_layout)
        main_layout.addWidget(self.main_splitter)
        logger.debug("TestResultsView: UI components initialized.")

    def set_results_model(self, model: TestResultsModel) -> None:
        """
        Set the test results model.

        Args:
            model: Test results model
        """
        logger.debug(f"TestResultsView: Setting new TestResultsModel. New model: {model}")
        # Disconnect old model signals
        if self.results_model:
            logger.debug("TestResultsView: Disconnecting signals from old model.")
            try:
                self.results_model.results_updated.disconnect(self._on_results_updated)
                self.results_model.groups_updated.disconnect(self._on_groups_updated)
            except TypeError:
                logger.debug(
                    "TestResultsView: Error disconnecting signals from old model (possibly already disconnected or never connected)."
                )

            if hasattr(self, "analysis_results_view") and self.analysis_results_view.results_model:
                logger.debug(
                    "TestResultsView: Disconnecting signals for AnalysisResultsView from old model."
                )
                try:
                    self.analysis_results_view.results_model.suggestions_updated.disconnect(
                        self.analysis_results_view._on_model_data_updated
                    )
                except TypeError:
                    logger.debug(
                        "TestResultsView: Error disconnecting suggestions_updated from AnalysisResultsView (possibly already disconnected)."
                    )
                try:
                    self.analysis_results_view.results_model.analysis_status_updated.disconnect(
                        self.analysis_results_view._on_model_data_updated
                    )
                except TypeError:
                    logger.debug(
                        "TestResultsView: Error disconnecting analysis_status_updated from AnalysisResultsView (possibly already disconnected)."
                    )

        self.results_model = model
        logger.debug("TestResultsView: New model assigned.")

        if hasattr(self, "analysis_results_view"):
            logger.debug("TestResultsView: Updating AnalysisResultsView with new model.")
            self.analysis_results_view.results_model = self.results_model
            self.analysis_results_view._connect_signals()

        if self.results_model:
            logger.debug("TestResultsView: Connecting signals to new model.")
            self.results_model.results_updated.connect(self._on_results_updated)
            self.results_model.groups_updated.connect(self._on_groups_updated)

            logger.debug("TestResultsView: Triggering UI update with new model data.")
            self._on_results_updated()
            self._on_groups_updated()
            self.fix_suggestion_code_view.clear()
            logger.debug("TestResultsView: FixSuggestionCodeView cleared.")
        else:
            logger.warning("TestResultsView: set_results_model called with a None model.")

    def clear(self) -> None:
        """Clear all test results data."""
        logger.debug("TestResultsView: Clearing view.")
        # Clear UI elements
        self.results_table_model.set_results([])
        self.groups_model.clear()
        self.groups_model.setHorizontalHeaderLabels(["Group", "Count", "Root Cause"])

        self.failure_details.clear()
        self.traceback_details.clear()

        self.summary_label.setText("No test results loaded")

        # Reset selected items
        self.selected_test = None
        self.selected_group = None

        if hasattr(self, "analysis_results_view"):
            self.analysis_results_view.clear_view()
        if hasattr(self, "fix_suggestion_code_view"):
            self.fix_suggestion_code_view.clear()
        logger.debug("TestResultsView: View cleared.")

    def _update_summary(self) -> None:
        """Update the summary label with current results data."""
        logger.debug("TestResultsView: Updating summary.")
        if not self.results_model.results:
            self.summary_label.setText("No test results loaded")
            logger.debug("TestResultsView: Summary updated - No results.")
            return

        total = self.results_model.total_count
        failed = self.results_model.failed_count
        errors = self.results_model.error_count
        passed = total - failed - errors

        if failed > 0 or errors > 0:
            self.summary_label.setText(
                f"Results: {total} tests, "
                f"<span style='color:green'>{passed} passed</span>, "
                f"<span style='color:red'>{failed} failed</span>, "
                f"<span style='color:red'>{errors} errors</span>"
            )
        else:
            self.summary_label.setText(
                f"Results: {total} tests, <span style='color:green'>{passed} passed</span>"
            )
        logger.debug(f"TestResultsView: Summary updated. Text: {self.summary_label.text()}")

    def _update_details(self, test: Optional[TestResult] = None) -> None:
        """
        Update the details section with the selected test.

        Args:
            test: Selected test result
        """
        test_name = test.name if test else "None"
        logger.debug(f"TestResultsView: Updating details for test: {test_name}.")
        if not test:
            self.failure_details.clear()
            self.traceback_details.clear()
            if hasattr(self, "analysis_results_view"):
                self.analysis_results_view.update_view_for_test(None)
            logger.debug("TestResultsView: Details cleared as no test is selected.")
            return

        # Update failure details
        details_text = f"<h3>{test.name}</h3>"

        if test.status == TestStatus.FAILED or test.status == TestStatus.ERROR:
            if test.failure_details:
                details_text += f"<p><b>Message:</b> {test.failure_details.message}</p>"

                if test.failure_details.file_path and test.failure_details.line_number:
                    details_text += f"<p><b>Location:</b> {test.failure_details.file_path}:{test.failure_details.line_number}</p>"

                if test.failure_details.expected is not None:
                    details_text += f"<p><b>Expected:</b> {test.failure_details.expected}</p>"

                if test.failure_details.actual is not None:
                    details_text += f"<p><b>Actual:</b> {test.failure_details.actual}</p>"

        self.failure_details.setHtml(details_text)

        # Update traceback
        if test.failure_details and test.failure_details.traceback:
            self.traceback_details.setPlainText(test.failure_details.traceback)
        else:
            self.traceback_details.clear()

        if hasattr(self, "analysis_results_view"):
            self.analysis_results_view.update_view_for_test(test)
        logger.debug(f"TestResultsView: Details updated for test: {test.name}.")

    @pyqtSlot()
    def _on_results_updated(self) -> None:
        """Handle results model update."""
        logger.debug(
            f"TestResultsView: _on_results_updated (results_updated signal received). Model has {len(self.results_model.results)} results."
        )
        self.results_table_model.set_results(self.results_model.results)
        logger.debug("TestResultsView: Results table model updated.")
        self._update_summary()
        self.selected_test = None
        self._update_details()  # This will clear details as selected_test is None
        logger.debug("TestResultsView: Selection cleared and details updated (cleared).")

    @pyqtSlot()
    def _on_groups_updated(self) -> None:
        """Handle groups model update."""
        logger.debug(
            f"TestResultsView: _on_groups_updated (groups_updated signal received). Model has {len(self.results_model.groups)} groups."
        )
        self.groups_model.clear()
        self.groups_model.setHorizontalHeaderLabels(["Group", "Count", "Root Cause"])
        logger.debug("TestResultsView: Groups model cleared.")

        root_item = self.groups_model.invisibleRootItem()
        for group_idx, group in enumerate(self.results_model.groups):
            # Create group item
            group_name_item = QStandardItem(group.name)
            group_count_item = QStandardItem(str(len(group.tests)))
            group_cause_item = QStandardItem(group.root_cause or "Unknown")

            # Store group in user role
            group_name_item.setData(group, Qt.ItemDataRole.UserRole)

            # Add group to model
            root_item.appendRow([group_name_item, group_count_item, group_cause_item])

            # Add tests to group
            for test in group.tests:
                test_item = QStandardItem(test.name)
                test_item.setData(test, Qt.ItemDataRole.UserRole)

                # Create empty items for other columns
                count_item = QStandardItem("")
                cause_item = QStandardItem("")

                group_name_item.appendRow([test_item, count_item, cause_item])
            logger.debug(
                f"TestResultsView: Added group '{group.name}' with {len(group.tests)} tests to groups model."
            )
        logger.debug("TestResultsView: Groups model populated.")

    @pyqtSlot()
    def _on_test_selection_changed(self) -> None:
        """Handle test selection change in the table view."""
        indexes = self.results_table.selectionModel().selectedIndexes()
        if not indexes:
            logger.debug("TestResultsView: _on_test_selection_changed - No selection.")
            return

        row = indexes[0].row()
        logger.debug(f"TestResultsView: _on_test_selection_changed - Selected row: {row}.")

        if 0 <= row < len(self.results_model.results):
            self.selected_test = self.results_model.results[row]
            logger.debug(f"TestResultsView: Selected test: {self.selected_test.name}.")
            self._update_details(self.selected_test)
            logger.debug(
                f"TestResultsView: Emitting test_selected signal for {self.selected_test.name}."
            )
            self.test_selected.emit(self.selected_test)
        else:
            logger.warning(
                f"TestResultsView: Selected row {row} is out of bounds for results list (len {len(self.results_model.results)})."
            )

    @pyqtSlot(FixSuggestion)
    def _on_view_code_requested(self, fix_suggestion: FixSuggestion) -> None:
        logger.debug(
            f"TestResultsView: _on_view_code_requested signal received. Suggestion: '{fix_suggestion.suggestion[:30]}...' for test '{fix_suggestion.failure.test_name}'."
        )
        self.fix_suggestion_code_view.load_fix_suggestion(fix_suggestion)

        code_preview_tab_index = -1
        for i in range(self.details_tabs.count()):
            if self.details_tabs.widget(i) == self.fix_suggestion_code_view:
                code_preview_tab_index = i
                break

        if code_preview_tab_index != -1:
            logger.debug(
                f"TestResultsView: Switching to 'Code Preview' tab (index {code_preview_tab_index})."
            )
            self.details_tabs.setCurrentIndex(code_preview_tab_index)
        else:
            logger.error("TestResultsView: Could not find 'Code Preview' tab.")

    @pyqtSlot()
    def _on_group_selection_changed(self) -> None:
        """Handle group selection change in the tree view."""
        indexes = self.groups_tree.selectionModel().selectedIndexes()
        if not indexes:
            logger.debug("TestResultsView: _on_group_selection_changed - No selection.")
            return

        index = indexes[0]
        item = self.groups_model.itemFromIndex(index)
        data = item.data(Qt.ItemDataRole.UserRole)
        logger.debug(
            f"TestResultsView: _on_group_selection_changed - Selected item text: '{item.text()}', data type: {type(data)}."
        )

        if isinstance(data, TestGroup):
            self.selected_group = data
            logger.debug(
                f"TestResultsView: Selected group: {self.selected_group.name}. Emitting group_selected signal."
            )
            self.group_selected.emit(self.selected_group)
        elif isinstance(data, TestResult):
            self.selected_test = data
            logger.debug(
                f"TestResultsView: Selected test (from group view): {self.selected_test.name}."
            )
            self._update_details(self.selected_test)
            logger.debug(
                f"TestResultsView: Emitting test_selected signal for {self.selected_test.name}."
            )
            self.test_selected.emit(self.selected_test)
        else:
            logger.debug(
                "TestResultsView: Selected item in group view is neither TestGroup nor TestResult."
            )
