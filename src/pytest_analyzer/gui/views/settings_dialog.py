import logging
from typing import TYPE_CHECKING, cast

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ...utils.config_types import Settings

if TYPE_CHECKING:
    from PyQt6.QtCore import QSettings as QSettingsType  # For type hinting QSettings

logger = logging.getLogger(__name__)

# Common models for convenience, users can also type their own
OPENAI_MODELS = ["gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"]
ANTHROPIC_MODELS = ["claude-3-opus-20240229", "claude-3-sonnet-20240229", "claude-3-haiku-20240307"]
LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
PREFERRED_FORMATS = ["json", "xml", "text"]


class SettingsDialog(QDialog):
    """Dialog for configuring application settings."""

    # Emits the updated core settings when Apply or OK is clicked and validated
    settings_updated = pyqtSignal(Settings)
    # Emits GUI-specific key-value pairs that need to be saved to QSettings
    gui_setting_changed = pyqtSignal(str, object)

    def __init__(
        self,
        current_core_settings: Settings,
        app_q_settings: "QSettingsType",  # QSettings object from the app
        parent: QWidget = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Settings - Pytest Analyzer")
        self.setMinimumSize(700, 600)  # Increased size for more content

        self.initial_core_settings = current_core_settings
        # Create a working copy to modify. Using vars() and ** is a shallow copy.
        # For dataclasses with mutable defaults (like lists), a proper deepcopy or careful handling is needed.
        # Settings dataclass fields are mostly simple types or default_factory=list,
        # so direct field assignment in _save_ui_to_settings should be fine.
        self.working_core_settings = Settings(**vars(current_core_settings))
        self.app_q_settings = app_q_settings

        # Main layout
        main_layout = QVBoxLayout(self)

        # Tab widget
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # Create tabs
        self._create_llm_tab()
        self._create_test_execution_tab()
        self._create_analysis_tab()
        self._create_gui_preferences_tab()
        self._create_git_integration_tab()

        # Dialog buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Apply
        )
        self.reset_button = QPushButton("Reset to Defaults")
        self.button_box.addButton(self.reset_button, QDialogButtonBox.ButtonRole.ResetRole)

        main_layout.addWidget(self.button_box)

        # Connect signals
        self.button_box.accepted.connect(self.accept)  # OK
        self.button_box.rejected.connect(self.reject)  # Cancel
        apply_button = self.button_box.button(QDialogButtonBox.StandardButton.Apply)
        if apply_button:  # Ensure button exists
            apply_button.clicked.connect(self._apply_settings)
        self.reset_button.clicked.connect(self._reset_to_defaults)

        self._load_settings_to_ui()  # Load initial settings into UI fields
        self._update_llm_fields_visibility()  # Initial visibility update

    def _create_llm_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        group_box = QGroupBox("LLM Provider Configuration")
        form_layout = QFormLayout(group_box)

        self.llm_provider_combo = QComboBox()
        self.llm_provider_combo.addItems(["none", "openai", "anthropic"])
        self.llm_provider_combo.currentTextChanged.connect(self._update_llm_fields_visibility)
        form_layout.addRow("LLM Provider:", self.llm_provider_combo)

        # OpenAI settings
        self.openai_api_key_edit = QLineEdit()
        self.openai_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.openai_api_key_edit.setPlaceholderText("Enter OpenAI API Key")
        form_layout.addRow("OpenAI API Key:", self.openai_api_key_edit)

        self.openai_model_combo = QComboBox()
        self.openai_model_combo.addItems(OPENAI_MODELS)
        self.openai_model_combo.setEditable(True)
        form_layout.addRow("OpenAI Model:", self.openai_model_combo)

        openai_test_button = QPushButton("Test OpenAI Connection")
        openai_test_button.setObjectName("Test OpenAI Connection")  # For easier lookup
        openai_test_button.clicked.connect(lambda: self._test_llm_connection("openai"))
        form_layout.addRow(openai_test_button)

        # Anthropic settings
        self.anthropic_api_key_edit = QLineEdit()
        self.anthropic_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.anthropic_api_key_edit.setPlaceholderText("Enter Anthropic API Key")
        form_layout.addRow("Anthropic API Key:", self.anthropic_api_key_edit)

        self.anthropic_model_combo = QComboBox()
        self.anthropic_model_combo.addItems(ANTHROPIC_MODELS)
        self.anthropic_model_combo.setEditable(True)
        form_layout.addRow("Anthropic Model:", self.anthropic_model_combo)

        anthropic_test_button = QPushButton("Test Anthropic Connection")
        anthropic_test_button.setObjectName("Test Anthropic Connection")  # For easier lookup
        anthropic_test_button.clicked.connect(lambda: self._test_llm_connection("anthropic"))
        form_layout.addRow(anthropic_test_button)

        layout.addWidget(group_box)

        # General LLM Settings
        general_group_box = QGroupBox("General LLM Settings")
        general_form_layout = QFormLayout(general_group_box)

        self.llm_use_fallback_checkbox = QCheckBox("Use fallback providers if primary fails")
        general_form_layout.addRow(self.llm_use_fallback_checkbox)

        self.llm_timeout_spinbox = QSpinBox()
        self.llm_timeout_spinbox.setRange(10, 600)
        self.llm_timeout_spinbox.setSuffix(" seconds")
        general_form_layout.addRow("LLM Request Timeout:", self.llm_timeout_spinbox)

        self.llm_cache_enabled_checkbox = QCheckBox("Enable LLM response cache")
        general_form_layout.addRow(self.llm_cache_enabled_checkbox)

        self.llm_cache_ttl_spinbox = QSpinBox()
        self.llm_cache_ttl_spinbox.setRange(60, 86400)  # 1 min to 1 day
        self.llm_cache_ttl_spinbox.setSuffix(" seconds")
        general_form_layout.addRow("LLM Cache TTL:", self.llm_cache_ttl_spinbox)
        self.llm_cache_enabled_checkbox.toggled.connect(self.llm_cache_ttl_spinbox.setEnabled)

        layout.addWidget(general_group_box)
        layout.addStretch()
        self.tab_widget.addTab(tab, "LLM Configuration")

    def _update_llm_fields_visibility(self):
        provider = self.llm_provider_combo.currentText()
        form_layout = cast("QFormLayout", self.llm_provider_combo.parentWidget().layout())

        is_openai = provider == "openai"
        is_anthropic = provider == "anthropic"

        # Iterate through the form layout to find and set visibility for rows
        for i in range(form_layout.rowCount()):
            label_item = form_layout.itemAt(i, QFormLayout.ItemRole.LabelRole)
            field_item = form_layout.itemAt(i, QFormLayout.ItemRole.FieldRole)

            label_widget = label_item.widget() if label_item else None
            field_widget = field_item.widget() if field_item else None  # Could be a layout too

            if label_widget and isinstance(label_widget, QLabel):
                label_text = label_widget.text()
                if "OpenAI API Key:" in label_text or "OpenAI Model:" in label_text:
                    label_widget.setVisible(is_openai)
                    if field_widget:
                        field_widget.setVisible(is_openai)
                elif "Anthropic API Key:" in label_text or "Anthropic Model:" in label_text:
                    label_widget.setVisible(is_anthropic)
                    if field_widget:
                        field_widget.setVisible(is_anthropic)

            # Handle buttons specifically if they don't have a QLabel or are in a layout
            if field_widget and isinstance(field_widget, QPushButton):
                if "OpenAI" in field_widget.text():
                    field_widget.setVisible(is_openai)
                elif "Anthropic" in field_widget.text():
                    field_widget.setVisible(is_anthropic)
            elif (
                field_item and field_item.layout()
            ):  # Check if field item is a layout (e.g. for button)
                # This part might need more specific handling if buttons are nested
                for j in range(field_item.layout().count()):
                    inner_widget = field_item.layout().itemAt(j).widget()
                    if inner_widget and isinstance(inner_widget, QPushButton):
                        if "OpenAI" in inner_widget.text():
                            inner_widget.setVisible(is_openai)
                        elif "Anthropic" in inner_widget.text():
                            inner_widget.setVisible(is_anthropic)

    def _create_test_execution_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        form_layout = QFormLayout()

        group_box = QGroupBox("Pytest Execution")
        group_box.setLayout(form_layout)

        self.pytest_timeout_spinbox = QSpinBox()
        self.pytest_timeout_spinbox.setRange(10, 3600)
        self.pytest_timeout_spinbox.setSuffix(" seconds")
        form_layout.addRow("Pytest Timeout:", self.pytest_timeout_spinbox)

        self.pytest_args_edit = QLineEdit()
        self.pytest_args_edit.setPlaceholderText("e.g., -v --cov")
        form_layout.addRow("Additional Pytest Arguments:", self.pytest_args_edit)

        layout.addWidget(group_box)

        resource_group_box = QGroupBox("Resource Limits")
        resource_form_layout = QFormLayout(resource_group_box)

        self.max_memory_mb_spinbox = QSpinBox()
        self.max_memory_mb_spinbox.setRange(128, 8192)
        self.max_memory_mb_spinbox.setSuffix(" MB")
        resource_form_layout.addRow("Max Memory:", self.max_memory_mb_spinbox)

        self.parser_timeout_spinbox = QSpinBox()
        self.parser_timeout_spinbox.setRange(5, 300)
        self.parser_timeout_spinbox.setSuffix(" seconds")
        resource_form_layout.addRow("Parser Timeout:", self.parser_timeout_spinbox)

        self.analyzer_timeout_spinbox = QSpinBox()
        self.analyzer_timeout_spinbox.setRange(10, 600)
        self.analyzer_timeout_spinbox.setSuffix(" seconds")
        resource_form_layout.addRow("Analyzer Timeout:", self.analyzer_timeout_spinbox)

        layout.addWidget(resource_group_box)

        async_group_box = QGroupBox("Asynchronous Processing")
        async_form_layout = QFormLayout(async_group_box)

        self.batch_size_spinbox = QSpinBox()
        self.batch_size_spinbox.setRange(1, 100)
        async_form_layout.addRow("Batch Size:", self.batch_size_spinbox)

        self.max_concurrency_spinbox = QSpinBox()
        self.max_concurrency_spinbox.setRange(1, 50)
        async_form_layout.addRow("Max Concurrency:", self.max_concurrency_spinbox)

        layout.addWidget(async_group_box)
        layout.addStretch()
        self.tab_widget.addTab(tab, "Test Execution")

    def _create_analysis_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        form_layout = QFormLayout()
        group_box = QGroupBox("Failure Analysis Settings")
        group_box.setLayout(form_layout)

        self.max_failures_spinbox = QSpinBox()
        self.max_failures_spinbox.setRange(1, 1000)
        form_layout.addRow("Max Failures to Process:", self.max_failures_spinbox)

        self.max_suggestions_spinbox = QSpinBox()
        self.max_suggestions_spinbox.setRange(1, 20)
        form_layout.addRow("Max Suggestions (Overall):", self.max_suggestions_spinbox)

        self.max_suggestions_per_failure_spinbox = QSpinBox()
        self.max_suggestions_per_failure_spinbox.setRange(1, 10)
        form_layout.addRow("Max Suggestions per Failure:", self.max_suggestions_per_failure_spinbox)

        self.min_confidence_spinbox = QDoubleSpinBox()
        self.min_confidence_spinbox.setRange(0.0, 1.0)
        self.min_confidence_spinbox.setSingleStep(0.05)
        self.min_confidence_spinbox.setDecimals(2)
        form_layout.addRow("Min Confidence for Suggestions:", self.min_confidence_spinbox)

        self.auto_apply_checkbox = QCheckBox("Automatically apply suggested fixes (if confident)")
        form_layout.addRow(self.auto_apply_checkbox)

        layout.addWidget(group_box)
        layout.addStretch()
        self.tab_widget.addTab(tab, "Analysis")

    def _create_gui_preferences_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        form_layout = QFormLayout()
        group_box = QGroupBox("User Interface")
        group_box.setLayout(form_layout)

        self.preferred_format_combo = QComboBox()
        self.preferred_format_combo.addItems(PREFERRED_FORMATS)
        form_layout.addRow("Preferred Report Format (Core):", self.preferred_format_combo)

        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(LOG_LEVELS)
        form_layout.addRow("Logging Level (Core):", self.log_level_combo)

        # Example of a GUI-only setting (not in core Settings dataclass)
        # self.gui_theme_combo = QComboBox()
        # self.gui_theme_combo.addItems(["Default", "Dark", "Light"])
        # form_layout.addRow("Application Theme:", self.gui_theme_combo)

        layout.addWidget(group_box)
        layout.addStretch()
        self.tab_widget.addTab(tab, "GUI Preferences")

    def _create_git_integration_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        form_layout = QFormLayout()
        group_box = QGroupBox("Git Integration")
        group_box.setLayout(form_layout)

        self.check_git_checkbox = QCheckBox("Enable Git integration features")
        form_layout.addRow(self.check_git_checkbox)

        self.auto_init_git_checkbox = QCheckBox(
            "Automatically initialize Git if not a repo (requires confirmation)"
        )
        form_layout.addRow(self.auto_init_git_checkbox)
        self.check_git_checkbox.toggled.connect(self.auto_init_git_checkbox.setEnabled)

        self.use_git_branches_checkbox = QCheckBox("Create new branches for fix suggestions")
        form_layout.addRow(self.use_git_branches_checkbox)
        self.check_git_checkbox.toggled.connect(self.use_git_branches_checkbox.setEnabled)

        layout.addWidget(group_box)
        layout.addStretch()
        self.tab_widget.addTab(tab, "Git Integration")

    def _load_settings_to_ui(self):
        # LLM Tab
        self.llm_provider_combo.setCurrentText(self.working_core_settings.llm_provider)
        self.openai_api_key_edit.setText(self.working_core_settings.llm_api_key_openai)
        self.openai_model_combo.setCurrentText(self.working_core_settings.llm_model_openai)
        self.anthropic_api_key_edit.setText(self.working_core_settings.llm_api_key_anthropic)
        self.anthropic_model_combo.setCurrentText(self.working_core_settings.llm_model_anthropic)
        self.llm_use_fallback_checkbox.setChecked(self.working_core_settings.use_fallback)
        self.llm_timeout_spinbox.setValue(self.working_core_settings.llm_timeout)
        self.llm_cache_enabled_checkbox.setChecked(self.working_core_settings.llm_cache_enabled)
        self.llm_cache_ttl_spinbox.setValue(self.working_core_settings.llm_cache_ttl_seconds)
        self.llm_cache_ttl_spinbox.setEnabled(self.working_core_settings.llm_cache_enabled)

        # Test Execution Tab
        self.pytest_timeout_spinbox.setValue(self.working_core_settings.pytest_timeout)
        self.pytest_args_edit.setText(" ".join(self.working_core_settings.pytest_args))
        self.max_memory_mb_spinbox.setValue(self.working_core_settings.max_memory_mb)
        self.parser_timeout_spinbox.setValue(self.working_core_settings.parser_timeout)
        self.analyzer_timeout_spinbox.setValue(self.working_core_settings.analyzer_timeout)
        self.batch_size_spinbox.setValue(self.working_core_settings.batch_size)
        self.max_concurrency_spinbox.setValue(self.working_core_settings.max_concurrency)

        # Analysis Tab
        self.max_failures_spinbox.setValue(self.working_core_settings.max_failures)
        self.max_suggestions_spinbox.setValue(self.working_core_settings.max_suggestions)
        self.max_suggestions_per_failure_spinbox.setValue(
            self.working_core_settings.max_suggestions_per_failure
        )
        self.min_confidence_spinbox.setValue(self.working_core_settings.min_confidence)
        self.auto_apply_checkbox.setChecked(self.working_core_settings.auto_apply)

        # GUI Preferences Tab
        self.preferred_format_combo.setCurrentText(self.working_core_settings.preferred_format)
        self.log_level_combo.setCurrentText(self.working_core_settings.log_level.upper())
        # Example for GUI-only setting:
        # self.gui_theme_combo.setCurrentText(self.app_q_settings.value("gui/theme", "Default"))

        # Git Integration Tab
        self.check_git_checkbox.setChecked(self.working_core_settings.check_git)
        self.auto_init_git_checkbox.setChecked(self.working_core_settings.auto_init_git)
        self.use_git_branches_checkbox.setChecked(self.working_core_settings.use_git_branches)
        self.auto_init_git_checkbox.setEnabled(self.working_core_settings.check_git)
        self.use_git_branches_checkbox.setEnabled(self.working_core_settings.check_git)

        self._update_llm_fields_visibility()  # Ensure correct visibility after loading

    def _save_ui_to_settings(self) -> bool:
        if not self._validate_inputs():
            return False

        # LLM Tab
        self.working_core_settings.llm_provider = self.llm_provider_combo.currentText()
        self.working_core_settings.llm_api_key_openai = self.openai_api_key_edit.text()
        self.working_core_settings.llm_model_openai = self.openai_model_combo.currentText()
        self.working_core_settings.llm_api_key_anthropic = self.anthropic_api_key_edit.text()
        self.working_core_settings.llm_model_anthropic = self.anthropic_model_combo.currentText()
        self.working_core_settings.use_fallback = self.llm_use_fallback_checkbox.isChecked()
        self.working_core_settings.llm_timeout = self.llm_timeout_spinbox.value()
        self.working_core_settings.llm_cache_enabled = self.llm_cache_enabled_checkbox.isChecked()
        self.working_core_settings.llm_cache_ttl_seconds = self.llm_cache_ttl_spinbox.value()

        # Test Execution Tab
        self.working_core_settings.pytest_timeout = self.pytest_timeout_spinbox.value()
        self.working_core_settings.pytest_args = (
            self.pytest_args_edit.text().split()
        )  # Simple split
        self.working_core_settings.max_memory_mb = self.max_memory_mb_spinbox.value()
        self.working_core_settings.parser_timeout = self.parser_timeout_spinbox.value()
        self.working_core_settings.analyzer_timeout = self.analyzer_timeout_spinbox.value()
        self.working_core_settings.batch_size = self.batch_size_spinbox.value()
        self.working_core_settings.max_concurrency = self.max_concurrency_spinbox.value()

        # Analysis Tab
        self.working_core_settings.max_failures = self.max_failures_spinbox.value()
        self.working_core_settings.max_suggestions = self.max_suggestions_spinbox.value()
        self.working_core_settings.max_suggestions_per_failure = (
            self.max_suggestions_per_failure_spinbox.value()
        )
        self.working_core_settings.min_confidence = self.min_confidence_spinbox.value()
        self.working_core_settings.auto_apply = self.auto_apply_checkbox.isChecked()

        # GUI Preferences Tab (Core settings part)
        self.working_core_settings.preferred_format = self.preferred_format_combo.currentText()
        self.working_core_settings.log_level = self.log_level_combo.currentText().upper()
        # Example for GUI-only setting:
        # self.gui_setting_changed.emit("gui/theme", self.gui_theme_combo.currentText())

        # Git Integration Tab
        self.working_core_settings.check_git = self.check_git_checkbox.isChecked()
        self.working_core_settings.auto_init_git = self.auto_init_git_checkbox.isChecked()
        self.working_core_settings.use_git_branches = self.use_git_branches_checkbox.isChecked()

        return True

    def _validate_inputs(self) -> bool:
        # LLM Provider Validation
        provider = self.llm_provider_combo.currentText()
        if provider == "openai" and not self.openai_api_key_edit.text():
            QMessageBox.warning(
                self,
                "Validation Error",
                "OpenAI API Key is required when OpenAI provider is selected.",
            )
            self.tab_widget.setCurrentIndex(0)  # Switch to LLM tab
            self.openai_api_key_edit.setFocus()
            return False
        if provider == "anthropic" and not self.anthropic_api_key_edit.text():
            QMessageBox.warning(
                self,
                "Validation Error",
                "Anthropic API Key is required when Anthropic provider is selected.",
            )
            self.tab_widget.setCurrentIndex(0)  # Switch to LLM tab
            self.anthropic_api_key_edit.setFocus()
            return False

        # Add more specific validations as needed (e.g., for QSpinBox ranges, though they often self-validate)
        # Example: Pytest args could be validated with a regex if necessary.
        return True

    def accept(self):  # OK button
        if self._save_ui_to_settings():  # This already calls _validate_inputs
            self.settings_updated.emit(self.working_core_settings)
            super().accept()
        # If validation failed, _save_ui_to_settings returns False, message already shown by _validate_inputs

    def _apply_settings(self):  # Apply button
        if self._save_ui_to_settings():  # This already calls _validate_inputs
            self.settings_updated.emit(self.working_core_settings)
            QMessageBox.information(
                self,
                "Settings Applied",
                "Settings have been applied and will be used for new operations.",
            )
        # If validation failed, _save_ui_to_settings returns False, message already shown

    def _reset_to_defaults(self):
        reply = QMessageBox.question(
            self,
            "Reset Settings",
            "Are you sure you want to reset all settings to their default values?\n"
            "This will affect settings for the current session. Applied or OK'd changes will be persisted.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.working_core_settings = Settings()  # New default core settings

            # For GUI-specific settings stored in QSettings, you might need to reset them explicitly
            # Example: self.gui_setting_changed.emit("gui/theme", "Default") # if you had a default theme
            # Or, the controller could handle resetting QSettings based on a signal.

            self._load_settings_to_ui()  # Reload UI with defaults
            QMessageBox.information(
                self,
                "Settings Reset",
                "Settings have been reset to defaults in this dialog. Click Apply or OK to use them.",
            )

    def get_updated_core_settings(self) -> Settings:
        """Returns the current state of core settings in the dialog."""
        # Ensure working_core_settings is up-to-date with UI before returning,
        # especially if called externally without Apply/OK.
        # However, standard flow is Apply/OK updates it.
        return self.working_core_settings

    def _test_llm_connection(self, provider: str):
        # This is a placeholder. Actual implementation would:
        # 1. Get API key and model from the dialog's current fields.
        # 2. Make a lightweight API call (e.g., list models, simple query).
        # 3. Show success/failure message.
        # This might be better handled in the SettingsController.
        api_key = ""
        model = ""
        if provider == "openai":
            api_key = self.openai_api_key_edit.text()
            model = self.openai_model_combo.currentText()
        elif provider == "anthropic":
            api_key = self.anthropic_api_key_edit.text()
            model = self.anthropic_model_combo.currentText()

        if not api_key:
            QMessageBox.warning(
                self, "Test Connection", f"Please enter the API key for {provider} first."
            )
            return

        QMessageBox.information(
            self,
            "Test Connection",
            f"Simulating test connection for {provider} with key '...{api_key[-4:] if len(api_key) > 3 else ''}' and model '{model}'.\n"
            "(Actual test logic not implemented yet.)",
        )
