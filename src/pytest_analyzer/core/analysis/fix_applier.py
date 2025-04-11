"""
Fix Applier - Safely applies suggested fixes to code.

This module provides functionality to:
1. Take a FixSuggestion with code changes
2. Safely apply those changes to the target files
3. Validate the changes work (tests pass)
4. Roll back if needed
"""

import os
import sys
import shutil
import difflib
import logging
import time
import subprocess
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union, Tuple

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
    Applies suggested fixes safely to files with proper backup and validation.
    
    This class handles the safe application of code changes, including:
    - Backing up original files
    - Applying changes
    - Validating the changes work (tests pass)
    - Rolling back if validation fails
    """
    
    def __init__(self, project_root: Optional[Path] = None, backup_suffix: str = ".bak"):
        """
        Initialize the FixApplier.
        
        Args:
            project_root: Root directory of the project
            backup_suffix: Suffix to use for backup files
        """
        self.project_root = project_root or Path.cwd()
        self.backup_suffix = backup_suffix
        
    def apply_fix(self, code_changes: Dict[str, str], tests_to_validate: List[str]) -> FixApplicationResult:
        """
        Applies code changes, validates with tests, and rolls back on failure.
        
        Args:
            code_changes: Dict mapping file paths (str) to new content (str)
            tests_to_validate: List of pytest node IDs to run for validation
            
        Returns:
            FixApplicationResult indicating success or failure
        """
        applied_files: List[Path] = []
        rolled_back_files: List[Path] = []
        backup_paths: Dict[Path, Path] = {}
        error_message: Optional[str] = None
        
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
        
        try:
            # 1. Create backups of all files
            for file_path in target_files:
                if not file_path.is_file():
                    raise FileNotFoundError(f"Target file not found: {file_path}")
                
                backup_path = file_path.with_suffix(file_path.suffix + self.backup_suffix)
                shutil.copy2(file_path, backup_path)  # Preserves metadata
                backup_paths[file_path] = backup_path
                logger.info(f"Backed up '{file_path}' to '{backup_path}'")
            
            # 2. Apply the changes
            for file_path_str, new_content in code_changes.items():
                # Skip metadata keys
                if not isinstance(file_path_str, str) or '/' not in file_path_str and '\\' not in file_path_str:
                    continue
                
                file_path = Path(file_path_str)
                file_path.write_text(new_content, encoding='utf-8')
                applied_files.append(file_path)
                logger.info(f"Applied changes to '{file_path}'")
            
            # 3. Validate by running tests
            validation_passed = self._run_validation_tests(tests_to_validate)
            
            # 4. Handle validation result
            if validation_passed:
                return FixApplicationResult(
                    success=True,
                    message=f"Fix applied and validated successfully for {len(applied_files)} file(s)",
                    applied_files=applied_files,
                    rolled_back_files=[]
                )
            else:
                error_message = f"Validation failed for tests: {tests_to_validate}. Rolling back changes."
                logger.warning(error_message)
                self._rollback(applied_files, backup_paths)
                return FixApplicationResult(
                    success=False,
                    message=error_message,
                    applied_files=[],
                    rolled_back_files=applied_files
                )
                
        except FileNotFoundError as e:
            error_message = str(e)
            logger.error(error_message)
            # Roll back any files that were already modified
            self._rollback([p for p in applied_files if p in backup_paths], backup_paths)
            return FixApplicationResult(
                success=False,
                message=error_message,
                applied_files=[],
                rolled_back_files=[p for p in applied_files if p in backup_paths]
            )
            
        except Exception as e:
            error_message = f"Unexpected error during fix application: {e}"
            logger.exception(error_message)
            # Roll back any files that were already modified
            self._rollback([p for p in applied_files if p in backup_paths], backup_paths)
            return FixApplicationResult(
                success=False,
                message=error_message,
                applied_files=[],
                rolled_back_files=[p for p in applied_files if p in backup_paths]
            )
    
    def _run_validation_tests(self, tests_to_run: List[str]) -> bool:
        """
        Run pytest tests to validate applied changes.
        
        Args:
            tests_to_run: List of pytest node IDs to run
            
        Returns:
            True if all tests passed, False otherwise
        """
        if not tests_to_run:
            logger.warning("No tests provided for validation. Skipping validation.")
            return True  # No tests to run means no failures
        
        logger.info(f"Running validation tests: {tests_to_run}")
        command = ["pytest", "-v"] + tests_to_run
        
        try:
            result = subprocess.run(
                command,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                check=False,  # Don't raise on non-zero exit
                timeout=60  # 1 minute timeout
            )
            
            if result.returncode == 0:
                logger.info("Validation successful: All tests passed")
                return True
            else:
                logger.warning(f"Validation failed: Tests returned code {result.returncode}")
                logger.debug(f"Test stdout:\n{result.stdout}")
                logger.debug(f"Test stderr:\n{result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("Validation timed out")
            return False
            
        except Exception as e:
            logger.error(f"Error running validation tests: {e}")
            return False
    
    def _rollback(self, files_to_restore: List[Path], backup_paths: Dict[Path, Path]) -> None:
        """
        Restore files from backups after a failed application.
        
        Args:
            files_to_restore: Files to restore from backup
            backup_paths: Mapping of original files to backup files
        """
        logger.warning(f"Rolling back changes to {len(files_to_restore)} file(s)")
        
        for file_path in files_to_restore:
            backup_path = backup_paths.get(file_path)
            if backup_path and backup_path.exists():
                try:
                    shutil.copy2(backup_path, file_path)  # Use copy2 for metadata preservation
                    logger.info(f"Rolled back '{file_path}' from '{backup_path}'")
                except Exception as e:
                    logger.error(f"Failed to roll back '{file_path}' from '{backup_path}': {e}")
                    logger.error(f"Manual recovery needed: copy '{backup_path}' to '{file_path}'")
            elif backup_path:
                logger.error(f"Backup file '{backup_path}' not found for '{file_path}'. Cannot roll back.")
            else:
                logger.error(f"No backup path recorded for '{file_path}'. Cannot roll back.")
                
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