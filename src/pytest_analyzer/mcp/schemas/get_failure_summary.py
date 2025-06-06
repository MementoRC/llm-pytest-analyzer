"""Schema definitions for the get_failure_summary MCP tool.

This tool provides failure statistics and categorization.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from . import (
    MCPRequest,
    MCPResponse,
    PytestFailureData,
)


@dataclass
class GetFailureSummaryRequest(MCPRequest):
    """Request schema for get_failure_summary MCP tool.
    
    Gets failure statistics and categorization.
    
    Example:
        request = GetFailureSummaryRequest(
            tool_name="get_failure_summary",
            include_details=True,
            group_by="type",
            time_range="last_run"
        )
    """
    
    include_details: bool = True
    group_by: str = "type"  # type, file, class, function
    time_range: str = "last_run"  # last_run, last_hour, last_day
    filter_by_type: Optional[List[str]] = None
    include_resolved: bool = False
    max_failures: int = 100
    
    def validate(self) -> List[str]:
        """Validate request data."""
        errors = super().validate()
        
        # Validate group_by
        valid_group_by = {"type", "file", "class", "function", "none"}
        if self.group_by not in valid_group_by:
            errors.append(f"Invalid group_by '{self.group_by}'. Must be one of: {valid_group_by}")
        
        # Validate time_range
        valid_time_ranges = {"last_run", "last_hour", "last_day", "all"}
        if self.time_range not in valid_time_ranges:
            errors.append(f"Invalid time_range '{self.time_range}'. Must be one of: {valid_time_ranges}")
        
        # Validate max_failures
        if self.max_failures <= 0:
            errors.append("max_failures must be positive")
        elif self.max_failures > 1000:
            errors.append("max_failures cannot exceed 1000")
        
        return errors


@dataclass
class GetFailureSummaryResponse(MCPResponse):
    """Response schema for get_failure_summary MCP tool.
    
    Contains failure statistics and categorization data.
    """
    
    total_failures: int = 0
    failure_groups: Dict[str, List[PytestFailureData]] = field(default_factory=dict)
    summary_stats: Dict[str, Any] = field(default_factory=dict)
    trends: Dict[str, Any] = field(default_factory=dict)
    top_failing_files: List[Dict[str, Any]] = field(default_factory=list)
    top_failing_tests: List[Dict[str, Any]] = field(default_factory=list)
    resolution_suggestions: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Initialize summary statistics after creation."""
        if not self.summary_stats:
            self._compute_summary_stats()
    
    def _compute_summary_stats(self):
        """Compute summary statistics from failure groups."""
        all_failures = []
        for group_failures in self.failure_groups.values():
            all_failures.extend(group_failures)
        
        self.total_failures = len(all_failures)
        
        # Count by type
        type_counts = {}
        for failure in all_failures:
            failure_type = failure.failure_type
            type_counts[failure_type] = type_counts.get(failure_type, 0) + 1
        
        # Count by file
        file_counts = {}
        for failure in all_failures:
            file_path = failure.file_path
            file_counts[file_path] = file_counts.get(file_path, 0) + 1
        
        self.summary_stats = {
            "total_failures": self.total_failures,
            "failure_types": type_counts,
            "files_affected": len(file_counts),
            "most_common_type": max(type_counts.items(), key=lambda x: x[1])[0] if type_counts else None,
            "average_failures_per_file": self.total_failures / len(file_counts) if file_counts else 0,
        }
    
    @property
    def has_failures(self) -> bool:
        """Check if there are any failures."""
        return self.total_failures > 0
    
    def get_failures_by_type(self, failure_type: str) -> List[PytestFailureData]:
        """Get all failures of a specific type."""
        failures = []
        for group_failures in self.failure_groups.values():
            failures.extend([f for f in group_failures if f.failure_type == failure_type])
        return failures


__all__ = ["GetFailureSummaryRequest", "GetFailureSummaryResponse"]