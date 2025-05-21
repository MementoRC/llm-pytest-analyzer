"""
Tests for the PytestAnalyzerApp class.

This module contains tests for the application initialization and settings.
"""

from pathlib import Path

import pytest

from pytest_analyzer.gui.app import PytestAnalyzerApp

# Mark all tests in this module as GUI tests
pytestmark = pytest.mark.gui


def test_app_initialization(qapp: PytestAnalyzerApp) -> None:
    """Test that the application initializes correctly."""
    # Check that the application has the correct properties
    assert qapp.applicationName() == "Pytest Analyzer"
    assert qapp.applicationVersion() != ""
    assert qapp.style().objectName() == "fusion"


def test_app_settings(qapp: PytestAnalyzerApp) -> None:
    """Test that the application settings work correctly."""
    # Set a test setting
    qapp.set_setting("test_key", "test_value")

    # Get the setting back
    value = qapp.get_setting("test_key")

    # Check that the setting was stored correctly
    assert value == "test_value"


def test_core_settings_loaded(qapp: PytestAnalyzerApp) -> None:
    """Test that the core settings are loaded."""
    # Check that core settings are initialized
    assert qapp.core_settings is not None
    assert isinstance(qapp.core_settings.project_root, Path)


def test_app_settings_persistence(qapp_session: PytestAnalyzerApp) -> None:
    """Test that settings persist within the session."""
    # We use qapp_session to ensure we get the same instance
    # Set a test setting
    qapp_session.set_setting("persistence_test", "persisted_value")

    # Get the setting back immediately
    value = qapp_session.get_setting("persistence_test")

    # Check that it's available
    assert value == "persisted_value"
