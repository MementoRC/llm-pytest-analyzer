from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import Button, DirectoryTree, Input, Label


class FileSelectionView(Widget):
    """A view for selecting files or directories."""

    DEFAULT_CSS = """
    FileSelectionView {
        layout: vertical;
        overflow-y: auto;
        padding: 1;
        border: round $primary;
        height: auto;
    }
    DirectoryTree {
        padding: 1;
        min-height: 10;
        border: round $background-darken-2;
    }
    Input {
        margin-bottom: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Label("Selected Path:")
        yield Input(placeholder="Enter path or select from tree", id="path_input")
        yield DirectoryTree(".", id="directory_tree")
        with Vertical():
            yield Button("Load Path", id="load_path_button", variant="primary")
            # Add more buttons if needed, e.g., for report types

    async def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        """Handle file selection in the directory tree."""
        path_input = self.query_one("#path_input", Input)
        path_input.value = str(event.path)
        # Optionally, post a message or call a controller method
        # self.post_message(self.FileSelected(str(event.path)))

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "load_path_button":
            path_input = self.query_one("#path_input", Input)
            selected_path = path_input.value
            if selected_path:
                # Post a message to be handled by a controller
                # from ..messages import PathSelected
                # self.post_message(PathSelected(selected_path))
                self.app.logger.info(f"Path selected for loading: {selected_path}")
                # This would typically call a controller method.
                # For now, just log.
                # Example: self.app.file_controller.on_path_selected(Path(selected_path))
                pass
            else:
                self.app.notify("No path entered or selected.", severity="warning")
