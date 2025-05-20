"""
Fix Applier Adapter - Adapter between FixApplier and Applier protocol.

This module provides an adapter that implements the Applier protocol defined in
the core protocols using the concrete FixApplier implementation. This adapter
bridges the implementation details of FixApplier with the standardized Applier
protocol interface.

The adapter follows the adapter pattern to:
1. Implement the Applier protocol interface
2. Delegate work to the internal FixApplier
3. Convert between the protocol's API expectations and the concrete class's implementation
4. Handle proper error propagation according to the protocol's contracts
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pytest_analyzer.core.analysis.fix_applier import FixApplicationResult, FixApplier
from pytest_analyzer.core.errors import FixApplicationError
from pytest_analyzer.core.models.pytest_failure import FixSuggestion
from pytest_analyzer.core.protocols import Applier

logger = logging.getLogger(__name__)


class FixApplierAdapter(Applier):
    """
    Implements the Applier protocol by adapting the FixApplier class.

    This adapter wraps the concrete FixApplier class to conform to the
    Applier protocol interface. It handles:
    - Protocol method signatures
    - Parameter conversion
    - Result transformation
    - Error handling according to protocol specifications
    """

    def __init__(
        self,
        fix_applier: Optional[FixApplier] = None,
        project_root: Optional[Path] = None,
        use_safe_mode: bool = True,
        verbose_test_output: bool = False,
    ):
        """
        Initialize the adapter with an optional existing FixApplier or settings.

        Args:
            fix_applier: Optional existing FixApplier instance to use
            project_root: Root directory of the project (used if creating FixApplier)
            use_safe_mode: If True, uses temporary environment validation (used if creating FixApplier)
            verbose_test_output: If True, enables verbose test output during validation (used if creating FixApplier)
        """
        self._fix_applier = fix_applier or FixApplier(
            project_root=project_root,
            use_safe_mode=use_safe_mode,
            verbose_test_output=verbose_test_output,
        )

    def apply(
        self, changes: Dict[str, str], validation_tests: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Apply code changes to fix test failures.

        Args:
            changes: Dictionary mapping file paths to new content
            validation_tests: Optional list of tests to run for validation

        Returns:
            Results of the application including success status

        Raises:
            FixApplicationError: If application fails
        """
        try:
            # Clean validation_tests
            cleaned_tests = []
            if validation_tests:
                cleaned_tests = [test for test in validation_tests if test]

            # Call the internal FixApplier
            result: FixApplicationResult = self._fix_applier.apply_fix(
                code_changes=changes,
                tests_to_validate=cleaned_tests,
            )

            # Convert result to protocol-expected dictionary
            applied_files = [str(path) for path in result.applied_files]
            rolled_back_files = [str(path) for path in result.rolled_back_files]

            return {
                "success": result.success,
                "message": result.message,
                "applied_files": applied_files,
                "rolled_back_files": rolled_back_files,
            }

        except Exception as e:
            error_message = f"Error applying fixes: {str(e)}"
            logger.error(error_message)
            raise FixApplicationError(error_message) from e

    def apply_fix_suggestion(self, suggestion: FixSuggestion) -> Dict[str, Any]:
        """
        Apply a specific fix suggestion.

        Args:
            suggestion: The fix suggestion to apply

        Returns:
            Results of the application including success status

        Raises:
            FixApplicationError: If application fails
        """
        try:
            # Check if suggestion has code changes
            if not suggestion.code_changes:
                return {
                    "success": False,
                    "message": "Cannot apply fix: No code changes provided in suggestion.",
                    "applied_files": [],
                    "rolled_back_files": [],
                }

            # Filter code_changes to include only file paths (not metadata)
            code_changes_to_apply = {}
            for key, value in suggestion.code_changes.items():
                # Skip metadata keys like 'source' and 'fingerprint'
                if not isinstance(key, str) or ("/" not in key and "\\" not in key):
                    continue
                # Skip empty values
                if not value:
                    continue
                # Include valid file paths with content
                code_changes_to_apply[key] = value

            if not code_changes_to_apply:
                return {
                    "success": False,
                    "message": "Cannot apply fix: No valid file changes found in suggestion.",
                    "applied_files": [],
                    "rolled_back_files": [],
                }

            # Determine which tests to run for validation
            tests_to_validate = []
            if hasattr(suggestion, "validation_tests") and suggestion.validation_tests:
                tests_to_validate = suggestion.validation_tests
            elif (
                hasattr(suggestion.failure, "test_name")
                and suggestion.failure.test_name
            ):
                # Use the original failing test for validation
                tests_to_validate = [suggestion.failure.test_name]

            # Apply the fix
            return self.apply(code_changes_to_apply, tests_to_validate)

        except Exception as e:
            error_message = f"Error applying fix suggestion: {str(e)}"
            logger.error(error_message)
            raise FixApplicationError(error_message) from e

    def show_diff(self, file_path: Union[str, Path], new_content: str) -> str:
        """
        Generate a diff between original and new file content.

        Args:
            file_path: Path to the original file (str or Path)
            new_content: New content to compare against

        Returns:
            Unified diff as a string
        """
        path = Path(file_path) if isinstance(file_path, str) else file_path
        return self._fix_applier.show_diff(path, new_content)
