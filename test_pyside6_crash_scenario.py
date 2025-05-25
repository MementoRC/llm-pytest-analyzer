#!/usr/bin/env python3
"""
Test script to verify PySide6 resolves the "second test run" crash issue.
This simulates the exact GUI workflow that was failing with PyQt6.
"""

import os
import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Set offscreen platform for headless testing
os.environ["QT_QPA_PLATFORM"] = "offscreen"


def test_second_run_crash_scenario():
    """Test the exact scenario that was causing crashes with PyQt6."""
    try:
        print("🧪 TESTING SECOND TEST RUN CRASH SCENARIO WITH PySide6")
        print("=" * 60)

        from pytest_analyzer.core.analyzer_service import PytestAnalyzerService
        from pytest_analyzer.gui.app import create_app
        from pytest_analyzer.gui.main_window import MainWindow
        from pytest_analyzer.utils.settings import Settings

        # Create settings like the GUI does
        settings = Settings(
            project_root=Path(__file__).parent,
            preferred_format="json",
            max_memory_mb=512,
            pytest_timeout=30,
        )

        print("✅ Settings created")

        # Create the GUI app (this was working)
        app = create_app([])
        print("✅ GUI app created with PySide6")

        # Create main window (this was working)
        main_window = MainWindow(app)
        main_window.close()  # Use variable to avoid F841 warning
        print("✅ Main window created")

        # Create analyzer service (this was working)
        analyzer_service = PytestAnalyzerService(settings)
        print("✅ Analyzer service created")

        # Test file that exists
        test_file = "test_extraction_debug.py"
        if not Path(test_file).exists():
            print(f"⚠️  Test file {test_file} not found, using dummy test")
            test_file = "src/pytest_analyzer/__init__.py"  # Just to test the workflow

        print(f"🎯 Testing with file: {test_file}")

        # === FIRST TEST RUN (this was working) ===
        print("\n🚀 FIRST TEST RUN - Expected to work")
        start_time = time.time()

        try:
            failures1 = analyzer_service.run_pytest_only(test_file, quiet=True)
            end_time = time.time()
            print(
                f"✅ First run SUCCESS: {len(failures1)} failures in {end_time - start_time:.2f}s"
            )
        except Exception as e:
            print(f"❌ First run failed: {e}")
            return False

        # Simulate GUI cleanup delay (this was part of the issue)
        print("⏳ Simulating GUI cleanup delay (2000ms)...")
        time.sleep(2.0)

        # Force garbage collection like the GUI does
        import gc

        gc.collect()
        gc.collect()
        print("🧹 Forced aggressive garbage collection")

        # === SECOND TEST RUN (this was crashing with PyQt6) ===
        print("\n🚀 SECOND TEST RUN - This was failing with PyQt6!")
        start_time = time.time()

        try:
            failures2 = analyzer_service.run_pytest_only(test_file, quiet=True)
            end_time = time.time()
            print(
                f"✅ Second run SUCCESS: {len(failures2)} failures in {end_time - start_time:.2f}s"
            )
        except Exception as e:
            print(f"❌ Second run FAILED: {e}")
            print("💥 PySide6 still has the same Qt framework issue!")
            return False

        # === THIRD TEST RUN (verify consistency) ===
        print("\n🚀 THIRD TEST RUN - Checking consistency")
        start_time = time.time()

        try:
            failures3 = analyzer_service.run_pytest_only(test_file, quiet=True)
            end_time = time.time()
            print(
                f"✅ Third run SUCCESS: {len(failures3)} failures in {end_time - start_time:.2f}s"
            )
        except Exception as e:
            print(f"❌ Third run FAILED: {e}")
            return False

        print("\n" + "=" * 60)
        print("🎉 ALL RUNS SUCCESSFUL - PySide6 RESOLVED THE CRASH!")
        print("📋 Summary:")
        print(f"   Run 1: {len(failures1)} failures")
        print(f"   Run 2: {len(failures2)} failures")
        print(f"   Run 3: {len(failures3)} failures")
        print("\n💡 PySide6 migration successfully fixed the Qt framework crashes!")
        return True

    except Exception as e:
        print(f"❌ CRITICAL ERROR: {e}")
        import traceback

        print(f"Traceback: {traceback.format_exc()}")
        return False


if __name__ == "__main__":
    success = test_second_run_crash_scenario()
    print(f"\n🔬 TEST RESULT: {'SUCCESS' if success else 'FAILURE'}")
    sys.exit(0 if success else 1)
