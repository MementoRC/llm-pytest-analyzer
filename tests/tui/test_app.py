"""
Tests for the TUI application.

This module contains tests for the main TUI application class and basic
functionality verification.
"""

import pytest

from pytest_analyzer.tui.app import TUIApp


class TestTUIApp:
    """Test cases for the TUI application."""

    @pytest.mark.asyncio
    async def test_app_creation(self, tui_app: TUIApp) -> None:
        """Test that TUI app can be created successfully."""
        assert tui_app is not None
        assert tui_app.title == "Pytest Analyzer TUI"
        assert tui_app.settings is not None
        assert tui_app.analyzer_service is not None

    @pytest.mark.asyncio
    async def test_app_startup(self, tui_app: TUIApp) -> None:
        """Test that TUI app can start up without errors."""
        # This test verifies the app can run in headless mode
        # without crashing or compromising the terminal
        async with tui_app.run_test() as pilot:
            assert pilot is not None

            # Test basic functionality - the app starts without errors
            app = pilot.app
            assert app.title == "Pytest Analyzer TUI"

            # Test that we can simulate key presses safely
            await pilot.press("q")  # This should not actually quit in test mode

    @pytest.mark.asyncio
    async def test_main_view_loads(self, tui_app: TUIApp) -> None:
        """Test that the main view loads properly."""
        async with tui_app.run_test() as pilot:
            # Wait for the app to fully load
            await pilot.pause()

            # Verify main screen is loaded
            assert pilot.app.screen is not None

            # Test we can press quit key without crashing
            await pilot.press("ctrl+q")
