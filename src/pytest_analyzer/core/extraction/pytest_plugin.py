import logging
from typing import Any, Dict, List

import pytest

from ..models.pytest_failure import PytestFailure

logger = logging.getLogger(__name__)


class FailureCollectorPlugin:
    """
    Pytest plugin that collects all test results (passed, failed, skipped, error)
    during test execution.

    This plugin hooks into pytest's reporting mechanism to capture
    detailed information about test results directly from the test run.

    Usage:
        plugin = FailureCollectorPlugin()
        pytest.main(['tests/'], plugins=[plugin])
        results = plugin.get_results()
    """

    def __init__(self) -> None:
        self.results: List[PytestFailure] = []
        self.test_items: Dict[str, Any] = {}

    @pytest.hookimpl(hookwrapper=True)
    def pytest_collection_modifyitems(self, items):
        """Store test items for later reference."""
        for item in items:
            try:
                self.test_items[item.nodeid] = {
                    "path": str(item.path) if hasattr(item, "path") else None,
                    "module": item.module.__name__ if hasattr(item, "module") else None,
                    "function": (item.function.__name__ if hasattr(item, "function") else None),
                }
            except Exception as e:
                logger.error(
                    f"Error processing test item {getattr(item, 'nodeid', 'unknown')}: {e}"
                )
        yield

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(self, item, call):
        """Capture test failures during test execution."""
        outcome = yield
        report = outcome.get_result()

        # Process all outcomes during the 'call' phase
        if report.when == "call":
            try:
                self._process_result(item, report)
            except Exception as e:
                logger.error(f"Error processing test result: {e}")

    def _process_result(self, item, report):
        """Process a test result and add it to the results list."""
        test_outcome = report.outcome

        # Initialize fields with defaults
        test_name = item.nodeid
        test_file = str(item.path) if hasattr(item, "path") else ""
        line_number = None
        error_type = None
        error_message = None
        traceback_text = None
        relevant_code = ""  # Consistent with original initialization for failures
        raw_output_section = str(report.longrepr) if hasattr(report, "longrepr") else ""

        if test_outcome == "failed":
            # Overwrite defaults with failure-specific values from original logic
            error_type = "Unknown"
            error_message = ""
            traceback_text = ""
            # relevant_code is already ""

            if hasattr(report, "longrepr"):  # Check is somewhat redundant due to raw_output_section
                longrepr = report.longrepr

                if hasattr(longrepr, "reprtraceback"):
                    traceback_text = str(longrepr)  # Original logic for traceback

                    entries = longrepr.reprtraceback.entries
                    if entries:
                        last_entry = entries[-1]
                        if hasattr(last_entry, "lineno"):
                            line_number = last_entry.lineno
                        if hasattr(last_entry, "reprfuncargs"):  # Original logic for relevant_code
                            relevant_code = str(last_entry.reprfuncargs)

                if hasattr(longrepr, "reprcrash"):
                    crash = longrepr.reprcrash
                    error_type = (
                        crash.message.split(":", 1)[0] if ":" in crash.message else "AssertionError"
                    )
                    error_message = crash.message
            # If no longrepr, or no reprcrash, error_type/message remain "Unknown"/"" as per original

        elif test_outcome == "skipped":
            if report.longrepr:  # report.longrepr is source for raw_output_section
                if isinstance(report.longrepr, tuple) and len(report.longrepr) == 3:
                    error_message = str(report.longrepr[2])  # Skip reason
                elif isinstance(report.longrepr, str):
                    error_message = report.longrepr

        # For "passed" outcome, specific error fields remain at their initial None or "" values.

        result_entry = PytestFailure(
            test_name=test_name,
            test_file=test_file,
            outcome=test_outcome,
            line_number=line_number,
            error_type=error_type,
            error_message=error_message,
            traceback=traceback_text,
            relevant_code=relevant_code,
            raw_output_section=raw_output_section,
        )
        self.results.append(result_entry)

    def get_results(self) -> List[PytestFailure]:
        """Get the collected test results."""
        return self.results

    def clear_results(self) -> None:
        """Clear the collected test results and reset plugin state."""
        self.results.clear()
        self.test_items.clear()


def collect_failures_with_plugin(pytest_args: List[str]) -> List[PytestFailure]:
    """
    Run pytest with the FailureCollectorPlugin to collect all test results.

    Args:
        pytest_args: Arguments to pass to pytest

    Returns:
        List of PytestFailure objects representing all test results.
    """
    plugin = FailureCollectorPlugin()
    pytest.main(pytest_args, plugins=[plugin])
    return plugin.get_results()
