"""Test output view for displaying real-time test execution output."""

from typing import Optional

from rich.syntax import Syntax
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button, Label, ProgressBar, RichLog, Static


class OutputCleared(Message):
    """Message posted when output is cleared."""

    pass


class TestOutputView(Widget):
    """A view for displaying real-time test execution output."""

    DEFAULT_CSS = """
    TestOutputView {
        layout: vertical;
        overflow-y: auto;
        padding: 1;
        border: round $primary;
        height: auto;
    }

    RichLog {
        height: 1fr;
        border: round $background-darken-2;
        margin-top: 1;
        margin-bottom: 1;
    }

    ProgressBar {
        margin-top: 1;
        margin-bottom: 1;
    }

    .status-info {
        background: $background-lighten-1;
        padding: 1;
        margin-bottom: 1;
        border: round $accent;
    }
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._is_running = False
        self._current_progress = 0.0
        self._total_tests = 0
        self._completed_tests = 0

    def compose(self) -> ComposeResult:
        """Create child widgets for the test output view."""
        yield Label("Test Execution Output", classes="header")

        with Vertical():
            # Status information
            with Vertical(classes="status-info"):
                yield Static("Status: Ready", id="execution_status")
                yield Static("Progress: 0/0 tests", id="test_progress_text")
                yield ProgressBar(id="test_progress_bar", show_eta=False)

            # Control buttons
            with Horizontal():
                yield Button(
                    "Clear Output", id="clear_output_button", variant="warning"
                )
                yield Button("Save Output", id="save_output_button", variant="primary")
                yield Button(
                    "Stop Execution", id="stop_execution_button", variant="error"
                )

            # Output log
            yield RichLog(id="output_log", highlight=True, markup=True)

    def on_mount(self) -> None:
        """Set up the test output view when mounted."""
        progress_bar = self.query_one("#test_progress_bar", ProgressBar)
        progress_bar.update(total=100, progress=0)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses in the output view."""
        if event.button.id == "clear_output_button":
            self._clear_output()
        elif event.button.id == "save_output_button":
            await self._save_output()
        elif event.button.id == "stop_execution_button":
            await self._stop_execution()

    def _clear_output(self) -> None:
        """Clear the output log."""
        log = self.query_one("#output_log", RichLog)
        log.clear()

        # Reset status
        self._reset_status()
        self.post_message(OutputCleared())
        self.app.notify("Output cleared")

    async def _save_output(self) -> None:
        """Save the current output to a file."""
        try:
            # In a real implementation, this would open a file dialog
            # For now, just notify the user
            self.app.notify(
                "Output save feature not yet implemented", severity="warning"
            )
        except Exception as e:
            self.app.notify(f"Failed to save output: {e}", severity="error")

    async def _stop_execution(self) -> None:
        """Stop the current test execution."""
        if self._is_running:
            try:
                # Signal the test execution controller to stop
                if hasattr(self.app, "test_execution_controller"):
                    await self.app.run_sync_in_worker(
                        self.app.test_execution_controller.stop_execution
                    )
                else:
                    self.app.notify(
                        "Test execution controller not available", severity="warning"
                    )
            except Exception as e:
                self.app.notify(f"Failed to stop execution: {e}", severity="error")
        else:
            self.app.notify("No test execution is currently running", severity="info")

    def start_execution(self, total_tests: int = 0) -> None:
        """Start tracking test execution progress."""
        self._is_running = True
        self._total_tests = total_tests
        self._completed_tests = 0
        self._current_progress = 0.0

        # Update status
        status = self.query_one("#execution_status", Static)
        status.update("Status: Running tests...")

        progress_text = self.query_one("#test_progress_text", Static)
        progress_text.update(f"Progress: 0/{total_tests} tests")

        progress_bar = self.query_one("#test_progress_bar", ProgressBar)
        progress_bar.update(total=total_tests or 100, progress=0)

        # Add start message to log
        log = self.query_one("#output_log", RichLog)
        log.write(Text("🚀 Starting test execution...", style="bold green"))

    def update_progress(self, completed: int, total: Optional[int] = None) -> None:
        """Update the test execution progress."""
        if total is not None:
            self._total_tests = total
        self._completed_tests = completed

        # Update progress text
        progress_text = self.query_one("#test_progress_text", Static)
        progress_text.update(f"Progress: {completed}/{self._total_tests} tests")

        # Update progress bar
        progress_bar = self.query_one("#test_progress_bar", ProgressBar)
        if self._total_tests > 0:
            progress_bar.update(progress=completed)
            self._current_progress = (completed / self._total_tests) * 100
        else:
            # Indeterminate progress
            progress_bar.update(progress=completed % 100)

    def finish_execution(self, success: bool = True) -> None:
        """Mark test execution as finished."""
        self._is_running = False

        # Update status
        status = self.query_one("#execution_status", Static)
        if success:
            status.update("Status: ✅ Execution completed")
        else:
            status.update("Status: ❌ Execution failed")

        # Add completion message to log
        log = self.query_one("#output_log", RichLog)
        if success:
            log.write(
                Text("✅ Test execution completed successfully!", style="bold green")
            )
        else:
            log.write(
                Text("❌ Test execution completed with errors!", style="bold red")
            )

    def add_output_line(self, line: str, output_type: str = "stdout") -> None:
        """Add a line of output to the log."""
        log = self.query_one("#output_log", RichLog)

        # Format the line based on output type
        if output_type == "stderr":
            formatted_line = Text(line, style="red")
        elif output_type == "error":
            formatted_line = Text(line, style="bold red")
        elif output_type == "success":
            formatted_line = Text(line, style="green")
        elif output_type == "warning":
            formatted_line = Text(line, style="yellow")
        else:
            # Try to detect pytest output patterns for coloring
            if "PASSED" in line:
                formatted_line = Text(line, style="green")
            elif "FAILED" in line:
                formatted_line = Text(line, style="red")
            elif "ERROR" in line:
                formatted_line = Text(line, style="bold red")
            elif "SKIPPED" in line:
                formatted_line = Text(line, style="yellow")
            elif line.startswith("==="):
                formatted_line = Text(line, style="bold blue")
            else:
                formatted_line = Text(line)

        log.write(formatted_line)

    def add_code_output(self, code: str, language: str = "python") -> None:
        """Add syntax-highlighted code to the output."""
        log = self.query_one("#output_log", RichLog)

        try:
            syntax = Syntax(
                code, language, theme="monokai", line_numbers=True, word_wrap=True
            )
            log.write(syntax)
        except Exception:
            # Fallback to plain text if syntax highlighting fails
            log.write(Text(code))

    def _reset_status(self) -> None:
        """Reset the view to initial state."""
        self._is_running = False
        self._current_progress = 0.0
        self._total_tests = 0
        self._completed_tests = 0

        # Update UI elements
        status = self.query_one("#execution_status", Static)
        status.update("Status: Ready")

        progress_text = self.query_one("#test_progress_text", Static)
        progress_text.update("Progress: 0/0 tests")

        progress_bar = self.query_one("#test_progress_bar", ProgressBar)
        progress_bar.update(total=100, progress=0)

    def is_execution_running(self) -> bool:
        """Check if test execution is currently running."""
        return self._is_running
