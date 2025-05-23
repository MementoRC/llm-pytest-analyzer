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

        self.results: List[TestResult] = []
        self.headers = ["Status", "Test Name", "Duration", "File"]

    def set_results(self, results: List[TestResult]) -> None:
        """
        Set test results data.

        Args:
            results: List of test results
        """
        self.beginResetModel()
        self.results = results
        self.endResetModel()

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

        self.results_model = TestResultsModel()
        self.results_model.results_updated.connect(self._on_results_updated)
        self.results_model.groups_updated.connect(self._on_groups_updated)

        self.selected_test: Optional[TestResult] = None
        self.selected_group: Optional[TestGroup] = None

        self.analysis_results_view = AnalysisResultsView(self.results_model, self)
        self.fix_suggestion_code_view = fix_suggestion_code_view.FixSuggestionCodeView(
            self
        )  # Changed instantiation

        self._init_ui()

        # Connect the new signal from AnalysisResultsView
        self.analysis_results_view.view_code_requested.connect(self._on_view_code_requested)

    def _init_ui(self) -> None:
        """Initialize the UI components."""
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

    def set_results_model(self, model: TestResultsModel) -> None:
        """
        Set the test results model.

        Args:
            model: Test results model
        """
        # Disconnect old model signals (for TestResultsView itself)
        if self.results_model:
            self.results_model.results_updated.disconnect(self._on_results_updated)
            self.results_model.groups_updated.disconnect(self._on_groups_updated)
            # Also disconnect for analysis_results_view if it was connected to the old model
            if hasattr(self, "analysis_results_view") and self.analysis_results_view.results_model:
                try:
                    self.analysis_results_view.results_model.suggestions_updated.disconnect(
                        self.analysis_results_view._on_model_data_updated
                    )
                except TypeError:  # Raised if not connected
                    pass
                try:
                    self.analysis_results_view.results_model.analysis_status_updated.disconnect(
                        self.analysis_results_view._on_model_data_updated
                    )
                except TypeError:  # Raised if not connected
                    pass

        # Set new model
        self.results_model = model

        # Update AnalysisResultsView with the new model and reconnect its signals
        if hasattr(self, "analysis_results_view"):  # If AnalysisResultsView exists
            self.analysis_results_view.results_model = (
                self.results_model
            )  # Give it the new model instance
            self.analysis_results_view._connect_signals()  # Tell it to connect to this new model instance

        # Connect new model signals (for TestResultsView itself)
        if self.results_model:
            self.results_model.results_updated.connect(self._on_results_updated)
            self.results_model.groups_updated.connect(self._on_groups_updated)

            # Update UI with current model data
            self._on_results_updated()
            self._on_groups_updated()
            self.fix_suggestion_code_view.clear()  # Clear when model changes

    def clear(self) -> None:
        """Clear all test results data."""
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

    def _update_summary(self) -> None:
        """Update the summary label with current results data."""
        if not self.results_model.results:
            self.summary_label.setText("No test results loaded")
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

    def _update_details(self, test: Optional[TestResult] = None) -> None:
        """
        Update the details section with the selected test.

        Args:
            test: Selected test result
        """
        if not test:
            self.failure_details.clear()
            self.traceback_details.clear()
            if hasattr(self, "analysis_results_view"):
                self.analysis_results_view.update_view_for_test(None)
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

    @pyqtSlot()
    def _on_results_updated(self) -> None:
        """Handle results model update."""
        # Update table model
        self.results_table_model.set_results(self.results_model.results)

        # Update summary
        self._update_summary()

        # Clear selection
        self.selected_test = None
        self._update_details()

    @pyqtSlot()
    def _on_groups_updated(self) -> None:
        """Handle groups model update."""
        # Clear groups model
        self.groups_model.clear()
        self.groups_model.setHorizontalHeaderLabels(["Group", "Count", "Root Cause"])

        # Add groups to model
        root_item = self.groups_model.invisibleRootItem()

        for group in self.results_model.groups:
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

    @pyqtSlot()
    def _on_test_selection_changed(self) -> None:
        """Handle test selection change in the table view."""
        indexes = self.results_table.selectionModel().selectedIndexes()
        if not indexes:
            return

        # Get the selected row (assuming single selection mode)
        row = indexes[0].row()

        # Get the selected test
        if 0 <= row < len(self.results_model.results):
            self.selected_test = self.results_model.results[row]
            self._update_details(self.selected_test)

            # Emit signal
            self.test_selected.emit(self.selected_test)

    @pyqtSlot(FixSuggestion)
    def _on_view_code_requested(self, fix_suggestion: FixSuggestion) -> None:
        logger.debug(
            f"TestResultsView: Received request to view code for suggestion: {fix_suggestion.suggestion[:30]}..."
        )
        self.fix_suggestion_code_view.load_fix_suggestion(fix_suggestion)

        # Switch to the "Code Preview" tab
        code_preview_tab_index = -1
        for i in range(self.details_tabs.count()):
            if self.details_tabs.widget(i) == self.fix_suggestion_code_view:
                code_preview_tab_index = i
                break

        if code_preview_tab_index != -1:
            self.details_tabs.setCurrentIndex(code_preview_tab_index)
        else:
            logger.error("Could not find 'Code Preview' tab.")

    @pyqtSlot()
    def _on_group_selection_changed(self) -> None:
        """Handle group selection change in the tree view."""
        indexes = self.groups_tree.selectionModel().selectedIndexes()
        if not indexes:
            return

        # Get the selected item
        index = indexes[0]
        item = self.groups_model.itemFromIndex(index)

        # Get the data from user role
        data = item.data(Qt.ItemDataRole.UserRole)

        if isinstance(data, TestGroup):
            self.selected_group = data
            # Emit signal
            self.group_selected.emit(self.selected_group)
        elif isinstance(data, TestResult):
            self.selected_test = data
            self._update_details(self.selected_test)
            # Emit signal
            self.test_selected.emit(self.selected_test)
