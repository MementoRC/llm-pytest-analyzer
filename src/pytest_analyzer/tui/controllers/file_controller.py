from pathlib import Path
from typing import TYPE_CHECKING, List

from pytest_analyzer.core.models.pytest_failure import PytestFailure

from .base_controller import BaseController

if TYPE_CHECKING:
    from ..app import TUIApp


class FileController(BaseController):
    """Handles file selection, loading, and report parsing for the TUI."""

    def __init__(self, app: "TUIApp"):
        super().__init__(app)
        self.analyzer_service = app.analyzer_service
        self.logger.info("FileControllerTUI initialized")

    def load_file(self, file_path: Path) -> None:
        """Synchronous file loading method for test compatibility."""
        # For testing compatibility, just do the minimal required work
        # Don't try to run async code in sync context
        self.app.current_test_target = file_path
        self.logger.info(f"File loaded synchronously: {file_path}")

        # Notify the app (simplified for testing)
        if hasattr(self.app, "notify"):
            self.app.notify(f"File loaded: {file_path.name}")

    def load_directory(self, dir_path: Path) -> None:
        """Synchronous directory loading method for test compatibility."""
        # For testing compatibility, just do the minimal required work
        self.app.current_test_target = dir_path
        self.logger.info(f"Directory loaded synchronously: {dir_path}")

        # Notify the app (simplified for testing)
        if hasattr(self.app, "notify"):
            self.app.notify(f"Directory loaded: {dir_path.name}")

    async def on_path_selected(self, path_str: str) -> None:
        """Handle path selection from the file selection view (or other source)."""
        path = Path(path_str)
        file_type = path.suffix.lower()
        self.logger.info(f"Path selected: {path}, type: {file_type}")

        # Update status bar (example, TUIApp should have a way to show status)
        # self.app.update_status(f"Selected: {path.name}")

        if file_type == ".py":
            await self._load_test_file(path)
        elif path.is_dir():
            await self._load_directory(path)
        elif file_type == ".json":
            await self._load_json_report(path)
        elif file_type == ".xml":
            await self._load_xml_report(path)
        else:
            self.app.notify(f"Unsupported file type: {path.name}", severity="warning")
            self.logger.warning(
                f"Unsupported file type: {file_type} for path {path.name}"
            )

    async def _load_test_file(self, path: Path) -> None:
        """Prepare for running tests from a specific Python file."""
        self.logger.info(f"Preparing for test file: {path}")

        # Set test target on TestExecutionController
        if hasattr(self.app, "test_execution_controller"):
            self.app.test_execution_controller.set_test_target(str(path))

        # Clear previous results
        if hasattr(self.app, "test_results_controller"):
            self.app.test_results_controller.clear_results()

        self.app.notify(f"Test file selected: {path.name}. Ready for test execution.")

    async def _load_directory(self, path: Path) -> None:
        """Prepare for running tests from a directory."""
        self.logger.info(f"Preparing for test directory: {path}")

        # Set test target on TestExecutionController
        if hasattr(self.app, "test_execution_controller"):
            self.app.test_execution_controller.set_test_target(str(path))

        # Clear previous results
        if hasattr(self.app, "test_results_controller"):
            self.app.test_results_controller.clear_results()

        self.app.notify(f"Directory selected: {path.name}. Ready for test execution.")

    async def _load_json_report(self, path: Path) -> None:
        """Load test results from a JSON report file (TUI version)."""
        self.logger.info(f"Loading JSON report: {path}")
        self.app.notify(f"Processing JSON report: {path.name}...")
        try:
            # Parse the report to get PytestFailure objects
            failures = await self.app.run_sync_in_worker(
                self._parse_report_to_failures, path, "json"
            )

            # Send results to TestResultsController
            if hasattr(self.app, "test_results_controller") and failures is not None:
                self.app.test_results_controller.load_report_data(
                    failures, path, "json"
                )

            status_msg = (
                f"Loaded {len(failures) if failures else 0} results from {path.name}"
            )
            self.app.notify(status_msg)
            self.logger.info(status_msg)

        except Exception as e:
            self.logger.error(f"Error loading JSON report {path}: {e}", exc_info=True)
            self.app.notify(f"Error loading JSON report: {str(e)}", severity="error")

    async def _load_xml_report(self, path: Path) -> None:
        """Load test results from an XML report file (TUI version)."""
        self.logger.info(f"Loading XML report: {path}")
        self.app.notify(f"Processing XML report: {path.name}...")
        try:
            # Parse the report to get PytestFailure objects
            failures = await self.app.run_sync_in_worker(
                self._parse_report_to_failures, path, "xml"
            )

            # Send results to TestResultsController
            if hasattr(self.app, "test_results_controller") and failures is not None:
                self.app.test_results_controller.load_report_data(failures, path, "xml")

            status_msg = (
                f"Loaded {len(failures) if failures else 0} results from {path.name}"
            )
            self.app.notify(status_msg)
            self.logger.info(status_msg)

        except Exception as e:
            self.logger.error(f"Error loading XML report {path}: {e}", exc_info=True)
            self.app.notify(f"Error loading XML report: {str(e)}", severity="error")

    def _parse_report_to_failures(
        self, path: Path, report_type: str
    ) -> List[PytestFailure]:
        """Parse a report file to extract PytestFailure objects."""
        try:
            if report_type == "json":
                from pytest_analyzer.core.extraction.json_extractor import JSONExtractor

                extractor = JSONExtractor()
            elif report_type == "xml":
                from pytest_analyzer.core.extraction.xml_extractor import XMLExtractor

                extractor = XMLExtractor()
            else:
                raise ValueError(f"Unsupported report type: {report_type}")

            # Extract failures from the report
            failures = extractor.extract_failures(path)
            self.logger.info(
                f"Extracted {len(failures)} failures from {report_type} report: {path.name}"
            )
            return failures

        except Exception as e:
            self.logger.error(
                f"Error parsing {report_type} report {path}: {e}", exc_info=True
            )
            raise
