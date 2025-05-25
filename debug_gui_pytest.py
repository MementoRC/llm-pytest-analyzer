#!/usr/bin/env python3
"""
Debug script to test GUI pytest execution and see debug output.

This script mimics how the GUI runs pytest to identify why reports are empty.
"""

import logging
import sys
from pathlib import Path

# Set up debug logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler("debug_gui_pytest.log")],
)

from src.pytest_analyzer.core.analyzer_service import PytestAnalyzerService
from src.pytest_analyzer.utils.settings import Settings


def test_gui_pytest_execution():
    """Test pytest execution the same way the GUI does it."""
    print("=== Testing GUI Pytest Execution ===")

    # Initialize service the same way GUI does
    settings = Settings()
    settings.project_root = Path.cwd()
    settings.preferred_format = "json"  # Test JSON extraction

    analyzer = PytestAnalyzerService(
        settings=settings, use_async=False, batch_size=5, max_concurrency=10
    )

    # Test with the failing GUI tests we know exist
    test_path = "tests/gui/test_reporting_features.py"

    print(f"Running pytest on: {test_path}")
    print("Check debug_gui_pytest.log for detailed debug output...")

    # This should trigger our enhanced debugging
    failures = analyzer.run_pytest_only(
        test_path=test_path,
        pytest_args=["-s", "--disable-warnings"],  # Same args GUI uses
        quiet=False,  # Don't use quiet mode so we see output
    )

    print(f"\nResult: Found {len(failures)} failures")
    for i, failure in enumerate(failures, 1):
        print(f"  {i}. {failure.test_name} - {failure.outcome}")

    return failures


def test_gui_pytest_quiet_mode():
    """Test with quiet mode like GUI typically uses."""
    print("\n=== Testing GUI Pytest Execution (Quiet Mode) ===")

    settings = Settings()
    settings.project_root = Path.cwd()
    settings.preferred_format = "json"

    analyzer = PytestAnalyzerService(
        settings=settings, use_async=False, batch_size=5, max_concurrency=10
    )

    test_path = "tests/gui/test_reporting_features.py"

    print(f"Running pytest on: {test_path} (quiet mode)")
    print("Check debug_gui_pytest.log for detailed debug output...")

    # Test with quiet mode that GUI often uses
    failures = analyzer.run_pytest_only(
        test_path=test_path,
        pytest_args=["-qq", "--disable-warnings"],  # Quiet mode
        quiet=True,
    )

    print(f"\nResult (quiet): Found {len(failures)} failures")
    for i, failure in enumerate(failures, 1):
        print(f"  {i}. {failure.test_name} - {failure.outcome}")

    return failures


if __name__ == "__main__":
    print("Starting GUI pytest execution debugging...")
    print("This will help identify why the GUI generates empty reports.")
    print("Debug output will be saved to debug_gui_pytest.log")

    try:
        # Test normal mode
        normal_failures = test_gui_pytest_execution()

        # Test quiet mode
        quiet_failures = test_gui_pytest_quiet_mode()

        print("\n=== Summary ===")
        print(f"Normal mode: {len(normal_failures)} failures")
        print(f"Quiet mode: {len(quiet_failures)} failures")

        if len(normal_failures) > 0 or len(quiet_failures) > 0:
            print("✅ Pytest execution is working!")
            print("The issue may be in the GUI's specific environment or threading.")
        else:
            print("❌ Both modes returned 0 failures - this helps reproduce the issue!")

    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback

        traceback.print_exc()
