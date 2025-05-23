import logging
import subprocess  # For direct Git calls where git_manager lacks functionality
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from ...core.models.pytest_failure import FixSuggestion
from ...core.protocols import Applier
from ...utils import git_manager  # Import for git_manager functions
from ...utils.git_manager import GitError  # Specific import for GitError
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
    git_commit_hash: Optional[str] = None  # Added for Git integration


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

    # Git specific signals
    git_repo_status_checked = pyqtSignal(
        bool, str, str
    )  # is_git_repo, git_root_path_str, error_message
    git_status_updated = pyqtSignal(str, dict)  # task_id, {file_path_str: status_str}
    git_status_update_failed = pyqtSignal(str, str)  # task_id, error_message
    branch_created = pyqtSignal(str, str, str)  # task_id, new_branch_name, original_branch_name
    branch_creation_failed = pyqtSignal(str, str)  # task_id, error_message
    commit_succeeded = pyqtSignal(str, str, str)  # task_id, commit_hash, commit_message
    commit_failed = pyqtSignal(str, str)  # task_id, error_message

    def __init__(
        self,
        applier: Applier,
        task_manager: TaskManager,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent, task_manager=task_manager)
        self.applier = applier
        self._change_history: List[AppliedFixRecord] = []

        # Git integration attributes
        self._is_git_repo: bool = False
        self._git_root: Optional[Path] = None
        self._active_fix_branch: Optional[str] = None  # Branch created/managed by FixController
        self._original_branch_before_fix_branch: Optional[str] = None

        self.logger.info("FixController initialized.")
        self.check_git_status()  # Initialize Git status check

    # --- Git Integration Methods ---

    @pyqtSlot()
    def check_git_status(self) -> Optional[str]:
        """
        Checks if the project is a Git repository and gets its root.
        Emits git_repo_status_checked upon completion.
        Returns task_id if submitted.
        """
        self.logger.info("Request to check Git repository status.")
        return self.submit_background_task(
            callable_task=self._execute_check_git_status,
            use_progress_bridge=False,
        )

    def _execute_check_git_status(self) -> Tuple[bool, str, str]:
        """Worker method to check Git status."""
        if not git_manager.check_git_installed():
            self._is_git_repo = False
            return False, "", "Git is not installed or not found in PATH."

        # Assuming project_root is available, e.g. from applier or config
        # For now, let's use current working directory as a proxy if project_root is complex to get here.
        # A better approach would be to pass project_root to FixController.
        # Using self.applier if it has project_root, else CWD.
        project_path_to_check = Path.cwd()
        if hasattr(self.applier, "_fix_applier") and hasattr(
            self.applier._fix_applier, "project_root"
        ):  # type: ignore
            project_path_to_check = self.applier._fix_applier.project_root  # type: ignore
        elif hasattr(self.applier, "project_root"):  # For generic applier that might have it
            project_path_to_check = self.applier.project_root  # type: ignore

        if git_manager.is_git_repository(str(project_path_to_check)):
            git_root_str = git_manager.get_git_root(str(project_path_to_check))
            if git_root_str:
                self._is_git_repo = True
                self._git_root = Path(git_root_str)
                # Get current branch
                try:
                    current_branch_proc = subprocess.run(
                        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                        cwd=self._git_root,
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    self._active_fix_branch = (
                        current_branch_proc.stdout.strip()
                    )  # Initially, active is current
                except (subprocess.CalledProcessError, FileNotFoundError) as e:
                    logger.warning(f"Could not determine current Git branch: {e}")
                return True, git_root_str, ""
            self._is_git_repo = False
            return False, "", "Located in Git repo, but couldn't get root."
        self._is_git_repo = False
        return False, "", "Not a Git repository or sub-directory."

    @pyqtSlot(list)  # List[Union[str, Path]]
    def refresh_file_git_status(self, file_paths: List[Union[str, Path]]) -> Optional[str]:
        """
        Gets the Git status for a list of files.
        Emits git_status_updated or git_status_update_failed.
        Returns task_id if submitted.
        """
        self.logger.info(f"Request to refresh Git status for {len(file_paths)} files.")
        if not self._is_git_repo or not self._git_root:
            self.logger.warning("Cannot get file status, not in a Git repository.")
            # Emit failure directly if task submission is skipped
            self.git_status_update_failed.emit("", "Not in a Git repository.")
            return None

        str_file_paths = [str(p) for p in file_paths]
        return self.submit_background_task(
            callable_task=self._execute_refresh_file_git_status,
            args=(str_file_paths,),
            use_progress_bridge=False,
        )

    def _execute_refresh_file_git_status(self, file_paths_str: List[str]) -> Dict[str, str]:
        """Worker method to get file Git statuses."""
        if not self._is_git_repo or not self._git_root:
            raise GitError("Not in a Git repository.")

        statuses: Dict[str, str] = {}
        try:
            # git_manager.py does not have a get_files_status function.
            # Using subprocess directly. This should ideally be in git_manager.
            # `git status --porcelain <file1> <file2> ...`
            cmd = ["git", "status", "--porcelain"] + file_paths_str
            result = subprocess.run(
                cmd,
                cwd=self._git_root,
                capture_output=True,
                text=True,
                check=False,  # check=False to parse output
            )
            if result.returncode != 0 and result.stderr:
                # If specific files are not found by git status (e.g. if they are not tracked and not modified)
                # it might not be an error for the command itself, but stderr might contain info.
                # For simplicity, we'll rely on stdout. An empty stdout for a file means it's clean or untracked & clean.
                logger.warning(f"Git status command for specific files had issues: {result.stderr}")

            # Parse porcelain status
            # Example: " M path/to/file.py", "?? path/to/new_file.py"
            # Create a map of full path to its status string
            path_to_status = {}
            for line in result.stdout.strip().splitlines():
                if not line:
                    continue
                status_code = line[:2].strip()
                file_path_rel = line[3:]
                # git status --porcelain returns paths relative to repo root.
                # We need to map them back to the absolute paths provided in file_paths_str or ensure consistency.
                # For simplicity, assume file_paths_str are relative to git_root or absolute.
                # This part needs careful path handling.
                # For now, let's assume the paths match up or we store by relative path.
                # This is a simplification. Robust path matching is needed.
                abs_file_path = str(self._git_root / file_path_rel)  # type: ignore
                path_to_status[abs_file_path] = status_code

            for p_str in file_paths_str:
                # Ensure p_str is absolute for consistent lookup
                abs_p_str = str(Path(p_str).resolve())
                statuses[p_str] = path_to_status.get(
                    abs_p_str, "Clean"
                )  # Default to clean if not in output

        except subprocess.CalledProcessError as e:
            logger.error(f"Error getting Git status: {e.stderr}")
            raise GitError(f"Failed to get Git status: {e.stderr}") from e
        except FileNotFoundError:  # Git not found
            logger.error("Git command not found during status refresh.")
            raise GitError("Git command not found.")
        return statuses

    @pyqtSlot(str)
    @pyqtSlot()  # Allow calling without branch_name for auto-generated name
    def create_git_branch(self, branch_name: Optional[str] = None) -> Optional[str]:
        """
        Creates a new Git branch for fixes.
        Emits branch_created or branch_creation_failed.
        Returns task_id if submitted.
        """
        self.logger.info(f"Request to create Git branch (name: {branch_name or 'auto'}).")
        if not self._is_git_repo or not self._git_root:
            self.logger.warning("Cannot create branch, not in a Git repository.")
            self.branch_creation_failed.emit("", "Not in a Git repository.")
            return None

        return self.submit_background_task(
            callable_task=self._execute_create_git_branch,
            args=(branch_name,),
            use_progress_bridge=False,
        )

    def _execute_create_git_branch(self, branch_name: Optional[str]) -> Tuple[str, str]:
        """Worker method to create Git branch."""
        if not self._is_git_repo or not self._git_root:  # Should be caught by caller
            raise GitError("Not in a Git repository.")

        if not git_manager.is_working_tree_clean(str(self._git_root)):
            raise GitError(
                "Working tree is not clean. Please commit or stash changes before creating a new branch."
            )

        new_branch, original_branch = git_manager.create_branch_for_fixes(
            str(self._git_root), branch_name
        )
        # Update controller's knowledge of active branches
        self._active_fix_branch = new_branch
        self._original_branch_before_fix_branch = original_branch
        return new_branch, original_branch

    @pyqtSlot(float, str)  # record_timestamp, custom_message
    @pyqtSlot(float)  # record_timestamp, no custom_message
    def commit_applied_fix(
        self, record_timestamp: float, custom_message: Optional[str] = None
    ) -> Optional[str]:
        """
        Commits an applied fix from history.
        Emits commit_succeeded or commit_failed.
        Returns task_id if submitted.
        """
        self.logger.info(f"Request to commit fix record (timestamp: {record_timestamp}).")
        if not self._is_git_repo or not self._git_root:
            self.logger.warning("Cannot commit, not in a Git repository.")
            self.commit_failed.emit("", "Not in a Git repository.")
            return None

        record_to_commit = next(
            (r for r in self._change_history if r.timestamp == record_timestamp), None
        )
        if not record_to_commit:
            self.logger.error(f"No AppliedFixRecord found for timestamp {record_timestamp}.")
            self.commit_failed.emit("", f"No fix record found for timestamp {record_timestamp}.")
            return None

        if record_to_commit.git_commit_hash:
            self.logger.info(
                f"Fix record {record_timestamp} already committed (Hash: {record_to_commit.git_commit_hash})."
            )
            # Optionally, emit commit_succeeded again or a different signal for "already committed"
            self.commit_failed.emit(
                "", f"Fix record already committed (Hash: {record_to_commit.git_commit_hash})."
            )
            return None

        return self.submit_background_task(
            callable_task=self._execute_commit_applied_fix,
            args=(record_to_commit, custom_message),
            use_progress_bridge=False,
        )

    def _execute_commit_applied_fix(
        self, record: AppliedFixRecord, custom_message: Optional[str]
    ) -> Tuple[str, str, AppliedFixRecord]:
        """Worker method to commit an applied fix."""
        if not self._is_git_repo or not self._git_root:
            raise GitError("Not in a Git repository.")

        applied_files_paths_obj = record.application_result.get("applied_files", [])
        if not applied_files_paths_obj:
            raise GitError("No applied files in the record to commit.")

        applied_file_paths_str = [str(Path(p).resolve()) for p in applied_files_paths_obj]

        # Staging files
        # git_manager.py does not have a multi-file stage function. Using subprocess.
        # This should ideally be `git_manager.stage_files(str(self._git_root), applied_file_paths_str)`
        try:
            subprocess.run(
                ["git", "add"] + applied_file_paths_str,
                cwd=str(self._git_root),
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to stage files for commit: {e.stderr}")
            raise GitError(f"Failed to stage files: {e.stderr}") from e
        except FileNotFoundError:
            raise GitError("Git command not found during staging.")

        # Committing staged files
        # git_manager.py's commit_fix is per-file and has a fixed message format.
        # We need one commit for all files in the suggestion with a custom message.
        # This should ideally be `git_manager.commit_staged(str(self._git_root), commit_msg_to_use)`
        commit_msg_to_use = (
            custom_message
            or f"fix: Apply fix for {record.suggestion.failure.test_name} (suggestion {record.suggestion.id[:8] if record.suggestion.id else 'N/A'})"
        )

        try:
            subprocess.run(
                ["git", "commit", "-m", commit_msg_to_use],
                cwd=str(self._git_root),
                check=True,
                capture_output=True,
                text=True,
            )
            # Get commit hash
            hash_proc = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(self._git_root),
                check=True,
                capture_output=True,
                text=True,
            )
            commit_hash = hash_proc.stdout.strip()
        except subprocess.CalledProcessError as e:
            # Check if commit failed because nothing to commit (e.g., files were already staged and committed)
            # or other reasons.
            if "nothing to commit" in e.stdout.lower() or "nothing to commit" in e.stderr.lower():
                # This might happen if files were already committed. Try to get current HEAD as potential hash.
                logger.warning(
                    f"Commit attempt resulted in 'nothing to commit'. Files might have been committed already. Error: {e.stderr}"
                )
                try:
                    hash_proc = subprocess.run(
                        ["git", "rev-parse", "HEAD"],
                        cwd=str(self._git_root),
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    commit_hash = hash_proc.stdout.strip()  # Assume current HEAD is relevant
                except Exception as he:
                    raise GitError(f"Commit seemed empty, and failed to get HEAD hash: {he}")

            else:
                logger.error(f"Failed to commit changes: {e.stderr}")
                raise GitError(f"Failed to commit changes: {e.stderr}") from e
        except FileNotFoundError:
            raise GitError("Git command not found during commit.")

        return commit_hash, commit_msg_to_use, record

    # --- Existing methods modified/awareness of Git ---

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
                # If original_code not provided, read from disk or Git HEAD if available
                file_to_read = item.file_path.resolve()
                content: Optional[str] = None
                read_error: Optional[str] = None

                if self._is_git_repo and self._git_root:
                    try:
                        # Try to get content from Git HEAD first for tracked files
                        # This represents the last committed state.
                        # `git show HEAD:<path_relative_to_repo_root>`
                        relative_path = file_to_read.relative_to(self._git_root)
                        proc = subprocess.run(
                            ["git", "show", f"HEAD:{relative_path}"],
                            cwd=self._git_root,
                            capture_output=True,
                            text=True,
                            check=False,
                        )
                        if proc.returncode == 0:
                            content = proc.stdout
                        else:
                            # File might be new or not in HEAD, fallback to disk
                            logger.debug(
                                f"File {relative_path} not in HEAD, or git show failed. Fallback to disk. stderr: {proc.stderr}"
                            )
                            pass
                    except (ValueError, subprocess.CalledProcessError, FileNotFoundError) as e:
                        # ValueError if not relative, CalledProcessError if git command fails for other reasons
                        logger.warning(
                            f"Could not get {file_to_read} from Git HEAD, fallback to disk: {e}"
                        )
                        pass  # Fallback to reading from disk

                if content is None:  # Fallback or not a Git repo
                    try:
                        if file_to_read.exists() and file_to_read.is_file():
                            content = file_to_read.read_text(encoding="utf-8")
                        else:
                            # File doesn't exist on disk. Original content is empty.
                            # This is fine if the fix creates the file.
                            content = ""
                    except OSError as e:
                        read_error = f"Error reading original content for {file_to_read}: {e}"

                if read_error:
                    logger.error(read_error)
                    return {}, read_error

                originals[file_to_read] = content if content is not None else ""

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
            self.fix_application_failed.emit("", "TaskManager not available.")
            return None

        # Git pre-check: if in a Git repo and on a managed fix branch, ensure working tree is clean
        # This is a complex policy. For now, let's assume user manages this or GitFixApplier handles it.
        # If self._active_fix_branch and self._git_root and not git_manager.is_working_tree_clean(str(self._git_root)):
        #     msg = "Git working tree is not clean on the fix branch. Please commit or stash changes."
        #     self.logger.error(msg)
        #     self.fix_application_failed.emit("", msg)
        #     return None

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

        # Determine task type by inspecting result_data structure and callable name if available.
        task_callable_name = ""
        if self.task_manager:  # Check if task_manager is set
            # Accessing protected member _active_workers of TaskManager
            worker = self.task_manager._active_workers.get(task_id)
            if worker:
                task_callable_name = worker.callable_task.__name__

        is_likely_git_status_result = False
        # This heuristic is specifically for _execute_refresh_file_git_status when task_callable_name might be unavailable
        # or as a secondary check. Primary dispatch should be on task_callable_name.
        if task_callable_name == "_execute_refresh_file_git_status" and isinstance(
            result_data, dict
        ):
            if (
                not result_data
            ):  # Empty dict is a valid git status result (no changes for specified files)
                is_likely_git_status_result = True
            elif result_data:  # if dict is not empty
                first_val = next(iter(result_data.values()))
                # Common git status codes/markers
                if isinstance(first_val, str) and first_val.strip() in [
                    "M",
                    "A",
                    "D",
                    "R",
                    "C",
                    "U",
                    "??",
                    "!!",
                    "Clean",
                    "AM",
                    "MM",
                ]:
                    is_likely_git_status_result = True

        # Git: Check Git Status
        if (
            task_callable_name == "_execute_check_git_status"
            and isinstance(result_data, tuple)
            and len(result_data) == 3
            and isinstance(result_data[0], bool)
            and isinstance(result_data[1], str)
            and isinstance(result_data[2], str)
        ):
            is_repo, root_path_str, err_msg = result_data
            self.git_repo_status_checked.emit(is_repo, root_path_str, err_msg)
            if is_repo:
                self.logger.info(f"Git repository detected at {root_path_str}.")
            else:
                self.logger.info(f"Git check completed. Not a repo or error: {err_msg}")

        # Git: Refresh File Status
        elif (
            task_callable_name == "_execute_refresh_file_git_status" and is_likely_git_status_result
        ):
            self.logger.info(f"Git file status refresh task {task_id} completed.")
            self.git_status_updated.emit(task_id, result_data)  # result_data is Dict[str, str]

        # Git: Create Branch
        elif (
            task_callable_name == "_execute_create_git_branch"
            and isinstance(result_data, tuple)
            and len(result_data) == 2
            and isinstance(result_data[0], str)
            and isinstance(result_data[1], str)
        ):
            new_branch, orig_branch = result_data
            self.logger.info(
                f"Git branch creation task {task_id} completed. New: {new_branch}, Original: {orig_branch}."
            )
            self.branch_created.emit(task_id, new_branch, orig_branch)

        # Git: Commit Applied Fix
        elif (
            task_callable_name == "_execute_commit_applied_fix"
            and isinstance(result_data, tuple)
            and len(result_data) == 3
            and isinstance(result_data[2], AppliedFixRecord)
        ):
            commit_hash, commit_message, committed_record = result_data
            # Update the record in _change_history
            for i, r in enumerate(self._change_history):
                if r.timestamp == committed_record.timestamp:
                    self._change_history[i].git_commit_hash = commit_hash
                    break
            self.logger.info(f"Git commit task {task_id} succeeded. Hash: {commit_hash}.")
            self.commit_succeeded.emit(task_id, commit_hash, commit_message)
            self.change_history_updated.emit(self.get_change_history())

        # Case 1: Single fix application (_execute_apply_fix)
        elif task_callable_name == "_execute_apply_fix" and (
            isinstance(result_data, tuple)
            and len(result_data) == 3
            and isinstance(result_data[0], dict)
            and isinstance(result_data[1], FixSuggestion)
            and isinstance(result_data[2], dict)  # original_contents
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

                if self._is_git_repo and application_result.get("applied_files"):
                    applied_paths = [
                        str(Path(p).resolve()) for p in application_result["applied_files"]
                    ]
                    self.refresh_file_git_status(applied_paths)
            else:
                self.logger.error(
                    f"Fix application failed for {suggestion.failure.test_name}: {application_result.get('message')}"
                )
                self.fix_application_failed.emit(
                    task_id, application_result.get("message", "Unknown error")
                )

        # Case 2: Batch fix application (_execute_apply_multiple_fixes)
        elif task_callable_name == "_execute_apply_multiple_fixes" and (
            isinstance(result_data, tuple)
            and len(result_data) == 4
            and isinstance(result_data[3], list)  # applied_records
        ):
            succeeded_count, failed_count, errors, applied_records_data = (
                result_data  # Renamed to applied_records_data
            )
            newly_applied_paths = []
            for record_obj in applied_records_data:  # Iterate over AppliedFixRecord instances
                record_obj.task_id = task_id
                self._change_history.append(record_obj)
                if record_obj.application_result.get(
                    "success"
                ) and record_obj.application_result.get("applied_files"):
                    newly_applied_paths.extend(
                        [
                            str(Path(p).resolve())
                            for p in record_obj.application_result["applied_files"]
                        ]
                    )

            self.logger.info(
                f"Batch fix operation {task_id} completed. Succeeded: {succeeded_count}, Failed: {failed_count}."
            )
            if applied_records_data:
                self.change_history_updated.emit(self.get_change_history())
            self.batch_operation_completed.emit(task_id, succeeded_count, failed_count, errors)

            if self._is_git_repo and newly_applied_paths:
                self.refresh_file_git_status(list(set(newly_applied_paths)))

        # Case 3: Diff generation (_execute_show_diff - returns Dict[str, str])
        elif (
            task_callable_name == "_execute_show_diff"
            and isinstance(result_data, dict)
            and not is_likely_git_status_result
        ):  # Added check against git status
            diff_results = result_data
            self.logger.info(f"Diff generation task {task_id} completed.")
            self.diff_generated.emit(task_id, diff_results)

        # Case 4: Rollback (_execute_rollback)
        elif task_callable_name == "_execute_rollback" and (
            isinstance(result_data, tuple)
            and len(result_data) == 2
            and isinstance(result_data[0], dict)  # rollback_result
            and isinstance(result_data[1], AppliedFixRecord)  # rolled_back_record
        ):
            rollback_result, rolled_back_record = result_data
            reverted_paths = []
            if rollback_result.get("success"):
                original_history_len = len(self._change_history)
                self._change_history = [
                    r for r in self._change_history if r.timestamp != rolled_back_record.timestamp
                ]
                if len(self._change_history) < original_history_len:
                    self.logger.info(
                        f"Rollback for {rolled_back_record.suggestion.failure.test_name} successful. History updated."
                    )
                    self.fix_applied_successfully.emit(task_id, rollback_result)
                    self.change_history_updated.emit(self.get_change_history())
                    if rollback_result.get("applied_files"):  # Files reverted to original
                        reverted_paths.extend(
                            [str(Path(p).resolve()) for p in rollback_result["applied_files"]]
                        )
                else:
                    self.logger.error(
                        "Rollback successful but record not found in history or history state inconsistent."
                    )
                    self.fix_application_failed.emit(
                        task_id, "Rollback successful but record not found in history."
                    )
            else:
                self.logger.error(
                    f"Rollback failed for {rolled_back_record.suggestion.failure.test_name}: {rollback_result.get('message')}"
                )
                self.fix_application_failed.emit(
                    task_id, rollback_result.get("message", "Unknown error during rollback")
                )

            if self._is_git_repo and reverted_paths:
                self.refresh_file_git_status(list(set(reverted_paths)))

        else:  # Fallthrough for unhandled result types or mismatched task_callable_name
            self.logger.warning(
                f"Task {task_id} (callable: {task_callable_name}) completed in FixController with unhandled result type: {type(result_data)} or structure."
            )

    @pyqtSlot(str, str)
    def _handle_task_failure(self, task_id: str, error_message: str) -> None:
        """Handles failure of tasks initiated by FixController."""
        self.logger.error(f"Task {task_id} failed in FixController: {error_message}")

        task_callable_name = ""
        if self.task_manager:  # Check if task_manager is set
            # Accessing protected member _active_workers of TaskManager
            worker = self.task_manager._active_workers.get(task_id)
            if worker:
                task_callable_name = worker.callable_task.__name__

        if "_execute_check_git_status" in task_callable_name:
            self.git_repo_status_checked.emit(False, "", error_message)
        elif "_execute_refresh_file_git_status" in task_callable_name:
            self.git_status_update_failed.emit(task_id, error_message)
        elif "_execute_create_git_branch" in task_callable_name:
            self.branch_creation_failed.emit(task_id, error_message)
        elif "_execute_commit_applied_fix" in task_callable_name:
            self.commit_failed.emit(task_id, error_message)
        elif "_execute_show_diff" in task_callable_name:
            self.diff_generation_failed.emit(task_id, error_message)
        else:  # Default to fix application failure for other tasks
            self.fix_application_failed.emit(task_id, error_message)

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
