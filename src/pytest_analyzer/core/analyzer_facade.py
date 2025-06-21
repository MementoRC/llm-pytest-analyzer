"""
Facade pattern implementation for backward compatibility with the original API.

This module provides a facade that maintains backward compatibility with the
existing API while using the new architecture internally. The facade pattern
is used to provide a simpler interface to a complex subsystem. In this case,
the complex subsystem is the new architecture that uses dependency injection,
protocol-based interfaces, and a state machine.

Key features of this facade implementation:
- Presents the same interface as the original PytestAnalyzerService
- Uses the new architecture's DI container and components internally
- Delegates work to the AnalyzerStateMachine
- Handles error conditions and maintains expected return formats
- Manages resources like temporary files
- Provides a bridge between the old and new architectures

See docs/facade_architecture.md for more detailed documentation.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pytest_analyzer.core import analyzer_state_machine

# Use absolute import for AnalyzerStateMachine to align with typical patch targets
from pytest_analyzer.core.analyzer_state_machine import (
    AnalyzerContext,
    AnalyzerStateMachine,
)

from ..utils.path_resolver import PathResolver
from ..utils.settings import Settings
from .analysis.failure_analyzer import FailureAnalyzer
from .analysis.fix_suggester import FixSuggester
from .analysis.llm_suggester import LLMSuggester
from .di.container import Container
from .di.service_collection import ServiceCollection
from .errors import DependencyResolutionError
from .llm.llm_service_protocol import LLMServiceProtocol
from .models.pytest_failure import FixSuggestion
from .protocols import Applier

logger = logging.getLogger(__name__)


class PytestAnalyzerFacade:
    """
    Facade that provides the same interface as the original PytestAnalyzerService
    but uses the new architecture components internally.

    This facade implements the Facade design pattern to simplify interaction with
    the complex subsystem consisting of DI container, state machine, and various
    protocol implementations. It presents a unified interface that matches the
    original service while delegating work to specialized components.

    Key responsibilities:
    - Initialize and configure the DI container
    - Create and manage the analyzer context
    - Delegate test extraction, analysis, and fix application to the state machine
    - Handle errors and maintain consistent return formats
    - Manage resources like temporary files

    This facade allows existing code to continue working while benefiting from
    the improved architecture internally.
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

    def _create_analyzer_context_from_container(
        self, settings: Settings, container: Container
    ) -> AnalyzerContext:
        """Helper to create AnalyzerContext from DI container and settings."""
        path_resolver = container.resolve(PathResolver)

        llm_service: Optional[LLMServiceProtocol] = None
        if settings.use_llm:
            try:
                llm_service = container.resolve(LLMServiceProtocol)
            except DependencyResolutionError:
                logger.warning(
                    "LLMServiceProtocol not resolved. LLM features might be affected."
                )

        analyzer: Optional[FailureAnalyzer] = None
        try:
            analyzer = container.resolve(FailureAnalyzer)
        except DependencyResolutionError:
            logger.debug(
                "FailureAnalyzer not resolved from container for AnalyzerContext."
            )

        suggester: Optional[FixSuggester] = None
        try:
            suggester = container.resolve(FixSuggester)
        except DependencyResolutionError:
            logger.debug(
                "FixSuggester not resolved from container for AnalyzerContext."
            )

        llm_suggester: Optional[LLMSuggester] = None
        if settings.use_llm and llm_service:
            try:
                llm_suggester = container.resolve(LLMSuggester)
            except DependencyResolutionError:
                logger.debug(
                    "LLMSuggester not resolved from container for AnalyzerContext."
                )

        fix_applier: Optional[Applier] = (
            None  # Type Applier, as resolved, instance is FixApplier
        )
        try:
            fix_applier = container.resolve(Applier)
        except DependencyResolutionError:
            logger.debug(
                "FixApplier (via Applier protocol) not resolved from container for AnalyzerContext."
            )

        context = AnalyzerContext(
            settings=settings,
            path_resolver=path_resolver,
            llm_service=llm_service,
            analyzer=analyzer,
            suggester=suggester,
            llm_suggester=llm_suggester,
            fix_applier=fix_applier,  # type: ignore[assignment] # FixApplier is an Applier
        )
        return context

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
            # Create AnalyzerContext and then the state machine
            analyzer_context = self._create_analyzer_context_from_container(
                self.settings, self.di_container
            )
            state_machine = analyzer_state_machine.AnalyzerStateMachine(
                analyzer_context
            )
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
            # Create AnalyzerContext and then the state machine
            analyzer_context = self._create_analyzer_context_from_container(
                self.settings, self.di_container
            )
            state_machine = analyzer_state_machine.AnalyzerStateMachine(
                analyzer_context
            )
            # Set up the state machine with the test parameters
            state_machine.setup(
                test_path=test_path,
                pytest_args=pytest_args or [],
                quiet=quiet,
            )
            result = state_machine.run()

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
            # Create AnalyzerContext and then the state machine
            analyzer_context = self._create_analyzer_context_from_container(
                self.settings, self.di_container
            )
            state_machine = analyzer_state_machine.AnalyzerStateMachine(
                analyzer_context
            )
            # Set up the state machine with the test parameters
            state_machine.setup(
                test_path=test_path,
                pytest_args=pytest_args or [],
                quiet=quiet,
            )
            result = state_machine.run(apply_fixes=False)

            if isinstance(result, dict) and "error" in result:
                logger.error(f"Error analyzing tests: {result['error']}")
                return []

            return result.get("suggestions", [])

        except Exception as e:
            logger.error(f"Error analyzing tests: {e}")
            return []

    def analyze_test_results(self, test_output: str) -> Dict[str, Any]:
        """
        Analyze pytest test results from raw output string and return analysis.

        Args:
            test_output: Raw pytest test output as a string

        Returns:
            Dictionary with analysis results including success status, analyses, and suggestions
        """
        try:
            # Write the test output to a temporary file
            import tempfile

            with tempfile.NamedTemporaryFile(
                mode="w+", suffix=".txt", delete=False
            ) as tmp:
                tmp.write(test_output)
                tmp_path = tmp.name

            # Create AnalyzerContext and then the state machine
            analyzer_context = self._create_analyzer_context_from_container(
                self.settings, self.di_container
            )
            state_machine = AnalyzerStateMachine(analyzer_context)
            result = state_machine.run(test_results_path=tmp_path, apply_fixes=False)

            # Clean up the temporary file
            import os

            try:
                os.unlink(tmp_path)
            except Exception:
                pass

            if isinstance(result, dict) and "error" in result:
                logger.error(f"Error analyzing pytest output: {result['error']}")
                return {
                    "success": False,
                    "error": result["error"],
                    "analyses": [],
                    "suggestions": [],
                }

            return {
                "success": True,
                "analyses": result.get("analysis_results", {}).get("analyses", []),
                "suggestions": result.get("suggestions", []),
            }

        except Exception as e:
            logger.error(f"Error analyzing pytest output: {e}")
            return {
                "success": False,
                "error": str(e),
                "analyses": [],
                "suggestions": [],
            }

    def suggest_fixes(self, test_output: str) -> List[Dict[str, Any]]:
        """
        Analyze test results and suggest fixes.

        Args:
            test_output: Raw pytest test output as a string

        Returns:
            List of suggested fixes
        """
        result = self.analyze_test_results(test_output)
        return result.get("suggestions", [])

    def apply_fixes(
        self, test_output: str, target_files: List[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze test results, suggest and apply fixes.

        Args:
            test_output: Raw pytest test output as a string
            target_files: Optional list of files to which fixes should be applied

        Returns:
            Dictionary with results of fix application
        """
        try:
            # Write the test output to a temporary file
            import tempfile

            with tempfile.NamedTemporaryFile(
                mode="w+", suffix=".txt", delete=False
            ) as tmp:
                tmp.write(test_output)
                tmp_path = tmp.name

            # Create AnalyzerContext and then the state machine
            analyzer_context = self._create_analyzer_context_from_container(
                self.settings, self.di_container
            )
            state_machine = AnalyzerStateMachine(analyzer_context)

            # Set target files if provided
            if target_files:
                analyzer_context.target_files = target_files

            result = state_machine.run(test_results_path=tmp_path, apply_fixes=True)

            # Clean up the temporary file
            import os

            try:
                os.unlink(tmp_path)
            except Exception:
                pass

            if isinstance(result, dict) and "error" in result:
                logger.error(f"Error applying fixes: {result['error']}")
                return {
                    "success": False,
                    "error": result["error"],
                    "fixes_applied": False,
                }

            return {
                "success": True,
                "fixes_applied": result.get("fixes_applied", False),
                "suggestions": result.get("suggestions", []),
            }

        except Exception as e:
            logger.error(f"Error applying fixes: {e}")
            return {"success": False, "error": str(e), "fixes_applied": False}

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
