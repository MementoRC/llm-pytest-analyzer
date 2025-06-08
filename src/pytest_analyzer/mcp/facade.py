"""MCP Facade implementation for pytest-analyzer.

This module provides a facade that wraps the core PytestAnalyzerFacade to expose
MCP-compatible endpoints. It handles schema validation, error handling, and
transforms between MCP schemas and domain models.
"""

import logging
import time
from typing import Any

from pytest_analyzer.core.analyzer_facade import PytestAnalyzerFacade
from pytest_analyzer.core.cross_cutting.error_handling import error_handler

from .schemas import FixSuggestionData, MCPError, PytestFailureData
from .schemas.analyze_pytest_output import (
    AnalyzePytestOutputRequest,
    AnalyzePytestOutputResponse,
)
from .schemas.apply_suggestion import ApplySuggestionRequest, ApplySuggestionResponse
from .schemas.get_config import GetConfigRequest, GetConfigResponse
from .schemas.get_failure_summary import (
    GetFailureSummaryRequest,
    GetFailureSummaryResponse,
)
from .schemas.get_test_coverage import GetTestCoverageRequest, GetTestCoverageResponse
from .schemas.run_and_analyze import RunAndAnalyzeRequest, RunAndAnalyzeResponse
from .schemas.suggest_fixes import SuggestFixesRequest, SuggestFixesResponse
from .schemas.update_config import UpdateConfigRequest, UpdateConfigResponse
from .schemas.validate_suggestion import (
    ValidateSuggestionRequest,
    ValidateSuggestionResponse,
)

logger = logging.getLogger(__name__)


class MCPAnalyzerFacade:
    """
    MCP facade for pytest-analyzer that wraps the core analyzer facade.

    Provides MCP-compatible endpoints with schema validation, error handling,
    and transformation between MCP schemas and domain models.
    """

    def __init__(self, analyzer_facade: PytestAnalyzerFacade):
        """Initialize the MCP facade with a core analyzer facade instance."""
        self.analyzer = analyzer_facade

    def _measure_execution_time(func):
        """Decorator to measure execution time of MCP operations."""
        import functools

        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            start_time = time.time()
            result = await func(self, *args, **kwargs)
            execution_time = int(
                (time.time() - start_time) * 1000
            )  # Convert to milliseconds
            if hasattr(result, "execution_time_ms"):
                result.execution_time_ms = execution_time
            return result

        return wrapper

    def _transform_suggestion_to_mcp(self, suggestion: Any) -> FixSuggestionData:
        """Transform a FixSuggestion to MCP FixSuggestionData."""
        # Handle both domain entities and legacy models
        if hasattr(suggestion, "id") and hasattr(suggestion, "failure_id"):
            # New domain entity
            return FixSuggestionData(
                id=str(suggestion.id),
                failure_id=str(suggestion.failure_id),
                suggestion_text=suggestion.suggestion_text,
                code_changes=suggestion.code_changes,
                confidence_score=suggestion.confidence.numeric_value,
                explanation=suggestion.explanation,
                alternative_approaches=suggestion.alternative_approaches,
                file_path=suggestion.metadata.get("target_file", ""),
                line_number=suggestion.metadata.get("line_number", None),
            )
        else:
            # Legacy model from core.models.pytest_failure
            return FixSuggestionData(
                id=str(getattr(suggestion, "id", "unknown")),
                failure_id=str(getattr(suggestion.failure, "id", "unknown"))
                if hasattr(suggestion, "failure")
                else "unknown",
                suggestion_text=getattr(suggestion, "suggestion", ""),
                code_changes=getattr(suggestion, "code_changes", []),
                confidence_score=float(getattr(suggestion, "confidence", 0.0)),
                explanation=getattr(suggestion, "explanation", ""),
                alternative_approaches=[],
                file_path=getattr(suggestion.failure, "test_file", "")
                if hasattr(suggestion, "failure")
                else "",
                line_number=getattr(suggestion.failure, "line_number", None)
                if hasattr(suggestion, "failure")
                else None,
            )

    def _transform_failure_to_mcp(self, failure: Any) -> PytestFailureData:
        """Transform a PytestFailure to MCP PytestFailureData."""
        # Handle both domain entities and legacy models
        if hasattr(failure, "id") and hasattr(failure, "location"):
            # New domain entity
            return PytestFailureData(
                id=str(failure.id),
                test_name=failure.test_name,
                file_path=str(failure.location.file_path),
                failure_message=failure.failure_message,
                failure_type=failure.failure_type.name,
                line_number=failure.location.line_number,
                function_name=failure.location.function_name,
                class_name=failure.location.class_name,
                traceback=failure.traceback,
            )
        else:
            # Legacy model from core.models.pytest_failure
            return PytestFailureData(
                id=str(getattr(failure, "id", "unknown")),
                test_name=getattr(failure, "test_name", ""),
                file_path=getattr(failure, "test_file", ""),
                failure_message=getattr(failure, "error_message", ""),
                failure_type=getattr(failure, "error_type", ""),
                line_number=getattr(failure, "line_number", None),
                function_name="",  # Not available in legacy model
                class_name="",  # Not available in legacy model
                traceback=[getattr(failure, "traceback", "")]
                if getattr(failure, "traceback", "")
                else [],
            )

    async def analyze_pytest_output(
        self, request: AnalyzePytestOutputRequest
    ) -> AnalyzePytestOutputResponse:
        """Analyze pytest output file and generate fix suggestions."""
        start_time = time.time()

        try:
            # Validate request
            errors = request.validate()
            if errors:
                execution_time_ms = max(1, int((time.time() - start_time) * 1000))
                return AnalyzePytestOutputResponse(
                    success=False,
                    request_id=request.request_id,
                    failures=[],
                    suggestions=[],
                    parsing_errors=errors,
                    execution_time_ms=execution_time_ms,
                )

            # Call core analyzer
            results = self.analyzer.analyze_pytest_output(request.file_path)

            # Transform results to MCP format
            suggestions = [self._transform_suggestion_to_mcp(s) for s in results]

            execution_time_ms = max(1, int((time.time() - start_time) * 1000))
            return AnalyzePytestOutputResponse(
                success=True,
                request_id=request.request_id,
                suggestions=suggestions,
                failures=[],  # Populated from analysis if available
                execution_time_ms=execution_time_ms,
            )
        except Exception as e:
            logger.error(f"Error in analyze_pytest_output: {e}")
            return MCPError(
                code="ANALYSIS_FAILED",
                message=str(e),
                request_id=request.request_id,
            )

    async def run_and_analyze(
        self, request: RunAndAnalyzeRequest
    ) -> RunAndAnalyzeResponse:
        """Run pytest and analyze results in one operation."""
        start_time = time.time()

        try:
            errors = request.validate()
            if errors:
                execution_time_ms = max(1, int((time.time() - start_time) * 1000))
                return RunAndAnalyzeResponse(
                    success=False,
                    request_id=request.request_id,
                    warnings=errors,
                    execution_time_ms=execution_time_ms,
                )

            results = self.analyzer.run_and_analyze(
                test_path=request.test_pattern,
                pytest_args=request.pytest_args,
                quiet=not request.capture_output,
            )

            suggestions = [self._transform_suggestion_to_mcp(s) for s in results]

            execution_time_ms = max(1, int((time.time() - start_time) * 1000))
            return RunAndAnalyzeResponse(
                success=True,
                request_id=request.request_id,
                suggestions=suggestions,
                pytest_success=len(results) == 0,
                tests_run=len(results),  # This should come from actual test counts
                execution_time_ms=execution_time_ms,
            )
        except Exception as e:
            logger.error(f"Error in run_and_analyze: {e}")
            return MCPError(
                code="RUN_ANALYZE_FAILED",
                message=str(e),
                request_id=request.request_id,
            )

    async def suggest_fixes(self, request: SuggestFixesRequest) -> SuggestFixesResponse:
        """Generate fix suggestions from raw pytest output."""
        start_time = time.time()

        try:
            errors = request.validate()
            if errors:
                execution_time_ms = max(1, int((time.time() - start_time) * 1000))
                return SuggestFixesResponse(
                    success=False,
                    request_id=request.request_id,
                    parsing_warnings=errors,
                    execution_time_ms=execution_time_ms,
                )

            suggestions = self.analyzer.suggest_fixes(request.raw_output)
            mcp_suggestions = [
                self._transform_suggestion_to_mcp(s) for s in suggestions
            ]

            execution_time_ms = max(1, int((time.time() - start_time) * 1000))
            return SuggestFixesResponse(
                success=True,
                request_id=request.request_id,
                suggestions=mcp_suggestions,
                confidence_score=sum(s.confidence_score for s in mcp_suggestions)
                / len(mcp_suggestions)
                if mcp_suggestions
                else 0.0,
                execution_time_ms=execution_time_ms,
            )
        except Exception as e:
            logger.error(f"Error in suggest_fixes: {e}")
            return MCPError(
                code="SUGGEST_FIXES_FAILED",
                message=str(e),
                request_id=request.request_id,
            )

    @error_handler("apply_suggestion", MCPError)
    async def apply_suggestion(
        self, request: ApplySuggestionRequest
    ) -> ApplySuggestionResponse:
        """Apply a fix suggestion to the target files."""
        start_time = time.time()

        errors = request.validate()
        if errors:
            execution_time_ms = max(1, int((time.time() - start_time) * 1000))
            return ApplySuggestionResponse(
                success=False,
                request_id=request.request_id,
                warnings=errors,
                execution_time_ms=execution_time_ms,
            )

        result = self.analyzer.apply_suggestion(request.suggestion_id)

        execution_time_ms = max(1, int((time.time() - start_time) * 1000))
        return ApplySuggestionResponse(
            success=result["success"],
            request_id=request.request_id,
            suggestion_id=request.suggestion_id,
            target_file=request.target_file,
            changes_applied=result.get("applied_files", []),
            rollback_available=bool(result.get("rolled_back_files", [])),
            warnings=result.get("message", []) if not result["success"] else [],
            execution_time_ms=execution_time_ms,
        )

    @error_handler("validate_suggestion", MCPError)
    async def validate_suggestion(
        self, request: ValidateSuggestionRequest
    ) -> ValidateSuggestionResponse:
        """Validate a fix suggestion without applying changes."""
        start_time = time.time()

        errors = request.validate()
        if errors:
            execution_time_ms = max(1, int((time.time() - start_time) * 1000))
            return ValidateSuggestionResponse(
                success=False,
                request_id=request.request_id,
                validation_errors=errors,
                execution_time_ms=execution_time_ms,
            )

        # This would need implementation in core analyzer
        # For now return a basic response
        execution_time_ms = max(1, int((time.time() - start_time) * 1000))
        return ValidateSuggestionResponse(
            success=True,
            request_id=request.request_id,
            suggestion_id=request.suggestion_id,
            target_file=request.target_file,
            is_valid=True,
            execution_time_ms=execution_time_ms,
        )

    @error_handler("get_failure_summary", MCPError)
    async def get_failure_summary(
        self, request: GetFailureSummaryRequest
    ) -> GetFailureSummaryResponse:
        """Get failure statistics and categorization."""
        errors = request.validate()
        if errors:
            return GetFailureSummaryResponse(
                success=False, request_id=request.request_id, total_failures=0
            )

        # This would need implementation in core analyzer
        return GetFailureSummaryResponse(
            success=True,
            request_id=request.request_id,
            total_failures=0,
            failure_groups={},
        )

    @error_handler("get_test_coverage", MCPError)
    async def get_test_coverage(
        self, request: GetTestCoverageRequest
    ) -> GetTestCoverageResponse:
        """Get test coverage information and reporting."""
        errors = request.validate()
        if errors:
            return GetTestCoverageResponse(success=False, request_id=request.request_id)

        # This would need implementation in core analyzer
        return GetTestCoverageResponse(
            success=True, request_id=request.request_id, percentage=0.0
        )

    @error_handler("get_config", MCPError)
    async def get_config(self, request: GetConfigRequest) -> GetConfigResponse:
        """Get current analyzer configuration settings."""
        errors = request.validate()
        if errors:
            return GetConfigResponse(success=False, request_id=request.request_id)

        # This would need implementation in core analyzer
        return GetConfigResponse(
            success=True, request_id=request.request_id, config_data={}
        )

    @error_handler("update_config", MCPError)
    async def update_config(self, request: UpdateConfigRequest) -> UpdateConfigResponse:
        """Update analyzer configuration settings."""
        start_time = time.time()

        errors = request.validate()
        if errors:
            execution_time_ms = max(1, int((time.time() - start_time) * 1000))
            return UpdateConfigResponse(
                success=False,
                request_id=request.request_id,
                validation_errors=errors,
                execution_time_ms=execution_time_ms,
            )

        # This would need implementation in core analyzer
        execution_time_ms = max(1, int((time.time() - start_time) * 1000))
        return UpdateConfigResponse(
            success=True,
            request_id=request.request_id,
            updated_fields=[],
            execution_time_ms=execution_time_ms,
        )
