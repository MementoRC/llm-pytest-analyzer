# Analysis for TUI TestExecutionController Integration with PytestAnalyzerService

This document outlines the steps and considerations for integrating `PytestAnalyzerService` into the TUI `TestExecutionController` to enable real test execution functionality.

## 1. Current TUI TestExecution Functionality (Placeholders)

The TUI currently has basic UI elements for test execution but lacks real integration with the analysis core.

*   **`src/pytest_analyzer/tui/views/test_execution_view.py`**:
    *   Contains a `TestExecutionView` widget with a "Run Tests" button (`run_tests_button`), a `ProgressBar` (`test_progress_bar`), and a `Log` (`execution_log`).
    *   The `on_button_pressed` handler for "Run Tests" currently simulates test execution with a loop that advances the progress bar and writes to the log. This needs to be replaced with actual test execution logic.
    *   It provides methods like `update_progress` and `add_log_message` that a controller can use.

*   **`src/pytest_analyzer/tui/controllers/test_results_controller.py`**:
    *   The `auto_load_test_results` method has a placeholder comment: `pytest_failures: List[PytestFailure] = [] # Placeholder` and `This part needs the TUI TestExecutionController to be implemented`. This indicates it expects a TUI `TestExecutionController` to provide the actual test failure data.

*   **Missing TUI `TestExecutionController`**:
    *   There isn't a dedicated TUI `TestExecutionController` analogous to the GUI version. This controller needs to be created or its responsibilities incorporated into an existing TUI controller. It will mediate between the `TestExecutionView` and the `PytestAnalyzerService`.

## 2. GUI TestExecutionController Integration with PytestAnalyzerService

The GUI `TestExecutionController` (`src/pytest_analyzer/gui/controllers/test_execution_controller.py`) provides a reference model for integration:

*   **Service Invocation**:
    *   The `start_test_run` method is responsible for initiating a test run.
    *   It calls `self.analyzer_service.run_pytest_only(test_path, effective_pytest_args)` to execute tests.

*   **Background Task Management**:
    *   It uses a `TaskManager` (from `gui.background.task_manager`) to run `analyzer_service.run_pytest_only` in a background thread, preventing UI freezes. The `submit_background_task` method of `BaseController` is used.

*   **Signal/Slot Mechanism for Updates**:
    *   `task_started`: Handles UI setup (resetting views, showing progress view, starting timer).
    *   `task_progress`: Updates the progress view with percentage and messages. (Note: `run_pytest_only` itself provides coarse progress; this might be more for the `TaskManager`'s own progress reporting).
    *   `task_completed`: Handles successful completion, processes results (`List[PytestFailure]`), updates stats, and emits `test_execution_completed`.
    *   `task_failed`: Handles errors during test execution.
    *   `output_received`: A signal in the GUI controller, connected to `output_view.append_output`. The `_output_callback_handler` method emits this signal. This suggests the GUI's task execution mechanism captures and streams live output from the test process.

*   **Progress Bridge**:
    *   If `use_progress_bridge=True` is passed to `submit_background_task`, a `ProgressBridge` instance is created and passed as the `progress` argument to the `callable_task` (e.g., `run_pytest_only`).
    *   `ProgressBridge` adapts `rich.progress`-like calls from the service to Qt signals.

*   **Result Handling**:
    *   Test failures (`List[PytestFailure]`) are received as the result of the background task.
    *   These are cached in `_cached_failures`. The `test_execution_completed` signal emits an empty list to avoid Qt memory issues with large data in signals; consumers then call `get_last_failures()` to retrieve the cached data.

## 3. Core Service Test Execution Methods (PytestAnalyzerService)

The `src/pytest_analyzer/core/analyzer_service.py` provides methods for test execution. The primary method for the TUI `TestExecutionController` will be:

*   **`run_pytest_only(test_path: str, pytest_args: Optional[List[str]] = None, quiet: bool = False, progress: Optional[Progress] = None, task_id: Optional[TaskID] = None) -> List[PytestFailure]`**:
    *   **Functionality**: Executes pytest on the specified `test_path` with given `pytest_args`. It then extracts and returns a list of `PytestFailure` objects. It does *not* generate fix suggestions.
    *   **Synchronous**: This is a blocking, synchronous method.
    *   **Parameters**:
        *   `test_path`: The file or directory to test.
        *   `pytest_args`: A list of additional arguments for the pytest command.
        *   `quiet`: If `True`, suppresses pytest's own console output (e.g., by adding `-qq`, `--tb=short`). The service itself still logs.
        *   `progress`: An optional `rich.progress.Progress` object. If provided along with `task_id`, `run_pytest_only` will add a sub-task to it and report start/completion of the pytest run.
        *   `task_id`: The parent `TaskID` for the `progress` object.
    *   **Return Value**: A `List[PytestFailure]` containing details of all tests (passed, failed, error, skipped).
    *   **Live Output**: This method, as currently implemented, runs pytest as a subprocess and captures its output upon completion (`process.communicate()`). It does not inherently provide a mechanism for streaming live stdout/stderr lines via a callback.
    *   **Progress Granularity**: The progress updates provided via the `progress` object are coarse: it signals the start of "Running pytest..." and then its completion or failure. It does not provide test-by-test progress.

## 4. Implementing Real Test Execution in TUI

A TUI `TestExecutionController` needs to be implemented.

*   **TUI `TestExecutionController` Structure**:
    *   It should be a `BaseController` subclass (or similar, depending on TUI architecture).
    *   It will require an instance of `PytestAnalyzerService` (likely injected via its `__init__`).
    *   It will hold state, such as the path to test, arguments, and last execution results.

*   **Async Event Handling for Test Execution**:
    *   The `TestExecutionView.on_button_pressed` (an `async` method) will call a method on the TUI `TestExecutionController`, e.g., `async def execute_tests(self, test_path: str, pytest_args: List[str]):`.
    *   Inside `execute_tests`:
        1.  Update `TestExecutionView`: `log_widget.clear()`, `log_widget.write_line("Starting test execution...")`, `progress_bar.visible = True`, `progress_bar.progress = 0` (or set to indeterminate).
        2.  Call `analyzer_service.run_pytest_only` in a worker thread to avoid blocking the TUI event loop. This can be done using `await self.app.workers.run_in_thread(self.analyzer_service.run_pytest_only, test_path, pytest_args_list, quiet=True, progress=tui_progress_adapter, task_id=parent_task_id_for_tui_progress)`.
            *   `quiet=True` is recommended so the TUI can control its own log output.
            *   `tui_progress_adapter` and `parent_task_id_for_tui_progress` are discussed in the next section.
        3.  The result (`List[PytestFailure]`) from the thread will be returned to this `async` method.
        4.  Handle the results (see next section).

*   **Parameters for `run_pytest_only`**:
    *   `test_path`: Should be configurable in the TUI, perhaps from a file tree or input field.
    *   `pytest_args`: Also configurable, potentially from an input field or settings.
    *   `quiet`: Likely `True`.
    *   `progress`, `task_id`: See Section 5.

## 5. TUI Progress Reporting and Result Handling

*   **Progress Reporting**:
    *   `PytestAnalyzerService.run_pytest_only` updates a `rich.progress.Progress`-like object if provided.
    *   **Challenge**: The TUI `TestExecutionView.ProgressBar` is a Textual widget, not a Rich `Progress` object.
    *   **Approach**:
        1.  **No Granular Progress from Service**: Given `run_pytest_only` offers coarse progress (start/finish of pytest execution itself), the TUI can reflect this:
            *   Before calling `run_in_thread`: Update TUI log to "Executing tests...", set progress bar to 0 or indeterminate.
            *   After `run_in_thread` completes: Update TUI log to "Execution finished.", set progress bar to 100.
        2.  **Live Output**: `PytestAnalyzerService.run_pytest_only` does not stream live output. The TUI `Log` will therefore not show live pytest output unless `PytestAnalyzerService` is modified or the TUI controller reimplements the subprocess handling to stream output. The GUI `TestExecutionController` achieves live output, likely through its `TaskManager`'s capabilities or a modified/wrapped service call that the TUI doesn't have access to by default. The TUI `Log` should primarily display status messages from the TUI `TestExecutionController` itself (e.g., "Starting tests", "X failures found").

*   **Result Handling**:
    1.  The `List[PytestFailure]` returned by `analyzer_service.run_pytest_only` (from the worker thread) is received by the TUI `TestExecutionController`'s `async` method.
    2.  Store these failures in the controller (e.g., `self._last_failures: List[PytestFailure]`).
    3.  Update `TestExecutionView`:
        *   `add_log_message(f"Test execution finished. Found {len(self._last_failures)} results (passed, failed, etc.).")`
        *   Specifically count failures: `num_actual_failures = sum(1 for pf in self._last_failures if pf.outcome in ["failed", "error"])`.
        *   `add_log_message(f"Reported {num_actual_failures} failures/errors.")`
    4.  Notify the `TestResultsController` (or the relevant TUI view/component responsible for displaying detailed test results) that new data is available. This could be:
        *   A direct method call: `self.app.test_results_controller.load_results(self._last_failures)`.
        *   Posting a Textual message that the `TestResultsController` (or view) subscribes to.
    5.  The `TestResultsController.auto_load_test_results` (or a new method like `display_execution_results`) would then use this list to update its view.

*   **Error Handling**:
    *   The call to `self.app.workers.run_in_thread(...)` should be wrapped in a `try...except` block within the TUI `TestExecutionController`'s `async` method.
    *   If an exception occurs (e.g., `PytestAnalyzerService` raises an error, or the thread itself fails):
        *   Update `TestExecutionView.Log` with an error message: `self.query_one(Log).write_line(f"[red]Error during test execution: {e}[/red]")`.
        *   Set `ProgressBar` to a failed state if possible, or hide/reset it.
        *   Ensure any ongoing test state is cleared.

By implementing these points, the TUI can leverage `PytestAnalyzerService` for actual test execution, providing a more functional and integrated user experience. The main difference compared to the GUI will be the lack of live pytest output streaming and potentially less granular progress updates during the pytest execution phase itself, based on the current `PytestAnalyzerService.run_pytest_only` capabilities.
