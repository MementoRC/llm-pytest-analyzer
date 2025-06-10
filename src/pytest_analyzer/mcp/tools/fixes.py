"""Fix application tools for MCP server.

Implements the MCP tool for safely applying fix suggestions to code files,
with backup, rollback, and optional Git integration.
"""

import logging
from typing import Any, Dict, Optional

from mcp.types import CallToolResult, TextContent

from ..facade import MCPAnalyzerFacade
from ..schemas.apply_suggestion import (
    ApplySuggestionRequest,
    ApplySuggestionResponse,
)

logger = logging.getLogger(__name__)


async def apply_suggestion(
    arguments: Dict[str, Any], facade: MCPAnalyzerFacade
) -> CallToolResult:
    """MCP tool for safely applying fix suggestions to code files.

    This tool applies a fix suggestion to a code file, with backup, rollback,
    and optional Git integration.

    Args:
        arguments: Tool arguments containing:
            - suggestion_id: ID of the suggestion to apply (required)
            - target_file: Path to the file to apply the suggestion to (required)
            - create_backup: Whether to create a backup before applying (default: True)
            - validate_syntax: Whether to validate syntax after applying (default: True)
            - dry_run: If True, do not actually write changes (default: False)
            - backup_suffix: Suffix for backup files (default: ".backup")
        facade: MCPAnalyzerFacade instance for executing the operation

    Returns:
        CallToolResult with application result and rollback info

    Raises:
        ValueError: If input validation fails or file permissions are insufficient
    """
    from ..security import SecurityError
    from ..server import PytestAnalyzerMCPServer

    try:
        # Security: Validate and sanitize input
        server: Optional[PytestAnalyzerMCPServer] = getattr(facade, "server", None)
        if server and hasattr(server, "security_manager"):
            try:
                server.security_manager.validate_tool_input(
                    "apply_suggestion", arguments, read_only=False
                )
            except SecurityError as sec_err:
                return CallToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text=f"Security error: {str(sec_err)}",
                        )
                    ],
                    isError=True,
                )

        # Create request from arguments
        request = ApplySuggestionRequest(
            tool_name="apply_suggestion",
            suggestion_id=arguments.get("suggestion_id", ""),
            target_file=arguments.get("target_file", ""),
            create_backup=arguments.get("create_backup", True),
            validate_syntax=arguments.get("validate_syntax", True),
            dry_run=arguments.get("dry_run", False),
            backup_suffix=arguments.get("backup_suffix", ".backup"),
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
            f"Applying suggestion {request.suggestion_id} to {request.target_file} (dry_run={request.dry_run})"
        )

        # Call facade to process the request
        response: ApplySuggestionResponse = await facade.apply_suggestion(request)

        # Format response as text content
        content_text = _format_apply_suggestion_response(response)

        return CallToolResult(
            content=[TextContent(type="text", text=content_text)],
            isError=not response.success,
        )

    except Exception as e:
        logger.error(f"Error in apply_suggestion tool: {e}")
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=f"Tool execution failed: {str(e)}",
                )
            ],
            isError=True,
        )


def _format_apply_suggestion_response(response: ApplySuggestionResponse) -> str:
    """Format apply_suggestion response as readable text."""
    lines = [
        "✅ Fix Suggestion Applied"
        if response.success
        else "❌ Failed to Apply Suggestion",
        f"Request ID: {response.request_id}",
        f"Suggestion ID: {response.suggestion_id}",
        f"Target File: {response.target_file}",
        f"Execution Time: {response.execution_time_ms}ms",
        "",
    ]

    if response.success:
        if response.changes_applied:
            lines.append(f"🛠️  Changes Applied: {', '.join(response.changes_applied)}")
        if response.backup_path:
            lines.append(f"💾 Backup Created: {response.backup_path}")
        if response.syntax_valid:
            lines.append("✅ Syntax check passed")
        else:
            lines.append("❗ Syntax errors detected after applying changes")
        if response.can_rollback:
            lines.append("↩️  Rollback available")
        if response.warnings:
            lines.append("⚠️  Warnings:")
            lines.extend([f"   • {w}" for w in response.warnings])
        if response.diff_preview:
            lines.append("")
            lines.append("🔍 Changes Preview:")
            lines.append(response.diff_preview)
    else:
        if response.warnings:
            lines.append("⚠️  Warnings:")
            lines.extend([f"   • {w}" for w in response.warnings])
        if response.syntax_errors:
            lines.append("❗ Syntax Errors:")
            lines.extend([f"   • {e}" for e in response.syntax_errors])
        if response.backup_path:
            lines.append(f"💾 Backup Created: {response.backup_path}")
        if response.can_rollback:
            lines.append("↩️  Rollback available")

    return "\n".join(lines)


APPLY_SUGGESTION_TOOL_INFO = {
    "name": "apply_suggestion",
    "description": "Safely apply a fix suggestion to a code file with backup and rollback support",
    "input_schema": {
        "type": "object",
        "properties": {
            "suggestion_id": {
                "type": "string",
                "description": "ID of the suggestion to apply",
            },
            "target_file": {
                "type": "string",
                "description": "Path to the file to apply the suggestion to",
            },
            "create_backup": {
                "type": "boolean",
                "description": "Whether to create a backup before applying",
                "default": True,
            },
            "validate_syntax": {
                "type": "boolean",
                "description": "Whether to validate syntax after applying",
                "default": True,
            },
            "dry_run": {
                "type": "boolean",
                "description": "If True, do not actually write changes",
                "default": False,
            },
            "backup_suffix": {
                "type": "string",
                "description": "Suffix for backup files",
                "default": ".backup",
            },
        },
        "required": ["suggestion_id", "target_file"],
    },
    "handler": apply_suggestion,
}


__all__ = [
    "apply_suggestion",
    "APPLY_SUGGESTION_TOOL_INFO",
]
