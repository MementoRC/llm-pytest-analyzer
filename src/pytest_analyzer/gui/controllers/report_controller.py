"""Report controller for managing report generation and export functionality."""

import logging
from pathlib import Path
from typing import Dict, List, Optional

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QWidget

from ..models.report import ReportConfig, ReportFormat, ReportGenerator, ReportType
from ..views.report_generation_dialog import ReportGenerationDialog

logger = logging.getLogger(__name__)


class ReportController(QObject):
    """Controller for managing report generation and export functionality."""

    report_generated = pyqtSignal(str)  # file_path
    report_generation_started = pyqtSignal()
    report_generation_finished = pyqtSignal(bool, str)  # success, message

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.parent_widget = parent
        self.generator = ReportGenerator()
        self._test_results = None
        self._analysis_results = None
        self._recent_reports: List[str] = []

    def set_test_results(self, test_results):
        """Set the current test results for report generation."""
        self._test_results = test_results
        logger.debug(
            f"Test results updated for reporting: {len(test_results) if test_results else 0} results"
        )

    def set_analysis_results(self, analysis_results):
        """Set the current analysis results for report generation."""
        self._analysis_results = analysis_results
        logger.debug("Analysis results updated for reporting")

    def show_report_dialog(self):
        """Show the report generation dialog."""
        if not self._test_results and not self._analysis_results:
            QMessageBox.warning(
                self.parent_widget,
                "No Data Available",
                "No test results or analysis data available for reporting.\n"
                "Please run tests and analysis first.",
            )
            return

        dialog = ReportGenerationDialog(
            test_results=self._test_results,
            analysis_results=self._analysis_results,
            parent=self.parent_widget,
        )
        dialog.report_generated.connect(self._on_report_generated)
        dialog.exec()

    def generate_quick_report(
        self, report_type: ReportType, report_format: ReportFormat = ReportFormat.HTML
    ):
        """Generate a quick report with default settings."""
        try:
            # Get default output path
            default_name = f"pytest_report_{report_type.value}.{report_format.value.lower()}"
            output_path = Path.cwd() / default_name

            config = ReportConfig(
                report_type=report_type,
                format=report_format,
                output_path=output_path,
                title="Pytest Analysis Report",
                include_charts=True,
                include_analysis_details=True,
                include_fix_suggestions=True,
            )

            self.report_generation_started.emit()

            file_path = self.generator.generate_report(
                config=config,
                test_results=self._test_results,
                analysis_results=self._analysis_results,
            )

            self._on_report_generated(str(file_path))
            self.report_generation_finished.emit(True, f"Report saved to {file_path}")

        except Exception as e:
            logger.error(f"Failed to generate quick report: {e}")
            self.report_generation_finished.emit(False, f"Failed to generate report: {str(e)}")

    def export_to_format(self, report_format: ReportFormat):
        """Export current data to specified format with file dialog."""
        if not self._test_results and not self._analysis_results:
            QMessageBox.warning(
                self.parent_widget, "No Data Available", "No data available for export."
            )
            return

        # File dialog for export location
        filters = {
            ReportFormat.HTML: "HTML Files (*.html)",
            ReportFormat.PDF: "PDF Files (*.pdf)",
            ReportFormat.JSON: "JSON Files (*.json)",
            ReportFormat.CSV: "CSV Files (*.csv)",
        }

        file_path, _ = QFileDialog.getSaveFileName(
            self.parent_widget,
            f"Export {report_format.value.upper()} Report",
            f"pytest_export.{report_format.value.lower()}",
            filters.get(report_format, "All Files (*)"),
        )

        if not file_path:
            return

        try:
            config = ReportConfig(
                report_type=ReportType.FULL_ANALYSIS,
                format=report_format,
                output_path=Path(file_path),
                title="Pytest Analysis Export",
                include_charts=True,
                include_analysis_details=True,
                include_fix_suggestions=True,
            )

            self.report_generation_started.emit()

            generated_path = self.generator.generate_report(
                config=config,
                test_results=self._test_results,
                analysis_results=self._analysis_results,
            )

            self._on_report_generated(str(generated_path))
            self.report_generation_finished.emit(True, f"Export saved to {generated_path}")

        except Exception as e:
            logger.error(f"Failed to export to {report_format.value}: {e}")
            self.report_generation_finished.emit(False, f"Export failed: {str(e)}")

    def get_recent_reports(self) -> List[str]:
        """Get list of recently generated reports."""
        return self._recent_reports.copy()

    def open_recent_report(self, file_path: str):
        """Open a recent report file."""
        try:
            path = Path(file_path)
            if not path.exists():
                QMessageBox.warning(
                    self.parent_widget, "File Not Found", f"Report file not found: {file_path}"
                )
                # Remove from recent list
                if file_path in self._recent_reports:
                    self._recent_reports.remove(file_path)
                return

            # Open with system default application
            import subprocess
            import sys

            if sys.platform == "win32":
                subprocess.run(["start", str(path)], shell=True, check=True)
            elif sys.platform == "darwin":
                subprocess.run(["open", str(path)], check=True)
            else:
                subprocess.run(["xdg-open", str(path)], check=True)

        except Exception as e:
            logger.error(f"Failed to open report {file_path}: {e}")
            QMessageBox.critical(
                self.parent_widget, "Open Error", f"Failed to open report: {str(e)}"
            )

    def clear_recent_reports(self):
        """Clear the recent reports list."""
        self._recent_reports.clear()
        logger.debug("Recent reports list cleared")

    @pyqtSlot(str)
    def _on_report_generated(self, file_path: str):
        """Handle successful report generation."""
        # Add to recent reports (max 10)
        if file_path in self._recent_reports:
            self._recent_reports.remove(file_path)
        self._recent_reports.insert(0, file_path)
        self._recent_reports = self._recent_reports[:10]

        logger.info(f"Report generated successfully: {file_path}")
        self.report_generated.emit(file_path)

        # Only show dialog if not in testing environment
        if not self._is_testing_environment():
            # Show success message with option to open
            reply = QMessageBox.question(
                self.parent_widget,
                "Report Generated",
                f"Report saved successfully to:\n{file_path}\n\nWould you like to open it now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )

            if reply == QMessageBox.StandardButton.Yes:
                self.open_recent_report(file_path)

    def has_data_for_reporting(self) -> bool:
        """Check if there is data available for reporting."""
        return bool(self._test_results or self._analysis_results)

    def _is_testing_environment(self) -> bool:
        """Check if we're running in a testing environment."""
        import os
        import sys

        # Check for pytest runner
        if "pytest" in sys.modules or "pytest" in sys.argv[0]:
            return True

        # Check for test environment variables
        if os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("TESTING"):
            return True

        # Check if any test modules are in the current stack
        import inspect

        for frame_info in inspect.stack():
            if "test_" in frame_info.filename or "/tests/" in frame_info.filename:
                return True

        return False

    def get_available_report_types(self) -> List[ReportType]:
        """Get list of available report types based on current data."""
        available_types: List[ReportType] = []

        if self._test_results:
            available_types.extend(
                [ReportType.FULL_ANALYSIS, ReportType.SUMMARY, ReportType.COVERAGE]
            )

        if self._analysis_results:
            available_types.append(ReportType.FIX_HISTORY)

        return available_types

    def get_report_statistics(self) -> Dict[str, int]:
        """Get statistics about available data for reporting."""
        stats = {
            "total_tests": 0,
            "failed_tests": 0,
            "passed_tests": 0,
            "analysis_items": 0,
            "fix_suggestions": 0,
        }

        if self._test_results:
            stats["total_tests"] = len(self._test_results)
            stats["failed_tests"] = sum(
                1 for result in self._test_results if not result.get("passed", True)
            )
            stats["passed_tests"] = stats["total_tests"] - stats["failed_tests"]

        if self._analysis_results:
            stats["analysis_items"] = len(self._analysis_results)
            stats["fix_suggestions"] = sum(
                len(result.get("suggestions", [])) for result in self._analysis_results
            )

        return stats
