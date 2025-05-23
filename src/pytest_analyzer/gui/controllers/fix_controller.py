import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from ...core.models.pytest_failure import FixSuggestion
from ...core.protocols import Applier
from ..background.task_manager import TaskManager
from ..models.code_change import CodeChangeItem, CodeChangeSet
from .base_controller import BaseController

logger = logging.getLogger(__name__)


@dataclass
class AppliedFixRecord:
    """Record of an applied fix, for history and rollback."""

    suggestion: FixSuggestion
    application_result: Dict[str, Any]  # Result from applier.apply_fix_suggestion
    original_file_contents: Dict[Path, str]  # Path -> original content before this fix
    timestamp: float = field(default_factory=time.time)
    task_id: Optional[str] = None  # Task ID that applied this fix


class FixController(BaseController):
    """Controller for applying fixes and managing change history."""

    # Signals
    fix_applied_successfully = pyqtSignal(str, dict)  # task_id, application_result
    fix_application_failed = pyqtSignal(str, str)  # task_id, error_message
    batch_operation_completed = pyqtSignal(
        str, int, int, list
    )  # task_id, succeeded_count, failed_count, errors
    diff_generated = pyqtSignal(str, dict)  # task_id, diff_results (file_path_str: diff_text)
    diff_generation_failed = pyqtSignal(str, str)  # task_id, error_message
    change_history_updated = pyqtSignal(list)  # new_history_list

    def __init__(
        self,
        applier: Applier,
        task_manager: TaskManager,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent, task_manager=task_manager)
        self.applier = applier
        self._change_history: List[AppliedFixRecord] = []
        self.logger.info("FixController initialized.")

    def _capture_original_contents(
        self, code_change_set: CodeChangeSet
    ) -> Tuple[Dict[Path, str], Optional[str]]:
        """Captures original content of files to be modified.
        Returns a dictionary of Path -> original_content and an error string if any.
        """
        originals: Dict[Path, str] = {}
        for item in code_change_set.items:
            if item.original_code is not None:
                originals[item.file_path] = item.original_code
            else:
                # If original_code not provided in suggestion, read from disk
                try:
                    if item.file_path.exists() and item.file_path.is_file():
                        originals[item.file_path] = item.file_path.read_text(encoding="utf-8")
                    else:
                        # This case should ideally be caught earlier,
                        # but if a file doesn't exist, its "original" content is empty.
                        # However, applying a fix to a non-existent file might be an issue for the applier.
                        # For rollback purposes, if we create a new file, its original state is non-existence.
                        # This needs careful handling in rollback. For now, assume file exists or original_code is provided.
                        logger.warning(
                            f"File {item.file_path} does not exist and no original_code provided. Cannot capture original content."
                        )
                        # This is a tricky state. If the fix *creates* the file, original is "non-existent".
                        # If the fix *modifies* it, but it's missing, that's an error.
                        # For now, let's return an error if we can't determine original content for an existing file path.
                        return (
                            {},
                            f"File {item.file_path} not found, cannot capture original content.",
                        )
                except OSError as e:
                    logger.error(f"Error reading original content for {item.file_path}: {e}")
                    return {}, f"Error reading original content for {item.file_path}: {e}"
        return originals, None

    @pyqtSlot(FixSuggestion)
    def apply_fix_suggestion(self, suggestion: FixSuggestion) -> Optional[str]:
        """
        Applies a single fix suggestion in the background.
        Returns the task_id if submitted, else None.
        """
        self.logger.info(f"Request to apply fix for: {suggestion.failure.test_name}")
        if not self.task_manager:
            self.logger.error("TaskManager not available for apply_fix_suggestion.")
            self.fix_application_failed.emit("", "TaskManager not available.")  # No task_id yet
            return None

        code_change_set = CodeChangeSet.from_fix_suggestion_changes(suggestion.code_changes)
        if code_change_set.parsing_error or not code_change_set.items:
            msg = f"Cannot apply fix: Invalid or empty code changes. {code_change_set.parsing_error or ''}"
            self.logger.error(msg)
            self.fix_application_failed.emit("", msg)
            return None

        original_contents, error = self._capture_original_contents(code_change_set)
        if error:
            self.logger.error(f"Failed to capture original contents: {error}")
            self.fix_application_failed.emit("", f"Failed to capture original contents: {error}")
            return None

        # Store original_contents with the task, so _handle_apply_task_completion can access it
        # The task itself will be self.applier.apply_fix_suggestion
        # We need to pass `original_contents` to the completion handler.
        # One way is to make a small wrapper callable or pass it via kwargs if the task system supports passing arbitrary data to handlers.
        # For now, let's make the background task a bit more complex or store it temporarily keyed by task_id.
        # A simpler way: the task itself can be a method of this controller.

        task_id = self.submit_background_task(
            callable_task=self._execute_apply_fix,
            args=(suggestion, original_contents),
            kwargs={},
            use_progress_bridge=False,  # Applying one fix is usually quick
        )

        if task_id:
            self.logger.info(
                f"Fix application task {task_id} submitted for {suggestion.failure.test_name}."
            )
            # Store task_id with original_contents for completion handler
            # This is a bit hacky; ideally, task system allows passing context to completion.
            # For now, _execute_apply_fix will return a tuple: (result, original_contents_for_history)
        else:
            self.logger.error("Failed to submit fix application task.")
            self.fix_application_failed.emit("", "Failed to submit fix application task.")
        return task_id

    def _execute_apply_fix(
        self, suggestion: FixSuggestion, original_contents: Dict[Path, str]
    ) -> Tuple[Dict[str, Any], FixSuggestion, Dict[Path, str]]:
        """Worker method to apply fix and return data for history."""
        try:
            # Ensure applier is robust against non-dict code_changes
            if not isinstance(suggestion.code_changes, dict):
                return (
                    {
                        "success": False,
                        "message": "Cannot apply fix: code_changes must be a dictionary.",
                        "applied_files": [],
                        "rolled_back_files": [],
                    },
                    suggestion,
                    original_contents,
                )

            result = self.applier.apply_fix_suggestion(suggestion)
            return result, suggestion, original_contents
        except Exception as e:
            self.logger.exception(
                f"Exception during _execute_apply_fix for {suggestion.failure.test_name}"
            )
            return (
                {
                    "success": False,
                    "message": f"Exception during fix application: {e}",
                    "applied_files": [],
                    "rolled_back_files": [],
                },
                suggestion,
                original_contents,
            )

    @pyqtSlot(list)  # List[FixSuggestion]
    def apply_multiple_fixes(self, suggestions: List[FixSuggestion]) -> Optional[str]:
        """
        Applies multiple fix suggestions in a single background task.
        Returns the task_id if submitted, else None.
        """
        self.logger.info(f"Request to apply {len(suggestions)} fixes.")
        if not self.task_manager:
            self.logger.error("TaskManager not available for apply_multiple_fixes.")
            # Emitting batch_operation_completed with failure for all
            self.batch_operation_completed.emit(
                "", 0, len(suggestions), ["TaskManager not available."]
            )
            return None

        if not suggestions:
            self.logger.info("No suggestions provided to apply_multiple_fixes.")
            self.batch_operation_completed.emit("", 0, 0, [])
            return None

        # Prepare original contents for all suggestions
        tasks_data = []
        for sugg in suggestions:
            code_change_set = CodeChangeSet.from_fix_suggestion_changes(sugg.code_changes)
            if code_change_set.parsing_error or not code_change_set.items:
                # This suggestion will be skipped or marked as failed immediately
                tasks_data.append(
                    (
                        sugg,
                        None,
                        f"Invalid code changes: {code_change_set.parsing_error or 'empty'}",
                    )
                )
                continue

            originals, error = self._capture_original_contents(code_change_set)
            if error:
                tasks_data.append((sugg, None, error))
                continue
            tasks_data.append((sugg, originals, None))

        task_id = self.submit_background_task(
            callable_task=self._execute_apply_multiple_fixes,
            args=(tasks_data,),
            kwargs={},
            use_progress_bridge=True,  # For multiple items, progress is good
        )

        if task_id:
            self.logger.info(
                f"Batch fix application task {task_id} submitted for {len(suggestions)} suggestions."
            )
        else:
            self.logger.error("Failed to submit batch fix application task.")
            self.batch_operation_completed.emit("", 0, len(suggestions), ["Failed to submit task."])
        return task_id

    def _execute_apply_multiple_fixes(
        self,
        tasks_data: List[Tuple[FixSuggestion, Optional[Dict[Path, str]], Optional[str]]],
        progress=None,
    ) -> Tuple[int, int, List[str], List[AppliedFixRecord]]:
        """Worker method for applying multiple fixes."""
        succeeded_count = 0
        failed_count = 0
        errors: List[str] = []
        applied_records: List[AppliedFixRecord] = []

        total_tasks = len(tasks_data)
        if progress:
            progress.add_task(
                "apply_multiple", total=total_tasks, description="Applying multiple fixes..."
            )

        for i, (suggestion, original_contents, pre_error) in enumerate(tasks_data):
            if progress:
                progress.update(
                    "apply_multiple",
                    advance=1,
                    description=f"Applying fix for {suggestion.failure.test_name} ({i + 1}/{total_tasks})",
                )

            if pre_error:
                failed_count += 1
                errors.append(f"Skipped {suggestion.failure.test_name}: {pre_error}")
                logger.error(f"Skipping fix for {suggestion.failure.test_name}: {pre_error}")
                continue

            if original_contents is None:  # Should not happen if pre_error is None
                failed_count += 1
                errors.append(
                    f"Internal error: Missing original_contents for {suggestion.failure.test_name}"
                )
                logger.error(
                    f"Internal error: Missing original_contents for {suggestion.failure.test_name}"
                )
                continue

            try:
                # Ensure applier is robust against non-dict code_changes
                if not isinstance(suggestion.code_changes, dict):
                    result = {
                        "success": False,
                        "message": "Cannot apply fix: code_changes must be a dictionary.",
                        "applied_files": [],
                        "rolled_back_files": [],
                    }
                else:
                    result = self.applier.apply_fix_suggestion(suggestion)

                if result.get("success"):
                    succeeded_count += 1
                    record = AppliedFixRecord(
                        suggestion=suggestion,
                        application_result=result,
                        original_file_contents=original_contents,
                    )
                    applied_records.append(record)
                else:
                    failed_count += 1
                    errors.append(
                        f"Failed {suggestion.failure.test_name}: {result.get('message', 'Unknown error')}"
                    )
            except Exception as e:
                self.logger.exception(
                    f"Exception during batch application for {suggestion.failure.test_name}"
                )
                failed_count += 1
                errors.append(f"Exception for {suggestion.failure.test_name}: {e}")

        if progress:
            progress.update(
                "apply_multiple", completed=total_tasks, description="Batch apply finished."
            )
            progress.stop_task("apply_multiple")

        return succeeded_count, failed_count, errors, applied_records

    @pyqtSlot(FixSuggestion)
    def show_diff_preview(self, suggestion: FixSuggestion) -> Optional[str]:
        """
        Generates diffs for a fix suggestion in the background.
        Returns the task_id if submitted, else None.
        """
        self.logger.info(f"Request to show diff for: {suggestion.failure.test_name}")
        if not self.task_manager:
            self.logger.error("TaskManager not available for show_diff_preview.")
            self.diff_generation_failed.emit("", "TaskManager not available.")
            return None

        code_change_set = CodeChangeSet.from_fix_suggestion_changes(suggestion.code_changes)
        if code_change_set.parsing_error or not code_change_set.items:
            msg = f"Cannot generate diff: Invalid or empty code changes. {code_change_set.parsing_error or ''}"
            self.logger.error(msg)
            self.diff_generation_failed.emit("", msg)
            return None

        task_id = self.submit_background_task(
            callable_task=self._execute_show_diff,
            args=(code_change_set.items,),  # Pass items: List[CodeChangeItem]
            kwargs={},
            use_progress_bridge=False,
        )

        if task_id:
            self.logger.info(
                f"Diff generation task {task_id} submitted for {suggestion.failure.test_name}."
            )
        else:
            self.logger.error("Failed to submit diff generation task.")
            self.diff_generation_failed.emit("", "Failed to submit diff generation task.")
        return task_id

    def _execute_show_diff(self, code_change_items: List[CodeChangeItem]) -> Dict[str, str]:
        """Worker method to generate diffs."""
        diff_results: Dict[str, str] = {}
        try:
            for item in code_change_items:
                if item.error_message:  # Skip items that had parsing errors
                    diff_results[str(item.file_path)] = (
                        f"Error in change item: {item.error_message}"
                    )
                    continue
                diff_text = self.applier.show_diff(item.file_path, item.fixed_code)
                diff_results[str(item.file_path)] = diff_text
            return diff_results
        except Exception:
            self.logger.exception("Exception during _execute_show_diff")
            # Return partial results along with an error marker, or raise to be caught by task runner
            # For simplicity, let's assume task runner handles exceptions from callable_task
            # and emits task_failed. So, this method should ideally return the dict or raise.
            # If we want to pass partial diffs on error, the return type needs to accommodate that.
            # For now, let the exception propagate to be handled by TaskManager.
            raise  # This will trigger task_failed signal from TaskManager

    @pyqtSlot()
    def rollback_last_change(self) -> Optional[str]:
        """
        Rolls back the last applied change.
        Returns the task_id if submitted, else None.
        """
        self.logger.info("Request to rollback last change.")
        if not self._change_history:
            self.logger.warning("No changes in history to rollback.")
            self.fix_application_failed.emit(
                "", "No changes in history to rollback."
            )  # Using this signal for general feedback
            return None

        if not self.task_manager:
            self.logger.error("TaskManager not available for rollback_last_change.")
            self.fix_application_failed.emit("", "TaskManager not available.")
            return None

        last_applied_record = self._change_history[-1]  # Don't pop yet, pop on success

        # Prepare changes for rollback: apply original_file_contents
        changes_to_revert: Dict[str, str] = {
            str(path): content
            for path, content in last_applied_record.original_file_contents.items()
        }

        # Determine tests to validate (optional, could be original failing test)
        # For a simple rollback, maybe no validation or validate with the original test.
        validation_tests = [last_applied_record.suggestion.failure.test_name]

        task_id = self.submit_background_task(
            callable_task=self._execute_rollback,
            args=(changes_to_revert, validation_tests, last_applied_record),
            kwargs={},
            use_progress_bridge=False,
        )

        if task_id:
            self.logger.info(f"Rollback task {task_id} submitted.")
        else:
            self.logger.error("Failed to submit rollback task.")
            self.fix_application_failed.emit("", "Failed to submit rollback task.")
        return task_id

    def _execute_rollback(
        self,
        changes_to_revert: Dict[str, str],
        validation_tests: List[str],
        record_to_rollback: AppliedFixRecord,
    ) -> Tuple[Dict[str, Any], AppliedFixRecord]:
        """Worker method for rollback."""
        try:
            # The Applier's `apply` method is suitable here.
            # `FixApplierAdapter.apply` is the one to call.
            result = self.applier.apply(changes_to_revert, validation_tests)
            return result, record_to_rollback
        except Exception as e:
            self.logger.exception(
                f"Exception during _execute_rollback for {record_to_rollback.suggestion.failure.test_name}"
            )
            return {
                "success": False,
                "message": f"Exception during rollback: {e}",
                "applied_files": [],  # These would be files reverted to original
                "rolled_back_files": [],  # These would be files that failed to revert
            }, record_to_rollback

    def get_change_history(self) -> List[AppliedFixRecord]:
        """Returns the current change history."""
        return list(self._change_history)

    @pyqtSlot()
    def clear_change_history(self) -> None:
        """Clears the change history."""
        self.logger.info("Clearing change history.")
        self._change_history.clear()
        self.change_history_updated.emit(self.get_change_history())

    # Task completion/failure handlers
    # These would be connected to self.task_manager.task_completed and self.task_manager.task_failed
    # For simplicity, assuming BaseController or MainController might handle generic wiring,
    # or these are explicitly connected when tasks are submitted if task_id needs specific context.
    # Let's add specific handlers here, connected in __init__ or dynamically.
    # For now, the _execute_* methods return tuples that include context,
    # so a generic handler can unpack and decide.

    @pyqtSlot(str, object)
    def _handle_task_completion(self, task_id: str, result_data: Any) -> None:
        """Handles completion of tasks initiated by FixController."""
        self.logger.info(
            f"Task {task_id} completed in FixController. Result type: {type(result_data)}"
        )

        # Unpack result_data based on which _execute method it came from.
        # This relies on the structure of what _execute_* methods return.

        # Case 1: Single fix application (_execute_apply_fix)
        if (
            isinstance(result_data, tuple)
            and len(result_data) == 3
            and isinstance(result_data[0], dict)
            and isinstance(result_data[1], FixSuggestion)
        ):
            application_result, suggestion, original_contents = result_data
            if application_result.get("success"):
                record = AppliedFixRecord(
                    suggestion=suggestion,
                    application_result=application_result,
                    original_file_contents=original_contents,
                    task_id=task_id,
                )
                self._change_history.append(record)
                self.logger.info(
                    f"Fix for {suggestion.failure.test_name} applied successfully. History updated."
                )
                self.fix_applied_successfully.emit(task_id, application_result)
                self.change_history_updated.emit(self.get_change_history())
            else:
                self.logger.error(
                    f"Fix application failed for {suggestion.failure.test_name}: {application_result.get('message')}"
                )
                self.fix_application_failed.emit(
                    task_id, application_result.get("message", "Unknown error")
                )

        # Case 2: Batch fix application (_execute_apply_multiple_fixes)
        elif (
            isinstance(result_data, tuple)
            and len(result_data) == 4
            and isinstance(result_data[3], list)
        ):
            succeeded_count, failed_count, errors, applied_records = result_data
            for record in applied_records:  # These are already AppliedFixRecord instances
                record.task_id = task_id  # Assign batch task_id
                self._change_history.append(record)

            self.logger.info(
                f"Batch fix operation {task_id} completed. Succeeded: {succeeded_count}, Failed: {failed_count}."
            )
            if applied_records:  # Only emit history update if something was actually added
                self.change_history_updated.emit(self.get_change_history())
            self.batch_operation_completed.emit(task_id, succeeded_count, failed_count, errors)

        # Case 3: Diff generation (_execute_show_diff - returns Dict[str, str])
        elif isinstance(result_data, dict) and all(
            isinstance(k, str) and isinstance(v, str) for k, v in result_data.items()
        ):
            diff_results = result_data
            self.logger.info(f"Diff generation task {task_id} completed.")
            self.diff_generated.emit(task_id, diff_results)

        # Case 4: Rollback (_execute_rollback)
        elif (
            isinstance(result_data, tuple)
            and len(result_data) == 2
            and isinstance(result_data[0], dict)
            and isinstance(result_data[1], AppliedFixRecord)
        ):
            rollback_result, rolled_back_record = result_data
            if rollback_result.get("success"):
                # Remove the rolled-back record from history
                if (
                    self._change_history and self._change_history[-1] is rolled_back_record
                ):  # Check if it's indeed the last one
                    self._change_history.pop()
                    self.logger.info(
                        f"Rollback for {rolled_back_record.suggestion.failure.test_name} successful. History updated."
                    )
                    self.fix_applied_successfully.emit(
                        task_id, rollback_result
                    )  # Re-using this signal for "success"
                    self.change_history_updated.emit(self.get_change_history())
                else:
                    # This case should ideally not happen if logic is correct
                    self.logger.error("Rollback successful but history state inconsistent.")
                    self.fix_application_failed.emit(
                        task_id, "Rollback successful but history state inconsistent."
                    )
            else:
                self.logger.error(
                    f"Rollback failed for {rolled_back_record.suggestion.failure.test_name}: {rollback_result.get('message')}"
                )
                self.fix_application_failed.emit(
                    task_id, rollback_result.get("message", "Unknown error during rollback")
                )
        else:
            self.logger.warning(
                f"Task {task_id} completed in FixController with unhandled result type: {type(result_data)}"
            )

    @pyqtSlot(str, str)
    def _handle_task_failure(self, task_id: str, error_message: str) -> None:
        """Handles failure of tasks initiated by FixController."""
        # Determine which signal to emit based on task context (if possible/needed)
        # For now, broadly emit fix_application_failed or diff_generation_failed
        # This requires knowing what kind of task failed.
        # If task_id prefixes were used, we could check.
        # For now, let's assume most critical failures are related to applying fixes.
        self.logger.error(f"Task {task_id} failed in FixController: {error_message}")

        # Heuristic: if the error message contains "diff", it's likely a diff task.
        if "diff" in error_message.lower() or "show_diff" in error_message.lower():  # A bit fragile
            self.diff_generation_failed.emit(task_id, error_message)
        else:  # Default to fix application failure
            self.fix_application_failed.emit(task_id, error_message)

        # Note: If a batch operation task fails entirely (e.g., _execute_apply_multiple_fixes raises unhandled exception),
        # this handler will be called. The batch_operation_completed signal might not be emitted with partial results.
        # The _execute_apply_multiple_fixes is designed to catch exceptions per item and return a summary,
        # so it should ideally complete successfully and emit batch_operation_completed.
        # This handler is for catastrophic failure of the task itself.

    def connect_to_task_manager(self):
        """Connects to TaskManager signals. Call this after TaskManager is available."""
        if self.task_manager:
            # Disconnect first to avoid multiple connections if called multiple times
            try:
                self.task_manager.task_completed.disconnect(self._handle_task_completion)
                self.task_manager.task_failed.disconnect(self._handle_task_failure)
            except TypeError:  # Raised if not connected
                pass
            self.task_manager.task_completed.connect(self._handle_task_completion)
            self.task_manager.task_failed.connect(self._handle_task_failure)
            self.logger.info("FixController connected to TaskManager signals.")
        else:
            self.logger.warning("FixController: TaskManager not available to connect signals.")
