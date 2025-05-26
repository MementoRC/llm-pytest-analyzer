#!/usr/bin/env python3
"""
Focused test to reproduce the exact second test run issue.
This simulates the GUI workflow that was failing.
"""

import gc
import logging
import sys
import time
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from pytest_analyzer.core.analyzer_service import PytestAnalyzerService
from pytest_analyzer.utils.settings import Settings


def test_second_run_failure():
    """Test the exact scenario that was failing in GUI."""

    # Configure logging to match GUI logging level
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    logger = logging.getLogger(__name__)

    logger.info("🔍 TESTING SECOND RUN FAILURE SCENARIO")
    logger.info("=" * 60)

    # Create settings similar to GUI
    settings = Settings(
        project_root=Path(__file__).parent,
        preferred_format="json",
        max_memory_mb=512,  # Match GUI memory constraints
        pytest_timeout=30,
    )

    # Create analyzer service (same as GUI)
    service = PytestAnalyzerService(settings)

    # Test file that GUI was using
    test_file = "test_extraction_debug.py"

    try:
        # === FIRST TEST RUN (this works) ===
        logger.info("🚀 FIRST TEST RUN - Expected to succeed")
        start_time = time.time()

        failures1 = service.run_pytest_only(test_file, quiet=True)

        end_time = time.time()
        logger.info(
            f"✅ First run SUCCESS: {len(failures1)} failures in {end_time - start_time:.2f}s"
        )

        # Simulate GUI delay and cleanup
        time.sleep(2.0)  # Match the 2000ms cleanup delay
        gc.collect()
        gc.collect()

        # === SECOND TEST RUN (this was failing in GUI) ===
        logger.info("\n🚀 SECOND TEST RUN - This was failing in GUI")
        start_time = time.time()

        failures2 = service.run_pytest_only(test_file, quiet=True)

        end_time = time.time()
        logger.info(
            f"✅ Second run SUCCESS: {len(failures2)} failures in {end_time - start_time:.2f}s"
        )

        # === THIRD TEST RUN (to verify pattern) ===
        logger.info("\n🚀 THIRD TEST RUN - Checking consistency")
        start_time = time.time()

        failures3 = service.run_pytest_only(test_file, quiet=True)

        end_time = time.time()
        logger.info(
            f"✅ Third run SUCCESS: {len(failures3)} failures in {end_time - start_time:.2f}s"
        )

        logger.info("\n" + "=" * 60)
        logger.info("🎉 ALL RUNS SUCCESSFUL - Core engine is working!")
        logger.info("📋 Summary:")
        logger.info(f"   Run 1: {len(failures1)} failures")
        logger.info(f"   Run 2: {len(failures2)} failures")
        logger.info(f"   Run 3: {len(failures3)} failures")
        logger.info("\n💡 If this succeeds but GUI fails, the issue is GUI-specific.")
        return True

    except Exception as e:
        logger.error(f"❌ FAILED on: {e}")
        logger.error("📍 This confirms the issue is in the core engine, not just GUI")
        return False


if __name__ == "__main__":
    success = test_second_run_failure()
    sys.exit(0 if success else 1)
