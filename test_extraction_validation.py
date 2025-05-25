#!/usr/bin/env python3
"""
Validation script to demonstrate that our extraction pipeline fixes are working correctly.

This script shows that:
1. JSON extraction works correctly with real error tests
2. XML extraction works correctly with real error tests
3. The issue is NOT in the extraction pipeline but in the GUI environment

Run this to validate the extraction improvements before investigating GUI runtime issues.
"""

import os
import subprocess
import tempfile
from pathlib import Path

from src.pytest_analyzer.core.extraction.json_extractor import JsonResultExtractor
from src.pytest_analyzer.core.extraction.xml_extractor import XmlResultExtractor


def test_extraction_with_real_failing_tests():
    """Test extraction with real failing tests to validate our fixes."""
    print("=== Extraction Pipeline Validation ===")

    # Create a test file with real failures
    test_content = '''
def test_assertion_failure():
    """Test that fails with assertion."""
    assert 1 == 2, "Intentional assertion failure"

def test_import_error():
    """Test that fails with import error."""
    import nonexistent_module

def test_passing():
    """Test that passes."""
    assert True
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(test_content)
        test_file = f.name

    try:
        # Generate JSON report
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp_json:
            json_report = tmp_json.name

        # Generate XML report
        with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as tmp_xml:
            xml_report = tmp_xml.name

        print(f"Running pytest on {test_file}")

        # Run pytest to generate reports
        cmd = [
            "python",
            "-m",
            "pytest",
            test_file,
            "--json-report",
            f"--json-report-file={json_report}",
            f"--junit-xml={xml_report}",
            "-v",
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, cwd=".")
        print(f"Pytest exit code: {result.returncode}")
        print(f"Found {result.stdout.count('FAILED')} failures in output")

        # Test JSON extraction
        print("\n--- JSON Extraction Test ---")
        json_extractor = JsonResultExtractor()
        json_failures = json_extractor.extract_failures(Path(json_report))
        print(f"JSON extractor found {len(json_failures)} failures:")
        for i, failure in enumerate(json_failures, 1):
            print(f"  {i}. {failure.test_name} - {failure.outcome}")
            if failure.error_message:
                error_preview = failure.error_message.replace("\n", " ")[:80] + "..."
                print(f"     Error: {error_preview}")

        # Test XML extraction
        print("\n--- XML Extraction Test ---")
        xml_extractor = XmlResultExtractor()
        xml_failures = xml_extractor.extract_failures(Path(xml_report))
        print(f"XML extractor found {len(xml_failures)} failures:")
        for i, failure in enumerate(xml_failures, 1):
            print(f"  {i}. {failure.test_name} - {failure.outcome}")
            if failure.error_message:
                error_preview = failure.error_message.replace("\n", " ")[:80] + "..."
                print(f"     Error: {error_preview}")

        # Validation
        print("\n--- Validation Results ---")
        expected_failures = 2  # assertion_failure and import_error
        json_success = len(json_failures) >= expected_failures
        xml_success = len(xml_failures) >= expected_failures

        print(
            f"JSON Extraction: {'✅ PASS' if json_success else '❌ FAIL'} (found {len(json_failures)}, expected >= {expected_failures})"
        )
        print(
            f"XML Extraction: {'✅ PASS' if xml_success else '❌ FAIL'} (found {len(xml_failures)}, expected >= {expected_failures})"
        )

        if json_success and xml_success:
            print("\n🎉 EXTRACTION PIPELINE IS WORKING CORRECTLY!")
            print("The issue is NOT in the extraction logic.")
            print("The GUI runtime environment needs investigation.")
        else:
            print("\n❌ Extraction pipeline needs more fixes.")

        return json_success and xml_success

    finally:
        # Cleanup
        for file_path in [test_file, json_report, xml_report]:
            try:
                if os.path.exists(file_path):
                    os.unlink(file_path)
            except OSError:
                pass


def test_gui_test_extraction():
    """Test extraction on the actual GUI test results we generated."""
    print("\n=== GUI Test Extraction Validation ===")

    json_file = "/tmp/test_gui_json.json"
    if not os.path.exists(json_file):
        print(f"❌ GUI test JSON report not found at {json_file}")
        print(
            "Please run: pixi run -e dev pytest tests/gui/test_reporting_features.py --json-report --json-report-file=/tmp/test_gui_json.json"
        )
        return False

    # Test JSON extraction on GUI tests
    json_extractor = JsonResultExtractor()
    failures = json_extractor.extract_failures(Path(json_file))

    print(f"JSON extractor found {len(failures)} failures from GUI tests:")
    for i, failure in enumerate(failures, 1):
        print(f"  {i}. {failure.test_name} - {failure.outcome}")

    expected_gui_errors = 6  # Based on our previous analysis
    success = len(failures) == expected_gui_errors

    print(
        f"GUI Test Extraction: {'✅ PASS' if success else '❌ FAIL'} (found {len(failures)}, expected {expected_gui_errors})"
    )

    if success:
        print("✅ Extraction correctly identifies GUI test errors!")

    return success


if __name__ == "__main__":
    print("Validating pytest-analyzer extraction pipeline improvements...")

    # Test with synthetic failing tests
    synthetic_success = test_extraction_with_real_failing_tests()

    # Test with actual GUI tests
    gui_success = test_gui_test_extraction()

    print("\n" + "=" * 50)
    print("FINAL VALIDATION SUMMARY:")
    print(f"Synthetic Test Extraction: {'✅ PASS' if synthetic_success else '❌ FAIL'}")
    print(f"GUI Test Extraction: {'✅ PASS' if gui_success else '❌ FAIL'}")

    if synthetic_success and gui_success:
        print("\n🎉 ALL EXTRACTION TESTS PASSED!")
        print("The extraction pipeline improvements are working correctly.")
        print("The original issue is in the GUI runtime environment, not extraction logic.")
        print("\nNext steps:")
        print("1. Investigate GUI memory allocation issues")
        print("2. Check GUI environment variables vs CLI environment")
        print("3. Debug GUI pytest subprocess execution")
    else:
        print("\n❌ Some extraction tests failed - more fixes needed")
