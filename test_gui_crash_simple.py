#!/usr/bin/env python3
"""
Simplified test for the GUI crash scenario.
Tests the core issue: multiple test runs in a GUI context that was crashing with PyQt6.
"""

import os
import subprocess
import sys


def test_gui_crash_simple():
    """Test multiple test runs in GUI context."""

    print("🧪 SIMPLIFIED GUI CRASH TEST")
    print("Testing multiple test runs in GUI context that crashed with PyQt6")
    print("=" * 60)

    # Set environment
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PYTHONPATH"] = "src"

    test_script = """
import sys
import time
from pathlib import Path
sys.path.insert(0, "src")

print("🚀 Creating GUI app context...")

# Create the GUI app (this initializes Qt and all the GUI framework)
from pytest_analyzer.gui.app import create_app
app = create_app([])

print("✅ GUI app created (Qt framework initialized)")

# Create analyzer service in GUI context (this was the crash scenario)
from pytest_analyzer.core.analyzer_service import PytestAnalyzerService
from pytest_analyzer.utils.settings import Settings

settings = Settings(
    project_root=Path("."),
    preferred_format="json",
    max_memory_mb=512,
    pytest_timeout=30,
)

analyzer = PytestAnalyzerService(settings)
print("✅ Analyzer service created in GUI context")

# Test file
test_file = "src/pytest_analyzer/__init__.py"
print(f"🎯 Testing with: {test_file}")

# === FIRST TEST RUN ===
print("\\n🚀 FIRST TEST RUN in GUI context...")
start = time.time()
try:
    failures1 = analyzer.run_pytest_only(test_file, quiet=True)
    print(f"✅ First run: {len(failures1)} failures in {time.time() - start:.1f}s")
except Exception as e:
    print(f"❌ First run failed: {e}")
    raise

# Simulate GUI cleanup and Qt event processing
print("⏳ GUI cleanup (Qt event processing)...")
app.processEvents()  # This was part of the crash scenario
time.sleep(1)

# === SECOND TEST RUN (CRASH POINT) ===
print("\\n🚀 SECOND TEST RUN - PyQt6 crash point...")
start = time.time()
try:
    failures2 = analyzer.run_pytest_only(test_file, quiet=True)
    print(f"✅ Second run: {len(failures2)} failures in {time.time() - start:.1f}s")
    print("🎉 NO CRASH - PySide6 works!")
except Exception as e:
    print(f"💥 CRASH on second run: {e}")
    import traceback
    print(traceback.format_exc())
    raise

# === THIRD TEST RUN ===
print("\\n🚀 THIRD TEST RUN - Consistency check...")
app.processEvents()
time.sleep(0.5)

start = time.time()
try:
    failures3 = analyzer.run_pytest_only(test_file, quiet=True)
    print(f"✅ Third run: {len(failures3)} failures in {time.time() - start:.1f}s")
except Exception as e:
    print(f"❌ Third run failed: {e}")
    raise

print("\\n🎉 ALL GUI CONTEXT RUNS SUCCESSFUL!")
print("✅ PySide6 resolved the Qt framework crash issue!")
print(f"📊 Results: {len(failures1)}, {len(failures2)}, {len(failures3)} failures")
"""

    try:
        result = subprocess.run(
            ["pixi", "run", "-e", "dev", "python", "-c", test_script],
            cwd="/home/memento/ClaudeCode/pytest-analyzer/llm-pytest-analyzer",
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )

        print("OUTPUT:")
        print(result.stdout)

        if result.stderr:
            print("\nLOGS:")
            # Only show non-memory monitor logs
            stderr_lines = result.stderr.split("\n")
            relevant_logs = [line for line in stderr_lines if "MEMORY" not in line and line.strip()]
            if relevant_logs:
                print("\n".join(relevant_logs))

        success = result.returncode == 0
        print(f"\n🔬 GUI CRASH TEST: {'SUCCESS' if success else 'FAILED'}")

        if success:
            print("🎉 PySide6 migration successfully resolved GUI framework crashes!")

        return success

    except subprocess.TimeoutExpired:
        print("❌ Test timed out")
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


if __name__ == "__main__":
    success = test_gui_crash_simple()
    sys.exit(0 if success else 1)
