"""
Main entry point for the Pytest Analyzer TUI.
"""

import logging
import sys


def main() -> int:
    """Run the Textual TUI application."""
    # Ensure tui.app can be imported
    # This might require adjustments based on your project structure and PYTHONPATH
    try:
        from pytest_analyzer.tui.app import run_tui
    except ImportError as e:
        logging.basicConfig(level=logging.DEBUG)
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to import TUI components: {e}")
        logger.error("Ensure that the 'src' directory is in your PYTHONPATH if running directly.")
        print(
            "Error: Could not start TUI. Ensure pytest_analyzer is installed or PYTHONPATH is set.",
            file=sys.stderr,
        )
        return 1

    run_tui()
    return 0


if __name__ == "__main__":
    sys.exit(main())
