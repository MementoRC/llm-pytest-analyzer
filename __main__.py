#!/usr/bin/env python3

"""
Main entry point for the pytest_analyzer package.

This module allows the package to be executed directly with:
python -m pytest_analyzer
"""

from pytest_analyzer.cli.analyzer_cli import main

if __name__ == "__main__":
    main()