from typing import TYPE_CHECKING, Any, Callable, Optional

if TYPE_CHECKING:
    from ..app import TUIApp


class BaseController:
    """
    Abstract base class for TUI controllers.

    Controllers are responsible for handling user input, interacting with
    core services, and updating the TUI views/models.
    """

    def __init__(self, app: "TUIApp") -> None:
        self.app = app
        self.logger = self.app.logger.getChild(self.__class__.__name__)
        self.logger.info(f"{self.__class__.__name__} initialized")

    async def handle_event(self, event: Any) -> None:
        """
        Placeholder for handling TUI events.
        Subclasses should implement this to react to specific events.
        """
        self.logger.debug(f"Received event: {event}")

    def submit_background_task(
        self,
        callable_task: Callable,
        *args: Any,
        description: Optional[str] = None,
        on_complete: Optional[Callable[[Any], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        """
        Helper to submit a task to be run in a worker thread via the TUIApp.
        This is a simplified version; a more robust TaskManager equivalent for TUI
        would be beneficial, potentially integrating with Textual's workers.

        Args:
            callable_task: The function to execute.
            *args: Positional arguments for the callable.
            description: A description of the task for logging/UI.
            on_complete: Callback function when task completes successfully.
            on_error: Callback function when task raises an exception.
        """
        self.logger.info(f"Submitting background task: {description or callable_task.__name__}")

        async def task_wrapper():
            try:
                result = await self.app.run_sync_in_worker(callable_task, *args)
                if on_complete:
                    self.app.call_from_thread(on_complete, result)
            except Exception as e:
                self.logger.error(
                    f"Error in background task {description or callable_task.__name__}: {e}",
                    exc_info=True,
                )
                if on_error:
                    self.app.call_from_thread(on_error, e)

        self.app.run_worker(
            task_wrapper(), exclusive=True, group=description or callable_task.__name__
        )

    # Placeholder for methods to interact with core services or update models
    # For example:
    # async def load_data(self) -> None:
    #     pass

    # async def update_view(self) -> None:
    #     pass
