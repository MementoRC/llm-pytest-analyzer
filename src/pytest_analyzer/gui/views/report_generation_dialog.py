"""Report generation dialog for the pytest analyzer GUI."""

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QThread, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from ..models.report import ReportConfig, ReportFormat, ReportGenerator, ReportType


class ReportGenerationWorker(QThread):
    """Worker thread for generating reports in the background."""

    progress_updated = Signal(int)
    status_updated = Signal(str)
    finished = Signal(str)  # file_path
    error_occurred = Signal(str)

    def __init__(self, config: ReportConfig, test_results, analysis_results, parent=None):
        super().__init__(parent)
        self.config = config
        self.test_results = test_results
        self.analysis_results = analysis_results
        self.generator = ReportGenerator()

    def run(self):
        """Generate the report in background thread."""
        try:
            self.status_updated.emit("Initializing report generation...")
            self.progress_updated.emit(10)

            self.status_updated.emit("Generating report content...")
            self.progress_updated.emit(30)

            file_path = self.generator.generate_report(
                config=self.config,
                test_results=self.test_results,
                analysis_results=self.analysis_results,
            )

            self.progress_updated.emit(100)
            self.status_updated.emit("Report generated successfully!")
            self.finished.emit(str(file_path))

        except Exception as e:
            self.error_occurred.emit(f"Failed to generate report: {str(e)}")


class ReportGenerationDialog(QDialog):
    """Dialog for configuring and generating analysis reports."""

    report_generated = Signal(str)  # file_path

    def __init__(self, test_results=None, analysis_results=None, parent=None):
        super().__init__(parent)
        self.test_results = test_results
        self.analysis_results = analysis_results
        self.worker: Optional[ReportGenerationWorker] = None

        self.setWindowTitle("Generate Report")
        self.setModal(True)
        self.resize(500, 400)

        self._setup_ui()
        self._connect_signals()
        self._populate_defaults()

    def _setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)

        # Report Configuration Group
        config_group = QGroupBox("Report Configuration")
        config_layout = QFormLayout(config_group)

        # Report Type
        self.type_combo = QComboBox()
        self.type_combo.addItems(
            [
                "Full Analysis Report",
                "Summary Report",
                "Test Coverage Report",
                "Fix Application History",
            ]
        )
        config_layout.addRow("Report Type:", self.type_combo)

        # Report Format
        self.format_combo = QComboBox()
        self.format_combo.addItems(["HTML", "PDF", "JSON", "CSV"])
        config_layout.addRow("Format:", self.format_combo)

        # Custom Title
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Enter custom report title (optional)")
        config_layout.addRow("Title:", self.title_edit)

        layout.addWidget(config_group)

        # Options Group
        options_group = QGroupBox("Report Options")
        options_layout = QVBoxLayout(options_group)

        self.include_charts_check = QCheckBox("Include charts and graphs")
        self.include_charts_check.setChecked(True)
        options_layout.addWidget(self.include_charts_check)

        self.include_details_check = QCheckBox("Include detailed test information")
        self.include_details_check.setChecked(True)
        options_layout.addWidget(self.include_details_check)

        self.include_fixes_check = QCheckBox("Include fix suggestions")
        self.include_fixes_check.setChecked(True)
        options_layout.addWidget(self.include_fixes_check)

        layout.addWidget(options_group)

        # Output Group
        output_group = QGroupBox("Output Location")
        output_layout = QVBoxLayout(output_group)

        path_layout = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Select output file path...")
        path_layout.addWidget(self.path_edit)

        self.browse_button = QPushButton("Browse...")
        self.browse_button.clicked.connect(self._browse_output_path)
        path_layout.addWidget(self.browse_button)

        output_layout.addLayout(path_layout)
        layout.addWidget(output_group)

        # Progress Group
        self.progress_group = QGroupBox("Generation Progress")
        progress_layout = QVBoxLayout(self.progress_group)

        self.status_label = QLabel("Ready to generate report")
        progress_layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        progress_layout.addWidget(self.progress_bar)

        layout.addWidget(self.progress_group)
        self.progress_group.setVisible(False)

        # Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.generate_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        self.generate_button.setText("Generate Report")
        self.cancel_button = self.button_box.button(QDialogButtonBox.StandardButton.Cancel)

        layout.addWidget(self.button_box)

    def _connect_signals(self):
        """Connect UI signals to slots."""
        self.button_box.accepted.connect(self._generate_report)
        self.button_box.rejected.connect(self.reject)
        self.format_combo.currentTextChanged.connect(self._update_file_extension)

    def _populate_defaults(self):
        """Populate default values."""
        # Set default output path
        default_name = "pytest_analysis_report.html"
        default_path = Path.cwd() / default_name
        self.path_edit.setText(str(default_path))

    def _browse_output_path(self):
        """Open file dialog to select output path."""
        current_format = self.format_combo.currentText().lower()

        filters = {
            "html": "HTML Files (*.html)",
            "pdf": "PDF Files (*.pdf)",
            "json": "JSON Files (*.json)",
            "csv": "CSV Files (*.csv)",
        }

        file_filter = filters.get(current_format, "All Files (*)")

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Report As", self.path_edit.text(), file_filter
        )

        if file_path:
            self.path_edit.setText(file_path)

    def _update_file_extension(self, format_text: str):
        """Update file extension when format changes."""
        current_path = Path(self.path_edit.text())
        extensions = {"HTML": ".html", "PDF": ".pdf", "JSON": ".json", "CSV": ".csv"}

        new_extension = extensions.get(format_text, ".html")
        new_path = current_path.with_suffix(new_extension)
        self.path_edit.setText(str(new_path))

    def _generate_report(self):
        """Generate the report."""
        if not self._validate_inputs():
            return

        config = self._create_config()

        # Show progress
        self.progress_group.setVisible(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.generate_button.setEnabled(False)

        # Start background generation
        self.worker = ReportGenerationWorker(config, self.test_results, self.analysis_results, self)
        self.worker.progress_updated.connect(self.progress_bar.setValue)
        self.worker.status_updated.connect(self.status_label.setText)
        self.worker.finished.connect(self._on_report_finished)
        self.worker.error_occurred.connect(self._on_report_error)
        self.worker.start()

    def _validate_inputs(self) -> bool:
        """Validate user inputs."""
        if not self.path_edit.text().strip():
            self.status_label.setText("Please select an output file path")
            return False

        output_path = Path(self.path_edit.text())
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.status_label.setText(f"Invalid output path: {e}")
            return False

        return True

    def _create_config(self) -> ReportConfig:
        """Create report configuration from UI inputs."""
        type_mapping = {
            "Full Analysis Report": ReportType.FULL_ANALYSIS,
            "Summary Report": ReportType.SUMMARY,
            "Test Coverage Report": ReportType.COVERAGE,
            "Fix Application History": ReportType.FIX_HISTORY,
        }

        format_mapping = {
            "HTML": ReportFormat.HTML,
            "PDF": ReportFormat.PDF,
            "JSON": ReportFormat.JSON,
            "CSV": ReportFormat.CSV,
        }

        return ReportConfig(
            report_type=type_mapping[self.type_combo.currentText()],
            format=format_mapping[self.format_combo.currentText()],
            output_path=Path(self.path_edit.text()),
            title=self.title_edit.text().strip() or "Pytest Analysis Report",
            include_charts=self.include_charts_check.isChecked(),
            include_analysis_details=self.include_details_check.isChecked(),
            include_fix_suggestions=self.include_fixes_check.isChecked(),
        )

    @Slot(str)
    def _on_report_finished(self, file_path: str):
        """Handle successful report generation."""
        self.status_label.setText(f"Report saved to: {file_path}")
        self.generate_button.setEnabled(True)
        self.generate_button.setText("Generate Another")
        self.report_generated.emit(file_path)

    @Slot(str)
    def _on_report_error(self, error_message: str):
        """Handle report generation error."""
        self.status_label.setText(f"Error: {error_message}")
        self.generate_button.setEnabled(True)
        self.progress_bar.setVisible(False)

    def closeEvent(self, event):
        """Handle dialog close event."""
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait()
        event.accept()
