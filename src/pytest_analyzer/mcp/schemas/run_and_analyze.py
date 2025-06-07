"""Schema definitions for the run_and_analyze MCP tool.

This tool executes pytest and analyzes results in one operation.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from uuid import uuid4

from . import (
    FixSuggestionData,
    PytestFailureData,
    validate_timeout,
)


@dataclass
class RunAndAnalyzeRequest:
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

    # Required fields first
    tool_name: str

    # Optional fields with defaults
    request_id: str = field(default_factory=lambda: str(uuid4()))
    metadata: Dict[str, Any] = field(default_factory=dict)
    test_pattern: str = ""  # Empty string means run all tests
    pytest_args: List[str] = field(default_factory=list)
    timeout: int = 300  # 5 minutes default
    working_directory: Optional[str] = None
    capture_output: bool = True
    max_suggestions: int = 10
    environment_vars: Dict[str, str] = field(default_factory=dict)

    def validate(self) -> List[str]:
        """Validate request data."""
        errors = []

        # Validate common fields
        if not self.tool_name:
            errors.append("tool_name is required")
        if not self.request_id:
            errors.append("request_id is required")

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
                errors.append(
                    f"Working directory does not exist: {self.working_directory}"
                )
            elif not os.path.isdir(self.working_directory):
                errors.append(
                    f"Working directory is not a directory: {self.working_directory}"
                )

        return errors

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        from dataclasses import asdict

        return asdict(self)


@dataclass
class RunAndAnalyzeResponse:
    """Response schema for run_and_analyze MCP tool.

    Contains pytest execution results and generated fix suggestions.
    """

    # Required fields first
    success: bool
    request_id: str

    # Optional fields with defaults
    execution_time_ms: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
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

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        from dataclasses import asdict

        return asdict(self)

    def to_json(self) -> str:
        """Convert to JSON string."""
        import json

        return json.dumps(self.to_dict(), indent=2)


__all__ = ["RunAndAnalyzeRequest", "RunAndAnalyzeResponse"]
