"""Schema definitions for the update_config MCP tool.

This tool updates analyzer configuration settings.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from . import (
    MCPRequest,
    MCPResponse,
)


@dataclass
class UpdateConfigRequest(MCPRequest):
    """Request schema for update_config MCP tool.

    Updates analyzer configuration settings.

    Example:
        request = UpdateConfigRequest(
            tool_name="update_config",
            config_updates={
                "llm": {
                    "model": "gpt-4",
                    "temperature": 0.7
                }
            },
            validate_only=False,
            create_backup=True
        )
    """

    config_updates: Dict[str, Any]
    validate_only: bool = False
    create_backup: bool = True
    section: Optional[str] = None
    merge_strategy: str = "merge"  # merge, replace, append

    def validate(self) -> List[str]:
        """Validate request data."""
        errors = super().validate()

        # Validate config_updates
        if not self.config_updates:
            errors.append("config_updates is required and cannot be empty")

        # Validate section if provided
        if self.section is not None:
            valid_sections = {"llm", "mcp", "analysis", "extraction", "logging", "git"}
            if self.section not in valid_sections:
                errors.append(
                    f"Invalid section '{self.section}'. Must be one of: {valid_sections}"
                )

        # Validate merge_strategy
        valid_strategies = {"merge", "replace", "append"}
        if self.merge_strategy not in valid_strategies:
            errors.append(
                f"Invalid merge_strategy '{self.merge_strategy}'. Must be one of: {valid_strategies}"
            )

        # Validate specific configuration values
        errors.extend(self._validate_config_values())

        return errors

    def _validate_config_values(self) -> List[str]:
        """Validate specific configuration values."""
        errors = []

        # Validate LLM configuration
        if "llm" in self.config_updates:
            llm_config = self.config_updates["llm"]
            if "temperature" in llm_config:
                temp = llm_config["temperature"]
                if not isinstance(temp, (int, float)) or not (0.0 <= temp <= 2.0):
                    errors.append(
                        "llm.temperature must be a number between 0.0 and 2.0"
                    )

            if "max_tokens" in llm_config:
                max_tokens = llm_config["max_tokens"]
                if not isinstance(max_tokens, int) or max_tokens <= 0:
                    errors.append("llm.max_tokens must be a positive integer")

        # Validate MCP configuration
        if "mcp" in self.config_updates:
            mcp_config = self.config_updates["mcp"]
            if "port" in mcp_config:
                port = mcp_config["port"]
                if not isinstance(port, int) or not (1024 <= port <= 65535):
                    errors.append("mcp.port must be an integer between 1024 and 65535")

        return errors


@dataclass
class UpdateConfigResponse(MCPResponse):
    """Response schema for update_config MCP tool.

    Contains results of configuration update operation.
    """

    updated_fields: List[str] = field(default_factory=list)
    validation_errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    backup_path: Optional[str] = None
    config_version: str = "1.0"
    applied_changes: Dict[str, Any] = field(default_factory=dict)
    rollback_available: bool = False

    def __post_init__(self):
        """Set success status based on validation errors."""
        if self.validation_errors:
            self.success = False

    @property
    def has_validation_errors(self) -> bool:
        """Check if there are validation errors."""
        return len(self.validation_errors) > 0

    @property
    def has_warnings(self) -> bool:
        """Check if there are warnings."""
        return len(self.warnings) > 0

    @property
    def changes_applied(self) -> int:
        """Get number of changes applied."""
        return len(self.updated_fields)

    @property
    def can_rollback(self) -> bool:
        """Check if rollback is available."""
        return self.rollback_available and self.backup_path is not None

    def get_updated_sections(self) -> List[str]:
        """Get list of configuration sections that were updated."""
        sections = set()
        for field_name in self.updated_fields:
            if "." in field_name:
                section = field_name.split(".")[0]
                sections.add(section)
        return list(sections)


__all__ = ["UpdateConfigRequest", "UpdateConfigResponse"]
