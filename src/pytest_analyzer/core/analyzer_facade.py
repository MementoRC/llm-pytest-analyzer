"""
Facade pattern implementation for backward compatibility with the original API.

This module provides a facade that maintains backward compatibility with the
existing API while using the new architecture internally.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ..utils.settings import Settings
from .analyzer_service_state_machine import AnalyzerStateMachine
from .di.container import Container
from .di.service_collection import ServiceCollection
from .models.pytest_failure import FixSuggestion
from .protocols import Applier

logger = logging.getLogger(__name__)


class PytestAnalyzerFacade:
    """
    Facade that provides the same interface as the original PytestAnalyzerService
    but uses the new architecture components internally.
    """

    def __init__(
        self, settings: Optional[Settings] = None, llm_client: Optional[Any] = None
    ):
        """
        Initialize the facade with optional settings and LLM client.

        Args:
            settings: Settings object
            llm_client: Optional client for language model API
        """
        self.settings = settings or Settings()

        # Create and configure the DI container
        self.di_container = self._create_container(llm_client)

    def _create_container(self, llm_client: Optional[Any] = None) -> Container:
        """
        Create and configure the dependency injection container.

        Args:
            llm_client: Optional LLM client to use

        Returns:
            Configured DIContainer
        """
        # Create service collection and register dependencies
        services = ServiceCollection()

        # Register settings
        services.add_singleton(Settings, self.settings)

        # Configure services based on settings
        services.configure_core_services()
        services.configure_extractors()

        if self.settings.use_llm:
            services.configure_llm_services(llm_client)

        # Build the container
        return services.build_container()

    def analyze_pytest_output(
        self, output_path: Union[str, Path]
    ) -> List[FixSuggestion]:
        """
        Analyze pytest output from a file and generate fix suggestions.

        Args:
            output_path: Path to the pytest output file

        Returns:
            List of suggested fixes
        """
        path = Path(output_path) if not isinstance(output_path, Path) else output_path
        if not path.exists():
            logger.error(f"Output file does not exist: {path}")
            return []

        try:
            # Create and run the state machine
            state_machine = AnalyzerStateMachine(self.di_container)
            result = state_machine.run(test_results_path=str(path), apply_fixes=False)

            if isinstance(result, dict) and "error" in result:
                logger.error(f"Error analyzing pytest output: {result['error']}")
                return []

            return result.get("suggestions", [])

        except Exception as e:
            logger.error(f"Error analyzing pytest output: {e}")
            return []

    def run_pytest_only(
        self,
        test_path: str,
        pytest_args: Optional[List[str]] = None,
        quiet: bool = False,
        progress: Optional[Any] = None,
        task_id: Optional[Any] = None,
    ) -> List[Any]:
        """
        Run pytest on the given path and return failures without generating suggestions.

        Args:
            test_path: Path to the directory or file to test
            pytest_args: Additional pytest arguments
            quiet: Whether to suppress pytest output
            progress: Optional Progress object for showing progress
            task_id: Optional parent task ID for progress tracking

        Returns:
            List of test failures
        """
        try:
            # Create and run the state machine - extraction phase only
            state_machine = AnalyzerStateMachine(self.di_container)
            result = state_machine.run(
                test_path=test_path,
                pytest_args=pytest_args or [],
                quiet=quiet,
                extract_only=True,
            )

            if isinstance(result, dict) and "error" in result:
                logger.error(f"Error running tests: {result['error']}")
                return []

            return result.get("extraction_results", {}).get("failures", [])

        except Exception as e:
            logger.error(f"Error running tests: {e}")
            return []

    def run_and_analyze(
        self,
        test_path: str,
        pytest_args: Optional[List[str]] = None,
        quiet: bool = False,
    ) -> List[FixSuggestion]:
        """
        Run pytest on the given path and analyze the output.

        Args:
            test_path: Path to the directory or file to test
            pytest_args: Additional pytest arguments
            quiet: Whether to suppress output and logging

        Returns:
            List of suggested fixes
        """
        try:
            # Create and run the state machine
            state_machine = AnalyzerStateMachine(self.di_container)
            result = state_machine.run(
                test_path=test_path,
                pytest_args=pytest_args or [],
                quiet=quiet,
                apply_fixes=False,
            )

            if isinstance(result, dict) and "error" in result:
                logger.error(f"Error analyzing tests: {result['error']}")
                return []

            return result.get("suggestions", [])

        except Exception as e:
            logger.error(f"Error analyzing tests: {e}")
            return []

    def apply_suggestion(self, suggestion: FixSuggestion) -> Dict[str, Any]:
        """
        Safely apply a fix suggestion to the target files.

        Args:
            suggestion: FixSuggestion to apply

        Returns:
            Result indicating success or failure
        """
        try:
            # Get the fix applier from the container
            applier = self.di_container.resolve(Applier)

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
            result = applier.apply(code_changes_to_apply, tests_to_validate)

            return {
                "success": result.get("success", False),
                "message": result.get("message", ""),
                "applied_files": result.get("applied_files", []),
                "rolled_back_files": result.get("rolled_back_files", []),
            }

        except Exception as e:
            logger.error(f"Error applying suggestion: {e}")
            return {
                "success": False,
                "message": f"Error applying suggestion: {str(e)}",
                "applied_files": [],
                "rolled_back_files": [],
            }
