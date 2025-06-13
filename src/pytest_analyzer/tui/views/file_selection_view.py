from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button, DirectoryTree, Input, Label, Static


class FileSelected(Message):
    """Message posted when a file is selected."""

    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path
        super().__init__()


class FileSelectionView(Widget):
    """A view for selecting files or directories."""

    DEFAULT_CSS = """
    FileSelectionView {
        layout: vertical;
        overflow-y: auto;
        padding: 1;
        height: auto;
    }

    DirectoryTree {
        padding: 1;
        min-height: 15;
        border: round $background-darken-2;
        margin-top: 1;
        margin-bottom: 1;
    }

    Input {
        margin-bottom: 1;
    }

    .file-info {
        background: $background-lighten-1;
        padding: 1;
        margin-bottom: 1;
        border: round $accent;
        height: auto;
    }
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._current_path: Path = Path(".")

    def compose(self) -> ComposeResult:
        """Create child widgets for the file selection view."""
        yield Label("File Selection", classes="header")

        with Vertical():
            yield Label("Selected Path:")
            yield Input(placeholder="Enter path or select from tree", id="path_input")

            with Horizontal():
                yield Button("Load File", id="load_file_button", variant="primary")
                yield Button(
                    "Load Directory", id="load_directory_button", variant="primary"
                )
                yield Button("Browse", id="browse_button", variant="default")

            # File information display
            with Vertical(classes="file-info"):
                yield Static("Current Path: .", id="current_path_display")
                yield Static("Type: None", id="file_type_display")
                yield Static("Status: Ready", id="file_status_display")

            yield Label("Directory Tree:")
            yield DirectoryTree(".", id="directory_tree")

    def on_mount(self) -> None:
        """Set up the file selection view when mounted."""
        self._update_path_display()

    async def on_directory_tree_file_selected(
        self, event: DirectoryTree.FileSelected
    ) -> None:
        """Handle file selection in the directory tree."""
        path_input = self.query_one("#path_input", Input)
        path_input.value = str(event.path)
        self._current_path = event.path
        self._update_path_display()

    async def on_directory_tree_directory_selected(
        self, event: DirectoryTree.DirectorySelected
    ) -> None:
        """Handle directory selection in the directory tree."""
        path_input = self.query_one("#path_input", Input)
        path_input.value = str(event.path)
        self._current_path = event.path
        self._update_path_display()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses in the file selection view."""
        if event.button.id == "load_file_button":
            await self._load_file()
        elif event.button.id == "load_directory_button":
            await self._load_directory()
        elif event.button.id == "browse_button":
            await self._browse_path()

    async def _load_file(self) -> None:
        """Load the selected file."""
        path_input = self.query_one("#path_input", Input)
        selected_path = path_input.value.strip()

        if not selected_path:
            self.app.notify("No path entered or selected", severity="warning")
            return

        file_path = Path(selected_path)

        if not file_path.exists():
            self.app.notify(f"Path does not exist: {file_path}", severity="error")
            return

        if not file_path.is_file():
            self.app.notify("Selected path is not a file", severity="warning")
            return

        try:
            # Use the app's file controller to load the file
            if hasattr(self.app, "file_controller"):
                # Call controller directly (load_file is already a sync method)
                self.app.file_controller.load_file(file_path)
                self.post_message(FileSelected(file_path))
                self._update_status(f"✅ Loaded: {file_path.name}")
            else:
                self.app.notify("File controller not available", severity="warning")
        except Exception as e:
            self.app.notify(f"Failed to load file: {e}", severity="error")
            self._update_status("❌ Load failed")

    async def _load_directory(self) -> None:
        """Load tests from the selected directory."""
        path_input = self.query_one("#path_input", Input)
        selected_path = path_input.value.strip()

        if not selected_path:
            self.app.notify("No path entered or selected", severity="warning")
            return

        dir_path = Path(selected_path)

        if not dir_path.exists():
            self.app.notify(f"Path does not exist: {dir_path}", severity="error")
            return

        if not dir_path.is_dir():
            self.app.notify("Selected path is not a directory", severity="warning")
            return

        try:
            # Use the app's file controller to load the directory
            if hasattr(self.app, "file_controller"):
                await self.app.run_sync_in_worker(
                    self.app.file_controller.load_directory, dir_path
                )
                self._update_status(f"✅ Loaded directory: {dir_path.name}")
            else:
                self.app.notify("File controller not available", severity="warning")
        except Exception as e:
            self.app.notify(f"Failed to load directory: {e}", severity="error")
            self._update_status("❌ Directory load failed")

    async def _browse_path(self) -> None:
        """Browse to the path in the input field."""
        path_input = self.query_one("#path_input", Input)
        selected_path = path_input.value.strip()

        if not selected_path:
            selected_path = "."

        browse_path = Path(selected_path)

        if browse_path.exists() and browse_path.is_dir():
            # Update the directory tree to show the selected path
            tree = self.query_one("#directory_tree", DirectoryTree)
            tree.path = browse_path
            self._current_path = browse_path
            self._update_path_display()
            self.app.notify(f"Browsed to: {browse_path}")
        else:
            self.app.notify("Invalid directory path", severity="warning")

    def _update_path_display(self) -> None:
        """Update the path information display."""
        path_display = self.query_one("#current_path_display", Static)
        path_display.update(f"Current Path: {self._current_path}")

        type_display = self.query_one("#file_type_display", Static)
        if self._current_path.is_file():
            if self._current_path.suffix in [".json", ".xml"]:
                type_display.update(f"Type: Test Report ({self._current_path.suffix})")
            elif self._current_path.suffix == ".py":
                type_display.update("Type: Python Test File")
            else:
                type_display.update(f"Type: File ({self._current_path.suffix})")
        elif self._current_path.is_dir():
            type_display.update("Type: Directory")
        else:
            type_display.update("Type: Unknown")

    def _update_status(self, status: str) -> None:
        """Update the status display."""
        status_display = self.query_one("#file_status_display", Static)
        status_display.update(f"Status: {status}")

    def set_path(self, path: Path) -> None:
        """Set the current path programmatically."""
        self._current_path = path
        path_input = self.query_one("#path_input", Input)
        path_input.value = str(path)
        self._update_path_display()
