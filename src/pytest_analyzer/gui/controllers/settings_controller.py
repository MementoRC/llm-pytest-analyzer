import logging
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import QObject, Signal, Slot

# QMessageBox is used by SettingsDialog, not directly here anymore for on_settings
# from PySide6.QtWidgets import QMessageBox
from PySide6.QtWidgets import QDialog  # For type hinting exec result

from ...utils.config_types import Settings  # For type hinting
from ..views.settings_dialog import SettingsDialog  # Import the new dialog
from .base_controller import BaseController

if TYPE_CHECKING:
    from PySide6.QtWidgets import QMainWindow

    from ..app import PytestAnalyzerApp


logger = logging.getLogger(__name__)


class SettingsController(BaseController):
    """Manages application settings and configuration."""

    core_settings_changed = Signal(Settings)  # Emitted when core settings are updated

    def __init__(self, app: "PytestAnalyzerApp", parent: QObject = None):
        super().__init__(parent)
        self.app = app
        # Assuming main_window is accessible, e.g., self.app.main_window
        # If not, it needs to be passed or accessible. For now, dialog parent can be None.
        self.main_window: Optional[QMainWindow] = getattr(app, "main_window", None)

    @Slot()
    def on_settings(self) -> None:
        """Handle the Settings action by showing the SettingsDialog."""
        self.logger.info("Settings action triggered. Opening SettingsDialog.")

        dialog = SettingsDialog(
            current_core_settings=self.app.core_settings,
            app_q_settings=self.app.settings,  # Pass the QSettings object
            parent=self.main_window,  # Or None if main_window not easily accessible
        )
        dialog.settings_updated.connect(self._handle_settings_updated_from_dialog)
        dialog.gui_setting_changed.connect(self._handle_gui_setting_changed_from_dialog)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Settings were accepted (OK clicked)
            # The _handle_settings_updated_from_dialog slot has already processed them.
            self.logger.info("SettingsDialog accepted. Core settings updated and persisted.")
        else:
            self.logger.info("SettingsDialog cancelled.")

    @Slot(Settings)
    def _handle_settings_updated_from_dialog(self, updated_core_settings: Settings):
        """
        Applies validated and updated core settings from the dialog
        to the application's core settings and persists them.
        """
        self.logger.info("Applying updated core settings from dialog.")
        # Update the application's core_settings instance
        # It's often better to update fields rather than replacing the instance if other
        # parts of the app hold a direct reference to self.app.core_settings.
        # However, if Settings is a simple dataclass, replacing might be fine if
        # all consumers get it via self.app.core_settings.
        # For safety, let's update field by field or re-assign if it's confirmed safe.

        # Option 1: Re-assign (simpler if Settings is just a data container)
        # self.app.core_settings = updated_core_settings

        # Option 2: Update fields (safer if self.app.core_settings is shared by reference)
        for field_name, field_value in vars(updated_core_settings).items():
            if hasattr(self.app.core_settings, field_name):
                setattr(self.app.core_settings, field_name, field_value)
            else:
                self.logger.warning(
                    f"Field {field_name} from dialog settings not found in app's core_settings."
                )

        # Persist all core settings to QSettings
        # This requires a comprehensive save method in PytestAnalyzerApp
        if hasattr(self.app, "save_all_core_settings_to_qsettings"):
            self.app.save_all_core_settings_to_qsettings()
        else:
            # Fallback to individual save methods if the comprehensive one isn't there yet
            self.app.save_core_llm_settings()  # Existing method for LLM
            # Add calls to save other groups of settings if specific methods exist
            self.logger.warning(
                "PytestAnalyzerApp.save_all_core_settings_to_qsettings() not found. Only LLM settings might be fully persisted via QSettings."
            )

        # Emit a general signal that core settings have changed.
        # Consumers can then react as needed (e.g., reinitialize services).
        if hasattr(self, "core_settings_changed") and isinstance(
            self.core_settings_changed, Signal
        ):
            self.core_settings_changed.emit(self.app.core_settings)
        # No explicit fallback to llm_settings_changed as it's removed.

        self.logger.info("Core settings updated and relevant parts persisted via QSettings.")
        # Potentially inform user that some changes might require a restart or re-initialization of services
        # QMessageBox.information(self.main_window, "Settings Applied", "Some settings may require re-initialization of services or application restart to take full effect.")

    @Slot(str, object)
    def _handle_gui_setting_changed_from_dialog(self, key: str, value: object):
        """Saves a GUI-specific setting to QSettings."""
        self.logger.info(f"GUI setting changed: {key} = {value}. Saving to QSettings.")
        self.app.set_setting(key, value)  # Uses app's QSettings instance
