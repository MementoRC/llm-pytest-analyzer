"""Schema definitions for the get_config MCP tool.

This tool retrieves current analyzer configuration settings.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from uuid import uuid4


@dataclass
class GetConfigRequest:
    """Request schema for get_config MCP tool.

    Gets current analyzer configuration settings.

    Example:
        request = GetConfigRequest(
            tool_name="get_config",
            section="llm",
            include_defaults=True,
            include_sensitive=False
        )
    """

    # Required fields first
    tool_name: str

    # Optional fields with defaults
    request_id: str = field(default_factory=lambda: str(uuid4()))
    metadata: Dict[str, Any] = field(default_factory=dict)
    section: Optional[str] = None  # llm, mcp, analysis, etc.
    include_defaults: bool = True
    include_sensitive: bool = False
    format: str = "json"  # json, yaml, dict

    def validate(self) -> List[str]:
        """Validate request data."""
        errors = []

        # Validate common fields
        if not self.tool_name:
            errors.append("tool_name is required")
        if not self.request_id:
            errors.append("request_id is required")

        # Validate section if provided
        if self.section is not None:
            valid_sections = {"llm", "mcp", "analysis", "extraction", "logging", "git"}
            if self.section not in valid_sections:
                errors.append(
                    f"Invalid section '{self.section}'. Must be one of: {valid_sections}"
                )

        # Validate format
        valid_formats = {"json", "yaml", "dict"}
        if self.format not in valid_formats:
            errors.append(
                f"Invalid format '{self.format}'. Must be one of: {valid_formats}"
            )

        return errors

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        from dataclasses import asdict

        return asdict(self)


@dataclass
class GetConfigResponse:
    """Response schema for get_config MCP tool.

    Contains current analyzer configuration data.
    """

    # Required fields first
    success: bool
    request_id: str

    # Optional fields with defaults
    execution_time_ms: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    config_data: Dict[str, Any] = field(default_factory=dict)
    config_source: str = "settings"
    sections: List[str] = field(default_factory=list)
    defaults_included: bool = False
    sensitive_excluded: bool = True
    schema_version: str = "1.0"
    warnings: List[str] = field(default_factory=list)

    def __post_init__(self):
        """Initialize sections list after creation."""
        if not self.sections and self.config_data:
            self.sections = list(self.config_data.keys())

    @property
    def has_config_data(self) -> bool:
        """Check if configuration data is available."""
        return bool(self.config_data)

    @property
    def section_count(self) -> int:
        """Get number of configuration sections."""
        return len(self.sections)

    def get_section(self, section_name: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific section."""
        return self.config_data.get(section_name)

    def has_section(self, section_name: str) -> bool:
        """Check if a configuration section exists."""
        return section_name in self.config_data

    def get_setting(self, section: str, key: str, default: Any = None) -> Any:
        """Get a specific setting value."""
        section_data = self.get_section(section)
        if section_data is None:
            return default
        return section_data.get(key, default)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        from dataclasses import asdict

        return asdict(self)

    def to_json(self) -> str:
        """Convert to JSON string."""
        import json

        return json.dumps(self.to_dict(), indent=2)


__all__ = ["GetConfigRequest", "GetConfigResponse"]
