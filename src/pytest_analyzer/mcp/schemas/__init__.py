"""MCP schema definitions for pytest-analyzer.

Defines comprehensive JSON schemas for MCP request/response validation.
All schemas use dataclasses for type safety and easy JSON serialization.
"""

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional
from uuid import uuid4


@dataclass
class MCPRequest:
    """Base MCP request schema with common fields."""
    
    tool_name: str
    request_id: str = field(default_factory=lambda: str(uuid4()))
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def validate(self) -> List[str]:
        """Validate common request fields."""
        errors = []
        if not self.tool_name:
            errors.append("tool_name is required")
        if not self.request_id:
            errors.append("request_id is required")
        return errors
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class MCPResponse:
    """Base MCP response schema with success/error handling."""
    
    success: bool
    request_id: str
    execution_time_ms: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)


@dataclass 
class MCPError:
    """MCP error response schema."""
    
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)


@dataclass
class FixSuggestionData:
    """Data transfer object for fix suggestions in MCP responses."""
    
    id: str
    failure_id: str
    suggestion_text: str
    code_changes: List[str] = field(default_factory=list)
    confidence_score: float = 0.5
    explanation: str = ""
    alternative_approaches: List[str] = field(default_factory=list)
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    
    def validate(self) -> List[str]:
        """Validate suggestion data."""
        errors = []
        if not self.id:
            errors.append("id is required")
        if not self.failure_id:
            errors.append("failure_id is required")
        if not self.suggestion_text:
            errors.append("suggestion_text is required")
        if not (0.0 <= self.confidence_score <= 1.0):
            errors.append("confidence_score must be between 0.0 and 1.0")
        if self.line_number is not None and self.line_number < 1:
            errors.append("line_number must be positive")
        return errors
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class PytestFailureData:
    """Data transfer object for pytest failures in MCP responses."""
    
    id: str
    test_name: str
    file_path: str
    failure_message: str
    failure_type: str
    line_number: Optional[int] = None
    function_name: Optional[str] = None
    class_name: Optional[str] = None
    traceback: List[str] = field(default_factory=list)
    
    def validate(self) -> List[str]:
        """Validate failure data."""
        errors = []
        if not self.id:
            errors.append("id is required")
        if not self.test_name:
            errors.append("test_name is required")
        if not self.file_path:
            errors.append("file_path is required")
        if not self.failure_message:
            errors.append("failure_message is required")
        if not self.failure_type:
            errors.append("failure_type is required")
        if self.line_number is not None and self.line_number < 1:
            errors.append("line_number must be positive")
        return errors
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


# Validation utilities
def validate_file_path(file_path: str) -> List[str]:
    """Validate file path exists and is accessible."""
    import os
    errors = []
    if not file_path:
        errors.append("file_path is required")
    elif not os.path.exists(file_path):
        errors.append(f"File does not exist: {file_path}")
    elif not os.path.isfile(file_path):
        errors.append(f"Path is not a file: {file_path}")
    elif not os.access(file_path, os.R_OK):
        errors.append(f"File is not readable: {file_path}")
    return errors


def validate_output_format(format_type: str) -> List[str]:
    """Validate pytest output format type."""
    errors = []
    valid_formats = {"json", "xml", "text", "junit"}
    if format_type not in valid_formats:
        errors.append(f"Invalid format '{format_type}'. Must be one of: {valid_formats}")
    return errors


def validate_timeout(timeout: int) -> List[str]:
    """Validate timeout value."""
    errors = []
    if timeout <= 0:
        errors.append("timeout must be positive")
    elif timeout > 3600:  # 1 hour max
        errors.append("timeout cannot exceed 3600 seconds")
    return errors


__all__ = [
    "MCPRequest",
    "MCPResponse", 
    "MCPError",
    "FixSuggestionData",
    "PytestFailureData",
    "validate_file_path",
    "validate_output_format",
    "validate_timeout",
]