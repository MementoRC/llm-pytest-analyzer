"""Schema definitions for the validate_suggestion MCP tool.

This tool validates fix suggestions without applying changes (dry-run mode).
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List
from uuid import uuid4

from . import (
    validate_file_path,
)


@dataclass
class ValidateSuggestionRequest:
    """Request schema for validate_suggestion MCP tool.

    Validates fix suggestions without applying changes.

    Example:
        request = ValidateSuggestionRequest(
            tool_name="validate_suggestion",
            suggestion_id="suggestion-123",
            target_file="tests/test_example.py",
            check_syntax=True,
            check_imports=True
        )
    """

    # Required fields first
    tool_name: str
    suggestion_id: str
    target_file: str
    
    # Optional fields with defaults
    request_id: str = field(default_factory=lambda: str(uuid4()))
    metadata: Dict[str, Any] = field(default_factory=dict)
    check_syntax: bool = True
    check_imports: bool = True
    check_tests: bool = False
    context: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> List[str]:
        """Validate request data."""
        errors = []
        
        # Validate common fields
        if not self.tool_name:
            errors.append("tool_name is required")
        if not self.request_id:
            errors.append("request_id is required")

        # Validate suggestion_id
        if not self.suggestion_id:
            errors.append("suggestion_id is required")

        # Validate target_file
        if not self.target_file:
            errors.append("target_file is required")
        else:
            errors.extend(validate_file_path(self.target_file))

        return errors

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        from dataclasses import asdict
        return asdict(self)


@dataclass
class ValidateSuggestionResponse:
    """Response schema for validate_suggestion MCP tool.

    Contains validation results for a fix suggestion.
    """

    # Required fields first
    success: bool
    request_id: str
    
    # Optional fields with defaults
    execution_time_ms: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    suggestion_id: str = ""
    target_file: str = ""
    is_valid: bool = True
    validation_errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    syntax_check: Dict[str, Any] = field(default_factory=dict)
    import_check: Dict[str, Any] = field(default_factory=dict)
    test_impact: Dict[str, Any] = field(default_factory=dict)
    confidence_adjustment: float = 0.0
    recommendations: List[str] = field(default_factory=list)

    def __post_init__(self):
        """Initialize validation status after creation."""
        if self.validation_errors:
            self.is_valid = False

    @property
    def has_errors(self) -> bool:
        """Check if there are validation errors."""
        return len(self.validation_errors) > 0

    @property
    def has_warnings(self) -> bool:
        """Check if there are validation warnings."""
        return len(self.warnings) > 0

    @property
    def syntax_valid(self) -> bool:
        """Check if syntax validation passed."""
        return self.syntax_check.get("valid", True)

    @property
    def imports_valid(self) -> bool:
        """Check if import validation passed."""
        return self.import_check.get("valid", True)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        from dataclasses import asdict
        return asdict(self)

    def to_json(self) -> str:
        """Convert to JSON string."""
        import json
        return json.dumps(self.to_dict(), indent=2)


__all__ = ["ValidateSuggestionRequest", "ValidateSuggestionResponse"]
