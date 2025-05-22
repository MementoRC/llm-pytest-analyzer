import logging
from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import QModelIndex, Qt, pyqtSignal
from PyQt6.QtGui import QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from ...core.models.pytest_failure import PytestFailure

logger = logging.getLogger(__name__)


class TestDiscoveryView(QWidget):
    """
    Widget for displaying discovered tests and allowing selection.
    """

    discover_tests_requested = pyqtSignal()  # Emitted when refresh button is clicked
    # Emits list of selected node IDs, could be used by a controller if needed directly
    # For now, selection is primarily retrieved via get_selected_node_ids()
    selection_changed = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._init_ui()
        self._block_item_changed_signal = False

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Controls (Refresh button, Filter)
        controls_layout = QHBoxLayout()
        self.refresh_button = QPushButton("Refresh Tests")
        self.refresh_button.clicked.connect(self.discover_tests_requested)
        controls_layout.addWidget(self.refresh_button)

        controls_layout.addStretch()  # Pushes filter to the right

        filter_label = QLabel("Filter:")
        controls_layout.addWidget(filter_label)
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("e.g., test_login or specific_module")
        self.filter_edit.textChanged.connect(self._apply_filter)
        controls_layout.addWidget(self.filter_edit)

        main_layout.addLayout(controls_layout)

        # Test Tree View
        self.test_tree_model = QStandardItemModel()
        self.test_tree_model.setHorizontalHeaderLabels(["Test / Module / Class", "Node ID"])
        self.test_tree_model.itemChanged.connect(self._on_item_changed)

        self.test_tree_view = QTreeView()
        self.test_tree_view.setModel(self.test_tree_model)
        self.test_tree_view.setHeaderHidden(False)
        self.test_tree_view.setAlternatingRowColors(True)
        self.test_tree_view.setColumnHidden(
            1, True
        )  # Hide Node ID by default, useful for debugging
        self.test_tree_view.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.test_tree_view.header().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )

        main_layout.addWidget(self.test_tree_view)

    def _parse_node_id(self, node_id: str) -> Tuple[str, Optional[str], str]:
        """
        Parses a pytest node ID into file, class (optional), and function/method.
        Example: "test_module.py::TestClass::test_method" -> ("test_module.py", "TestClass", "test_method")
        Example: "test_module.py::test_function" -> ("test_module.py", None, "test_function")
        """
        parts = node_id.split("::")
        file_path = parts[0]
        if len(parts) == 2:  # test_file.py::test_function
            return file_path, None, parts[1]
        if len(parts) == 3:  # test_file.py::TestClass::test_method
            return file_path, parts[1], parts[2]
        logger.warning(f"Could not parse node ID: {node_id}")
        return node_id, None, node_id  # Fallback

    def update_test_tree(self, collected_items: List[PytestFailure]) -> None:
        """
        Populates the tree view with discovered tests.
        `collected_items` are PytestFailure objects where `test_name` is the node ID.
        """
        self._block_item_changed_signal = True  # Block signals during programmatic changes
        self.test_tree_model.clear()
        self.test_tree_model.setHorizontalHeaderLabels(["Test / Module / Class", "Node ID"])

        root_item = self.test_tree_model.invisibleRootItem()
        file_items: Dict[str, QStandardItem] = {}
        class_items: Dict[str, QStandardItem] = {}  # Keyed by "file_path::ClassName"

        for item_failure_obj in collected_items:
            node_id = item_failure_obj.test_name  # This is the nodeid
            file_part, class_part, func_part = self._parse_node_id(node_id)

            # Get or create file item
            if file_part not in file_items:
                file_item = QStandardItem(file_part)
                file_item.setFlags(
                    file_item.flags()
                    | Qt.ItemFlag.ItemIsAutoTristate
                    | Qt.ItemFlag.ItemIsUserCheckable
                )
                file_item.setCheckState(Qt.CheckState.Unchecked)
                file_items[file_part] = file_item
                col_node_id_file = QStandardItem(
                    file_part
                )  # Node ID for file item is just file_part
                root_item.appendRow([file_item, col_node_id_file])
            else:
                file_item = file_items[file_part]

            parent_item = file_item

            # Get or create class item (if exists)
            if class_part:
                class_key = f"{file_part}::{class_part}"
                if class_key not in class_items:
                    class_item_display = QStandardItem(class_part)
                    class_item_display.setFlags(
                        class_item_display.flags()
                        | Qt.ItemFlag.ItemIsAutoTristate
                        | Qt.ItemFlag.ItemIsUserCheckable
                    )
                    class_item_display.setCheckState(Qt.CheckState.Unchecked)
                    class_items[class_key] = class_item_display
                    col_node_id_class = QStandardItem(class_key)
                    file_item.appendRow([class_item_display, col_node_id_class])
                else:
                    class_item_display = class_items[class_key]
                parent_item = class_item_display

            # Create function/method item
            func_item_display = QStandardItem(func_part)
            func_item_display.setFlags(func_item_display.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            func_item_display.setCheckable(True)
            func_item_display.setCheckState(Qt.CheckState.Unchecked)  # Default to unchecked
            col_node_id_func = QStandardItem(node_id)  # Full node ID for test function
            parent_item.appendRow([func_item_display, col_node_id_func])

        self.test_tree_view.expandAll()
        self._block_item_changed_signal = False

    def _on_item_changed(self, item: QStandardItem) -> None:
        """Handle item check state changes to propagate to children/parents."""
        if self._block_item_changed_signal or not item.isCheckable():
            return

        self._block_item_changed_signal = True
        check_state = item.checkState()

        # Propagate to children
        if item.hasChildren():
            for r in range(item.rowCount()):
                child_item = item.child(r, 0)
                if child_item and child_item.isCheckable():
                    child_item.setCheckState(check_state)

        # Propagate to parent
        parent = item.parent()
        if parent:
            self._update_parent_check_state(parent)

        self._block_item_changed_signal = False
        self.selection_changed.emit()

    def _update_parent_check_state(self, parent_item: QStandardItem) -> None:
        """Update parent's check state based on its children's states."""
        if not parent_item or not (parent_item.flags() & Qt.ItemFlag.ItemIsUserCheckable):
            return

        num_children = parent_item.rowCount()
        if num_children == 0:
            return

        checked_children = 0
        partially_checked_children = 0  # For tristate

        for r in range(num_children):
            child = parent_item.child(r, 0)
            if child and child.isCheckable():
                if child.checkState() == Qt.CheckState.Checked:
                    checked_children += 1
                elif child.checkState() == Qt.CheckState.PartiallyChecked:
                    partially_checked_children += 1

        if checked_children == 0 and partially_checked_children == 0:
            parent_item.setCheckState(Qt.CheckState.Unchecked)
        elif checked_children == num_children:
            parent_item.setCheckState(Qt.CheckState.Checked)
        else:
            parent_item.setCheckState(Qt.CheckState.PartiallyChecked)

        # Recursively update grandparent
        grandparent = parent_item.parent()
        if grandparent:
            self._update_parent_check_state(grandparent)

    def get_selected_node_ids(self) -> List[str]:
        """
        Returns a list of node IDs for all checked test items (functions/methods).
        """
        selected_ids: List[str] = []
        model = self.test_tree_model

        for row in range(model.rowCount()):
            file_item = model.item(row, 0)
            if not file_item:
                continue

            # Iterate through children of file_item (classes or functions)
            for i in range(file_item.rowCount()):
                child_item = file_item.child(i, 0)  # e.g. class or function item
                if not child_item:
                    continue

                if not child_item.hasChildren():  # It's a direct test function under a file
                    if child_item.checkState() == Qt.CheckState.Checked:
                        node_id_item = file_item.child(i, 1)
                        if node_id_item and node_id_item.text():
                            selected_ids.append(node_id_item.text())
                else:  # It's a class item
                    # Iterate through children of class_item (test methods)
                    for j in range(child_item.rowCount()):
                        method_item = child_item.child(j, 0)
                        if method_item and method_item.checkState() == Qt.CheckState.Checked:
                            node_id_item = child_item.child(j, 1)
                            if node_id_item and node_id_item.text():
                                selected_ids.append(node_id_item.text())
        return selected_ids

    def clear_tree(self) -> None:
        self._block_item_changed_signal = True
        self.test_tree_model.clear()
        self.test_tree_model.setHorizontalHeaderLabels(["Test / Module / Class", "Node ID"])
        self._block_item_changed_signal = False
        self._filter_proxy_model = None  # Will be QSortFilterProxyModel if we use it

    def _apply_filter(self, text: str) -> None:
        """Filters the tree view based on the input text."""
        filter_text = text.lower()
        self._filter_recursive(self.test_tree_model.invisibleRootItem(), filter_text)

    def _filter_recursive(self, parent_item: QStandardItem, filter_text: str) -> bool:
        """
        Recursively apply filter. Returns True if this item or any child matches.
        An item is visible if its text matches OR any of its children match.
        """
        item_is_visible_due_to_self = False
        if filter_text == "":  # If filter is empty, all items are visible
            item_is_visible_due_to_self = True
        else:
            # Check current item's text (column 0)
            display_text_item = parent_item.child(
                parent_item.rowCount() - 1 if parent_item.rowCount() > 0 else 0, 0
            )  # Heuristic to get a displayable item if parent is invisibleRootItem
            if parent_item.index().isValid():  # Regular item
                display_text_item = self.test_tree_model.itemFromIndex(
                    parent_item.index().siblingAtColumn(0)
                )

            if display_text_item and display_text_item.text().lower().count(filter_text):
                item_is_visible_due_to_self = True

            # Also check Node ID (column 1) if it exists for this item
            if not item_is_visible_due_to_self and parent_item.index().isValid():
                node_id_item = self.test_tree_model.itemFromIndex(
                    parent_item.index().siblingAtColumn(1)
                )
                if node_id_item and node_id_item.text().lower().count(filter_text):
                    item_is_visible_due_to_self = True

        any_child_is_visible = False
        for r in range(parent_item.rowCount()):
            child_item = parent_item.child(r, 0)
            if child_item:
                if self._filter_recursive(child_item, filter_text):
                    any_child_is_visible = True

        should_be_visible = item_is_visible_due_to_self or any_child_is_visible

        if parent_item.index().isValid():  # Do not hide/show the invisible root item itself
            parent_model_index = (
                parent_item.parent().index() if parent_item.parent() else QModelIndex()
            )
            self.test_tree_view.setRowHidden(
                parent_item.row(), parent_model_index, not should_be_visible
            )
            if should_be_visible and filter_text:  # Expand if it's visible due to filter
                self.test_tree_view.expand(parent_item.index())
            elif not filter_text:  # Collapse all if filter is cleared, except top level
                if parent_item.parent() != self.test_tree_model.invisibleRootItem():
                    self.test_tree_view.collapse(parent_item.index())

        return should_be_visible
