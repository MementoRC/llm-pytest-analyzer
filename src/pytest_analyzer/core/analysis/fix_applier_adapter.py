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
from typing import Dict, List, Optional, Union

from pytest_analyzer.core.analysis.fix_applier import FixApplicationResult, FixApplier
from pytest_analyzer.core.errors import FixApplicationError
from pytest_analyzer.core.interfaces.protocols import Applier
from pytest_analyzer.core.models.pytest_failure import FixSuggestion

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
        self, code_changes: Dict[str, str], tests_to_validate: List[str]
    ) -> FixApplicationResult:
        """
        Apply code changes to fix test failures.

        Args:
            code_changes: Dictionary mapping file paths to new content
            tests_to_validate: List of tests to run for validation

        Returns:
            Results of the application including success status

        Raises:
            FixApplicationError: If application fails
        """
        try:
            # Clean tests_to_validate
            cleaned_tests = []
            if tests_to_validate:
                cleaned_tests = [test for test in tests_to_validate if test]

            # Call the internal FixApplier
            result: FixApplicationResult = self._fix_applier.apply_fix(
                code_changes=code_changes,
                tests_to_validate=cleaned_tests,
            )

            # Return the FixApplicationResult directly (as expected by the protocol)
            return result

        except Exception as e:
            error_message = f"Error applying fixes: {str(e)}"
            logger.error(error_message)
            raise FixApplicationError(error_message) from e

    def apply_suggestion(self, suggestion: FixSuggestion) -> FixApplicationResult:
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
            # Delegate directly to the underlying FixApplier's apply_fix_suggestion method
            return self._fix_applier.apply_fix_suggestion(suggestion)

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
