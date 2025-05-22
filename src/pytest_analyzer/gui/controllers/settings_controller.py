import logging

from PyQt6.QtCore import QObject, pyqtSlot
from PyQt6.QtWidgets import QMessageBox

from .base_controller import BaseController

# from PyQt6.QtCore import QSettings # For direct QSettings interaction


logger = logging.getLogger(__name__)


class SettingsController(BaseController):
    """Manages application settings and configuration."""

    def __init__(self, parent: QObject = None):  # Potentially pass app_settings object
        super().__init__(parent)
        # self.app_settings = app_settings # If using a global settings object

    @pyqtSlot()
    def on_settings(self) -> None:
        """Handle the Settings action."""
        self.logger.info("Settings action triggered.")
        # Will be implemented with a proper settings dialog
        QMessageBox.information(
            None, "Settings", "Settings dialog will be implemented in a future task."
        )
        # Example future logic:
        # settings_dialog = SettingsDialog(self.app_settings, parent=None) # Or parent=self.main_window
        # if settings_dialog.exec():
        #     self.logger.info("Settings updated.")
        #     # Apply settings if needed
