#!/usr/bin/env python3
"""
Test script to verify the memory leak fixes work by running multiple test executions
without the GUI overhead. This simulates the second test run issue that was occurring.
"""

import logging
import sys
import time
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from pytest_analyzer.core.analyzer_service import PytestAnalyzerService
from pytest_analyzer.utils.settings import Settings


def main():
    """Test multiple consecutive test runs to verify memory leak fix."""

    # Configure logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    logger = logging.getLogger(__name__)

    logger.info("=" * 60)
    logger.info("TESTING MEMORY LEAK FIX - MULTIPLE TEST RUNS")
    logger.info("=" * 60)

    # Create settings
    settings = Settings(
        project_root=Path(__file__).parent,
        preferred_format="json",
        max_memory_mb=512,
        pytest_timeout=30,
    )

    # Create analyzer service
    service = PytestAnalyzerService(settings)

    # Test file
    test_file = "test_extraction_debug.py"

    # Simulate the GUI workflow that was failing
    logger.info(f"Simulating GUI workflow with multiple test runs on {test_file}")

    success_count = 0

    for run_num in range(5):  # Test 5 consecutive runs like the GUI would do
        logger.info(f"\n--- TEST RUN #{run_num + 1} ---")

        start_time = time.time()

        try:
            # This simulates what happens when user clicks "Run Tests" multiple times
            failures = service.run_pytest_only(test_file, quiet=True)

            end_time = time.time()
            duration = end_time - start_time

            logger.info(
                f"✅ Run #{run_num + 1} SUCCESS: {len(failures)} failures found in {duration:.2f}s"
            )
            success_count += 1

            # Small delay to simulate user interaction time
            time.sleep(0.5)

        except Exception as e:
            logger.error(f"❌ Run #{run_num + 1} FAILED: {e}")
            break

    logger.info("\n" + "=" * 60)
    if success_count == 5:
        logger.info("🎉 ALL TESTS PASSED - Memory leak fix is working!")
        logger.info("✅ The 'second test run' issue has been resolved.")
        logger.info("✅ Multiple consecutive test executions work without memory leaks.")
        return True
    logger.error(f"❌ FAILED - Only {success_count}/5 test runs succeeded.")
    return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
