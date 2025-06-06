"""Schema definitions for the apply_suggestion MCP tool.

This tool applies suggested fixes to code files with backup/rollback support.
"""

from dataclasses import dataclass, field
from typing import List, Optional

from . import (
    MCPRequest,
    MCPResponse,
    validate_file_path,
)


@dataclass
class ApplySuggestionRequest(MCPRequest):
    """Request schema for apply_suggestion MCP tool.
    
    Applies suggested fixes to code files with backup and rollback support.
    
    Example:
        request = ApplySuggestionRequest(
            tool_name="apply_suggestion",
            suggestion_id="suggestion-123",
            target_file="tests/test_example.py",
            create_backup=True,
            validate_syntax=True
        )
    """
    
    suggestion_id: str
    target_file: str
    create_backup: bool = True
    validate_syntax: bool = True
    dry_run: bool = False
    backup_suffix: str = ".backup"
    
    def validate(self) -> List[str]:
        """Validate request data."""
        errors = super().validate()
        
        # Validate suggestion_id
        if not self.suggestion_id:
            errors.append("suggestion_id is required")
        
        # Validate target_file
        if not self.target_file:
            errors.append("target_file is required")
        elif not self.dry_run:
            # Only validate file exists if not dry run
            errors.extend(validate_file_path(self.target_file))
        
        # Validate backup_suffix
        if not self.backup_suffix:
            errors.append("backup_suffix cannot be empty")
        
        return errors


@dataclass
class ApplySuggestionResponse(MCPResponse):
    """Response schema for apply_suggestion MCP tool.
    
    Contains results of applying a fix suggestion to a code file.
    """
    
    suggestion_id: str = ""
    target_file: str = ""
    backup_path: Optional[str] = None
    changes_applied: List[str] = field(default_factory=list)
    syntax_valid: bool = True
    syntax_errors: List[str] = field(default_factory=list)
    rollback_available: bool = False
    diff_preview: str = ""
    warnings: List[str] = field(default_factory=list)
    
    @property
    def has_syntax_errors(self) -> bool:
        """Check if there are syntax errors after applying changes."""
        return not self.syntax_valid or len(self.syntax_errors) > 0
    
    @property
    def can_rollback(self) -> bool:
        """Check if rollback is possible."""
        return self.rollback_available and self.backup_path is not None


__all__ = ["ApplySuggestionRequest", "ApplySuggestionResponse"]