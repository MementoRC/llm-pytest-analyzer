from pathlib import Path
from typing import Any, Dict, Optional

from PySide6.QtCore import QObject, Signal

from .workflow_state_machine import WorkflowState


class WorkflowGuide(QObject):
    """Provides contextual guidance messages based on the current workflow state."""

    guidance_updated = Signal(str, str)  # message, tooltip

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._messages: Dict[WorkflowState, str] = {
            WorkflowState.IDLE: "Welcome! Open a test file, directory, or report to begin.",
            WorkflowState.FILE_SELECTED: "File '{file_name}' selected. You can now discover tests (if applicable) or run tests.",
            WorkflowState.TESTS_DISCOVERING: "Discovering tests in '{file_name}'...",
            WorkflowState.TESTS_DISCOVERED: "{test_count} tests discovered. You can now run these tests.",
            WorkflowState.TESTS_RUNNING: "Tests are running for '{file_name}'...",
            WorkflowState.RESULTS_AVAILABLE: "{result_count} test results available ({failure_count} failures). Analyze failures or view results.",
            WorkflowState.ANALYSIS_RUNNING: "Analyzing {failure_count} test failures...",
            WorkflowState.FIXES_AVAILABLE: "{suggestion_count} fix suggestions available. Review and apply fixes.",
            WorkflowState.APPLYING_FIXES: "Applying selected fixes...",
            WorkflowState.FIXES_APPLIED: "{applied_count} fixes applied. You may want to re-run tests.",
            WorkflowState.ERROR: "Error: {error_message}. Previous state: {previous_state}. Please check logs or try a different action.",
        }
        self._tooltips: Dict[WorkflowState, str] = {
            WorkflowState.IDLE: "Use File > Open or the 'Select Files/Reports' tab.",
            WorkflowState.FILE_SELECTED: "Use Tools > Run Tests or explore discovered tests if applicable.",
            WorkflowState.TESTS_DISCOVERING: "Test discovery is in progress. Please wait.",
            WorkflowState.TESTS_DISCOVERED: "Use Tools > Run Tests to execute the discovered tests.",
            WorkflowState.TESTS_RUNNING: "Test execution is in progress. Monitor the progress bar and output.",
            WorkflowState.RESULTS_AVAILABLE: "Use Tools > Analyze to get fix suggestions for failures.",
            WorkflowState.ANALYSIS_RUNNING: "LLM analysis is in progress. Please wait.",
            WorkflowState.FIXES_AVAILABLE: "Select suggestions from the test results view and apply them.",
            WorkflowState.APPLYING_FIXES: "Fix application is in progress. Please wait.",
            WorkflowState.FIXES_APPLIED: "Verify the changes and consider re-running tests to confirm fixes.",
            WorkflowState.ERROR: "An error occurred. Check the details and try to resolve or restart the workflow.",
        }

    def update_guidance(
        self, state: WorkflowState, context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Updates the guidance message and tooltip based on the current state and context.

        Args:
            state: The current WorkflowState.
            context: A dictionary containing contextual information for formatting messages.
        """
        context = context or {}

        # Ensure default values for context variables used in messages
        file_path = context.get("file_path")
        default_context = {
            "file_name": file_path.name if file_path else "N/A",
            "test_count": context.get("test_count", 0),
            "result_count": context.get("result_count", 0),
            "failure_count": context.get("failure_count", 0),
            "suggestion_count": context.get("suggestion_count", 0),
            "applied_count": context.get("applied_count", 0),
            "error_message": context.get("error_message", "Unknown error"),
            "previous_state": context.get("previous_state", "N/A"),
        }

        # Merge provided context with defaults, giving priority to provided context
        final_context = {**default_context, **context}
        # Ensure file_name is derived correctly if file_path is in final_context and is not None
        if "file_path" in final_context and final_context["file_path"] is not None:
            final_context["file_name"] = Path(final_context["file_path"]).name

        message_template = self._messages.get(state, "No guidance available for the current state.")
        tooltip_template = self._tooltips.get(state, "")

        try:
            message = message_template.format(**final_context)
            tooltip = tooltip_template.format(**final_context)
        except KeyError as e:
            # This can happen if a context variable is missing from final_context
            # but expected by the format string.
            message = f"Guidance message formatting error for state {state}: Missing key {e}"
            tooltip = "Error in guidance tooltip."
            # Potentially log this error

        self.guidance_updated.emit(message, tooltip)
