"""
DI-based analyzer service implementation - Backward compatibility wrapper.

This module provides backward compatibility for existing code that expects
the DIPytestAnalyzerService class. It delegates to the refactored PytestAnalyzerService.
"""

import logging
from pathlib import Path
from typing import List, Optional, Union

from ..utils.path_resolver import PathResolver
from ..utils.settings import Settings
from .analyzer_service import PytestAnalyzerService
from .analyzer_state_machine import AnalyzerStateMachine
from .environment.protocol import EnvironmentManager
from .llm.llm_service_protocol import LLMServiceProtocol
from .models.pytest_failure import FixSuggestion, PytestFailure

logger = logging.getLogger(__name__)


class DIPytestAnalyzerService:
    """
    Backward compatibility wrapper for the refactored PytestAnalyzerService.

    This class maintains the same interface as the old DI service but delegates
    to the new refactored service internally.
    """

    def __init__(
        self,
        settings: Settings,
        path_resolver: PathResolver,
        state_machine: Optional[AnalyzerStateMachine] = None,
        llm_service: Optional[LLMServiceProtocol] = None,
        env_manager: Optional[EnvironmentManager] = None,
    ):
        """
        Initialize the test analyzer service with injected dependencies.

        Note: This is a compatibility wrapper. The state_machine, llm_service,
        and env_manager parameters are accepted for backward compatibility but
        not used directly as the new service uses an orchestrator pattern.

        Args:
            settings: Settings object
            path_resolver: PathResolver object for resolving paths
            state_machine: Legacy parameter (ignored)
            llm_service: Legacy parameter (ignored)
            env_manager: Legacy parameter (ignored)
        """
        self.settings = settings
        self.path_resolver = path_resolver

        # For backward compatibility - store legacy dependencies
        self.state_machine = state_machine
        self.llm_service = llm_service
        self.env_manager = env_manager

        # Create the refactored service using DI container
        from .di.container import Container
        from .di.service_collection import configure_services

        container = Container()
        configure_services(container, settings)
        self._service = container.resolve(PytestAnalyzerService)

        # Legacy context access for backward compatibility
        if state_machine and hasattr(state_machine, "context"):
            self.context = state_machine.context
        else:
            # Create a minimal context-like object with fix_applier
            from .analysis.fix_applier import FixApplier

            fix_applier = FixApplier()
            self.context = type(
                "Context",
                (),
                {
                    "settings": settings,
                    "path_resolver": path_resolver,
                    "llm_service": llm_service,
                    "fix_applier": fix_applier,
                },
            )()

    def analyze_pytest_output(
        self, output_path: Union[str, Path]
    ) -> List[FixSuggestion]:
        """Analyze pytest output from a file and generate fix suggestions."""
        return self._service.analyze_pytest_output(output_path)

    def run_pytest_only(
        self,
        test_path: str,
        pytest_args: Optional[List[str]] = None,
        quiet: bool = False,
        progress=None,
        task_id=None,
    ) -> List[PytestFailure]:
        """Run pytest on the given path and return failures."""
        return self._service.run_pytest_only(
            test_path, pytest_args, quiet, progress, task_id
        )

    def run_and_analyze(
        self,
        test_path: str,
        pytest_args: Optional[List[str]] = None,
        quiet: bool = False,
        use_async: Optional[bool] = None,
    ) -> List[FixSuggestion]:
        """Run pytest on the given path and analyze the output."""
        return self._service.run_and_analyze(test_path, pytest_args, quiet, use_async)

    def apply_suggestion(self, suggestion: FixSuggestion):
        """Apply a fix suggestion."""
        # Try to use context.fix_applier for backward compatibility
        if hasattr(self.context, "fix_applier"):
            if self.context.fix_applier is not None:
                return self.context.fix_applier.apply_fix_suggestion(suggestion)
            else:
                # If fix_applier is explicitly set to None, return None for backward compatibility
                return None
        elif hasattr(self._service, "apply_suggestion"):
            return self._service.apply_suggestion(suggestion)
        else:
            logger.error("Cannot apply fix: Fix applier not initialized")
            return None

    def get_performance_metrics(self):
        """Get performance metrics."""
        if hasattr(self._service, "get_performance_metrics"):
            return self._service.get_performance_metrics()
        return {}

    def generate_performance_report(self) -> str:
        """Generate a human-readable performance report."""
        if hasattr(self._service, "generate_performance_report"):
            return self._service.generate_performance_report()
        return "Performance tracking not available"

    def reset_performance_metrics(self) -> None:
        """Reset all performance metrics."""
        if hasattr(self._service, "reset_performance_metrics"):
            self._service.reset_performance_metrics()
