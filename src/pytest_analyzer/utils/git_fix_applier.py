"""
Git-based fix applier implementation.

This module provides a Git-based implementation of the fix applier that uses
Git operations for managing changes instead of custom backup files.
"""

import os
import subprocess
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from .git_manager import (
    get_git_root,
    create_branch_for_fixes,
    is_working_tree_clean,
    commit_fix,
    reset_file,
    GitError
)

logger = logging.getLogger(__name__)

class GitFixApplier:
    """Applies fixes to files using Git for version control."""
    
    def __init__(self, project_root: Path, verbose_test_output: bool = False):
        """
        Initialize the Git-based fix applier.
        
        :param project_root: Root directory of the project
        :param verbose_test_output: Whether to show verbose output during test validation
        """
        self.project_root = project_root
        self.verbose_test_output = verbose_test_output
        self.git_root = get_git_root(str(project_root))
        self.current_branch = None
        self.original_branch = None
    
    def apply_fix(self, code_changes: Dict[str, str], tests_to_validate: List[str], verbose_test_output: Optional[bool] = None) -> Any:
        """
        Apply code changes to files using Git.
        
        :param code_changes: Dictionary mapping file paths to their new content
        :param tests_to_validate: Tests to run to validate the changes
        :param verbose_test_output: Override for verbose test output setting
        :return: Result object indicating success or failure
        """
        from ..core.analysis.fix_applier import FixApplicationResult
        
        if not self.git_root:
            return FixApplicationResult(
                success=False,
                message="Git root not found. Cannot apply fixes using Git.",
                applied_files=[],
                rolled_back_files=[]
            )
        
        verbose = self.verbose_test_output if verbose_test_output is None else verbose_test_output
        
        # Check if working tree is clean
        if not is_working_tree_clean(self.git_root):
            return FixApplicationResult(
                success=False,
                message="Git working tree is not clean. Please commit or stash changes before applying fixes.",
                applied_files=[],
                rolled_back_files=[]
            )
        
        try:
            # Create a branch for our fixes if we haven't already
            if not self.current_branch:
                self.current_branch, self.original_branch = create_branch_for_fixes(self.git_root)
                logger.info(f"Created branch '{self.current_branch}' for applying fixes")
            
            applied_files = []
            rolled_back_files = []
            
            # Apply changes to each file
            for file_path, new_content in code_changes.items():
                # Skip metadata keys
                if not isinstance(file_path, str) or ('/' not in file_path and '\\' not in file_path):
                    continue
                
                # Skip empty values
                if not new_content:
                    continue
                
                file_path = os.path.abspath(file_path)
                try:
                    # Write the new content to the file
                    with open(file_path, 'w') as f:
                        f.write(new_content)
                    
                    applied_files.append(Path(file_path))
                    logger.info(f"Applied changes to {file_path}")
                    
                except Exception as e:
                    logger.error(f"Error writing to {file_path}: {e}")
                    # Roll back any changes made so far
                    for applied_file in applied_files:
                        try:
                            reset_file(self.git_root, str(applied_file))
                            rolled_back_files.append(applied_file)
                        except Exception as reset_error:
                            logger.error(f"Error rolling back changes to {applied_file}: {reset_error}")
                    
                    return FixApplicationResult(
                        success=False,
                        message=f"Error applying fix to {file_path}: {e}",
                        applied_files=[],
                        rolled_back_files=rolled_back_files
                    )
            
            # Run tests to validate the changes
            if tests_to_validate:
                if not self._validate_changes(tests_to_validate, verbose=verbose):
                    # Tests failed, roll back changes
                    for applied_file in applied_files:
                        reset_file(self.git_root, str(applied_file))
                        rolled_back_files.append(applied_file)
                    
                    return FixApplicationResult(
                        success=False,
                        message="Tests failed after applying fixes. Changes were rolled back.",
                        applied_files=[],
                        rolled_back_files=rolled_back_files
                    )
            
            # Commit the changes
            for applied_file in applied_files:
                commit_fix(
                    self.git_root,
                    str(applied_file),
                    f"Test fix for {applied_file.name}"
                )
            
            return FixApplicationResult(
                success=True,
                message=f"Successfully applied and committed fixes to {len(applied_files)} files on branch '{self.current_branch}'",
                applied_files=applied_files,
                rolled_back_files=[]
            )
            
        except GitError as e:
            # Roll back any changes made so far
            for applied_file in applied_files:
                try:
                    reset_file(self.git_root, str(applied_file))
                    rolled_back_files.append(applied_file)
                except Exception as reset_error:
                    logger.error(f"Error rolling back changes to {applied_file}: {reset_error}")
            
            return FixApplicationResult(
                success=False,
                message=f"Git error: {e}",
                applied_files=[],
                rolled_back_files=rolled_back_files
            )
    
    def _validate_changes(self, tests: List[str], verbose: bool = False) -> bool:
        """
        Run tests to validate applied changes.
        
        :param tests: List of tests to run
        :param verbose: Whether to show verbose output
        :return: True if tests pass, False otherwise
        """
        try:
            import pytest
            
            # Build pytest arguments
            args = []
            if not verbose:
                args.append("-q")  # Quiet mode
            
            args.extend(tests)
            
            # Run pytest
            logger.info(f"Validating changes with tests: {tests}")
            result = pytest.main(args)
            
            # pytest.ExitCode.OK == 0
            return result == 0
            
        except ImportError:
            logger.warning("Failed to import pytest. Cannot validate changes.")
            return True  # Assume changes are valid if we can't run tests
        except Exception as e:
            logger.error(f"Error validating changes: {e}")
            return False  # Assume changes are invalid if tests fail