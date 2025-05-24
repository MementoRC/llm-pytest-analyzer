#!/usr/bin/env python3
"""
Test script to validate JSON extraction for real GUI test failures,
focusing on "error" outcomes.
"""

import logging
import sys
from pathlib import Path
from pprint import pformat
from typing import List

# Adjust the Python path to include the src directory
project_root = (
    Path(__file__).resolve().parent.parent
)  # Assuming script is in a 'tests' or similar top-level dir
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

try:
    from pytest_analyzer.core.extraction.json_extractor import JsonResultExtractor
    from pytest_analyzer.core.models.pytest_failure import PytestFailure
    from pytest_analyzer.utils.path_resolver import PathResolver
except ImportError as e:
    print(f"Error importing modules: {e}")
    print(
        "Please ensure that the script is run from a location where 'src' is accessible, "
        "or the PYTHONPATH is set correctly."
    )
    print(f"Attempted to add to sys.path: {src_path}")
    sys.exit(1)

# --- Configuration ---
# This is the path to the JSON file generated from a real failing GUI test.
JSON_REPORT_PATH = Path("/tmp/gui_failures.json")


def setup_debug_logging():
    """Configures logging to show debug messages from pytest_analyzer."""
    logger = logging.getLogger("pytest_analyzer")
    logger.setLevel(logging.DEBUG)

    if logger.hasHandlers():
        logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    print("Debug logging configured for 'pytest_analyzer'.\n")


def print_failure_details(failure: PytestFailure, source_path: Path):
    """Prints the details of an extracted PytestFailure object."""
    print("\n--- Extracted Failure Details ---")
    print(f"Source JSON: {source_path}")
    print(f"Outcome: {failure.outcome}")
    print("\nFull PytestFailure object:")
    # Using pformat for a cleaner display of the dataclass
    print(pformat(failure.__dict__, indent=2))
    print("--- End of Failure Details ---\n")


def main():
    """Main function to run the extraction test."""
    setup_debug_logging()

    print(f"Starting Real JSON Extraction Test for: {JSON_REPORT_PATH}")

    if not JSON_REPORT_PATH.exists():
        print(f"ERROR: JSON report file not found: {JSON_REPORT_PATH}")
        print("Please ensure the file exists at the specified path.")
        sys.exit(1)

    # PathResolver might be needed if the JSON report contains relative paths
    # that need resolving against a project root. For an absolute /tmp path
    # for the report itself, it's less critical but good practice to include.
    path_resolver = PathResolver()
    json_extractor = JsonResultExtractor(path_resolver=path_resolver)

    try:
        print(f"Attempting to extract failures from JSON: {JSON_REPORT_PATH}")
        # Using extract_failures which directly returns List[PytestFailure]
        failures: List[PytestFailure] = json_extractor.extract_failures(JSON_REPORT_PATH)

        if not failures:
            print(
                "No failures were extracted. This might indicate an issue or an empty/valid report."
            )
            sys.exit(1)

        print(f"Successfully extracted {len(failures)} failure(s).")

        # For this test, we expect at least one failure, specifically an "error"
        failure_to_inspect = None
        for f in failures:
            if f.outcome == "error":
                failure_to_inspect = f
                break

        if not failure_to_inspect:
            print("VALIDATION FAILED: No failure with outcome 'error' found.")
            print("Outcomes found:")
            for i, f in enumerate(failures):
                print(f"  Failure #{i + 1}: Outcome '{f.outcome}', NodeID: {f.test_name}")
            sys.exit(1)

        print(f"Found a failure with outcome 'error': {failure_to_inspect.test_name}")
        print_failure_details(failure_to_inspect, JSON_REPORT_PATH)

        # Basic assertions
        assert failure_to_inspect.outcome == "error", (
            f"Expected outcome 'error', got '{failure_to_inspect.outcome}'"
        )
        assert failure_to_inspect.test_name, "Test name should be populated"
        # Add more assertions here as needed to verify specific fields

        print(
            "Validation successful: Extracted 'error' outcome failure and key fields seem populated."
        )
        print(
            "Please review the printed details above to confirm all fields are correctly extracted."
        )

    except Exception as e:
        print(f"An error occurred during JSON extraction: {e}")
        logging.exception("JSON Extraction failed")
        sys.exit(1)

    print("\nReal extraction test completed.")


if __name__ == "__main__":
    main()
