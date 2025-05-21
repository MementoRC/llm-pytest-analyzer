"""
Main application module for the Pytest Analyzer GUI.

This module contains the QApplication instance and initialization logic
for the Pytest Analyzer GUI.
"""

import sys
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QSettings, Qt

from ..utils.settings import Settings

# Configure logging
logger = logging.getLogger(__name__)


class PytestAnalyzerApp(QApplication):
    """
    Main application class for the Pytest Analyzer GUI.
    
    This class initializes the QApplication and provides global
    application resources and settings.
    """
    
    def __init__(self, argv: List[str]):
        """
        Initialize the application.
        
        Args:
            argv: Command line arguments
        """
        super().__init__(argv)
        
        # Set application information
        self.setApplicationName("Pytest Analyzer")
        self.setApplicationVersion("0.1.0")  # Should match the package version
        self.setOrganizationName("MementoRC")
        self.setOrganizationDomain("github.com/MementoRC/llm-pytest-analyzer")
        
        # Default to fusion style for consistent cross-platform look
        self.setStyle("Fusion")
        
        # Initialize settings
        self._init_settings()
        
        # Load application resources
        self._init_resources()
        
        logger.info("PytestAnalyzerApp initialized")
    
    def _init_settings(self) -> None:
        """Initialize application settings."""
        # Create QSettings for GUI-specific settings
        self.settings = QSettings()
        
        # Load core settings
        self.core_settings = Settings()
        
        # Try to load settings from last session
        if self.settings.contains("core_settings/project_root"):
            project_root = self.settings.value("core_settings/project_root", "")
            if project_root and Path(project_root).exists():
                self.core_settings.project_root = Path(project_root)
    
    def _init_resources(self) -> None:
        """Initialize application resources like icons and themes."""
        # TODO: Add proper resource loading when resources are added
        # self.setWindowIcon(QIcon(":/icons/app_icon.png"))
        pass
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """
        Get a GUI setting by key.
        
        Args:
            key: The setting key
            default: Default value if setting doesn't exist
            
        Returns:
            The setting value
        """
        return self.settings.value(key, default)
    
    def set_setting(self, key: str, value: Any) -> None:
        """
        Set a GUI setting.
        
        Args:
            key: The setting key
            value: The setting value
        """
        self.settings.setValue(key, value)
        self.settings.sync()


def create_app(argv: Optional[List[str]] = None) -> PytestAnalyzerApp:
    """
    Create and initialize the application.
    
    Args:
        argv: Command line arguments (defaults to sys.argv)
        
    Returns:
        The initialized application instance
    """
    if argv is None:
        argv = sys.argv
        
    # Enable high DPI scaling
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    
    # Create the application
    app = PytestAnalyzerApp(argv)
    
    return app