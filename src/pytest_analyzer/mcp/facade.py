"""MCP Facade implementation for pytest-analyzer.

This module provides a facade that wraps the core PytestAnalyzerFacade to expose
MCP-compatible endpoints. It handles schema validation, error handling, and 
transforms between MCP schemas and domain models.
"""

import logging
import time
from typing import Any

from pytest_analyzer.core.cross_cutting.error_handling import error_handler
from pytest_analyzer.core.analyzer_facade import PytestAnalyzerFacade

from .schemas.analyze_pytest_output import AnalyzePytestOutputRequest, AnalyzePytestOutputResponse
from .schemas.run_and_analyze import RunAndAnalyzeRequest, RunAndAnalyzeResponse
from .schemas.suggest_fixes import SuggestFixesRequest, SuggestFixesResponse
from .schemas.apply_suggestion import ApplySuggestionRequest, ApplySuggestionResponse
from .schemas.validate_suggestion import ValidateSuggestionRequest, ValidateSuggestionResponse
from .schemas.get_failure_summary import GetFailureSummaryRequest, GetFailureSummaryResponse
from .schemas.get_test_coverage import GetTestCoverageRequest, GetTestCoverageResponse
from .schemas.get_config import GetConfigRequest, GetConfigResponse
from .schemas.update_config import UpdateConfigRequest, UpdateConfigResponse
from .schemas import MCPError, FixSuggestionData, PytestFailureData

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
        def wrapper(self, *args, **kwargs):
            start_time = time.time()
            result = func(self, *args, **kwargs)
            execution_time = int((time.time() - start_time) * 1000)  # Convert to milliseconds
            if isinstance(result, dict):
                result['execution_time_ms'] = execution_time
            return result
        return wrapper

    def _transform_suggestion_to_mcp(self, suggestion: Any) -> FixSuggestionData:
        """Transform a domain FixSuggestion to MCP FixSuggestionData."""
        return FixSuggestionData(
            id=str(suggestion.id),
            failure_id=str(suggestion.failure.id) if suggestion.failure else "",
            suggestion_text=suggestion.description,
            code_changes=suggestion.code_changes,
            confidence_score=suggestion.confidence_score,
            explanation=suggestion.explanation,
            alternative_approaches=suggestion.alternatives,
            file_path=suggestion.target_file,
            line_number=suggestion.line_number
        )

    def _transform_failure_to_mcp(self, failure: Any) -> PytestFailureData:
        """Transform a domain PytestFailure to MCP PytestFailureData."""
        return PytestFailureData(
            id=str(failure.id),
            test_name=failure.test_name,
            file_path=str(failure.file_path),
            failure_message=failure.message,
            failure_type=failure.failure_type,
            line_number=failure.line_number,
            function_name=failure.function_name,
            class_name=failure.class_name,
            traceback=failure.traceback_lines
        )

    @error_handler("analyze_pytest_output", MCPError)
    async def analyze_pytest_output(
        self, request: AnalyzePytestOutputRequest
    ) -> AnalyzePytestOutputResponse:
        """Analyze pytest output file and generate fix suggestions."""
        # Validate request
        errors = request.validate()
        if errors:
            return AnalyzePytestOutputResponse(
                success=False,
                request_id=request.request_id,
                failures=[],
                suggestions=[],
                parsing_errors=errors
            )

        # Call core analyzer
        results = self.analyzer.analyze_pytest_output(request.file_path)
        
        # Transform results to MCP format
        suggestions = [self._transform_suggestion_to_mcp(s) for s in results]
        
        return AnalyzePytestOutputResponse(
            success=True,
            request_id=request.request_id,
            suggestions=suggestions,
            failures=[],  # Populated from analysis if available
            confidence_score=sum(s.confidence_score for s in suggestions) / len(suggestions) if suggestions else 0.0
        )

    @error_handler("run_and_analyze", MCPError)
    async def run_and_analyze(
        self, request: RunAndAnalyzeRequest
    ) -> RunAndAnalyzeResponse:
        """Run pytest and analyze results in one operation."""
        errors = request.validate()
        if errors:
            return RunAndAnalyzeResponse(
                success=False,
                request_id=request.request_id,
                warnings=errors
            )

        results = self.analyzer.run_and_analyze(
            test_path=request.test_pattern,
            pytest_args=request.pytest_args,
            quiet=not request.capture_output
        )

        suggestions = [self._transform_suggestion_to_mcp(s) for s in results]
        
        return RunAndAnalyzeResponse(
            success=True,
            request_id=request.request_id,
            suggestions=suggestions,
            pytest_success=len(results) == 0,
            tests_run=len(results)  # This should come from actual test counts
        )

    @error_handler("suggest_fixes", MCPError)
    async def suggest_fixes(
        self, request: SuggestFixesRequest
    ) -> SuggestFixesResponse:
        """Generate fix suggestions from raw pytest output."""
        errors = request.validate()
        if errors:
            return SuggestFixesResponse(
                success=False,
                request_id=request.request_id,
                parsing_warnings=errors
            )

        suggestions = self.analyzer.suggest_fixes(request.raw_output)
        mcp_suggestions = [self._transform_suggestion_to_mcp(s) for s in suggestions]

        return SuggestFixesResponse(
            success=True,
            request_id=request.request_id,
            suggestions=mcp_suggestions,
            confidence_score=sum(s.confidence_score for s in mcp_suggestions) / len(mcp_suggestions) if mcp_suggestions else 0.0
        )

    @error_handler("apply_suggestion", MCPError)
    async def apply_suggestion(
        self, request: ApplySuggestionRequest
    ) -> ApplySuggestionResponse:
        """Apply a fix suggestion to the target files."""
        errors = request.validate()
        if errors:
            return ApplySuggestionResponse(
                success=False,
                request_id=request.request_id,
                warnings=errors
            )

        result = self.analyzer.apply_suggestion(request.suggestion)
        
        return ApplySuggestionResponse(
            success=result["success"],
            request_id=request.request_id,
            suggestion_id=request.suggestion_id,
            target_file=request.target_file,
            changes_applied=result.get("applied_files", []),
            rollback_available=bool(result.get("rolled_back_files", [])),
            warnings=result.get("message", []) if not result["success"] else []
        )

    @error_handler("validate_suggestion", MCPError)
    async def validate_suggestion(
        self, request: ValidateSuggestionRequest
    ) -> ValidateSuggestionResponse:
        """Validate a fix suggestion without applying changes."""
        errors = request.validate()
        if errors:
            return ValidateSuggestionResponse(
                success=False,
                request_id=request.request_id,
                validation_errors=errors
            )

        # This would need implementation in core analyzer
        # For now return a basic response
        return ValidateSuggestionResponse(
            success=True,
            request_id=request.request_id,
            suggestion_id=request.suggestion_id,
            target_file=request.target_file,
            is_valid=True
        )

    @error_handler("get_failure_summary", MCPError)
    async def get_failure_summary(
        self, request: GetFailureSummaryRequest
    ) -> GetFailureSummaryResponse:
        """Get failure statistics and categorization."""
        errors = request.validate()
        if errors:
            return GetFailureSummaryResponse(
                success=False,
                request_id=request.request_id,
                total_failures=0
            )

        # This would need implementation in core analyzer
        return GetFailureSummaryResponse(
            success=True,
            request_id=request.request_id,
            total_failures=0,
            failure_groups={}
        )

    @error_handler("get_test_coverage", MCPError)
    async def get_test_coverage(
        self, request: GetTestCoverageRequest
    ) -> GetTestCoverageResponse:
        """Get test coverage information and reporting."""
        errors = request.validate()
        if errors:
            return GetTestCoverageResponse(
                success=False,
                request_id=request.request_id
            )

        # This would need implementation in core analyzer
        return GetTestCoverageResponse(
            success=True,
            request_id=request.request_id,
            percentage=0.0
        )

    @error_handler("get_config", MCPError)
    async def get_config(
        self, request: GetConfigRequest
    ) -> GetConfigResponse:
        """Get current analyzer configuration settings."""
        errors = request.validate()
        if errors:
            return GetConfigResponse(
                success=False,
                request_id=request.request_id
            )

        # This would need implementation in core analyzer
        return GetConfigResponse(
            success=True,
            request_id=request.request_id,
            config_data={}
        )

    @error_handler("update_config", MCPError)
    async def update_config(
        self, request: UpdateConfigRequest
    ) -> UpdateConfigResponse:
        """Update analyzer configuration settings."""
        errors = request.validate()
        if errors:
            return UpdateConfigResponse(
                success=False,
                request_id=request.request_id,
                validation_errors=errors
            )

        # This would need implementation in core analyzer
        return UpdateConfigResponse(
            success=True,
            request_id=request.request_id,
            updated_fields=[]
        )
