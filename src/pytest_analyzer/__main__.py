#!/usr/bin/env python3

"""
Main entry point for the pytest_analyzer package.

This module allows the package to be executed directly with:
python -m pytest_analyzer
"""

import os

# Check for environment variable to control which implementation to use
# This allows for easy switching between the old and new implementations
# during the transition period
use_di = os.environ.get("PYTEST_ANALYZER_USE_DI", "1") == "1"

if use_di:
    from pytest_analyzer.cli.analyzer_cli_di import main
else:
    from pytest_analyzer.cli.analyzer_cli import main

if __name__ == "__main__":
    main()
