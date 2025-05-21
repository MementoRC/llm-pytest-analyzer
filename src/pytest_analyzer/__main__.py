#!/usr/bin/env python3

"""
Main entry point for the pytest_analyzer package.

This module allows the package to be executed directly with:
python -m pytest_analyzer

Use --gui flag to launch the graphical interface instead of the CLI.
"""

import sys
from pytest_analyzer.cli.analyzer_cli import main as cli_main

if __name__ == "__main__":
    # Check for GUI flag
    if "--gui" in sys.argv:
        # Remove the --gui flag from argv so it doesn't confuse the GUI
        sys.argv.remove("--gui")
        
        # Import GUI main entry point and run it
        from pytest_analyzer.gui.__main__ import main as gui_main
        sys.exit(gui_main())
    else:
        # Run CLI mode
        cli_main()
