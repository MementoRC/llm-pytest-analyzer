"""
Test configuration for GUI tests.

This module contains fixtures and configuration for testing GUI components.
"""

import os
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

# Skip all GUI tests if we don't have a display
if os.environ.get("DISPLAY", "") == "" and os.environ.get("QT_QPA_PLATFORM", "") == "":
    pytest.skip("No display available for GUI tests", allow_module_level=True)

from pytestqt.plugin import QtBot

from pytest_analyzer.gui.app import PytestAnalyzerApp, create_app
from pytest_analyzer.gui.main_window import MainWindow


# Ensure QApplication is only created once
@pytest.fixture(scope="session")
def qapp_session() -> PytestAnalyzerApp:
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

    return app


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
