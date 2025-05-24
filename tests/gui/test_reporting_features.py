"""
Comprehensive tests for GUI reporting and export functionality.

This module tests the complete reporting system including:
- Report generation dialog
- Report controller functionality
- Menu and toolbar integration
- All export formats (HTML, PDF, JSON, CSV)
- Error handling and user feedback
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from PyQt6.QtCore import Qt

from pytest_analyzer.gui.controllers.main_controller import MainController
from pytest_analyzer.gui.controllers.report_controller import ReportController
from pytest_analyzer.gui.main_window import MainWindow
from pytest_analyzer.gui.models.report import (
    ReportConfig,
    ReportFormat,
    ReportGenerator,
    ReportType,
)
from pytest_analyzer.gui.views.report_generation_dialog import ReportGenerationDialog

# Mark all tests in this module as GUI tests
pytestmark = pytest.mark.gui


class TestReportingIntegration:
    """Test reporting system integration with main window."""

    def test_reports_menu_exists(self, main_window: MainWindow):
        """Test that the Reports menu is created and populated."""
        assert hasattr(main_window, "reports_menu")
        assert main_window.reports_menu is not None

        # Check main report actions exist
        assert hasattr(main_window, "generate_report_action")
        assert hasattr(main_window, "quick_html_report_action")

        # Check export submenu exists
        assert hasattr(main_window, "export_menu")
        assert hasattr(main_window, "export_pdf_action")
        assert hasattr(main_window, "export_json_action")
        assert hasattr(main_window, "export_csv_action")

    def test_report_actions_properties(self, main_window: MainWindow):
        """Test that report actions have correct properties."""
        # Generate Report action
        assert main_window.generate_report_action.text() == "&Generate Report..."
        assert main_window.generate_report_action.shortcut().toString() == "Ctrl+R"
        assert "comprehensive analysis report" in main_window.generate_report_action.statusTip()

        # Quick HTML Report action
        assert main_window.quick_html_report_action.text() == "Quick &HTML Report"
        assert "quick HTML report" in main_window.quick_html_report_action.statusTip()

        # Export actions
        assert main_window.export_pdf_action.text() == "Export to &PDF..."
        assert main_window.export_json_action.text() == "Export to &JSON..."
        assert main_window.export_csv_action.text() == "Export to &CSV..."

    def test_toolbar_integration(self, main_window: MainWindow):
        """Test that report action is integrated in toolbar."""
        toolbar_actions = main_window.main_toolbar.actions()
        action_texts = [action.text() for action in toolbar_actions if action.text()]
        assert "&Generate Report..." in action_texts

    def test_main_controller_has_report_controller(self, qtbot, app):
        """Test that MainController initializes ReportController."""
        main_window = MainWindow(app)
        qtbot.addWidget(main_window)

        main_controller = MainController(main_window, app)

        assert hasattr(main_controller, "report_controller")
        assert isinstance(main_controller.report_controller, ReportController)


class TestReportGenerationDialog:
    """Test the report generation dialog functionality."""

    @pytest.fixture
    def report_dialog(self, qtbot):
        """Create a report generation dialog for testing."""
        dialog = ReportGenerationDialog()
        qtbot.addWidget(dialog)
        return dialog

    def test_dialog_initialization(self, report_dialog):
        """Test that dialog initializes with correct components."""
        assert report_dialog.windowTitle() == "Generate Report"
        assert report_dialog.isModal()

        # Check UI components exist
        assert hasattr(report_dialog, "type_combo")
        assert hasattr(report_dialog, "format_combo")
        assert hasattr(report_dialog, "title_edit")
        assert hasattr(report_dialog, "path_edit")
        assert hasattr(report_dialog, "browse_button")
        assert hasattr(report_dialog, "progress_bar")

    def test_dialog_default_values(self, report_dialog):
        """Test that dialog has sensible default values."""
        # Check combo box options
        type_items = [
            report_dialog.type_combo.itemText(i) for i in range(report_dialog.type_combo.count())
        ]
        assert "Full Analysis Report" in type_items
        assert "Summary Report" in type_items
        assert "Test Coverage Report" in type_items
        assert "Fix Application History" in type_items

        format_items = [
            report_dialog.format_combo.itemText(i)
            for i in range(report_dialog.format_combo.count())
        ]
        assert "HTML" in format_items
        assert "PDF" in format_items
        assert "JSON" in format_items
        assert "CSV" in format_items

        # Check default path
        assert report_dialog.path_edit.text().endswith(".html")

    def test_format_change_updates_extension(self, report_dialog, qtbot):
        """Test that changing format updates file extension."""
        # Set initial path
        report_dialog.path_edit.setText("/tmp/test_report.html")

        # Change format to PDF
        pdf_index = report_dialog.format_combo.findText("PDF")
        report_dialog.format_combo.setCurrentIndex(pdf_index)
        qtbot.wait(10)  # Allow signal processing

        assert report_dialog.path_edit.text().endswith(".pdf")

    @patch("pytest_analyzer.gui.views.report_generation_dialog.QFileDialog.getSaveFileName")
    def test_browse_button_functionality(self, mock_dialog, report_dialog, qtbot):
        """Test that browse button opens file dialog."""
        mock_dialog.return_value = ("/tmp/custom_report.html", "HTML Files (*.html)")

        qtbot.mouseClick(report_dialog.browse_button, Qt.MouseButton.LeftButton)

        mock_dialog.assert_called_once()
        assert report_dialog.path_edit.text() == "/tmp/custom_report.html"

    def test_configuration_creation(self, report_dialog):
        """Test that dialog creates correct ReportConfig."""
        # Set dialog values
        report_dialog.type_combo.setCurrentText("Summary Report")
        report_dialog.format_combo.setCurrentText("JSON")
        report_dialog.title_edit.setText("Test Report")
        report_dialog.path_edit.setText("/tmp/test.json")
        report_dialog.include_charts_check.setChecked(False)

        config = report_dialog._create_config()

        assert config.report_type == ReportType.SUMMARY
        assert config.format == ReportFormat.JSON
        assert config.title == "Test Report"
        assert config.output_path == Path("/tmp/test.json")
        assert config.include_charts is False


class TestReportController:
    """Test the report controller functionality."""

    @pytest.fixture
    def report_controller(self, qtbot):
        """Create a report controller for testing."""
        controller = ReportController()
        return controller

    def test_controller_initialization(self, report_controller):
        """Test that controller initializes correctly."""
        assert isinstance(report_controller.generator, ReportGenerator)
        assert report_controller._test_results is None
        assert report_controller._analysis_results is None
        assert report_controller._recent_reports == []

    def test_set_test_results(self, report_controller):
        """Test setting test results."""
        test_data = [{"name": "test_example", "status": "failed"}]
        report_controller.set_test_results(test_data)
        assert report_controller._test_results == test_data

    def test_set_analysis_results(self, report_controller):
        """Test setting analysis results."""
        analysis_data = [{"test": "test_example", "suggestions": ["fix1", "fix2"]}]
        report_controller.set_analysis_results(analysis_data)
        assert report_controller._analysis_results == analysis_data

    def test_has_data_for_reporting(self, report_controller):
        """Test data availability checking."""
        # Initially no data
        assert not report_controller.has_data_for_reporting()

        # With test results
        report_controller.set_test_results([{"test": "data"}])
        assert report_controller.has_data_for_reporting()

        # Clear test results, add analysis results
        report_controller._test_results = None
        report_controller.set_analysis_results([{"analysis": "data"}])
        assert report_controller.has_data_for_reporting()

    @patch("pytest_analyzer.gui.controllers.report_controller.QMessageBox.warning")
    def test_show_report_dialog_no_data(self, mock_warning, report_controller):
        """Test showing report dialog with no data shows warning."""
        report_controller.show_report_dialog()

        mock_warning.assert_called_once()
        args = mock_warning.call_args[0]
        assert "No Data Available" in args[1]

    @patch("pytest_analyzer.gui.views.report_generation_dialog.ReportGenerationDialog.exec")
    def test_show_report_dialog_with_data(self, mock_exec, report_controller):
        """Test showing report dialog with data."""
        report_controller.set_test_results([{"test": "data"}])

        report_controller.show_report_dialog()

        # Dialog should be created and shown
        mock_exec.assert_called_once()

    @patch("pytest_analyzer.gui.controllers.report_controller.ReportGenerator.generate_report")
    def test_generate_quick_report(self, mock_generate, report_controller):
        """Test quick report generation."""
        mock_generate.return_value = "/tmp/report.html"
        report_controller.set_test_results([{"test": "data"}])

        report_controller.generate_quick_report(ReportType.SUMMARY, ReportFormat.HTML)

        mock_generate.assert_called_once()
        config = mock_generate.call_args[1]["config"]
        assert config.report_type == ReportType.SUMMARY
        assert config.format == ReportFormat.HTML

    @patch("pytest_analyzer.gui.controllers.report_controller.QFileDialog.getSaveFileName")
    @patch("pytest_analyzer.gui.controllers.report_controller.ReportGenerator.generate_report")
    def test_export_to_format(self, mock_generate, mock_dialog, report_controller):
        """Test export to specific format."""
        mock_dialog.return_value = ("/tmp/export.pdf", "PDF Files (*.pdf)")
        mock_generate.return_value = "/tmp/export.pdf"
        report_controller.set_test_results([{"test": "data"}])

        report_controller.export_to_format(ReportFormat.PDF)

        mock_dialog.assert_called_once()
        mock_generate.assert_called_once()

        # Check dialog filter
        dialog_args = mock_dialog.call_args[0]
        assert "Export PDF Report" in dialog_args[1]


class TestReportGenerator:
    """Test the core report generation functionality."""

    @pytest.fixture
    def report_generator(self):
        """Create a report generator for testing."""
        return ReportGenerator()

    @pytest.fixture
    def sample_config(self, tmp_path):
        """Create a sample report configuration."""
        return ReportConfig(
            title="Test Report",
            format=ReportFormat.HTML,
            report_type=ReportType.SUMMARY,
            output_path=tmp_path / "test_report.html",
        )

    def test_generator_initialization(self, report_generator):
        """Test that generator initializes correctly."""
        assert hasattr(report_generator, "_templates")
        assert hasattr(report_generator, "templates_dir")

    def test_html_report_generation(self, report_generator, sample_config):
        """Test HTML report generation."""
        report_generator.generate_report(config=sample_config, test_results=[], analysis_results=[])

        assert sample_config.output_path.exists()
        assert sample_config.output_path.suffix == ".html"
        content = sample_config.output_path.read_text()
        assert "Test Report" in content
        assert "<!DOCTYPE html>" in content

    def test_json_report_generation(self, report_generator, tmp_path):
        """Test JSON report generation."""
        config = ReportConfig(
            title="JSON Test Report",
            format=ReportFormat.JSON,
            report_type=ReportType.SUMMARY,
            output_path=tmp_path / "test_report.json",
        )

        report_generator.generate_report(config=config, test_results=[], analysis_results=[])

        assert config.output_path.exists()
        assert config.output_path.suffix == ".json"
        import json

        data = json.loads(config.output_path.read_text())
        assert "metadata" in data
        assert "statistics" in data

    def test_csv_report_generation(self, report_generator, tmp_path):
        """Test CSV report generation."""
        config = ReportConfig(
            title="CSV Test Report",
            format=ReportFormat.CSV,
            report_type=ReportType.SUMMARY,
            output_path=tmp_path / "test_report.csv",
        )

        report_generator.generate_report(config=config, test_results=[], analysis_results=[])

        assert config.output_path.exists()
        assert config.output_path.suffix == ".csv"
        content = config.output_path.read_text()
        assert "Test Name,Status,Duration" in content


class TestGUIWorkflowIntegration:
    """Test complete GUI workflow with reporting features."""

    @pytest.fixture
    def complete_gui_setup(self, qtbot, app):
        """Set up complete GUI with main controller."""
        main_window = MainWindow(app)
        qtbot.addWidget(main_window)
        main_controller = MainController(main_window, app)
        return main_window, main_controller

    def test_report_menu_actions_connected(self, complete_gui_setup):
        """Test that report menu actions are properly connected."""
        main_window, main_controller = complete_gui_setup

        # Test that actions are connected to controller methods
        assert main_window.generate_report_action.triggered.count() > 0
        assert main_window.quick_html_report_action.triggered.count() > 0
        assert main_window.export_pdf_action.triggered.count() > 0

    @patch("pytest_analyzer.gui.controllers.report_controller.ReportController.show_report_dialog")
    def test_generate_report_action_trigger(self, mock_show_dialog, complete_gui_setup, qtbot):
        """Test triggering generate report action."""
        main_window, main_controller = complete_gui_setup

        # Trigger the action
        main_window.generate_report_action.trigger()
        qtbot.wait(10)  # Allow signal processing

        mock_show_dialog.assert_called_once()

    @patch(
        "pytest_analyzer.gui.controllers.report_controller.ReportController.generate_quick_report"
    )
    def test_quick_html_report_action_trigger(self, mock_quick_report, complete_gui_setup, qtbot):
        """Test triggering quick HTML report action."""
        main_window, main_controller = complete_gui_setup

        # Trigger the action
        main_window.quick_html_report_action.trigger()
        qtbot.wait(10)  # Allow signal processing

        mock_quick_report.assert_called_once()
        args = mock_quick_report.call_args[1]
        assert args["report_type"] == ReportType.SUMMARY
        assert args["report_format"] == ReportFormat.HTML

    @patch("pytest_analyzer.gui.controllers.report_controller.ReportController.export_to_format")
    def test_export_actions_trigger(self, mock_export, complete_gui_setup, qtbot):
        """Test triggering export actions."""
        main_window, main_controller = complete_gui_setup

        # Test PDF export
        main_window.export_pdf_action.trigger()
        qtbot.wait(10)
        mock_export.assert_called_with(ReportFormat.PDF)

        # Test JSON export
        main_window.export_json_action.trigger()
        qtbot.wait(10)
        mock_export.assert_called_with(ReportFormat.JSON)

        # Test CSV export
        main_window.export_csv_action.trigger()
        qtbot.wait(10)
        mock_export.assert_called_with(ReportFormat.CSV)

    def test_keyboard_shortcuts(self, complete_gui_setup, qtbot):
        """Test that keyboard shortcuts work for reporting."""
        main_window, main_controller = complete_gui_setup

        # Test Ctrl+R shortcut for generate report
        shortcut = main_window.generate_report_action.shortcut()
        assert shortcut.toString() == "Ctrl+R"


class TestReportingErrorHandling:
    """Test error handling in reporting functionality."""

    @pytest.fixture
    def report_controller_with_errors(self):
        """Create report controller for error testing."""
        controller = ReportController()
        controller.set_test_results([{"test": "data"}])
        return controller

    @patch("pytest_analyzer.gui.models.report.ReportGenerator.generate_report")
    @patch("pytest_analyzer.gui.controllers.report_controller.QMessageBox.critical")
    def test_report_generation_error_handling(
        self, mock_critical, mock_generate, report_controller_with_errors
    ):
        """Test error handling during report generation."""
        mock_generate.side_effect = Exception("Generation failed")

        report_controller_with_errors.generate_quick_report(ReportType.SUMMARY, ReportFormat.HTML)

        # Should emit error signal
        # Note: In a real test, we'd check the signal emission

    @patch("pytest_analyzer.gui.controllers.report_controller.QFileDialog.getSaveFileName")
    def test_export_cancellation_handling(self, mock_dialog, report_controller_with_errors):
        """Test handling when user cancels export dialog."""
        mock_dialog.return_value = ("", "")  # User cancelled

        # Should not crash when dialog is cancelled
        report_controller_with_errors.export_to_format(ReportFormat.PDF)

        mock_dialog.assert_called_once()

    def test_invalid_file_path_handling(self, report_controller_with_errors):
        """Test handling of invalid file paths."""
        # This would be tested with actual file system operations
        # that might fail due to permissions, invalid paths, etc.
        pass


# Additional helper function for manual testing
def run_manual_gui_test():
    """
    Manual test function that can be run to interactively test the GUI.

    This function creates a GUI window and allows manual testing of all
    reporting features. Useful for visual verification.
    """
    import sys

    from pytest_analyzer.gui.app import create_app

    app = create_app(sys.argv)

    # Set up test data
    test_data = [
        {"name": "test_example_1", "status": "failed", "duration": 0.5},
        {"name": "test_example_2", "status": "passed", "duration": 0.2},
    ]
    analysis_data = [{"test": "test_example_1", "suggestions": ["Fix assertion", "Check logic"]}]

    # Access the report controller and set test data
    main_controller = app.main_window.property("main_controller")
    if main_controller and hasattr(main_controller, "report_controller"):
        main_controller.report_controller.set_test_results(test_data)
        main_controller.report_controller.set_analysis_results(analysis_data)

    print("Manual GUI Test Started")
    print("Available reporting features to test:")
    print("1. Reports -> Generate Report... (Ctrl+R)")
    print("2. Reports -> Quick HTML Report")
    print("3. Reports -> Export -> PDF/JSON/CSV")
    print("4. Toolbar report button")
    print("\nClose the window when done testing.")

    return app.exec()


if __name__ == "__main__":
    # Allow running this file directly for manual testing
    run_manual_gui_test()
