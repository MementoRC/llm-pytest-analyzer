"""
Command-line interface for the pytest analyzer.

This package provides the CLI components for interacting with the pytest_analyzer system.
"""

from .analyzer_cli import main
from .check_env import CheckEnvironmentCommand
from .check_env import main as check_env_main
from .efficiency_report import EfficiencyReportCommand
from .efficiency_report import main as efficiency_report_main
from .smart_test import SmartTestCommand
from .smart_test import main as smart_test_main

__all__ = [
    "main",
    "CheckEnvironmentCommand",
    "check_env_main",
    "EfficiencyReportCommand",
    "efficiency_report_main",
    "SmartTestCommand",
    "smart_test_main",
]
