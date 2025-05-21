"""
Test configuration for GUI tests.

This module contains fixtures and configuration for testing GUI components.
"""

import os
import sys
import pytest
from pathlib import Path
from typing import Generator, Any

from PyQt6.QtWidgets import QApplication
from pytestqt.plugin import QtBot

from pytest_analyzer.gui.app import create_app, PytestAnalyzerApp
from pytest_analyzer.gui.main_window import MainWindow


# Ensure QApplication is only created once
@pytest.fixture(scope="session")
def qapp_session() -> Generator[PytestAnalyzerApp, None, None]:
    """
    Create a QApplication for the entire test session.
    
    Returns:
        A PytestAnalyzerApp instance
    """
    # Create a clean environment for testing
    os.environ.pop("QT_QPA_PLATFORM", None)  # Use the default platform
    
    # Create the application with test-specific arguments
    app = create_app(["pytest-analyzer-gui", "--test-mode"])
    
    # Set the application to test mode
    app.set_setting("test_mode", True)
    app.set_setting("core_settings/project_root", str(Path.cwd()))
    
    yield app


@pytest.fixture
def qapp(qapp_session: PytestAnalyzerApp) -> PytestAnalyzerApp:
    """
    Provide the QApplication for a single test.
    
    Args:
        qapp_session: The session-level QApplication
        
    Returns:
        The same QApplication instance
    """
    # Process any pending events before starting a new test
    qapp_session.processEvents()
    return qapp_session


@pytest.fixture
def main_window(qapp: PytestAnalyzerApp, qtbot: QtBot) -> Generator[MainWindow, None, None]:
    """
    Create and yield a MainWindow instance.
    
    Args:
        qapp: The QApplication instance
        qtbot: The QtBot fixture from pytest-qt
        
    Returns:
        A MainWindow instance
    """
    # Create a main window
    window = MainWindow(qapp)
    
    # Add the window to qtbot for cleanup
    qtbot.add_widget(window)
    
    # Show the window (important for some tests)
    window.show()
    qtbot.waitExposed(window)
    
    yield window
    
    # Clean up after the test
    window.close()


@pytest.fixture
def mock_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Mock settings to use test values.
    
    Args:
        monkeypatch: The monkeypatch fixture
    """
    # Example of mocking settings if needed
    from pytest_analyzer.utils.settings import Settings
    
    def mock_load_settings(*args: Any, **kwargs: Any) -> Settings:
        """Return a test settings object."""
        settings = Settings()
        settings.project_root = Path.cwd()
        return settings
    
    monkeypatch.setattr("pytest_analyzer.utils.settings.load_settings", mock_load_settings)