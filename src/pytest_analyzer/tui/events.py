from textual.message import Message


class TUIEvent(Message):
    """Base class for custom TUI events."""

    pass


class ShowNotification(TUIEvent):
    """Event to request showing a notification."""

    def __init__(
        self, message: str, title: str = "Notification", timeout: float = 3.0
    ) -> None:
        self.message = message
        self.title = title
        self.timeout = timeout
        super().__init__()


class StatusMessageUpdate(TUIEvent):
    """Event to update a status message area in the TUI."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__()


# Example of more specific events that might be added later:
# class FileSelectedEvent(TUIEvent):
#     def __init__(self, path: Path) -> None:
#         self.path = path
#         super().__init__()

# class RunTestsRequestedEvent(TUIEvent):
#     pass
