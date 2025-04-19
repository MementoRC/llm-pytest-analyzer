"""
Fix Applier - Safely applies suggested fixes to code.

This module provides functionality to:
1. Take a FixSuggestion with code changes
2. Create a temporary, isolated environment with project files
3. Apply and validate changes in the isolated environment first
4. Only when validation passes, apply changes to the original files with backup
5. Roll back if needed (as a redundant safety measure)

This implementation supports both:
- Safe Mode: Using a temporary environment to validate changes before modifying originals
- Direct Mode: Makes changes directly with backup/rollback for use in test environments
"""

import os
import sys
import shutil
import difflib
import logging
import tempfile
import subprocess
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

@dataclass
class FixApplicationResult:
    """Result of applying a fix suggestion."""
    success: bool
    message: str
    applied_files: List[Path] = field(default_factory=list)
    rolled_back_files: List[Path] = field(default_factory=list)

class FixApplier:
    """
    Applies suggested fixes safely to files with isolated environment validation.
    
    This class implements two modes:
    1. Safe Mode (default): 
       - Creates a temporary copy of the project structure
       - Applies changes to the temporary environment first
       - Runs tests in the isolated environment
       - Only if tests pass, applies changes to the original files
       
    2. Direct Mode (for tests):
       - Backs up original files
       - Applies changes directly
       - Validates
       - Rolls back if validation fails
    """
    
    def __init__(
        self, 
        project_root: Optional[Path] = None, 
        use_safe_mode: bool = True, 
        backup_suffix: str = ".bak",
        verbose_test_output: bool = False
    ):
        """
        Initialize the FixApplier.
        
        Args:
            project_root: Root directory of the project
            use_safe_mode: If True, uses temporary environment validation, otherwise direct
            backup_suffix: Suffix to use for backup files
            verbose_test_output: If True, shows verbose pytest output during validation
        """
        self.project_root = project_root or Path.cwd()
        self.use_safe_mode = use_safe_mode
        self.backup_suffix = backup_suffix
        self.verbose_test_output = verbose_test_output
        
    def apply_fix(
        self, 
        code_changes: Dict[str, str], 
        tests_to_validate: List[str],
        verbose_test_output: Optional[bool] = None
    ) -> FixApplicationResult:
        """
        Applies code changes safely with backup and validation.
        
        Args:
            code_changes: Dict mapping file paths to new content
            tests_to_validate: List of pytest node IDs to run for validation
            verbose_test_output: If True, shows verbose pytest output during validation.
                                 If None, uses the value set in __init__
            
        Returns:
            FixApplicationResult indicating success or failure
        """
        # Determine whether to use verbose test output
        use_verbose = self.verbose_test_output if verbose_test_output is None else verbose_test_output
        # Extract valid file paths from code changes
        target_files = []
        for path_str in code_changes.keys():
            # Skip metadata keys like 'source' or 'fingerprint'
            if not isinstance(path_str, str) or '/' not in path_str and '\\' not in path_str:
                continue
            target_files.append(Path(path_str))
        
        if not target_files:
            return FixApplicationResult(
                success=False,
                message="No valid file paths found in code changes",
                applied_files=[],
                rolled_back_files=[]
            )
        
        # Verify all target files exist
        for file_path in target_files:
            if not file_path.is_file():
                return FixApplicationResult(
                    success=False,
                    message=f"Target file not found: {file_path}",
                    applied_files=[],
                    rolled_back_files=[]
                )
        
        # Determine which mode to use (safe or direct)
        effective_use_safe_mode = self._should_use_safe_mode(target_files)
        
        # Use appropriate mode
        if effective_use_safe_mode:
            logger.info("Using safe mode with temporary environment validation")
            return self._apply_fix_safe(code_changes, tests_to_validate, target_files, use_verbose)
        else:
            logger.info("Using direct mode with backup/rollback")
            return self._apply_fix_direct(code_changes, tests_to_validate, target_files, use_verbose)
    
    def _should_use_safe_mode(self, target_files: List[Path]) -> bool:
        """
        Determine whether to use safe mode or direct mode.
        
        Auto-detects based on environment and target paths if use_safe_mode was not
        explicitly specified in __init__.
        
        Args:
            target_files: List of files to be modified
            
        Returns:
            True if safe mode should be used, False for direct mode
        """
        # If use_safe_mode was explicitly set in __init__, respect that
        if isinstance(self.use_safe_mode, bool):
            return self.use_safe_mode
            
        # Otherwise, auto-detect
        # Use direct mode for test environments or test paths
        if self._is_test_environment() or self._has_test_paths(target_files):
            logger.info("Auto-detected test environment - using direct mode")
            return False
        
        # Default to safe mode for production use
        logger.info("Using default safe mode in production environment")
        return True
                    
    def _apply_fix_safe(
        self, 
        code_changes: Dict[str, str], 
        tests_to_validate: List[str],
        target_files: List[Path],
        verbose: bool = False
    ) -> FixApplicationResult:
        """
        Applies changes safely using temporary environment validation.
        
        Args:
            code_changes: Dict mapping file paths to new content
            tests_to_validate: List of tests to run for validation
            target_files: List of target file paths extracted from code_changes
            verbose: If True, show verbose test output during validation
            
        Returns:
            FixApplicationResult indicating success or failure
        """
        applied_files: List[Path] = []
        backup_paths: Dict[Path, Path] = {}
        
        # Create a temporary environment for testing
        temp_dir = None
        try:
            # Create temporary directory for isolated testing
            temp_dir = tempfile.mkdtemp(prefix="pytest_analyzer_fix_")
            temp_root = Path(temp_dir)
            logger.info(f"Created temporary environment at: {temp_dir}")
            
            # Copy necessary structure
            temp_project = temp_root / "project"
            temp_project.mkdir(parents=True, exist_ok=True)
            
            # Copy source files and configuration
            self._copy_project_to_temp(temp_project)
            
            # Apply changes to temporary environment
            temp_files_changed = []
            for file_path_str, new_content in code_changes.items():
                # Skip metadata keys
                if not isinstance(file_path_str, str) or '/' not in file_path_str and '\\' not in file_path_str:
                    continue
                
                # Calculate the temporary path
                original_path = Path(file_path_str)
                temp_path = temp_project / original_path.relative_to(self.project_root)
                temp_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Apply change to temporary file
                temp_path.write_text(new_content, encoding='utf-8')
                temp_files_changed.append(temp_path)
                logger.info(f"Applied change to temporary file: {temp_path}")
            
            # Validate in temporary environment
            if tests_to_validate:
                validation_passed = self._run_validation_tests_in_temp_env(
                    temp_project, 
                    tests_to_validate,
                    verbose=verbose
                )
                
                if not validation_passed:
                    logger.warning("Validation failed in temporary environment. Original files untouched.")
                    return FixApplicationResult(
                        success=False,
                        message="Validation failed in temporary environment. Original files untouched.",
                        applied_files=[],
                        rolled_back_files=[]
                    )
                    
                logger.info("Validation passed in temporary environment. Applying to original files.")
            else:
                logger.warning("No tests provided for validation. Skipping validation.")
            
            # Apply changes to original files (with backup for additional safety)
            try:
                # 1. Create backups for all existing files
                for file_path in target_files:
                    if file_path.exists():
                        backup_path = file_path.with_suffix(file_path.suffix + self.backup_suffix)
                        shutil.copy2(file_path, backup_path)  # Preserves metadata
                        backup_paths[file_path] = backup_path
                        logger.info(f"Backed up '{file_path}' to '{backup_path}'")
                
                # 2. Apply changes to original files
                for file_path_str, new_content in code_changes.items():
                    # Skip metadata keys
                    if not isinstance(file_path_str, str) or '/' not in file_path_str and '\\' not in file_path_str:
                        continue
                    
                    file_path = Path(file_path_str)
                    orig_path = self.project_root / file_path.relative_to(self.project_root)
                    orig_path.parent.mkdir(parents=True, exist_ok=True)
                    orig_path.write_text(new_content, encoding='utf-8')
                    applied_files.append(orig_path)
                    logger.info(f"Applied change to original file: '{orig_path}'")
                
                # Success
                return FixApplicationResult(
                    success=True,
                    message=f"Fix applied and validated successfully for {len(applied_files)} file(s)",
                    applied_files=applied_files,
                    rolled_back_files=[]
                )
                
            except Exception as e:
                # If anything fails while applying to originals, roll back
                logger.error(f"Error applying changes to original files: {e}")
                if backup_paths:
                    self._rollback_changes(applied_files, backup_paths)
                    return FixApplicationResult(
                        success=False,
                        message=f"Error applying changes to original files after validation: {e}",
                        applied_files=[],
                        rolled_back_files=applied_files
                    )
                else:
                    return FixApplicationResult(
                        success=False,
                        message=f"Error creating backups before applying changes: {e}",
                        applied_files=[],
                        rolled_back_files=[]
                    )
                
        except Exception as e:
            error_message = f"Unexpected error during safe apply: {e}"
            logger.exception(error_message)
            
            # Roll back any files that were already modified
            if applied_files and backup_paths:
                self._rollback_changes(applied_files, backup_paths)
            
            return FixApplicationResult(
                success=False,
                message=error_message,
                applied_files=[],
                rolled_back_files=applied_files if backup_paths else []
            )
        finally:
            # Clean up the temporary directory
            if temp_dir and os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    logger.info(f"Cleaned up temporary environment: {temp_dir}")
                except Exception as e:
                    logger.warning(f"Failed to clean up temporary directory {temp_dir}: {e}")
                    
    def _apply_fix_direct(
        self, 
        code_changes: Dict[str, str], 
        tests_to_validate: List[str],
        target_files: List[Path],
        verbose: bool = False
    ) -> FixApplicationResult:
        """
        Applies changes directly with backup and rollback.
        
        Args:
            code_changes: Dict mapping file paths to new content
            tests_to_validate: List of tests to run for validation
            target_files: List of target file paths extracted from code_changes
            verbose: If True, show verbose test output during validation
            
        Returns:
            FixApplicationResult indicating success or failure
        """
        applied_files: List[Path] = []
        backup_paths: Dict[Path, Path] = {}
        
        # Create backup directory
        backup_dir = None
        try:
            # 1. Create backup directory for all files
            backup_dir = Path(tempfile.mkdtemp(prefix="pytest_analyzer_backup_"))
            logger.info(f"Created backup directory at: {backup_dir}")
            
            # 2. Create backups of all files
            for file_path in target_files:
                if file_path.exists():
                    # Create a backup with the original name in backup_dir
                    rel_path = file_path.relative_to(self.project_root)
                    backup_path = backup_dir / rel_path
                    backup_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(file_path, backup_path)  # Preserves metadata
                    backup_paths[file_path] = backup_path
                    logger.info(f"Backed up '{file_path}' to '{backup_path}'")
            
            # 3. Apply the changes directly
            for file_path_str, new_content in code_changes.items():
                # Skip metadata keys
                if not isinstance(file_path_str, str) or '/' not in file_path_str and '\\' not in file_path_str:
                    continue
                
                file_path = Path(file_path_str)
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(new_content, encoding='utf-8')
                applied_files.append(file_path)
                logger.info(f"Applied change directly to '{file_path}'")
            
            # 4. Validate by running tests
            validation_passed = True
            if tests_to_validate:
                validation_passed = self._run_validation_tests(
                    tests_to_validate,
                    verbose=verbose
                )
            
            # 5. Handle validation result
            if validation_passed:
                logger.info(f"Validation successful for {len(applied_files)} files")
                return FixApplicationResult(
                    success=True,
                    message=f"Fix applied and validated successfully for {len(applied_files)} file(s)",
                    applied_files=applied_files,
                    rolled_back_files=[]
                )
            else:
                error_message = f"Validation failed for tests: {tests_to_validate}. Rolling back changes."
                logger.warning(error_message)
                
                # Rollback the changes
                rolled_back = self._rollback_changes(applied_files, backup_paths)
                
                return FixApplicationResult(
                    success=False,
                    message=error_message,
                    applied_files=[],
                    rolled_back_files=rolled_back
                )
                
        except Exception as e:
            error_message = f"Unexpected error during direct apply: {e}"
            logger.exception(error_message)
            
            # Roll back any files that were already modified
            rolled_back = []
            if applied_files and backup_paths:
                rolled_back = self._rollback_changes(applied_files, backup_paths)
            
            return FixApplicationResult(
                success=False,
                message=error_message,
                applied_files=[],
                rolled_back_files=rolled_back
            )
        finally:
            # Clean up the backup directory
            if backup_dir and backup_dir.exists():
                try:
                    shutil.rmtree(backup_dir, ignore_errors=True)
                    logger.info(f"Cleaned up backup directory: {backup_dir}")
                except Exception as e:
                    logger.warning(f"Failed to clean up backup directory {backup_dir}: {e}")

    def _copy_project_to_temp(self, temp_dir: Path) -> None:
        """
        Copy project structure to temporary directory.
        
        Args:
            temp_dir: Destination temporary directory
        """
        # Copy common directories (src, tests, etc.)
        for common_dir in ['src', 'tests']:
            src_dir = self.project_root / common_dir
            if src_dir.exists() and src_dir.is_dir():
                dest_dir = temp_dir / common_dir
                logger.info(f"Copying directory: {src_dir} -> {dest_dir}")
                shutil.copytree(
                    src_dir, 
                    dest_dir,
                    symlinks=False,
                    ignore=shutil.ignore_patterns(
                        '.git', '__pycache__', '*.pyc', '.venv', 
                        'build', 'dist', '*.egg-info'
                    )
                )
        
        # Copy configuration files
        for config_file in ['pyproject.toml', 'pytest.ini', 'setup.py', 'setup.cfg']:
            config_path = self.project_root / config_file
            if config_path.exists():
                dest_path = temp_dir / config_file
                shutil.copy2(config_path, dest_path)
                logger.info(f"Copied config file: {config_path} -> {dest_path}")
    
    def _is_test_environment(self) -> bool:
        """
        Determine if we're running in a test environment.
        
        Returns:
            True if we're running in a test environment, False otherwise
        """
        # Check if we're running in pytest
        return 'pytest' in sys.modules or 'PYTEST_CURRENT_TEST' in os.environ
        
    def _has_test_paths(self, paths: List[Path]) -> bool:
        """
        Check if any of the paths are in a pytest temporary directory.
        
        Args:
            paths: List of paths to check
            
        Returns:
            True if any path is in a pytest temporary directory, False otherwise
        """
        for path in paths:
            try:
                path_str = str(path.resolve())
                # Check for common pytest temp dir patterns
                if ('pytest-of-' in path_str or
                    'pytest_' in path_str or 
                    '/tmp/' in path_str or
                    tempfile.gettempdir() in path_str):
                    return True
            except Exception:
                # If path resolution fails, continue to the next path
                continue
        return False
    
    def _run_validation_tests_in_temp_env(self, temp_dir: Path, tests_to_run: List[str], verbose: bool = False) -> bool:
        """
        Run pytest tests in the temporary environment to validate changes.
        
        Args:
            temp_dir: Path to temporary directory
            tests_to_run: List of pytest node IDs to run
            verbose: If True, run pytest in verbose mode
            
        Returns:
            True if all tests passed, False otherwise
        """
        if not tests_to_run:
            logger.warning("No tests provided for validation. Skipping validation.")
            return True  # No tests to run means no failures
        
        logger.info(f"Running validation tests in temporary environment: {tests_to_run}")
        
        # Use the same Python interpreter
        command = [
            sys.executable,  # Use the same Python interpreter
            "-m", "pytest",
        ]
        
        # Add verbosity flag only if requested
        if verbose:
            command.append("-v")
        else:
            # Only show summary and failures
            # Super quiet mode - only shows failures
            command.append("-qq")
            # Shorter tracebacks for failures
            command.append("--tb=short")
            # Disable warnings for cleaner output
            command.append("--disable-warnings")
            
        # Add test IDs
        command.extend(tests_to_run)
        
        try:
            logger.debug(f"Running command in {temp_dir}: {' '.join(command)}")
            result = subprocess.run(
                command,
                cwd=temp_dir,  # Critical: run from the temporary directory
                capture_output=True,
                text=True,
                check=False,  # Don't raise on non-zero exit
                timeout=60  # 1 minute timeout
            )
            
            # Log output for debugging
            if result.stdout:
                logger.debug(f"Pytest stdout:\n{result.stdout}")
            if result.stderr:
                logger.debug(f"Pytest stderr:\n{result.stderr}")
            
            if result.returncode == 0:
                logger.info("Validation successful: All tests passed in temporary environment")
                return True
            else:
                logger.warning(f"Validation failed: Tests returned code {result.returncode} in temporary environment")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("Validation timed out in temporary environment")
            return False
            
        except Exception as e:
            logger.error(f"Error running validation tests in temporary environment: {e}")
            return False
    
    def _run_validation_tests(self, tests_to_run: List[str], verbose: bool = False) -> bool:
        """
        Run pytest tests directly on the modified files.
        
        Args:
            tests_to_run: List of pytest node IDs to run
            verbose: If True, run pytest in verbose mode
            
        Returns:
            True if all tests passed, False otherwise
        """
        if not tests_to_run:
            logger.warning("No tests provided for validation. Skipping validation.")
            return True  # No tests to run means no failures
        
        logger.info(f"Running validation tests: {tests_to_run}")
        
        # Base command with Python interpreter
        command = [
            sys.executable,  # Use same interpreter 
            "-m", "pytest",
        ]
        
        # Add verbosity flag only if requested
        if verbose:
            command.append("-v")
        else:
            # Only show summary and failures
            # Super quiet mode - only shows failures
            command.append("-qq")
            # Shorter tracebacks for failures
            command.append("--tb=short")
            # Disable warnings for cleaner output
            command.append("--disable-warnings")
            
        # Add test IDs
        command.extend(tests_to_run)
        
        try:
            result = subprocess.run(
                command,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                check=False,  # Don't raise on non-zero exit
                timeout=60  # 1 minute timeout
            )
            
            # Log output
            if result.stdout:
                logger.debug(f"Pytest stdout:\n{result.stdout}")
            if result.stderr:
                logger.debug(f"Pytest stderr:\n{result.stderr}")
            
            if result.returncode == 0:
                logger.info("Validation successful: All tests passed")
                return True
            else:
                logger.warning(f"Validation failed: Tests returned code {result.returncode}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("Validation timed out")
            return False
            
        except Exception as e:
            logger.error(f"Error running validation tests: {e}")
            return False
    
    def _rollback_changes(self, files_to_restore: List[Path], backup_paths: Dict[Path, Path]) -> List[Path]:
        """
        Restore files from backups after a failed application.
        
        Args:
            files_to_restore: Files to restore from backup
            backup_paths: Mapping of original files to backup files
            
        Returns:
            List of files that were successfully rolled back
        """
        logger.warning(f"Rolling back changes to {len(files_to_restore)} file(s)")
        
        rolled_back_files = []
        
        for file_path in files_to_restore:
            backup_path = backup_paths.get(file_path)
            if backup_path and backup_path.exists():
                try:
                    shutil.copy2(backup_path, file_path)  # Use copy2 for metadata preservation
                    rolled_back_files.append(file_path)
                    logger.info(f"Rolled back '{file_path}' from '{backup_path}'")
                except Exception as e:
                    logger.error(f"Failed to roll back '{file_path}' from '{backup_path}': {e}")
                    logger.error(f"Manual recovery needed: copy '{backup_path}' to '{file_path}'")
            elif backup_path:
                logger.error(f"Backup file '{backup_path}' not found for '{file_path}'. Cannot roll back.")
            else:
                logger.error(f"No backup path recorded for '{file_path}'. Cannot roll back.")
        
        return rolled_back_files
                
    def show_diff(self, file_path: Path, new_content: str) -> str:
        """
        Generate a diff between original and new file content.
        
        Args:
            file_path: Path to the original file
            new_content: New content to compare against
            
        Returns:
            Unified diff as a string
        """
        if not file_path.exists():
            return f"File {file_path} does not exist. Cannot generate diff."
            
        try:
            original_content = file_path.read_text(encoding='utf-8')
            
            diff = difflib.unified_diff(
                original_content.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile=f"a/{file_path.name}",
                tofile=f"b/{file_path.name}",
                lineterm='\n'
            )
            
            diff_text = ''.join(diff)
            if not diff_text:
                return f"No changes detected for {file_path}"
                
            return diff_text
            
        except Exception as e:
            return f"Error generating diff for {file_path}: {e}"