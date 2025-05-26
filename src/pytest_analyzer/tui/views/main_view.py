from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Placeholder, Static


class MainView(Screen):
    """The main screen for the Pytest Analyzer TUI."""

    BINDINGS = [
        ("q", "quit", "Quit"),
        # Add other global bindings here
    ]

    def compose(self) -> ComposeResult:
        """Create child widgets for the main view."""
        yield Header()

        # Main layout
        with Horizontal(id="main_horizontal_layout"):
            with Vertical(id="left_panel", classes="panel"):
                yield Placeholder("File Selection / Test Discovery", id="file_discovery_view")
            with Vertical(id="center_panel", classes="panel"):
                yield Placeholder("Test Results / Analysis", id="results_analysis_view")
            with Vertical(id="right_panel", classes="panel"):
                yield Placeholder("Code Editor / Details", id="details_code_view")

        yield Static("Status messages will appear here...", id="status_bar")
        yield Footer()

    # Action handlers can be added here, e.g.:
    # def action_quit(self) -> None:
    #     self.app.exit()
