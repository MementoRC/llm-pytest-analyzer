"""
Command-line interface for the pytest analyzer.

This package provides the CLI components for interacting with the pytest_analyzer system.
"""

from .analyzer_cli import main
from .check_env import CheckEnvironmentCommand
from .check_env import main as check_env_main

__all__ = ["main", "CheckEnvironmentCommand", "check_env_main"]
