import logging

from PyQt6.QtCore import QObject

logger = logging.getLogger(__name__)


class BaseController(QObject):
    """Abstract base class for all controllers."""

    def __init__(self, parent: QObject = None):
        """
        Initialize the base controller.

        Args:
            parent: Optional parent QObject.
        """
        super().__init__(parent)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info(f"{self.__class__.__name__} initialized")

    def handle_error(self, message: str, error: Exception = None) -> None:
        """
        Handle an error, logging it.

        Args:
            message: The error message.
            error: The exception, if any.
        """
        self.logger.error(message)
        if error:
            self.logger.exception(error)
        # In a more advanced setup, this might emit a signal
        # for the main window to display an error dialog.
