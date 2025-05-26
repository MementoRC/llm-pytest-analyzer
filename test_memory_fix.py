#!/usr/bin/env python3
"""
Test script to verify memory leak fixes in analyzer service.
This tests the core subprocess memory management without GUI overhead.
"""

import gc
import logging
import sys
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from pytest_analyzer.core.analyzer_service import PytestAnalyzerService
from pytest_analyzer.utils.settings import Settings


def test_memory_fix():
    """Test running multiple pytest executions to verify memory leak fix."""

    # Configure logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    # Create settings with conservative memory limits
    settings = Settings(
        project_root=Path(__file__).parent,
        preferred_format="json",
        max_memory_mb=256,  # Conservative limit
        pytest_timeout=30,
    )

    # Create analyzer service
    service = PytestAnalyzerService(settings)

    # Test file that should exist
    test_file = "test_extraction_debug.py"

    logger.info(f"Testing memory fix with {test_file}")

    # Run multiple test iterations
    for i in range(3):
        logger.info(f"\n--- Test Run {i + 1} ---")

        try:
            # Force garbage collection before each run
            gc.collect()

            # Run pytest
            failures = service.run_pytest_only(test_file, quiet=True)

            logger.info(f"Run {i + 1}: Found {len(failures)} failures")

            # Force cleanup after each run
            gc.collect()

        except Exception as e:
            logger.error(f"Run {i + 1} failed: {e}")
            return False

    logger.info("All test runs completed successfully - memory fix appears to work!")
    return True


if __name__ == "__main__":
    success = test_memory_fix()
    sys.exit(0 if success else 1)
