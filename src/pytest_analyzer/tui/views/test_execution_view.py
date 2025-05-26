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
            log_widget.write_line("Preparing to start test execution...")
            progress_bar = self.query_one(ProgressBar)
            progress_bar.progress = 0
            progress_bar.visible = True

            current_test_target = getattr(self.app, "current_test_target", None)
            if not current_test_target:
                log_widget.write_line("[bold red]Error: Test target not set in the app.[/bold red]")
                self.app.notify("Error: Test target not set.", severity="error")
                # Optionally disable button or hide progress bar again
                progress_bar.visible = False
                return

            log_widget.write_line(f"Target for execution: {current_test_target}")

            if hasattr(self.app, "test_execution_controller") and hasattr(
                self.app.test_execution_controller, "execute_tests"
            ):
                # The TestExecutionController.execute_tests handles UI updates
                # like log clearing, progress, and button disabling.
                # So, we don't need to duplicate that here.
                # It will also re-enable the button in its finally block.
                await self.app.test_execution_controller.execute_tests(str(current_test_target))
            else:
                log_widget.write_line(
                    "[bold red]Error: TestExecutionController not available or 'execute_tests' method missing.[/bold red]"
                )
                self.app.notify("Test execution controller not configured.", severity="error")
                progress_bar.visible = False  # Hide progress bar as execution cannot start

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
