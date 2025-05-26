from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Button, Label, Log, ProgressBar


class TestExecutionView(Widget):
    """A view for controlling and monitoring test execution."""

    DEFAULT_CSS = """
    TestExecutionView {
        layout: vertical;
        padding: 1;
        border: round $primary;
        height: auto;
    }
    #run_tests_button {
        width: 100%;
        margin-bottom: 1;
    }
    ProgressBar {
        margin-bottom: 1;
        width: 100%;
        height: auto; /* Or specific height */
    }
    Log {
        height: 1fr; /* Take remaining space */
        border: round $background-darken-2;
    }
    """

    def compose(self) -> ComposeResult:
        yield Label("Test Execution:")
        yield Button("Run Tests", id="run_tests_button", variant="success")
        yield ProgressBar(total=100, show_eta=False, id="test_progress_bar")
        yield Label("Execution Log:")
        yield Log(id="execution_log", highlight=True, markup=True)

    def on_mount(self) -> None:
        # Initialize progress bar (e.g., hide or set to 0)
        progress_bar = self.query_one(ProgressBar)
        progress_bar.visible = False  # Hide until tests run

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "run_tests_button":
            self.app.logger.info("Run Tests button clicked (TUI).")
            log_widget = self.query_one(Log)
            log_widget.clear()
            log_widget.write_line("Starting test execution...")
            progress_bar = self.query_one(ProgressBar)
            progress_bar.progress = 0
            progress_bar.visible = True
            # This would typically call a controller method to start tests
            # Example: await self.app.test_execution_controller.run_tests()
            # For now, simulate some progress
            for i in range(101):
                await self.app.workers.sleep(0.05)  # Simulate work
                progress_bar.advance(1)
                if i % 10 == 0:
                    log_widget.write_line(f"Test progress: {i}%")
            log_widget.write_line("[green]Test execution finished (simulated).[/green]")

    def update_progress(self, current: float, total: float, description: str = "") -> None:
        progress_bar = self.query_one(ProgressBar)
        progress_bar.total = total
        progress_bar.progress = current
        if description:
            # Textual's ProgressBar doesn't have a text description area by default like Rich.
            # You might need a separate Label widget if you want to display this.
            pass

    def add_log_message(self, message: str) -> None:
        log_widget = self.query_one(Log)
        log_widget.write_line(message)
