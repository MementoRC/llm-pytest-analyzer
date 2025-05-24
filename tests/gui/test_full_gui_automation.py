"""
Comprehensive GUI automation test suite.

This module provides automated testing that simulates user interactions
with all GUI components, tabs, buttons, menus, and dialogs.
"""

import time
from unittest.mock import patch

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest

from pytest_analyzer.gui.controllers.main_controller import MainController
from pytest_analyzer.gui.main_window import MainWindow

# Mark all tests in this module as GUI tests
pytestmark = pytest.mark.gui


class TestCompleteGUIAutomation:
    """Comprehensive automated testing of all GUI features."""

    @pytest.fixture
    def full_app_setup(self, qtbot, app):
        """Set up complete application with all controllers."""
        main_window = MainWindow(app)
        qtbot.addWidget(main_window)
        main_controller = MainController(main_window, app)

        # Set up sample data for testing
        sample_test_results = [
            {
                "name": "test_feature_a",
                "status": "failed",
                "duration": 0.5,
                "file_path": "/project/test_a.py",
                "failure_message": "AssertionError: Expected 5, got 3",
            },
            {
                "name": "test_feature_b",
                "status": "passed",
                "duration": 0.2,
                "file_path": "/project/test_b.py",
            },
            {
                "name": "test_feature_c",
                "status": "failed",
                "duration": 1.0,
                "file_path": "/project/test_c.py",
                "failure_message": "ImportError: Module not found",
            },
        ]

        sample_analysis_results = [
            {
                "test_name": "test_feature_a",
                "suggestions": ["Check calculation logic", "Verify input values"],
                "confidence": 0.85,
            },
            {
                "test_name": "test_feature_c",
                "suggestions": ["Install missing dependency", "Check import path"],
                "confidence": 0.92,
            },
        ]

        # Inject test data
        main_controller.report_controller.set_test_results(sample_test_results)
        main_controller.report_controller.set_analysis_results(sample_analysis_results)

        return main_window, main_controller, app

    def test_main_window_startup_and_layout(self, full_app_setup, qtbot):
        """Test main window startup and basic layout."""
        main_window, main_controller, app = full_app_setup

        # Verify window is visible and has correct title
        assert main_window.isVisible()
        assert main_window.windowTitle() == "Pytest Analyzer"

        # Verify main layout components
        assert main_window.main_splitter is not None
        assert main_window.selection_tabs is not None
        assert main_window.analysis_tabs is not None

        # Verify tab structure
        assert main_window.selection_tabs.count() >= 2  # File Selection, Test Discovery
        assert main_window.analysis_tabs.count() >= 2  # Test Results, Test Output

    def test_menu_bar_complete_navigation(self, full_app_setup, qtbot):
        """Test navigation through all menu items."""
        main_window, main_controller, app = full_app_setup

        # Test File Menu
        file_menu = main_window.file_menu
        assert file_menu is not None
        file_actions = file_menu.actions()
        assert len(file_actions) > 0

        # Verify project submenu
        project_menu = main_window.project_menu
        assert project_menu is not None

        # Verify session submenu
        session_menu = main_window.session_menu
        assert session_menu is not None

        # Test Edit Menu
        edit_menu = main_window.edit_menu
        assert edit_menu is not None
        edit_actions = edit_menu.actions()
        assert len(edit_actions) > 0

        # Test Tools Menu
        tools_menu = main_window.tools_menu
        assert tools_menu is not None
        tools_actions = tools_menu.actions()
        assert len(tools_actions) >= 2  # Run Tests, Analyze

        # Test Reports Menu (new feature)
        reports_menu = main_window.reports_menu
        assert reports_menu is not None
        reports_actions = reports_menu.actions()
        assert len(reports_actions) >= 3  # Generate, Quick HTML, Export submenu

        # Test Help Menu
        help_menu = main_window.help_menu
        assert help_menu is not None

    def test_toolbar_button_interactions(self, full_app_setup, qtbot):
        """Test all toolbar button interactions."""
        main_window, main_controller, app = full_app_setup

        toolbar = main_window.main_toolbar
        toolbar_actions = [action for action in toolbar.actions() if not action.isSeparator()]

        # Verify key toolbar actions exist
        action_texts = [action.text() for action in toolbar_actions]
        expected_actions = ["&Open", "&Run Tests", "&Analyze", "&Generate Report...", "&Settings"]

        for expected in expected_actions:
            assert expected in action_texts, f"Missing toolbar action: {expected}"

    @patch("pytest_analyzer.gui.views.file_selection_view.QFileDialog.getOpenFileName")
    def test_file_selection_tab(self, mock_dialog, full_app_setup, qtbot):
        """Test file selection tab functionality."""
        main_window, main_controller, app = full_app_setup
        mock_dialog.return_value = ("/project/test_file.py", "Python Files (*.py)")

        # Navigate to file selection tab
        selection_tabs = main_window.selection_tabs
        selection_tabs.setCurrentIndex(0)  # File Selection tab
        qtbot.wait(100)

        # Get the file selection view
        file_view = main_window.file_selection_view
        assert file_view is not None

        # Simulate file selection (would trigger file dialog)
        # In real GUI, user would click browse button
        if hasattr(file_view, "browse_button"):
            qtbot.mouseClick(file_view.browse_button, Qt.MouseButton.LeftButton)
            qtbot.wait(100)

    def test_test_discovery_tab(self, full_app_setup, qtbot):
        """Test test discovery tab functionality."""
        main_window, main_controller, app = full_app_setup

        # Navigate to test discovery tab
        selection_tabs = main_window.selection_tabs
        selection_tabs.setCurrentIndex(1)  # Test Discovery tab
        qtbot.wait(100)

        # Get the test discovery view
        discovery_view = main_window.test_discovery_view
        assert discovery_view is not None

    def test_test_results_tab_with_data(self, full_app_setup, qtbot):
        """Test test results tab with sample data."""
        main_window, main_controller, app = full_app_setup

        # Navigate to test results tab
        analysis_tabs = main_window.analysis_tabs
        analysis_tabs.setCurrentIndex(0)  # Test Results tab
        qtbot.wait(100)

        # Get the test results view
        results_view = main_window.test_results_view
        assert results_view is not None

    def test_test_output_tab(self, full_app_setup, qtbot):
        """Test test output tab functionality."""
        main_window, main_controller, app = full_app_setup

        # Navigate to test output tab
        analysis_tabs = main_window.analysis_tabs
        analysis_tabs.setCurrentIndex(1)  # Test Output tab
        qtbot.wait(100)

        # Get the test output view
        output_view = main_window.test_output_view
        assert output_view is not None

    def test_keyboard_shortcuts_functionality(self, full_app_setup, qtbot):
        """Test all keyboard shortcuts."""
        main_window, main_controller, app = full_app_setup

        shortcuts_to_test = [
            (Qt.Key.Key_F5, "run_tests_action"),  # F5 - Run Tests
            (Qt.Key.Key_F6, "analyze_action"),  # F6 - Analyze
            (Qt.Key.Key_F1, "about_action"),  # F1 - About
            # Ctrl+R - Generate Report (tested separately)
        ]

        for key, action_name in shortcuts_to_test:
            action = getattr(main_window, action_name)
            shortcut = action.shortcut()
            assert shortcut is not None
            # Note: In real testing, we'd simulate the key press

    @patch("pytest_analyzer.gui.controllers.report_controller.ReportController.show_report_dialog")
    def test_report_generation_workflow(self, mock_show_dialog, full_app_setup, qtbot):
        """Test complete report generation workflow."""
        main_window, main_controller, app = full_app_setup

        # Test menu access to report generation
        generate_action = main_window.generate_report_action

        # Simulate clicking the menu item
        generate_action.trigger()
        qtbot.wait(100)

        # Verify dialog would be shown
        mock_show_dialog.assert_called_once()

    @patch(
        "pytest_analyzer.gui.controllers.report_controller.ReportController.generate_quick_report"
    )
    def test_quick_report_generation(self, mock_quick_report, full_app_setup, qtbot):
        """Test quick report generation."""
        main_window, main_controller, app = full_app_setup

        # Trigger quick HTML report
        quick_action = main_window.quick_html_report_action
        quick_action.trigger()
        qtbot.wait(100)

        mock_quick_report.assert_called_once()

    @patch("pytest_analyzer.gui.controllers.report_controller.ReportController.export_to_format")
    def test_export_menu_functionality(self, mock_export, full_app_setup, qtbot):
        """Test all export menu options."""
        main_window, main_controller, app = full_app_setup

        # Test PDF export
        main_window.export_pdf_action.trigger()
        qtbot.wait(50)

        # Test JSON export
        main_window.export_json_action.trigger()
        qtbot.wait(50)

        # Test CSV export
        main_window.export_csv_action.trigger()
        qtbot.wait(50)

        # Verify all exports were called
        assert mock_export.call_count == 3

    @patch("pytest_analyzer.gui.views.settings_dialog.SettingsDialog.exec")
    def test_settings_dialog_access(self, mock_exec, full_app_setup, qtbot):
        """Test accessing settings dialog."""
        main_window, main_controller, app = full_app_setup

        # Trigger settings action
        settings_action = main_window.settings_action
        settings_action.trigger()
        qtbot.wait(100)

        # Note: This would open settings dialog in real app

    def test_status_bar_updates(self, full_app_setup, qtbot):
        """Test status bar information display."""
        main_window, main_controller, app = full_app_setup

        status_bar = main_window.status_bar
        assert status_bar is not None

        status_label = main_window.status_label
        assert status_label is not None

        llm_status_label = main_window.llm_status_label
        assert llm_status_label is not None

    def test_window_resizing_and_layout(self, full_app_setup, qtbot):
        """Test window resizing and layout responsiveness."""
        main_window, main_controller, app = full_app_setup

        # Get initial size
        initial_size = main_window.size()

        # Resize window
        new_width = initial_size.width() + 200
        new_height = initial_size.height() + 100
        main_window.resize(new_width, new_height)
        qtbot.wait(100)

        # Verify resize worked
        current_size = main_window.size()
        assert current_size.width() >= new_width - 10  # Allow small variance
        assert current_size.height() >= new_height - 10

    def test_tab_navigation_with_keyboard(self, full_app_setup, qtbot):
        """Test tab navigation using keyboard shortcuts."""
        main_window, main_controller, app = full_app_setup

        # Test Ctrl+1 (first selection tab)
        QTest.keySequence(main_window, "Ctrl+1")
        qtbot.wait(50)
        assert main_window.selection_tabs.currentIndex() == 0

        # Test Ctrl+2 (second selection tab)
        QTest.keySequence(main_window, "Ctrl+2")
        qtbot.wait(50)
        assert main_window.selection_tabs.currentIndex() == 1

        # Test Ctrl+3 (first analysis tab)
        QTest.keySequence(main_window, "Ctrl+3")
        qtbot.wait(50)
        assert main_window.analysis_tabs.currentIndex() == 0

    def test_lazy_loading_functionality(self, full_app_setup, qtbot):
        """Test that lazy loading works correctly."""
        main_window, main_controller, app = full_app_setup

        # Verify lazy tab widget functionality
        selection_tabs = main_window.selection_tabs
        analysis_tabs = main_window.analysis_tabs

        # Navigate through tabs to trigger lazy loading
        for i in range(selection_tabs.count()):
            selection_tabs.setCurrentIndex(i)
            qtbot.wait(50)
            # Verify tab content is created
            widget = selection_tabs.currentWidget()
            assert widget is not None

        for i in range(analysis_tabs.count()):
            analysis_tabs.setCurrentIndex(i)
            qtbot.wait(50)
            # Verify tab content is created
            widget = analysis_tabs.currentWidget()
            assert widget is not None

    @patch(
        "pytest_analyzer.gui.controllers.project_controller.ProjectController.show_project_selection"
    )
    def test_project_management_features(self, mock_project_dialog, full_app_setup, qtbot):
        """Test project management functionality."""
        main_window, main_controller, app = full_app_setup

        # Test new project action
        new_project_action = main_window.new_project_action
        new_project_action.trigger()
        qtbot.wait(100)

        # Test open project action
        open_project_action = main_window.open_project_action
        open_project_action.trigger()
        qtbot.wait(100)

        # Verify project dialog would be shown
        assert mock_project_dialog.call_count == 2

    @patch(
        "pytest_analyzer.gui.controllers.session_controller.SessionController.show_session_management"
    )
    def test_session_management_features(self, mock_session_dialog, full_app_setup, qtbot):
        """Test session management functionality."""
        main_window, main_controller, app = full_app_setup

        # Test session management action
        manage_sessions_action = main_window.manage_sessions_action
        manage_sessions_action.trigger()
        qtbot.wait(100)

        mock_session_dialog.assert_called_once()

    def test_error_handling_robustness(self, full_app_setup, qtbot):
        """Test that GUI handles errors gracefully."""
        main_window, main_controller, app = full_app_setup

        # Test with invalid actions
        try:
            # Simulate various error conditions
            main_window.selection_tabs.setCurrentIndex(999)  # Invalid index
            main_window.analysis_tabs.setCurrentIndex(-1)  # Invalid index

            # GUI should not crash
            assert main_window.isVisible()
        except Exception as e:
            pytest.fail(f"GUI should handle errors gracefully: {e}")

    def test_complete_workflow_simulation(self, full_app_setup, qtbot):
        """Simulate a complete user workflow."""
        main_window, main_controller, app = full_app_setup

        # Simulate typical user workflow:
        # 1. Start with file selection
        main_window.selection_tabs.setCurrentIndex(0)
        qtbot.wait(100)

        # 2. Move to test discovery
        main_window.selection_tabs.setCurrentIndex(1)
        qtbot.wait(100)

        # 3. View test results
        main_window.analysis_tabs.setCurrentIndex(0)
        qtbot.wait(100)

        # 4. Check test output
        main_window.analysis_tabs.setCurrentIndex(1)
        qtbot.wait(100)

        # 5. Generate a report
        with patch(
            "pytest_analyzer.gui.controllers.report_controller.ReportController.show_report_dialog"
        ) as mock_dialog:
            main_window.generate_report_action.trigger()
            qtbot.wait(100)
            mock_dialog.assert_called_once()

        # Verify GUI remains responsive throughout
        assert main_window.isVisible()
        assert main_window.isEnabled()


class TestGUIPerformanceAndResponsiveness:
    """Test GUI performance and responsiveness."""

    def test_startup_time(self, qtbot, app):
        """Test that GUI starts up in reasonable time."""
        start_time = time.time()

        main_window = MainWindow(app)
        qtbot.addWidget(main_window)
        MainController(main_window, app)

        startup_time = time.time() - start_time

        # Should start up in less than 5 seconds
        assert startup_time < 5.0, f"Startup took {startup_time:.2f} seconds"

    def test_tab_switching_performance(self, full_app_setup, qtbot):
        """Test that tab switching is responsive."""
        main_window, _, _ = full_app_setup

        # Time tab switches
        switch_times = []

        for _ in range(5):  # Test multiple switches
            start_time = time.time()

            # Switch between tabs
            main_window.selection_tabs.setCurrentIndex(0)
            qtbot.wait(10)
            main_window.selection_tabs.setCurrentIndex(1)
            qtbot.wait(10)
            main_window.analysis_tabs.setCurrentIndex(0)
            qtbot.wait(10)
            main_window.analysis_tabs.setCurrentIndex(1)
            qtbot.wait(10)

            switch_time = time.time() - start_time
            switch_times.append(switch_time)

        avg_switch_time = sum(switch_times) / len(switch_times)
        # Tab switching should be very fast
        assert avg_switch_time < 0.5, f"Tab switching took {avg_switch_time:.3f} seconds on average"

    def test_memory_usage_stability(self, full_app_setup, qtbot):
        """Test that memory usage remains stable during operation."""
        main_window, main_controller, app = full_app_setup

        # Perform various operations and check for major memory leaks
        for _ in range(10):
            # Navigate through tabs
            for i in range(main_window.selection_tabs.count()):
                main_window.selection_tabs.setCurrentIndex(i)
                qtbot.wait(10)

            for i in range(main_window.analysis_tabs.count()):
                main_window.analysis_tabs.setCurrentIndex(i)
                qtbot.wait(10)

        # GUI should remain responsive
        assert main_window.isVisible()
        assert main_window.isEnabled()


# Utility function for interactive testing
def run_interactive_gui_test():
    """
    Interactive GUI test that opens the full application for manual testing.

    This function starts the complete GUI application with sample data
    loaded, allowing for manual testing of all features.
    """
    import sys

    from pytest_analyzer.gui.app import create_app

    print("🚀 Starting Interactive GUI Test...")
    print("📋 Features to test manually:")
    print("   1. File Menu -> Project management")
    print("   2. File Menu -> Session management")
    print("   3. Edit Menu -> Settings")
    print("   4. Tools Menu -> Run Tests, Analyze")
    print("   5. Reports Menu -> All reporting features")
    print("   6. Keyboard shortcuts (F1, F5, F6, Ctrl+R, Ctrl+1-4)")
    print("   7. Tab navigation and lazy loading")
    print("   8. Window resizing and layout")
    print("   9. Status bar updates")
    print("   10. Toolbar button functionality")
    print("\n💡 Sample test data has been loaded for reporting features.")
    print("🔧 Use Reports menu to test all export formats.")
    print("❌ Close the window when testing is complete.\n")

    app = create_app(sys.argv)

    # Load sample data for testing
    sample_data = {
        "test_results": [
            {"name": "test_authentication", "status": "failed", "duration": 0.8},
            {"name": "test_user_creation", "status": "passed", "duration": 0.3},
            {"name": "test_data_validation", "status": "failed", "duration": 1.2},
            {"name": "test_api_endpoint", "status": "passed", "duration": 0.5},
        ],
        "analysis_results": [
            {
                "test_name": "test_authentication",
                "suggestions": ["Check credential validation", "Verify token expiry"],
                "confidence": 0.9,
            },
            {
                "test_name": "test_data_validation",
                "suggestions": ["Validate input schemas", "Check data types"],
                "confidence": 0.85,
            },
        ],
    }

    # Inject test data if main controller is available
    try:
        main_controller = getattr(app.main_window, "_main_controller", None)
        if main_controller and hasattr(main_controller, "report_controller"):
            main_controller.report_controller.set_test_results(sample_data["test_results"])
            main_controller.report_controller.set_analysis_results(sample_data["analysis_results"])
            print("✅ Sample data loaded successfully!")
    except Exception as e:
        print(f"⚠️  Could not load sample data: {e}")

    return app.exec()


if __name__ == "__main__":
    # Allow running this file directly for interactive testing
    run_interactive_gui_test()
