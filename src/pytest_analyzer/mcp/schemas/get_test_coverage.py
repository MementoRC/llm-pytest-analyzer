"""Schema definitions for the get_test_coverage MCP tool.

This tool provides test coverage information and reporting.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from . import (
    MCPRequest,
    MCPResponse,
)


@dataclass
class GetTestCoverageRequest(MCPRequest):
    """Request schema for get_test_coverage MCP tool.

    Gets test coverage information and generates reports.

    Example:
        request = GetTestCoverageRequest(
            tool_name="get_test_coverage",
            format="json",
            include_files=["src/"],
            exclude_patterns=["**/test_*"],
            minimum_coverage=80.0
        )
    """

    format: str = "json"  # json, xml, html, text
    include_files: List[str] = field(default_factory=list)
    exclude_patterns: List[str] = field(default_factory=list)
    minimum_coverage: Optional[float] = None
    include_branches: bool = True
    show_missing: bool = True

    def validate(self) -> List[str]:
        """Validate request data."""
        errors = super().validate()

        # Validate format
        valid_formats = {"json", "xml", "html", "text", "lcov"}
        if self.format not in valid_formats:
            errors.append(
                f"Invalid format '{self.format}'. Must be one of: {valid_formats}"
            )

        # Validate minimum_coverage
        if self.minimum_coverage is not None:
            if not (0.0 <= self.minimum_coverage <= 100.0):
                errors.append("minimum_coverage must be between 0.0 and 100.0")

        return errors


@dataclass
class CoverageFileData:
    """Data for coverage of a single file."""

    file_path: str
    statements: int
    missing: int
    excluded: int
    coverage: float
    missing_lines: List[int] = field(default_factory=list)
    branch_coverage: Optional[float] = None

    @property
    def covered_statements(self) -> int:
        """Get number of covered statements."""
        return self.statements - self.missing


@dataclass
class GetTestCoverageResponse(MCPResponse):
    """Response schema for get_test_coverage MCP tool.

    Contains test coverage data and reporting information.
    """

    coverage_data: Dict[str, Any] = field(default_factory=dict)
    report_path: Optional[str] = None
    percentage: float = 0.0
    branch_percentage: Optional[float] = None
    files: List[CoverageFileData] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    def __post_init__(self):
        """Initialize summary data after creation."""
        if not self.summary and self.files:
            self._compute_summary()

    def _compute_summary(self):
        """Compute coverage summary from file data."""
        total_statements = sum(f.statements for f in self.files)
        total_missing = sum(f.missing for f in self.files)
        total_covered = total_statements - total_missing

        self.percentage = (
            (total_covered / total_statements * 100) if total_statements > 0 else 0.0
        )

        self.summary = {
            "total_statements": total_statements,
            "covered_statements": total_covered,
            "missing_statements": total_missing,
            "coverage_percentage": self.percentage,
            "files_covered": len(self.files),
            "files_with_full_coverage": len(
                [f for f in self.files if f.coverage >= 100.0]
            ),
            "files_below_threshold": len([f for f in self.files if f.coverage < 80.0]),
        }

    @property
    def has_coverage_data(self) -> bool:
        """Check if coverage data is available."""
        return bool(self.coverage_data or self.files)

    @property
    def meets_threshold(self) -> bool:
        """Check if coverage meets common threshold (80%)."""
        return self.percentage >= 80.0

    def get_files_below_threshold(
        self, threshold: float = 80.0
    ) -> List[CoverageFileData]:
        """Get files with coverage below threshold."""
        return [f for f in self.files if f.coverage < threshold]

    def get_uncovered_lines(self) -> Dict[str, List[int]]:
        """Get mapping of files to their uncovered line numbers."""
        return {f.file_path: f.missing_lines for f in self.files if f.missing_lines}


__all__ = ["GetTestCoverageRequest", "GetTestCoverageResponse", "CoverageFileData"]
