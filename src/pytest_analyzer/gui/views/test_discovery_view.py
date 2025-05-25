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
    selection_changed = pyqtSignal()  # Emitted when checkbox selection changes
    test_file_selected = pyqtSignal(str)  # Emitted with file path when a tree item is clicked

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        logger.debug("TestDiscoveryView: Initializing.")
        self._init_ui()
        self._block_item_changed_signal = False
        logger.debug("TestDiscoveryView: Initialization complete.")

    def _init_ui(self) -> None:
        logger.debug("TestDiscoveryView: Initializing UI.")
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Controls (Refresh button, Filter)
        controls_layout = QHBoxLayout()
        self.refresh_button = QPushButton("Refresh Tests")
        self.refresh_button.clicked.connect(
            self._emit_discover_tests_requested_debug
        )  # Changed connection
        controls_layout.addWidget(self.refresh_button)

        self.selected_tests_label = QLabel("Selected for run: 0 tests")
        controls_layout.addWidget(self.selected_tests_label)

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
        self.test_tree_view.setToolTip(
            "Check items to select them for execution.\n"
            "Click an item to view its source file in the editor (if applicable)."
        )
        self.test_tree_view.clicked.connect(self._on_tree_item_clicked)

        main_layout.addWidget(self.test_tree_view)
        logger.debug("TestDiscoveryView: UI initialized.")

    def _emit_discover_tests_requested_debug(self):  # New method
        logger.debug(
            "TestDiscoveryView: Refresh button clicked. Emitting discover_tests_requested signal."
        )
        self.discover_tests_requested.emit()

    def _parse_node_id(self, node_id: str) -> Tuple[str, Optional[str], str]:
        """
        Parses a pytest node ID into file, class (optional), and function/method.
        Example: "test_module.py::TestClass::test_method" -> ("test_module.py", "TestClass", "test_method")
        Example: "test_module.py::test_function" -> ("test_module.py", None, "test_function")
        Example: "tests/test_module.py" (file path only) -> ("tests/test_module.py", None, "test_module.py")
        """
        parts = node_id.split("::")
        file_path = parts[0]

        if len(parts) == 2:  # test_file.py::test_function
            return file_path, None, parts[1]
        if len(parts) == 3:  # test_file.py::TestClass::test_method
            return file_path, parts[1], parts[2]
        if len(parts) == 1:  # Just a file path (e.g., "tests/test_module.py")
            # For file-only node IDs, use the file path as-is and extract basename for display
            from pathlib import Path

            path_obj = Path(node_id)
            display_name = path_obj.name  # Just the filename for display
            return file_path, None, display_name
        # Unexpected format, but handle gracefully
        logger.debug(f"Unusual node ID format: {node_id}")
        return node_id, None, node_id  # Fallback

    def update_test_tree(self, collected_items: List[PytestFailure]) -> None:
        """
        Populates the tree view with discovered tests.
        `collected_items` are PytestFailure objects where `test_name` is the node ID.
        """
        logger.debug(f"TestDiscoveryView: Updating test tree with {len(collected_items)} items.")
        self._block_item_changed_signal = True
        self.test_tree_model.clear()
        self.test_tree_model.setHorizontalHeaderLabels(["Test / Module / Class", "Node ID"])
        logger.debug("TestDiscoveryView: Test tree model cleared.")

        root_item = self.test_tree_model.invisibleRootItem()
        file_items: Dict[str, QStandardItem] = {}
        class_items: Dict[str, QStandardItem] = {}

        processed_count = 0
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
            processed_count += 1
        logger.debug(f"TestDiscoveryView: Processed {processed_count} items into tree structure.")

        self.test_tree_view.expandAll()
        self._block_item_changed_signal = False
        self._update_selected_tests_count_label()
        logger.debug(
            "TestDiscoveryView: Test tree updated and expanded. Signal blocking re-enabled."
        )

    def _get_file_path_from_index(self, index: QModelIndex) -> Optional[str]:
        """Extracts the file path associated with a tree item index."""
        if not index.isValid():
            return None

        # The node ID is stored in the second column (index 1)
        node_id_index = index.sibling(index.row(), 1)
        if not node_id_index.isValid():
            logger.debug(
                f"TestDiscoveryView: No valid sibling index for node ID at row {index.row()}, col 1."
            )
            return None

        node_id_item = self.test_tree_model.itemFromIndex(node_id_index)
        if not node_id_item:
            logger.debug(
                f"TestDiscoveryView: No model item found for node ID index {node_id_index}."
            )
            return None

        node_id = node_id_item.text()
        if not node_id:
            logger.debug("TestDiscoveryView: Node ID item text is empty.")
            return None

        # The file path is the part of the node ID before the first '::'
        # or the whole node_id if '::' is not present (e.g. for top-level file items)
        file_path_str = node_id.split("::")[0]

        # Basic validation (can be expanded, e.g. check if Path(file_path_str).is_file())
        if file_path_str:
            logger.debug(f"TestDiscoveryView: Extracted file path: {file_path_str}")
            return file_path_str
        logger.warning(f"TestDiscoveryView: Could not extract file path from node ID: {node_id}")
        return None

    def _on_tree_item_clicked(self, index: QModelIndex) -> None:
        """Handles a click on a tree item to potentially load its file."""
        logger.debug(
            f"TestDiscoveryView: _on_tree_item_clicked - Index: row {index.row()}, col {index.column()}."
        )
        file_path = self._get_file_path_from_index(index)
        if file_path:
            from pathlib import Path

            # Check if the path seems like a Python file before emitting
            # This is a basic check; more robust validation might be needed depending on node_id structure
            if Path(file_path).suffix == ".py":
                logger.info(f"TestDiscoveryView: Emitting test_file_selected for: {file_path}")
                self.test_file_selected.emit(file_path)
            else:
                logger.debug(
                    f"TestDiscoveryView: Extracted path {file_path} is not a .py file, not emitting test_file_selected."
                )
        else:
            logger.debug(
                "TestDiscoveryView: No valid file path extracted from clicked item, not emitting test_file_selected."
            )

    def _on_item_changed(self, item: QStandardItem) -> None:
        """Handle item check state changes to propagate to children/parents."""
        if self._block_item_changed_signal or not item.isCheckable():
            # logger.debug(f"TestDiscoveryView: _on_item_changed skipped. Blocked: {self._block_item_changed_signal}, Not Checkable: {not item.isCheckable()}. Item: {item.text()}")
            return

        logger.debug(
            f"TestDiscoveryView: _on_item_changed. Item: '{item.text()}', CheckState: {item.checkState()}."
        )
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
        self._update_selected_tests_count_label()
        logger.debug(
            f"TestDiscoveryView: Item change propagation complete for '{item.text()}'. Emitting selection_changed signal."
        )
        self.selection_changed.emit()

    def _update_selected_tests_count_label(self) -> None:
        """Updates the label showing the count of selected tests for running."""
        if hasattr(self, "selected_tests_label"):
            count = len(
                self.get_selected_node_ids(silent=True)
            )  # Use silent to avoid verbose logging from get_selected_node_ids
            self.selected_tests_label.setText(f"Selected for run: {count} tests")
            logger.debug(
                f"TestDiscoveryView: Updated selected tests count label to: {count} tests."
            )
        else:
            logger.warning(
                "TestDiscoveryView: selected_tests_label not found, cannot update count."
            )

    def _update_parent_check_state(self, parent_item: QStandardItem) -> None:
        """Update parent's check state based on its children's states."""
        if not parent_item or not (parent_item.flags() & Qt.ItemFlag.ItemIsUserCheckable):
            return
        # logger.debug(f"TestDiscoveryView: Updating parent check state for '{parent_item.text()}'.") # Can be noisy
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

    def get_selected_node_ids(self, silent: bool = False) -> List[str]:
        """
        Returns a list of node IDs for all checked test items (functions/methods).
        Args:
            silent: If True, suppress debug logging for this call.
        """
        if not silent:
            logger.debug("TestDiscoveryView: get_selected_node_ids called.")
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
        if not silent:
            logger.debug(
                f"TestDiscoveryView: Found {len(selected_ids)} selected node IDs: {selected_ids if len(selected_ids) < 5 else str(selected_ids[:5]) + '...'}"
            )
        return selected_ids

    def clear_tree(self) -> None:
        logger.debug("TestDiscoveryView: Clearing tree.")
        self._block_item_changed_signal = True
        self.test_tree_model.clear()
        self.test_tree_model.setHorizontalHeaderLabels(["Test / Module / Class", "Node ID"])
        self._block_item_changed_signal = False
        # self._filter_proxy_model = None # QSortFilterProxyModel is not currently used.
        self._update_selected_tests_count_label()
        logger.debug("TestDiscoveryView: Tree cleared.")

    def _apply_filter(self, text: str) -> None:
        """Filters the tree view based on the input text."""
        logger.debug(f"TestDiscoveryView: Applying filter with text: '{text}'.")
        filter_text = text.lower()
        self._filter_recursive(self.test_tree_model.invisibleRootItem(), filter_text)
        logger.debug("TestDiscoveryView: Filter application complete.")

    def _filter_recursive(self, parent_item: QStandardItem, filter_text: str) -> bool:
        # This is recursive and can be noisy. Log entry/exit or key decisions.
        # current_item_text = parent_item.text() if parent_item.index().isValid() else "InvisibleRoot"
        # logger.debug(f"TestDiscoveryView: Filtering recursively. Item: '{current_item_text}', Filter: '{filter_text}'.")
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

        return should_be_visible  # should_be_visible defined in original code
