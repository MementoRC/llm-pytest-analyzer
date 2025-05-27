from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Static, TabbedContent, TabPane

from .analysis_results_view import AnalysisResultsView
from .file_selection_view import FileSelectionView
from .test_discovery_view import TestDiscoveryView
from .test_execution_view import TestExecutionView
from .test_output_view import TestOutputView
from .test_results_view import TestResultsView


class MainView(Screen):
    """The main screen for the Pytest Analyzer TUI."""

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("f1", "show_help", "Help"),
        ("ctrl+o", "open_file", "Open File"),
        ("ctrl+r", "run_tests", "Run Tests"),
    ]

    CSS = """
    .panel {
        border: round $primary;
        margin: 1;
        padding: 1;
    }

    #left_panel {
        width: 1fr;
        min-width: 30;
    }

    #center_panel {
        width: 2fr;
        min-width: 40;
    }

    #right_panel {
        width: 1fr;
        min-width: 30;
    }

    #status_bar {
        background: $background-lighten-1;
        color: $text;
        height: 1;
        content-align: center middle;
    }
    """

    def compose(self) -> ComposeResult:
        """Create child widgets for the main view."""
        yield Header()

        # Main layout with three panels
        with Horizontal(id="main_horizontal_layout"):
            # Left panel: File selection and test discovery
            with Vertical(id="left_panel", classes="panel"):
                with TabbedContent(initial="file_selection"):
                    with TabPane("Files", id="file_selection"):
                        yield FileSelectionView(id="file_selection_view")
                    with TabPane("Tests", id="test_discovery"):
                        yield TestDiscoveryView(id="test_discovery_view")

            # Center panel: Test results and analysis
            with Vertical(id="center_panel", classes="panel"):
                with TabbedContent(initial="test_results"):
                    with TabPane("Results", id="test_results"):
                        yield TestResultsView(id="test_results_view")
                    with TabPane("Analysis", id="analysis_results"):
                        yield AnalysisResultsView(id="analysis_results_view")

            # Right panel: Test execution and output
            with Vertical(id="right_panel", classes="panel"):
                with TabbedContent(initial="test_execution"):
                    with TabPane("Execute", id="test_execution"):
                        yield TestExecutionView(id="test_execution_view")
                    with TabPane("Output", id="test_output"):
                        yield TestOutputView(id="test_output_view")

        yield Static("Ready - Select files or discover tests to begin", id="status_bar")
        yield Footer()

    def action_show_help(self) -> None:
        """Show help information."""
        self.app.notify("Help: F1=Help, Ctrl+O=Open File, Ctrl+R=Run Tests, Q=Quit")

    def action_open_file(self) -> None:
        """Trigger file opening action."""
        # Focus on the file selection tab
        self.query_one("#file_selection_view", FileSelectionView).focus()
        self.app.notify("File selection focused - enter path or use directory tree")

    def action_run_tests(self) -> None:
        """Trigger test execution action."""
        # Focus on the test execution tab
        self.query_one("#test_execution_view", TestExecutionView).focus()
        self.app.notify("Test execution focused - configure and run tests")

    def update_status(self, message: str) -> None:
        """Update the status bar message."""
        status_bar = self.query_one("#status_bar", Static)
        status_bar.update(message)
