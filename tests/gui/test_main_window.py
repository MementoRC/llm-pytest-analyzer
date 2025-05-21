"""
Tests for the MainWindow class.

This module contains tests for the main window UI and functionality.
"""

import pytest
from PyQt6.QtWidgets import QMessageBox
from pytestqt.plugin import QtBot

from pytest_analyzer.gui.main_window import MainWindow

# Mark all tests in this module as GUI tests
pytestmark = pytest.mark.gui


def test_main_window_initialization(main_window: MainWindow) -> None:
    """Test that the main window initializes correctly."""
    # Check that the window has the correct title
    assert main_window.windowTitle() == "Pytest Analyzer"

    # Check that the window is visible
    assert main_window.isVisible()

    # Check that the main UI components are created
    assert main_window.main_splitter is not None
    assert main_window.test_selection_widget is not None
    assert main_window.analysis_widget is not None

    # Check that the menus are created
    assert main_window.file_menu is not None
    assert main_window.edit_menu is not None
    assert main_window.tools_menu is not None
    assert main_window.help_menu is not None

    # Check that the toolbar is created
    assert main_window.main_toolbar is not None

    # Check that the status bar is created
    assert main_window.status_bar is not None
    assert main_window.status_label is not None
    assert main_window.llm_status_label is not None


def test_window_actions(main_window: MainWindow) -> None:
    """Test that the window actions are correctly set up."""
    # Check that the actions are created
    assert main_window.open_action is not None
    assert main_window.exit_action is not None
    assert main_window.settings_action is not None
    assert main_window.run_tests_action is not None
    assert main_window.analyze_action is not None
    assert main_window.about_action is not None


def test_about_dialog(
    main_window: MainWindow, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that the about dialog shows correctly."""
    # Mock QMessageBox.about to capture the call
    shown_about = False
    title = ""
    text = ""

    def mock_about(parent: MainWindow, about_title: str, about_text: str) -> None:
        nonlocal shown_about, title, text
        shown_about = True
        title = about_title
        text = about_text

    monkeypatch.setattr(QMessageBox, "about", mock_about)

    # Click the About action
    main_window.on_about()

    # Check that QMessageBox.about was called with the correct parameters
    assert shown_about
    assert title == "About Pytest Analyzer"
    assert "Pytest Analyzer" in text
    assert "analyzing pytest test failures" in text.lower()


def test_settings_dialog(
    main_window: MainWindow, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that the settings dialog shows correctly."""
    # Mock QMessageBox.information to capture the call
    shown_info = False
    title = ""
    text = ""

    def mock_information(parent: MainWindow, info_title: str, info_text: str) -> None:
        nonlocal shown_info, title, text
        shown_info = True
        title = info_title
        text = info_text

    monkeypatch.setattr(QMessageBox, "information", mock_information)

    # Click the Settings action
    main_window.on_settings()

    # Check that QMessageBox.information was called with the correct parameters
    assert shown_info
    assert title == "Settings"
    assert "Settings dialog" in text
