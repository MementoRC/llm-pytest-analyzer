"""
Test configuration for TUI tests.

This module contains fixtures and configuration for testing TUI components
using the Textual framework with pytest-asyncio.
"""

from pathlib import Path
from typing import Any, Generator
from unittest.mock import Mock

import pytest

from pytest_analyzer.core.analyzer_service import PytestAnalyzerService
from pytest_analyzer.tui.app import TUIApp
from pytest_analyzer.utils.settings import Settings


@pytest.fixture
def mock_settings() -> Settings:
    """
    Create mock settings for TUI testing.

    Returns:
        A Settings object configured for testing
    """
    settings = Settings()
    settings.project_root = Path.cwd()
    settings.llm_provider = "mock"  # Use mock LLM for testing
    return settings


@pytest.fixture
def mock_analyzer_service(mock_settings: Settings) -> Mock:
    """
    Create a mock analyzer service for TUI testing.

    Args:
        mock_settings: Mock settings fixture

    Returns:
        A mocked PytestAnalyzerService
    """
    service = Mock(spec=PytestAnalyzerService)
    service.settings = mock_settings
    return service


@pytest.fixture
def tui_app(mock_settings: Settings, mock_analyzer_service: Mock) -> TUIApp:
    """
    Create a TUI application instance for testing.

    Args:
        mock_settings: Mock settings fixture
        mock_analyzer_service: Mock analyzer service fixture

    Returns:
        A TUIApp instance configured for testing
    """
    return TUIApp(settings=mock_settings, analyzer_service=mock_analyzer_service)


@pytest.fixture
async def tui_app_pilot(tui_app: TUIApp) -> Generator[Any, None, None]:
    """
    Create a TUI application pilot for interaction testing.

    Args:
        tui_app: TUI application instance

    Yields:
        A textual pilot for simulating user interactions
    """
    async with tui_app.run_test() as pilot:
        yield pilot


# Add marker for TUI tests
pytest.mark.tui = pytest.mark.asyncio
