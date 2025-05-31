"""Test discovery view for the TUI interface."""

import subprocess
from pathlib import Path
from typing import Dict, List

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button, DataTable, Input, Label, Tree


class TestSelected(Message):
    """Message posted when a test is selected."""

    def __init__(self, test_path: str) -> None:
        self.test_path = test_path
        super().__init__()


class TestDiscoveryView(Widget):
    """A view for discovering and selecting tests."""

    DEFAULT_CSS = """
    TestDiscoveryView {
        layout: vertical;
        overflow-y: auto;
        padding: 1;
        border: round $primary;
        height: auto;
    }

    Tree {
        height: 1fr;
        margin-top: 1;
        margin-bottom: 1;
    }

    DataTable {
        height: 10;
        margin-top: 1;
    }
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._discovered_tests: List[str] = []
        self._test_info: Dict[str, Dict] = {}  # Store detailed test info

    def compose(self) -> ComposeResult:
        """Create child widgets for the test discovery view."""
        yield Label("Test Discovery", classes="header")

        with Vertical():
            yield Input(
                placeholder="Enter test path or pattern", id="test_pattern_input"
            )

            with Horizontal():
                yield Button("Discover Tests", id="discover_button", variant="primary")
                yield Button(
                    "Run Selected", id="run_selected_button", variant="success"
                )

            yield Label("Discovered Tests:")
            yield Tree("Tests", id="test_tree")

            yield Label("Test Files:")
            yield DataTable(id="test_files_table")

    def on_mount(self) -> None:
        """Set up the test discovery view when mounted."""
        # Initialize the test files table
        table = self.query_one("#test_files_table", DataTable)
        table.add_columns("File", "Tests", "Status")

        # Initialize empty tree
        tree = self.query_one("#test_tree", Tree)
        tree.show_root = False

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses in the discovery view."""
        if event.button.id == "discover_button":
            await self._discover_tests()
        elif event.button.id == "run_selected_button":
            await self._run_selected_tests()

    async def _discover_tests(self) -> None:
        """Discover tests in the specified path."""
        pattern_input = self.query_one("#test_pattern_input", Input)
        test_pattern = pattern_input.value or "."

        self.app.notify("Discovering tests...")

        try:
            # Run test discovery in worker thread
            test_info = await self.app.run_sync_in_worker(
                self._run_pytest_collect, test_pattern
            )

            if test_info:
                self._test_info = test_info
                self._update_views_with_discovered_tests()
            else:
                self.app.notify("No tests found", severity="warning")

        except Exception as e:
            self.app.logger.error(f"Test discovery failed: {e}", exc_info=True)
            self.app.notify(f"Test discovery failed: {e}", severity="error")

    async def _run_selected_tests(self) -> None:
        """Run the selected tests."""
        if not self._discovered_tests:
            self.app.notify("No tests discovered to run", severity="warning")
            return

        try:
            # Get the current test selection - for now use the first discovered test
            test_target = self._discovered_tests[0] if self._discovered_tests else None

            if test_target and hasattr(self.app, "test_execution_controller"):
                # Set the test target and execute (use sync method for test compatibility)
                self.app.test_execution_controller.set_test_target(test_target)
                self.app.test_execution_controller.execute_tests(test_target)
            else:
                self.app.notify(
                    "Test execution controller not available", severity="warning"
                )

        except Exception as e:
            self.app.logger.error(f"Test execution failed: {e}", exc_info=True)
            self.app.notify(f"Test execution failed: {e}", severity="error")

    def _run_pytest_collect(self, test_path: str) -> Dict[str, Dict]:
        """Run pytest --collect-only to discover tests."""
        try:
            # Run pytest collection
            result = subprocess.run(
                ["python", "-m", "pytest", "--collect-only", "-q", test_path],
                capture_output=True,
                text=True,
                cwd=Path.cwd(),
            )

            test_info = {}

            if result.returncode == 0:
                # Parse the output to extract test information
                lines = result.stdout.strip().split("\n")
                current_file = None

                for line in lines:
                    line = line.strip()
                    if "::" in line and "test_" in line:
                        # This is a test item like "test_file.py::TestClass::test_method"
                        parts = line.split("::")
                        if len(parts) >= 2:
                            file_part = parts[0]
                            test_name = "::".join(parts[1:])

                            if file_part not in test_info:
                                test_info[file_part] = {
                                    "file": file_part,
                                    "tests": [],
                                    "count": 0,
                                }

                            test_info[file_part]["tests"].append(test_name)
                            test_info[file_part]["count"] += 1
                    elif line.endswith(".py") and "::" not in line:
                        # This might be a file without tests
                        current_file = line
                        if current_file not in test_info:
                            test_info[current_file] = {
                                "file": current_file,
                                "tests": [],
                                "count": 0,
                            }

            return test_info

        except Exception as e:
            self.app.logger.error(f"Error running pytest collect: {e}", exc_info=True)
            return {}

    def _update_views_with_discovered_tests(self) -> None:
        """Update the tree and table with discovered test information."""
        if not self._test_info:
            return

        # Extract file list for backward compatibility
        self._discovered_tests = list(self._test_info.keys())

        # Update the tree
        tree = self.query_one("#test_tree", Tree)
        tree.clear()

        for file_path, info in self._test_info.items():
            file_node = tree.root.add(Path(file_path).name, data=file_path)

            # Add individual tests as children
            for test_name in info["tests"]:
                file_node.add_leaf(test_name, data=f"{file_path}::{test_name}")

        # Update the table
        table = self.query_one("#test_files_table", DataTable)
        table.clear()

        for file_path, info in self._test_info.items():
            test_count = info["count"]
            status = "Ready" if test_count > 0 else "No tests"

            table.add_row(
                Path(file_path).name,
                str(test_count),
                status,
                key=file_path,
            )

        total_files = len(self._test_info)
        total_tests = sum(info["count"] for info in self._test_info.values())
        self.app.notify(f"Discovered {total_files} files with {total_tests} tests")

    def update_discovered_tests(self, test_files: List[str]) -> None:
        """Update the view with discovered tests (legacy method for compatibility)."""
        # Convert to the new format
        self._test_info = {}
        for test_file in test_files:
            self._test_info[test_file] = {"file": test_file, "tests": [], "count": 0}
        self._update_views_with_discovered_tests()

    async def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle test file selection in the tree."""
        if event.node.data:
            test_path = str(event.node.data)
            self.post_message(TestSelected(test_path))

            # Set the test target in the execution controller
            if hasattr(self.app, "test_execution_controller"):
                self.app.test_execution_controller.set_test_target(test_path)

            # Show selection feedback
            if "::" in test_path:
                # Individual test selected
                self.app.notify(f"Selected test: {test_path.split('::')[-1]}")
            else:
                # File selected
                self.app.notify(f"Selected file: {Path(test_path).name}")

    async def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle test file selection in the table."""
        if event.row_key and event.row_key.value:
            test_file = str(event.row_key.value)
            self.post_message(TestSelected(test_file))

            # Set the test target in the execution controller
            if hasattr(self.app, "test_execution_controller"):
                self.app.test_execution_controller.set_test_target(test_file)

            self.app.notify(f"Selected file: {Path(test_file).name}")
