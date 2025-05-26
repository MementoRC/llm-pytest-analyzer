#!/usr/bin/env python3
"""
Test script to verify PySide6 GUI basic functionality.
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Set offscreen platform for headless testing
os.environ["QT_QPA_PLATFORM"] = "offscreen"


def test_basic_gui_creation():
    """Test basic GUI app creation with PySide6."""
    try:
        from pytest_analyzer.gui.app import create_app

        print("🧪 Testing basic PySide6 GUI creation...")

        # Create app instance
        app = create_app([])

        print("✅ GUI app created successfully with PySide6")
        print("✅ No crashes during initialization")

        # Test app properties
        print(f"✅ App organization: {app.organizationName()}")
        print(f"✅ App version: {app.applicationVersion()}")

        return True

    except Exception as e:
        print(f"❌ GUI creation failed: {e}")
        import traceback

        print(f"Traceback: {traceback.format_exc()}")
        return False


if __name__ == "__main__":
    success = test_basic_gui_creation()
    sys.exit(0 if success else 1)
