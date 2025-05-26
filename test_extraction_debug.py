#!/usr/bin/env python3
"""
Comprehensive debug test script for the extraction pipeline.

This script:
1. Sets up debug logging for the pytest_analyzer.
2. Tests XML extraction using a sample report.
3. Tests JSON extraction using a sample report.
4. Prints detailed output of extracted data.
"""

import logging
import sys
from pathlib import Path
from pprint import pformat
from typing import List

# Adjust the Python path to include the src directory
# This is often needed when running scripts directly from a subfolder in a project
project_root = Path(__file__).resolve().parent  # Script is in the project root
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

try:
    from pytest_analyzer.core.extraction.json_extractor import JsonResultExtractor
    from pytest_analyzer.core.extraction.xml_extractor import XmlResultExtractor
    from pytest_analyzer.core.models.pytest_failure import PytestFailure
    from pytest_analyzer.utils.path_resolver import PathResolver
except ImportError as e:
    print(f"Error importing modules: {e}")
    print(
        "Please ensure that the script is run from the project root or the PYTHONPATH is set correctly."
    )
    print(f"Project root determined as: {project_root}")
    print(f"Src path added to sys.path: {src_path}")
    sys.exit(1)

# --- Configuration ---
XML_REPORT_PATH = project_root / "tests" / "sample_reports" / "assertion_fail_report.xml"
JSON_REPORT_PATH = project_root / "tests" / "sample_reports" / "assertion_fail_report.json"


def setup_debug_logging():
    """Configures logging to show debug messages from pytest_analyzer."""
    logger = logging.getLogger("pytest_analyzer")
    logger.setLevel(logging.DEBUG)

    # Clear existing handlers if any (e.g., from previous runs in an interactive session)
    if logger.hasHandlers():
        logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # Also ensure root logger or other relevant loggers don't suppress
    logging.getLogger().setLevel(logging.DEBUG)  # Example: set root logger to DEBUG
    print("Debug logging configured for 'pytest_analyzer'.\n")


def print_extraction_results(
    extractor_name: str, failures: List[PytestFailure], source_path: Path, format_name: str
):
    """Prints the results from an extraction operation."""
    print(f"\n--- {extractor_name} Results ---")
    print(f"Source: {source_path}")
    print(f"Format: {format_name}")
    print(f"Count of PytestFailure objects: {len(failures)}")

    # failures is now a direct parameter
    if not failures:
        print("No failures extracted.")
    else:
        print("\nExtracted PytestFailure objects:")
        for i, failure in enumerate(failures):
            print(f"\nFailure #{i + 1}:")
            # Using pformat for a cleaner display of the dataclass
            print(pformat(failure.__dict__, indent=2))
    print(f"--- End of {extractor_name} Results ---\n")


def main():
    """Main function to run the extraction tests."""
    setup_debug_logging()

    # --- Test XML Extraction ---
    print("Starting XML Extraction Test...")
    if not XML_REPORT_PATH.exists():
        print(f"XML report not found at: {XML_REPORT_PATH}")
        return

    path_resolver = PathResolver(
        project_root=project_root
    )  # Provide project_root if paths in XML are relative
    xml_extractor = XmlResultExtractor(path_resolver=path_resolver)

    try:
        print(f"Attempting to extract failures from XML: {XML_REPORT_PATH}")
        xml_failures = xml_extractor.extract_failures(XML_REPORT_PATH)
        print_extraction_results("XML Extractor", xml_failures, XML_REPORT_PATH, "xml")
    except Exception as e:
        print(f"An error occurred during XML extraction: {e}")
        logging.exception("XML Extraction failed")

    # --- Test JSON Extraction ---
    print("\nStarting JSON Extraction Test...")
    if not JSON_REPORT_PATH.exists():
        print(f"JSON report not found at: {JSON_REPORT_PATH}")
        return

    # PathResolver might be needed if JSON report contains relative paths that need resolving
    json_extractor = JsonResultExtractor(path_resolver=path_resolver)

    try:
        print(f"Attempting to extract failures from JSON: {JSON_REPORT_PATH}")
        json_failures = json_extractor.extract_failures(JSON_REPORT_PATH)
        print_extraction_results("JSON Extractor", json_failures, JSON_REPORT_PATH, "json")
    except Exception as e:
        print(f"An error occurred during JSON extraction: {e}")
        logging.exception("JSON Extraction failed")

    print("\nExtraction tests completed.")


if __name__ == "__main__":
    main()
