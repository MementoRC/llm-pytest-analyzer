"""Schema definitions for the run_and_analyze MCP tool.

This tool executes pytest and analyzes results in one operation.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from . import (
    FixSuggestionData,
    MCPRequest,
    MCPResponse,
    PytestFailureData,
    validate_timeout,
)


@dataclass
class RunAndAnalyzeRequest(MCPRequest):
    """Request schema for run_and_analyze MCP tool.
    
    Executes pytest with specified parameters and analyzes the results.
    
    Example:
        request = RunAndAnalyzeRequest(
            tool_name="run_and_analyze",
            test_pattern="tests/test_example.py::test_function",
            pytest_args=["--verbose", "--tb=short"],
            timeout=300,
            working_directory="/path/to/project"
        )
    """
    
    test_pattern: str = ""  # Empty string means run all tests
    pytest_args: List[str] = field(default_factory=list)
    timeout: int = 300  # 5 minutes default
    working_directory: Optional[str] = None
    capture_output: bool = True
    max_suggestions: int = 10
    environment_vars: Dict[str, str] = field(default_factory=dict)
    
    def validate(self) -> List[str]:
        """Validate request data."""
        errors = super().validate()
        
        # Validate timeout
        errors.extend(validate_timeout(self.timeout))
        
        # Validate max_suggestions
        if self.max_suggestions <= 0:
            errors.append("max_suggestions must be positive")
        elif self.max_suggestions > 100:
            errors.append("max_suggestions cannot exceed 100")
        
        # Validate working directory if provided
        if self.working_directory is not None:
            import os
            if not os.path.exists(self.working_directory):
                errors.append(f"Working directory does not exist: {self.working_directory}")
            elif not os.path.isdir(self.working_directory):
                errors.append(f"Working directory is not a directory: {self.working_directory}")
        
        return errors


@dataclass
class RunAndAnalyzeResponse(MCPResponse):
    """Response schema for run_and_analyze MCP tool.
    
    Contains pytest execution results and generated fix suggestions.
    """
    
    pytest_success: bool = False
    suggestions: List[FixSuggestionData] = field(default_factory=list)
    failures: List[PytestFailureData] = field(default_factory=list)
    raw_output: str = ""
    exit_code: int = 0
    tests_run: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    tests_skipped: int = 0
    coverage_data: Optional[Dict[str, Any]] = None
    warnings: List[str] = field(default_factory=list)
    
    @property
    def pass_rate(self) -> float:
        """Calculate test pass rate as percentage."""
        if self.tests_run == 0:
            return 0.0
        return (self.tests_passed / self.tests_run) * 100
    
    @property
    def has_failures(self) -> bool:
        """Check if there are any test failures."""
        return self.tests_failed > 0 or len(self.failures) > 0


__all__ = ["RunAndAnalyzeRequest", "RunAndAnalyzeResponse"]