#!/usr/bin/env python3

"""
Main entry point for the Pytest Analyzer GUI.

This module allows the GUI to be launched directly with:
python -m pytest_analyzer.gui
"""

import logging
import sys

from pytest_analyzer.gui.app import create_app
from pytest_analyzer.gui.main_window import MainWindow
from pytest_analyzer.utils.logging_config import configure_logging
from pytest_analyzer.utils.settings import load_settings


def main() -> int:
    """
    Main entry point for the GUI application.

    Returns:
        Exit code
    """
    # Load settings and configure logging
    settings = load_settings(debug=False)
    configure_logging(settings)
    logger = logging.getLogger(__name__)

    try:
        # Create application
        app = create_app(sys.argv)

        # Create main window
        main_window = MainWindow(app)
        main_window.show()

        # Run application
        logger.info("Starting Pytest Analyzer GUI")
        return app.exec()

    except Exception as e:
        logger.exception(f"Error starting Pytest Analyzer GUI: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
