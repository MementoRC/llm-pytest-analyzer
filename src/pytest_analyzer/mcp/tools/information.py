"""Information tools for MCP server.

Provides MCP tool implementations for getting test failure information and summaries.
"""

import logging
from typing import Any, Dict

from mcp.types import CallToolResult, TextContent

from ..facade import MCPAnalyzerFacade
from ..schemas.get_failure_summary import (
    GetFailureSummaryRequest,
    GetFailureSummaryResponse,
)

logger = logging.getLogger(__name__)


async def get_failure_summary(
    arguments: Dict[str, Any], facade: MCPAnalyzerFacade
) -> CallToolResult:
    """MCP tool for getting test failure statistics and categorization.

    This tool retrieves and analyzes test failure data to provide summary statistics,
    groupings, and trends.

    Args:
        arguments: Tool arguments containing:
            - include_details: Include detailed failure information (optional)
            - group_by: How to group failures (optional)
            - time_range: Time range for failures (optional)
            - filter_by_type: Filter by specific failure types (optional)
            - include_resolved: Include resolved failures (optional)
            - max_failures: Maximum failures to return (optional)
        facade: MCPAnalyzerFacade instance for executing the analysis

    Returns:
        CallToolResult with failure summary information

    Raises:
        ValueError: If input validation fails
    """
    try:
        # Create request from arguments
        request = GetFailureSummaryRequest(
            tool_name="get_failure_summary",
            include_details=arguments.get("include_details", True),
            group_by=arguments.get("group_by", "type"),
            time_range=arguments.get("time_range", "last_run"),
            filter_by_type=arguments.get("filter_by_type"),
            include_resolved=arguments.get("include_resolved", False),
            max_failures=arguments.get("max_failures", 100),
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
            f"Getting failure summary (group_by: {request.group_by}, time_range: {request.time_range})"
        )

        # Call facade to process the request
        response: GetFailureSummaryResponse = await facade.get_failure_summary(request)

        # Format response as text content
        if response.success:
            content_text = _format_failure_summary_response(response)
        else:
            content_text = _format_error_response(response)

        return CallToolResult(
            content=[TextContent(type="text", text=content_text)],
            isError=not response.success,
        )

    except Exception as e:
        logger.error(f"Error in get_failure_summary tool: {e}")
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=f"Tool execution failed: {str(e)}",
                )
            ],
            isError=True,
        )


def _format_failure_summary_response(response: GetFailureSummaryResponse) -> str:
    """Format successful failure summary response as readable text."""
    lines = [
        "📊 Test Failure Summary",
        f"Request ID: {response.request_id}",
        f"Execution Time: {response.execution_time_ms}ms",
        "",
        "📈 Statistics:",
        f"• Total Failures: {response.total_failures}",
    ]

    # Add summary stats if available
    if response.summary_stats:
        stats = response.summary_stats
        lines.extend(
            [
                f"• Files Affected: {stats.get('files_affected', 'N/A')}",
                f"• Most Common Type: {stats.get('most_common_type', 'N/A')}",
                f"• Average Failures per File: {stats.get('average_failures_per_file', 0):.1f}",
            ]
        )

    # Add failure groups
    if response.failure_groups:
        lines.extend(["", "🔍 Failure Groups:"])
        for group_name, failures in response.failure_groups.items():
            lines.extend(
                [
                    f"• {group_name} ({len(failures)} failures):",
                    *[
                        f"  - {failure.test_name}: {failure.failure_message[:100]}..."
                        for failure in failures[:3]
                    ],
                ]
            )
            if len(failures) > 3:
                lines.append(f"  ... and {len(failures) - 3} more")

    # Add top failing files
    if response.top_failing_files:
        lines.extend(["", "📁 Top Failing Files:"])
        for file_info in response.top_failing_files[:5]:
            lines.append(
                f"• {file_info.get('file', 'N/A')}: {file_info.get('count', 0)} failures"
            )

    # Add top failing tests
    if response.top_failing_tests:
        lines.extend(["", "🧪 Top Failing Tests:"])
        for test_info in response.top_failing_tests[:5]:
            lines.append(
                f"• {test_info.get('test', 'N/A')}: {test_info.get('count', 0)} failures"
            )

    # Add trends if available
    if response.trends:
        lines.extend(["", "📈 Trends:"])
        for trend_name, trend_value in response.trends.items():
            lines.append(f"• {trend_name}: {trend_value}")

    # Add resolution suggestions
    if response.resolution_suggestions:
        lines.extend(["", "💡 Resolution Suggestions:"])
        for suggestion in response.resolution_suggestions:
            lines.append(f"• {suggestion}")

    return "\n".join(lines)


def _format_error_response(response: GetFailureSummaryResponse) -> str:
    """Format error response as readable text."""
    lines = [
        "❌ Failed to Generate Failure Summary",
        f"Request ID: {response.request_id}",
        f"Execution Time: {response.execution_time_ms}ms",
    ]

    if hasattr(response, "error_message"):
        lines.extend(["", "Error Details:", f"• {response.error_message}"])

    return "\n".join(lines)


# Tool registration information
GET_FAILURE_SUMMARY_TOOL_INFO = {
    "name": "get_failure_summary",
    "description": "Get test failure statistics and categorization",
    "input_schema": {
        "type": "object",
        "properties": {
            "include_details": {
                "type": "boolean",
                "description": "Include detailed failure information",
                "default": True,
            },
            "group_by": {
                "type": "string",
                "description": "How to group failures",
                "enum": ["type", "file", "class", "function", "none"],
                "default": "type",
            },
            "time_range": {
                "type": "string",
                "description": "Time range for failures",
                "enum": ["last_run", "last_hour", "last_day", "all"],
                "default": "last_run",
            },
            "filter_by_type": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Filter by specific failure types",
            },
            "include_resolved": {
                "type": "boolean",
                "description": "Include previously resolved failures",
                "default": False,
            },
            "max_failures": {
                "type": "integer",
                "description": "Maximum failures to return",
                "minimum": 1,
                "maximum": 1000,
                "default": 100,
            },
        },
    },
    "handler": get_failure_summary,
}


__all__ = ["get_failure_summary", "GET_FAILURE_SUMMARY_TOOL_INFO"]
