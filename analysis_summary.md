# Analysis of TUI FileController Integration with PytestAnalyzerService

This document outlines the necessary integration work for `src/pytest_analyzer/tui/controllers/file_controller.py` with `PytestAnalyzerService`.

## 1. Current Placeholder Functionality in TUI `FileController`

The TUI `FileController` (`src/pytest_analyzer/tui/controllers/file_controller.py`) currently has placeholder logic for interacting with a backend service:

*   **`_load_test_file(self, path: Path)` and `_load_directory(self, path: Path)`**:
    *   These methods log the action and send a notification (e.g., `self.app.notify(...)`).
    *   They contain commented-out lines like `# self.app.analyzer_service.set_target_path(path, "py")`, indicating an intent to inform a service about the selected path.
    *   They do not currently trigger any test discovery or execution through `PytestAnalyzerService`.

*   **`_load_json_report(self, path: Path)` and `_load_xml_report(self, path: Path)`**:
    *   These methods implement their own parsing logic (`_parse_json_report_sync`, `_parse_xml_report_sync`) executed via `self.app.run_sync_in_worker`.
    *   They parse the report files into `PytestFailure` objects (or a similar structure).
    *   They do not use `PytestAnalyzerService` for parsing these report files or for any subsequent analysis based on these reports.

## 2. GUI `FileController` Integration Patterns (for Reference)

The GUI `FileController` (`src/pytest_analyzer/gui/controllers/file_controller.py`) provides some patterns, though its interaction with `PytestAnalyzerService` is mostly indirect:

*   **Model-based State**: The GUI `FileController` updates a `TestResultsModel` with `source_file` and `source_type` when a file or directory is selected. This model is then likely used by another controller (e.g., `AnalysisController` in the GUI) to trigger actions via `PytestAnalyzerService`.
*   **Direct Parsing for Reports**: Similar to the TUI, the GUI `FileController` parses JSON and XML reports directly (`_load_json_report`, `_load_xml_report`) and emits a `report_parsed` signal with `TestResult` objects. It does *not* use `PytestAnalyzerService.analyze_pytest_output()` for this parsing step.
*   **Separation of Concerns**: In the GUI, selecting a file/directory (handled by `FileController`) is separate from running tests or analysis (handled by `AnalysisController`). The `FileController` primarily prepares the context for these actions.

## 3. Core Service Methods Available for File Operations

The `PytestAnalyzerFacade` (which `PytestAnalyzerService` from `core.backward_compat` inherits) provides relevant methods:

*   **`analyze_pytest_output(self, output_path: Union[str, Path]) -> List[FixSuggestion]`**:
    *   Takes a path to an *existing* pytest output file (JSON or XML).
    *   Parses the file, extracts failures, analyzes them, and returns a list of `FixSuggestion` objects.
    *   This method could replace the TUI's custom `_parse_json_report_sync` and `_parse_xml_report_sync` if the goal is to get suggestions, not just raw test data. If only raw data is needed, a new service method or direct parsing (as currently done) is appropriate.

*   **`run_pytest_only(self, test_path: str, pytest_args: Optional[List[str]] = None, ...) -> List[PytestFailure]`**:
    *   Runs pytest on a specified test path (file or directory).
    *   Returns a list of `PytestFailure` objects representing the test outcomes.
    *   Suitable for when the TUI user selects a `.py` file or directory and wants to execute tests.

*   **`run_and_analyze(self, test_path: str, ...) -> List[FixSuggestion]`**:
    *   Runs pytest on the given path and then analyzes the output.
    *   Returns a list of `FixSuggestion` objects.

*   **`discover_tests_filesystem(self, project_root: Path, ...) -> List[PytestFailure]`**:
    *   (Available in `PytestAnalyzerService` from `core.analyzer_service.py`, not directly on the Facade but accessible if the TUI uses the full service).
    *   Performs a lightweight scan of the filesystem to discover tests without running pytest.
    *   Useful for a "Refresh Tests" or "Discover Tests" feature.

## 4. Adapting Integration for Async TUI Event Handling

The TUI `FileController` methods are already `async`. To integrate with the synchronous methods of `PytestAnalyzerService` (or `PytestAnalyzerFacade`):

*   **`app.run_sync_in_worker`**: All calls to `PytestAnalyzerService` methods (e.g., `run_pytest_only`, `analyze_pytest_output`) must be wrapped in `self.app.run_sync_in_worker(...)` to prevent blocking the TUI event loop. This is already the pattern used for the TUI's current synchronous parsing functions.
*   **Handling Results**: The TUI will need to handle the results (e.g., `List[PytestFailure]`, `List[FixSuggestion]`) returned from the worker thread. This typically involves:
    *   Defining messages that can be posted back to the TUI app upon completion.
    *   Updating TUI views or models with the received data.
*   **Progress Reporting**: `PytestAnalyzerService.run_pytest_only` and `run_and_analyze` can accept `progress` and `task_id` arguments (compatible with `rich.progress`). The TUI could potentially adapt its progress display mechanisms or pass a TUI-specific progress handler if the service's progress reporting is to be integrated. The GUI uses a `ProgressBridge` for this. A similar concept or a simpler callback mechanism might be needed for the TUI if fine-grained progress from the service is desired.

## Summary of Integration Work Needed for TUI `FileController`

1.  **Define TUI State/Model**:
    *   Establish how the TUI will manage the current context (selected path, loaded results). This could be attributes on `TUIApp`, a dedicated TUI model, or state within relevant controllers.

2.  **Integrate `_load_test_file` and `_load_directory`**:
    *   These methods should set the application's current target path (e.g., `self.app.current_test_target = path`).
    *   The actual test execution (`run_pytest_only` or `run_and_analyze`) would likely be triggered by a separate user action (e.g., a "Run Tests" command/button) handled by another controller or the main app, which would then use this stored path to call the appropriate `PytestAnalyzerService` method via `run_sync_in_worker`.
    *   Alternatively, if a "discover tests on select" feature is desired, these methods could trigger `PytestAnalyzerService.discover_tests_filesystem` (if using the full service) or `run_pytest_only` with collection-only arguments.

3.  **Integrate `_load_json_report` and `_load_xml_report`**:
    *   **Option A (Current Approach - Parse Only)**: Continue with direct parsing (`_parse_json_report_sync`, `_parse_xml_report_sync`) if the only requirement is to display raw test results as `PytestFailure` objects.
    *   **Option B (Service-based Parsing & Analysis)**: If suggestions or deeper analysis from pre-existing reports are needed, replace the custom parsing logic with calls to `PytestAnalyzerService.analyze_pytest_output(path)` via `run_sync_in_worker`.
        *   This returns `List[FixSuggestion]`. The TUI would need to adapt its data handling to process these suggestions (which include the original `PytestFailure` data).
    *   **Option C (Service-based Parsing Only)**: If the desire is to use the service's extractors but only get `PytestFailure` objects (without analysis/suggestions), a new method might need to be added to `PytestAnalyzerService` (e.g., `parse_report_file(path) -> List[PytestFailure]`).

4.  **Result Handling**:
    *   Implement mechanisms (e.g., Textual messages, callbacks) for the TUI to receive and process results (`List[PytestFailure]` or `List[FixSuggestion]`) from `run_sync_in_worker` calls.
    *   Update relevant TUI views (e.g., test list, details panel) with the processed data.

5.  **Error Handling**:
    *   Ensure robust error handling for service calls made via `run_sync_in_worker`, displaying appropriate error messages in the TUI.

6.  **User Notifications**:
    *   Continue using `self.app.notify` to provide feedback to the user about ongoing operations and outcomes.
    *   Consider more detailed progress updates if integrating with the service's progress reporting capabilities.
