import logging
import sys
from dataclasses import asdict
from pathlib import Path
from pprint import pprint
from typing import TYPE_CHECKING

# Ensure 'src' directory is in sys.path if the script is run from the project root
# and 'src' is a subdirectory. This helps in locating the project's modules.
# This assumes test_gui_workflow.py is in the project root.
# If it's elsewhere, this path might need adjustment, or the project should be installed/PYTHONPATH set.
PROJECT_ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT_DIR))

try:
    from src.pytest_analyzer.core.analyzer_service import PytestAnalyzerService
    from src.pytest_analyzer.utils.config_types import Settings

    if TYPE_CHECKING:
        from src.pytest_analyzer.core.models.pytest_failure import PytestFailure
except ImportError as e:
    print(f"Error importing project modules: {e}")
    print(
        "Please ensure that test_gui_workflow.py is in the project root or that the 'src' directory is in your PYTHONPATH."
    )
    print(f"Current sys.path: {sys.path}")
    print(f"Attempted to add {PROJECT_ROOT_DIR} to sys.path.")
    sys.exit(1)

# Configure basic logging to see output from the service and this script
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger("test_gui_workflow")


def main():
    # 1. Define project root and the specific failing test path
    project_root = PROJECT_ROOT_DIR

    # --- USER ACTION REQUIRED ---
    # Replace this with the actual path to a failing test file or specific test function
    # relevant to the GUI workflow you want to test.
    # This path should be relative to the project_root (i.e., relative to this script's location).
    # Example for a file: "tests/my_module/test_specific_failure.py"
    # Example for a function: "tests/my_module/test_specific_failure.py::test_something_fails"
    # Example for a directory: "tests/my_failing_tests/"
    failing_test_target_relative = "tests/gui/test_reporting_features.py::TestReportingIntegration::test_main_controller_has_report_controller"
    # --- END USER ACTION ---

    # Construct the full path string for the test target
    test_target_path_str = str(project_root / failing_test_target_relative)

    # Basic check if the file/directory part of the path exists.
    # This check is simplistic as pytest handles more complex target resolution.
    # It checks the part before any '::' if present.
    file_or_dir_part_of_target = project_root / failing_test_target_relative.split("::")[0]
    if not file_or_dir_part_of_target.exists():
        logger.error(f"Test file/directory not found: {file_or_dir_part_of_target}")
        logger.error(
            f"Please ensure '{failing_test_target_relative}' points to a valid test target relative to the project root."
        )
        return

    logger.info(f"Using project root: {project_root}")
    logger.info(f"Attempting to analyze target: {test_target_path_str}")

    # 2. Create PytestAnalyzerService, mimicking GUI setup
    settings = Settings(
        project_root=project_root,
        llm_provider="none",  # Avoids LLM calls; focus on extraction
        check_git=False,  # Avoids Git checks for simplicity
        # Add any other settings that the GUI typically configures and are relevant.
        # For example, pytest_timeout or preferred_format.
        # settings.pytest_timeout = 60 # Default is 60
        # settings.preferred_format = "json" # Default is json
    )

    service = PytestAnalyzerService(settings=settings)

    # 3. Call _run_and_extract_json() with the failing test
    # Pytest args can be used to pass additional options to pytest.
    # For example, if the GUI adds specific markers or verbosity:
    # pytest_args = ["-m", "critical", "-v"]
    pytest_args = []  # Start with no extra args for default behavior

    logger.info(
        f"Calling service._run_and_extract_json(test_path='{test_target_path_str}', pytest_args={pytest_args})"
    )

    failures: list[PytestFailure] = []
    try:
        # The _run_and_extract_json method is protected but called here for specific testing.
        failures = service._run_and_extract_json(
            test_path=test_target_path_str, pytest_args=pytest_args
        )
    except Exception as e:
        logger.error(
            f"An error occurred during the call to _run_and_extract_json: {e}", exc_info=True
        )
        return

    # 4. Show what the GUI would receive
    logger.info("--- Extraction Results ---")
    if failures:
        logger.info(f"Extracted {len(failures)} failure(s):")
        for i, failure_obj in enumerate(failures):
            logger.info(f"Failure #{i + 1}:")
            # Pretty print each failure object (converted to dict) for detailed view
            pprint(asdict(failure_obj), indent=2, width=120)
            logger.info("-" * 40)  # Separator for readability
    else:
        logger.info("No failures were extracted.")
        logger.info("This could mean:")
        logger.info("  1. The test(s) at the specified path passed successfully.")
        logger.info(
            "  2. There was an issue with the pytest execution itself (e.g., collection errors, internal errors)."
        )
        logger.info(
            "  3. The JSON report was not generated or was empty (check service logs for details on subprocess calls)."
        )
        logger.info(
            "  4. An error occurred within _run_and_extract_json that was caught by its internal error handling."
        )
    logger.info("--- End of Results ---")


if __name__ == "__main__":
    main()
