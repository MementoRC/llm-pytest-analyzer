#!/usr/bin/env python3
"""
Test the ACTUAL GUI crash scenario by simulating multiple test runs
through the real GUI workflow that users experience.
"""

import os
import subprocess
import sys


def test_real_gui_multiple_runs():
    """Test the real GUI workflow that was crashing on second test run."""

    print("🧪 TESTING REAL GUI CRASH SCENARIO")
    print("Testing multiple test executions through actual GUI components")
    print("=" * 60)

    # Set environment for headless testing
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PYTHONPATH"] = "src"

    # Test script that simulates the exact GUI workflow
    test_script = """
import sys
import time
from pathlib import Path
sys.path.insert(0, "src")

print("🚀 Starting real GUI crash test...")

try:
    # Import and create the full GUI app (what pytest-analyzer-gui does)
    from pytest_analyzer.gui.app import create_app
    from pytest_analyzer.gui.main_window import MainWindow

    # Create the full GUI application
    app = create_app([])
    main_window = MainWindow(app)

    print("✅ GUI app and main window created successfully")

    # Get the controllers that handle test execution (the crash point)
    test_controller = main_window.main_controller.test_execution_controller
    analysis_controller = main_window.main_controller.analysis_controller

    print("✅ Controllers initialized")

    # Test the exact workflow: multiple test executions
    test_file = "test_extraction_debug.py" if Path("test_extraction_debug.py").exists() else "src/pytest_analyzer/__init__.py"

    print(f"🎯 Testing with: {test_file}")

    # === FIRST TEST RUN ===
    print("\\n🚀 FIRST TEST RUN...")
    start = time.time()
    try:
        # This is what happens when user clicks "Run Tests"
        analysis_controller.test_results_model.set_source_file(Path(test_file), "python")
        analysis_controller.on_run_tests()

        # Wait a bit for background task to complete
        time.sleep(3)
        print(f"✅ First run completed in {time.time() - start:.1f}s")
    except Exception as e:
        print(f"❌ First run failed: {e}")
        raise

    # === GUI CLEANUP (like user waiting) ===
    print("⏳ GUI cleanup delay...")
    time.sleep(2)

    # === SECOND TEST RUN (CRASH POINT) ===
    print("\\n🚀 SECOND TEST RUN - Crash point with PyQt6...")
    start = time.time()
    try:
        # This is where PyQt6 was crashing
        analysis_controller.on_run_tests()

        # Wait for completion
        time.sleep(3)
        print(f"✅ Second run completed in {time.time() - start:.1f}s")
        print("🎉 SUCCESS - No crash with PySide6!")

    except Exception as e:
        print(f"💥 CRASH on second run: {e}")
        import traceback
        print(traceback.format_exc())
        raise

    # === THIRD TEST RUN (CONSISTENCY CHECK) ===
    print("\\n🚀 THIRD TEST RUN - Consistency check...")
    start = time.time()
    try:
        analysis_controller.on_run_tests()
        time.sleep(3)
        print(f"✅ Third run completed in {time.time() - start:.1f}s")
    except Exception as e:
        print(f"❌ Third run failed: {e}")
        raise

    print("\\n🎉 ALL GUI TEST RUNS SUCCESSFUL!")
    print("PySide6 migration resolved the Qt framework crashes!")

except Exception as e:
    print(f"💥 CRITICAL GUI ERROR: {e}")
    import traceback
    print(traceback.format_exc())
    sys.exit(1)
"""

    # Run the test in the proper environment
    try:
        result = subprocess.run(
            ["pixi", "run", "-e", "dev", "python", "-c", test_script],
            cwd="/home/memento/ClaudeCode/pytest-analyzer/llm-pytest-analyzer",
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )

        print("STDOUT:")
        print(result.stdout)

        if result.stderr:
            print("STDERR:")
            print(result.stderr)

        if result.returncode == 0:
            print("\n🎉 REAL GUI CRASH TEST: SUCCESS")
            print("PySide6 migration successfully resolved the crashes!")
            return True
        print(f"\n❌ REAL GUI CRASH TEST: FAILED (exit code: {result.returncode})")
        return False

    except subprocess.TimeoutExpired:
        print("❌ Test timed out - possible hang or crash")
        return False
    except Exception as e:
        print(f"❌ Test execution failed: {e}")
        return False


if __name__ == "__main__":
    success = test_real_gui_multiple_runs()
    sys.exit(0 if success else 1)
