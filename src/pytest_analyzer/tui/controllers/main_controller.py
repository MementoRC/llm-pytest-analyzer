from typing import TYPE_CHECKING

from .base_controller import BaseController
from .file_controller import FileController
# from .test_execution_controller import TestExecutionController # If you create this
from .test_results_controller import TestResultsController

if TYPE_CHECKING:
    from ..app import TUIApp


class MainController(BaseController):
    """
    Main TUI controller to orchestrate other controllers and overall TUI logic.
    """

    def __init__(self, app: "TUIApp"):
        super().__init__(app)
        self.logger.info("MainControllerTUI initializing...")

        # Initialize other controllers
        # These controllers will need access to the app instance to interact
        # with services, other controllers, or post messages.
        self.file_controller = FileController(app=app)
        self.test_results_controller = TestResultsController(app=app)
        # self.test_execution_controller = TestExecutionController(app=app) # Example

        self._connect_signals() # Or setup message handlers
        self.logger.info("MainControllerTUI initialized.")

    def _connect_signals(self) -> None:
        """
        In a TUI context, this might involve setting up how controllers
        communicate, perhaps by passing references or relying on Textual's
        message passing system.
        """
        self.logger.debug("Setting up TUI controller interactions.")

        # Example: If TestResultsController needs a reference to TestExecutionController
        # (similar to the GUI version for get_last_failures)
        # self.test_results_controller.set_test_execution_controller(self.test_execution_controller)

        # Unlike Qt's signal/slot, Textual uses a message bubbling system.
        # Controllers can post messages that the App or other widgets can handle.
        # Alternatively, controllers can call methods on each other directly if appropriate.

        # For instance, when FileController parses a report, it might call a method
        # on TestResultsController to load the data, or post a message that
        # TestResultsController (or the App/Screen) listens for.

        # Example of direct call setup (if FileController needs to inform TestResultsController):
        # self.file_controller.report_parsed_handler = self.test_results_controller.load_report_data

        pass

    async def on_startup(self) -> None:
        """
        Called when the TUI app is ready.
        Perform initial setup, load initial data, etc.
        """
        self.logger.info("TUI MainController handling startup.")
        # Example: Load last session, or default view
        # await self.file_controller.load_default_or_last_path()

    # Add other methods to handle global commands or coordinate actions
    # For example, handling a "quit" action if not managed by App directly.

    # Example of a handler for a custom Textual Message
    # async def on_custom_message(self, message: CustomMessage) -> None:
    #     self.logger.debug(f"MainController received: {message}")
    #     # Process message and delegate to other controllers or views
