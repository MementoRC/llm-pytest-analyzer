import logging
from pathlib import Path
from typing import Any, Optional

from rich.logging import RichHandler
from textual.app import App, ComposeResult
from textual.binding import Binding

from ..core.analyzer_service import PytestAnalyzerService
from ..utils.settings import Settings, load_settings
from .views.main_view import MainView

# Configure logging for the TUI
# This should be configured early, possibly before other imports
# if they also use logging.
tui_logger = logging.getLogger("pytest_analyzer.tui")


class TUIApp(App):
    """The main application class for the Pytest Analyzer TUI."""

    TITLE = "Pytest Analyzer TUI"
    CSS_PATH = "app.tcss"  # Placeholder for TUI styling
    SCREENS = {"main": MainView}

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", show=True, priority=True),
    ]

    def __init__(
        self,
        settings: Optional[Settings] = None,
        analyzer_service: Optional[PytestAnalyzerService] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.settings = settings or load_settings()
        self.analyzer_service = analyzer_service or PytestAnalyzerService(settings=self.settings)
        self.logger = tui_logger  # Use the pre-configured logger

        # Placeholder for controllers and other TUI specific components
        # self.main_controller: Optional[MainController] = None

        self._configure_logging()

    def _configure_logging(self) -> None:
        """Configure Rich logging handler for the TUI."""
        # If logging is already configured by CLI or another part, this might need adjustment.
        # For TUI, we want RichHandler if possible.
        # This setup assumes TUI is the primary entry point or wants to override.
        if not any(isinstance(h, RichHandler) for h in logging.getLogger("pytest_analyzer").handlers):
            # Configure root logger for pytest_analyzer package
            package_logger = logging.getLogger("pytest_analyzer")
            package_logger.setLevel(self.settings.log_level.upper() if hasattr(self.settings, 'log_level') else "INFO") # TODO: Add log_level to Settings

            # Remove existing handlers if any, to replace with RichHandler
            for handler in package_logger.handlers[:]:
                package_logger.removeHandler(handler)

            rich_handler = RichHandler(rich_tracebacks=True, show_path=False)
            rich_handler.setFormatter(logging.Formatter("%(name)s: %(message)s")) # Simpler format for TUI
            package_logger.addHandler(rich_handler)
            self.logger.info("Rich logging configured for TUI.")
        else:
            self.logger.info("Logging seems to be already configured.")


    def on_mount(self) -> None:
        """Called when the app is first mounted."""
        self.logger.info("TUIApp mounted. Pushing main screen.")
        self.push_screen("main")
        # Initialize controllers here if needed
        # self.main_controller = MainController(self)

    # Example action
    # def action_show_settings(self) -> None:
    #     """Action to show a settings screen (placeholder)."""
    #     self.logger.info("Action: Show Settings triggered.")
    #     # self.push_screen(SettingsScreen()) # Example

    def run_sync_in_worker(self, func, *args, **kwargs):
        """
        Helper to run synchronous code in a Textual worker thread.
        This is a simplified version.
        """
        # This is a basic way to run sync code. For more complex scenarios,
        # Textual's worker system offers more control.
        import asyncio
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(None, lambda: func(*args, **kwargs))


def run_tui() -> None:
    """Entry point function to run the TUI application."""
    # Basic logging setup for when TUI is run directly
    # This might be overridden if TUIApp._configure_logging is more sophisticated
    logging.basicConfig(
        level="INFO",
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[RichHandler(rich_tracebacks=True)],
    )
    tui_logger.info("Starting Pytest Analyzer TUI...")
    app = TUIApp()
    app.run()


if __name__ == "__main__":
    # This allows running the TUI directly for development
    run_tui()
