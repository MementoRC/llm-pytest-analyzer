"""Configuration tools for MCP server.

Provides MCP tool implementations for updating analyzer configuration settings.
"""

import logging
from typing import Any, Dict

from mcp.types import CallToolResult, TextContent

from ..facade import MCPAnalyzerFacade
from ..schemas.update_config import (
    UpdateConfigRequest,
    UpdateConfigResponse,
)

logger = logging.getLogger(__name__)


async def update_config(
    arguments: Dict[str, Any], facade: MCPAnalyzerFacade
) -> CallToolResult:
    """MCP tool for updating analyzer configuration settings.

    This tool updates analyzer configuration settings, optionally validating and/or creating a backup.

    Args:
        arguments: Tool arguments containing:
            - config_updates: Dict of configuration updates (required)
            - validate_only: Only validate changes, do not apply (optional)
            - create_backup: Create a backup before applying (optional)
            - section: Section to update (optional)
            - merge_strategy: How to apply updates (merge, replace, append) (optional)
        facade: MCPAnalyzerFacade instance for executing the update

    Returns:
        CallToolResult with update results

    Raises:
        ValueError: If input validation fails
    """
    try:
        # Create request from arguments
        request = UpdateConfigRequest(
            tool_name="update_config",
            config_updates=arguments.get("config_updates", {}),
            validate_only=arguments.get("validate_only", False),
            create_backup=arguments.get("create_backup", True),
            section=arguments.get("section"),
            merge_strategy=arguments.get("merge_strategy", "merge"),
            metadata=arguments.get("metadata", {}),
        )

        # Validate request
        errors = request.validate()
        if errors:
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=f"Validation errors: {', '.join(errors)}",
                    )
                ],
                isError=True,
            )

        logger.info(
            f"Updating configuration (section: {request.section}, merge_strategy: {request.merge_strategy}, validate_only: {request.validate_only})"
        )

        # Call facade to process the request
        response: UpdateConfigResponse = await facade.update_config(request)

        # Format response as text content
        if response.success:
            content_text = _format_update_config_response(response)
        else:
            content_text = _format_update_config_error_response(response)

        return CallToolResult(
            content=[TextContent(type="text", text=content_text)],
            isError=not response.success,
        )

    except Exception as e:
        logger.error(f"Error in update_config tool: {e}")
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=f"Tool execution failed: {str(e)}",
                )
            ],
            isError=True,
        )


def _format_update_config_response(response: UpdateConfigResponse) -> str:
    """Format successful update config response as readable text."""
    lines = [
        "✅ Configuration Update Successful",
        f"Request ID: {response.request_id}",
        f"Execution Time: {response.execution_time_ms}ms",
        "",
        f"Updated Fields: {', '.join(response.updated_fields) if response.updated_fields else 'None'}",
        f"Config Version: {response.config_version}",
    ]

    if response.backup_path:
        lines.append(f"Backup Path: {response.backup_path}")

    if response.applied_changes:
        lines.append("")
        lines.append("🔧 Applied Changes:")
        for key, value in response.applied_changes.items():
            lines.append(f"• {key}: {value}")

    if response.warnings:
        lines.append("")
        lines.append("⚠️ Warnings:")
        for warning in response.warnings:
            lines.append(f"• {warning}")

    if response.can_rollback:
        lines.append("")
        lines.append("↩️ Rollback is available.")

    return "\n".join(lines)


def _format_update_config_error_response(response: UpdateConfigResponse) -> str:
    """Format error response as readable text."""
    lines = [
        "❌ Configuration Update Failed",
        f"Request ID: {response.request_id}",
        f"Execution Time: {response.execution_time_ms}ms",
    ]

    if response.validation_errors:
        lines.append("")
        lines.append("Validation Errors:")
        for err in response.validation_errors:
            lines.append(f"• {err}")

    if response.warnings:
        lines.append("")
        lines.append("⚠️ Warnings:")
        for warning in response.warnings:
            lines.append(f"• {warning}")

    return "\n".join(lines)


UPDATE_CONFIG_TOOL_INFO = {
    "name": "update_config",
    "description": "Update analyzer configuration settings (with validation and backup options)",
    "input_schema": {
        "type": "object",
        "properties": {
            "config_updates": {
                "type": "object",
                "description": "Dictionary of configuration updates to apply (required)",
            },
            "validate_only": {
                "type": "boolean",
                "description": "Only validate changes, do not apply",
                "default": False,
            },
            "create_backup": {
                "type": "boolean",
                "description": "Create a backup before applying changes",
                "default": True,
            },
            "section": {
                "type": ["string", "null"],
                "description": "Configuration section to update (llm, mcp, analysis, extraction, logging, git)",
            },
            "merge_strategy": {
                "type": "string",
                "description": "How to apply updates: merge, replace, or append",
                "enum": ["merge", "replace", "append"],
                "default": "merge",
            },
            "metadata": {
                "type": "object",
                "description": "Optional metadata for the request",
            },
        },
        "required": ["config_updates"],
    },
    "handler": update_config,
}


__all__ = [
    "update_config",
    "UPDATE_CONFIG_TOOL_INFO",
]
