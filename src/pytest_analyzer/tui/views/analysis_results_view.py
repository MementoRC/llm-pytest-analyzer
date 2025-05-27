"""Analysis results view for displaying failure analysis and fix suggestions."""

from typing import Any, Dict, List

from rich.syntax import Syntax
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button, DataTable, Label, Static

from pytest_analyzer.core.models.pytest_failure import PytestFailure


class FixApplied(Message):
    """Message posted when a fix is applied."""

    def __init__(self, fix_id: str, success: bool) -> None:
        self.fix_id = fix_id
        self.success = success
        super().__init__()


class AnalysisResultsView(Widget):
    """A view for displaying failure analysis results and fix suggestions."""

    DEFAULT_CSS = """
    AnalysisResultsView {
        layout: vertical;
        overflow-y: auto;
        padding: 1;
        border: round $primary;
        height: auto;
    }

    DataTable {
        height: 15;
        margin-top: 1;
        margin-bottom: 1;
    }

    VerticalScroll {
        height: 1fr;
        border: round $background-darken-2;
        margin-top: 1;
    }

    .fix-suggestion {
        margin: 1;
        padding: 1;
        border: round $accent;
        background: $background-lighten-1;
    }

    .suggestion-header {
        text-style: bold;
        color: $accent;
    }
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._current_failures: List[PytestFailure] = []
        self._current_suggestions: List[Any] = []  # FixSuggestion objects
        self._analysis_in_progress: bool = False

    def compose(self) -> ComposeResult:
        """Create child widgets for the analysis results view."""
        yield Label("Failure Analysis Results", classes="header")

        with Vertical():
            yield Label("Failed Tests:")
            yield DataTable(id="failures_table")

            with Horizontal():
                yield Button(
                    "Load Failures", id="load_failures_button", variant="default"
                )
                yield Button("Analyze Failures", id="analyze_button", variant="primary")
                yield Button(
                    "Apply All Fixes", id="apply_all_button", variant="success"
                )
                yield Button("Clear Results", id="clear_button", variant="warning")

            yield Label("Fix Suggestions:")
            yield VerticalScroll(id="suggestions_container")

    def on_mount(self) -> None:
        """Set up the analysis results view when mounted."""
        # Initialize the failures table
        table = self.query_one("#failures_table", DataTable)
        table.add_columns("Test", "Error Type", "Message", "Status")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses in the analysis view."""
        if event.button.id == "load_failures_button":
            self.load_failures_from_results_controller()
        elif event.button.id == "analyze_button":
            await self._analyze_failures()
        elif event.button.id == "apply_all_button":
            await self._apply_all_fixes()
        elif event.button.id == "clear_button":
            self._clear_results()

    async def _analyze_failures(self) -> None:
        """Analyze the current failures using LLM suggestions."""
        if not self._current_failures:
            self.app.notify("No failures to analyze", severity="warning")
            return

        if self._analysis_in_progress:
            self.app.notify("Analysis already in progress", severity="warning")
            return

        try:
            self._analysis_in_progress = True
            analyze_button = self.query_one("#analyze_button", Button)
            analyze_button.disabled = True

            self.app.notify("Analyzing failures with LLM...")

            # Use the analysis controller to analyze failures
            if hasattr(self.app, "analysis_controller"):
                await self.app.analysis_controller.analyze_failures(
                    self._current_failures
                )
                # Update table status
                self._update_analysis_status("Analyzed")
            else:
                # Fallback to direct analyzer service
                if hasattr(self.app, "analyzer_service"):
                    suggestions = await self.app.run_sync_in_worker(
                        self._run_analysis, self._current_failures
                    )

                    if suggestions:
                        self.update_suggestions(suggestions)
                        # Update table status
                        self._update_analysis_status("Analyzed")
                    else:
                        self.app.notify("No suggestions generated", severity="warning")
                else:
                    self.app.notify(
                        "Analysis controller not available", severity="warning"
                    )

        except Exception as e:
            self.app.logger.error(f"Analysis failed: {e}", exc_info=True)
            self.app.notify(f"Analysis failed: {e}", severity="error")
            self._update_analysis_status("Failed")
        finally:
            self._analysis_in_progress = False
            analyze_button.disabled = False

    async def _apply_all_fixes(self) -> None:
        """Apply all suggested fixes."""
        if not self._current_suggestions:
            self.app.notify("No fixes to apply", severity="warning")
            return

        self.app.notify("Applying suggested fixes...")

        try:
            applied_count = 0
            for i, suggestion in enumerate(self._current_suggestions):
                success = await self._apply_single_fix(suggestion)
                if success:
                    applied_count += 1
                    self.post_message(FixApplied(str(i), True))
                else:
                    self.post_message(FixApplied(str(i), False))

            if applied_count > 0:
                self.app.notify(
                    f"Applied {applied_count}/{len(self._current_suggestions)} fixes",
                    severity="success",
                )
            else:
                self.app.notify("No fixes could be applied", severity="warning")

        except Exception as e:
            self.app.logger.error(f"Fix application failed: {e}", exc_info=True)
            self.app.notify(f"Fix application failed: {e}", severity="error")

    def _clear_results(self) -> None:
        """Clear all analysis results."""
        self._current_failures = []
        self._current_suggestions = []

        # Clear the table
        table = self.query_one("#failures_table", DataTable)
        table.clear()

        # Clear suggestions
        container = self.query_one("#suggestions_container", VerticalScroll)
        container.remove_children()

        self.app.notify("Analysis results cleared")

    def _run_analysis(self, failures: List[PytestFailure]) -> List[Any]:
        """Run analysis using the analyzer service."""
        try:
            # Use the analyzer service to analyze failures and get suggestions
            suggestions = []
            for failure in failures:
                # Analyze individual failure - this would typically use LLM services
                # For now, create a mock suggestion structure
                suggestion = self._create_mock_suggestion(failure)
                suggestions.append(suggestion)
            return suggestions
        except Exception as e:
            self.app.logger.error(f"Error running analysis: {e}", exc_info=True)
            return []

    def _create_mock_suggestion(self, failure: PytestFailure) -> Dict[str, Any]:
        """Create a mock suggestion for demonstration."""
        return {
            "title": f"Fix for {failure.test_name}",
            "description": f"Suggested fix for {failure.error_type or 'unknown'} error",
            "code": f"# Fix for {failure.test_name}\n# TODO: Implement actual fix logic",
            "confidence": 0.8,
            "failure": failure,
        }

    async def _apply_single_fix(self, suggestion: Any) -> bool:
        """Apply a single fix suggestion."""
        try:
            # TODO: Integrate with actual fix application logic
            # For now, just simulate success
            return True
        except Exception as e:
            self.app.logger.error(f"Error applying fix: {e}", exc_info=True)
            return False

    def _update_analysis_status(self, status: str) -> None:
        """Update the analysis status in the failures table."""
        # Note: DataTable doesn't have direct row update, so we'd need to rebuild
        # For now, just log the status change
        self.app.logger.info(f"Analysis status updated to: {status}")

    def update_failures(self, failures: List[PytestFailure]) -> None:
        """Update the view with new failure data."""
        self._current_failures = failures

        # Update the failures table
        table = self.query_one("#failures_table", DataTable)
        table.clear()

        for failure in failures:
            # Extract error type from the failure message
            error_type = "Unknown"
            if failure.error_message:
                if "AssertionError" in failure.error_message:
                    error_type = "Assertion"
                elif "ImportError" in failure.error_message:
                    error_type = "Import"
                elif "AttributeError" in failure.error_message:
                    error_type = "Attribute"
                elif "TypeError" in failure.error_message:
                    error_type = "Type"

            # Truncate long messages for table display
            message = failure.error_message or ""
            if len(message) > 80:
                message = message[:77] + "..."

            table.add_row(
                failure.test_name,
                error_type,
                message,
                "Pending Analysis",
                key=failure.test_name,
            )

        self.app.notify(f"Loaded {len(failures)} failures for analysis")

    def load_failures_from_results_controller(self) -> None:
        """Load current failures from the TestResultsController."""
        if hasattr(self.app, "test_results_controller"):
            current_results = self.app.test_results_controller.get_current_results()
            if current_results:
                # Filter to only failed/error tests
                failures = [
                    r for r in current_results if r.outcome in ["failed", "error"]
                ]
                if failures:
                    self.update_failures(failures)
                else:
                    self.app.notify(
                        "No failures found in current results", severity="info"
                    )
            else:
                self.app.notify(
                    "No test results available for analysis", severity="warning"
                )
        else:
            self.app.notify("Test results controller not available", severity="warning")

    def update_suggestions(self, suggestions: List[Any]) -> None:
        """Update the view with LLM-generated fix suggestions."""
        self._current_suggestions = suggestions

        # Clear and rebuild suggestions container
        container = self.query_one("#suggestions_container", VerticalScroll)
        container.remove_children()

        for i, suggestion in enumerate(suggestions):
            suggestion_widget = self._create_suggestion_widget(i, suggestion)
            container.mount(suggestion_widget)

        self.app.notify(f"Generated {len(suggestions)} fix suggestions")

    def _create_suggestion_widget(self, index: int, suggestion: Any) -> Widget:
        """Create a widget for displaying a single fix suggestion."""
        suggestion_container = Vertical(classes="fix-suggestion")

        # Handle both dict and object formats
        if isinstance(suggestion, dict):
            title = suggestion.get("title", "Code Fix")
            description = suggestion.get("description", "No description available")
            code = suggestion.get("code", "")
            confidence = suggestion.get("confidence", 0.0)
        else:
            # Handle FixSuggestion objects or other formats
            title = getattr(suggestion, "title", "Code Fix")
            description = getattr(suggestion, "description", "No description available")
            code = getattr(suggestion, "code", "")
            confidence = getattr(suggestion, "confidence", 0.0)

        # Suggestion header with confidence
        confidence_text = f" (Confidence: {confidence:.1%})" if confidence > 0 else ""
        header = Static(
            f"Fix #{index + 1}: {title}{confidence_text}", classes="suggestion-header"
        )
        suggestion_container.compose_add_child(header)

        # Description
        desc_widget = Static(description)
        suggestion_container.compose_add_child(desc_widget)

        # Code diff with syntax highlighting
        if code:
            try:
                code_syntax = Syntax(code, "python", theme="monokai", line_numbers=True)
                code_widget = Static(code_syntax)
                suggestion_container.compose_add_child(code_widget)
            except Exception:
                # Fallback to plain text if syntax highlighting fails
                code_widget = Static(code)
                suggestion_container.compose_add_child(code_widget)

        # Action buttons
        button_container = Horizontal()
        apply_button = Button(
            f"Apply Fix #{index + 1}", id=f"apply_fix_{index}", variant="success"
        )
        reject_button = Button(
            f"Reject #{index + 1}", id=f"reject_fix_{index}", variant="error"
        )

        button_container.compose_add_child(apply_button)
        button_container.compose_add_child(reject_button)
        suggestion_container.compose_add_child(button_container)

        return suggestion_container

    async def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle failure selection in the table."""
        if event.row_key:
            failure_name = event.row_key.value
            selected_failure = next(
                (f for f in self._current_failures if f.test_name == failure_name), None
            )
            if selected_failure:
                self.app.notify(f"Selected failure: {selected_failure.test_name}")
                # Could trigger detailed view or individual analysis
