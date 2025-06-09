"""Analysis tools for MCP server.

Provides MCP tool implementations for pytest output analysis and fix suggestions.
"""

import logging
from typing import Any, Dict

from mcp.types import CallToolResult, TextContent

from ..facade import MCPAnalyzerFacade
from ..schemas.run_and_analyze import RunAndAnalyzeRequest, RunAndAnalyzeResponse
from ..schemas.suggest_fixes import SuggestFixesRequest, SuggestFixesResponse

logger = logging.getLogger(__name__)


async def suggest_fixes(
    arguments: Dict[str, Any], facade: MCPAnalyzerFacade
) -> CallToolResult:
    """MCP tool for generating fix suggestions from raw pytest output.

    This tool accepts raw pytest output string and returns structured fix suggestions
    with code changes, confidence scores, and explanations.

    Args:
        arguments: Tool arguments containing:
            - raw_output: Raw pytest output string (required)
            - max_suggestions: Maximum number of suggestions (optional, default: 10)
            - confidence_threshold: Minimum confidence threshold (optional, default: 0.3)
            - include_alternatives: Include alternative approaches (optional, default: True)
            - filter_by_type: Filter suggestions by type (optional)
        facade: MCPAnalyzerFacade instance for executing the analysis

    Returns:
        CallToolResult with structured fix suggestions or error information

    Raises:
        ValueError: If input validation fails or input is too large
    """
    try:
        # Validate input size early (1MB limit)
        raw_output = arguments.get("raw_output", "")
        if len(raw_output) > 1_000_000:  # 1MB limit
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=f"Input too large: {len(raw_output)} bytes (max 1MB)",
                    )
                ],
                isError=True,
            )

        # Create request from arguments
        request = SuggestFixesRequest(
            tool_name="suggest_fixes",
            raw_output=raw_output,
            max_suggestions=arguments.get("max_suggestions", 10),
            confidence_threshold=arguments.get("confidence_threshold", 0.3),
            include_alternatives=arguments.get("include_alternatives", True),
            filter_by_type=arguments.get("filter_by_type"),
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

        # Detect output format
        detected_format = "text"  # Default
        if raw_output.strip().startswith("{"):
            detected_format = "json"
        elif raw_output.strip().startswith("<?xml") or raw_output.strip().startswith(
            "<"
        ):
            detected_format = "xml"

        logger.info(
            f"Processing pytest output ({len(raw_output)} bytes, detected format: {detected_format})"
        )

        # Call facade to process the request
        response: SuggestFixesResponse = await facade.suggest_fixes(request)

        # Add detected format to metadata
        response.analysis_metadata["detected_format"] = detected_format

        # Format response as text content
        if response.success:
            content_text = _format_success_response(response, detected_format)
        else:
            content_text = _format_error_response(response)

        return CallToolResult(
            content=[TextContent(type="text", text=content_text)],
            isError=not response.success,
        )

    except Exception as e:
        logger.error(f"Error in suggest_fixes tool: {e}")
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=f"Tool execution failed: {str(e)}",
                )
            ],
            isError=True,
        )


def _format_success_response(
    response: SuggestFixesResponse, detected_format: str
) -> str:
    """Format successful response as readable text."""
    lines = [
        "✅ Fix Suggestions Generated Successfully",
        "📊 Analysis Results:",
        f"   • Request ID: {response.request_id}",
        f"   • Execution Time: {response.execution_time_ms}ms",
        f"   • Detected Format: {detected_format}",
        f"   • Suggestions Found: {len(response.suggestions)}",
        f"   • Overall Confidence: {response.confidence_score:.2f}",
        "",
    ]

    if response.parsing_warnings:
        lines.extend(
            [
                "⚠️  Parsing Warnings:",
                *[f"   • {warning}" for warning in response.parsing_warnings],
                "",
            ]
        )

    if response.suggestions:
        lines.append("🔧 Fix Suggestions:")
        for i, suggestion in enumerate(response.suggestions, 1):
            lines.extend(
                [
                    f"   {i}. {suggestion.suggestion_text}",
                    f"      📄 File: {suggestion.file_path or 'N/A'}",
                    f"      📍 Line: {suggestion.line_number or 'N/A'}",
                    f"      🎯 Confidence: {suggestion.confidence_score:.2f}",
                ]
            )

            if suggestion.code_changes:
                lines.append(
                    f"      🛠️  Code Changes: {len(suggestion.code_changes)} modifications"
                )

            if suggestion.explanation:
                lines.append(f"      💡 Explanation: {suggestion.explanation}")

            if suggestion.alternative_approaches:
                lines.append(
                    f"      🔀 Alternatives: {len(suggestion.alternative_approaches)} options"
                )

            lines.append("")
    else:
        lines.append("ℹ️  No fix suggestions generated")

    if response.failures:
        lines.extend(
            [
                f"🚨 Test Failures Detected: {len(response.failures)}",
                *[
                    f"   • {failure.test_name}: {failure.failure_type}"
                    for failure in response.failures[:5]
                ],
            ]
        )
        if len(response.failures) > 5:
            lines.append(f"   ... and {len(response.failures) - 5} more")

    return "\n".join(lines)


def _format_error_response(response: SuggestFixesResponse) -> str:
    """Format error response as readable text."""
    lines = [
        "❌ Fix Suggestion Generation Failed",
        "📊 Error Details:",
        f"   • Request ID: {response.request_id}",
        f"   • Execution Time: {response.execution_time_ms}ms",
    ]

    if response.parsing_warnings:
        lines.extend(
            [
                "⚠️  Issues Encountered:",
                *[f"   • {warning}" for warning in response.parsing_warnings],
            ]
        )

    return "\n".join(lines)


# Tool registration information
SUGGEST_FIXES_TOOL_INFO = {
    "name": "suggest_fixes",
    "description": "Generate fix suggestions from raw pytest output",
    "input_schema": {
        "type": "object",
        "properties": {
            "raw_output": {
                "type": "string",
                "description": "Raw pytest output string to analyze",
                "maxLength": 1000000,  # 1MB limit
            },
            "max_suggestions": {
                "type": "integer",
                "description": "Maximum number of suggestions to generate",
                "minimum": 1,
                "maximum": 100,
                "default": 10,
            },
            "confidence_threshold": {
                "type": "number",
                "description": "Minimum confidence threshold for suggestions",
                "minimum": 0.0,
                "maximum": 1.0,
                "default": 0.3,
            },
            "include_alternatives": {
                "type": "boolean",
                "description": "Include alternative approaches in suggestions",
                "default": True,
            },
            "filter_by_type": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Filter suggestions by failure type",
            },
        },
        "required": ["raw_output"],
    },
    "handler": suggest_fixes,
}


async def run_and_analyze(
    arguments: Dict[str, Any], facade: MCPAnalyzerFacade
) -> CallToolResult:
    """MCP tool for running pytest and analyzing results.

    This tool executes pytest with specified parameters and analyzes the results
    to generate fix suggestions.

    Args:
        arguments: Tool arguments containing:
            - test_pattern: Path or pattern to run tests against (optional)
            - pytest_args: Additional pytest arguments (optional)
            - timeout: Timeout in seconds (optional, default: 300)
            - working_directory: Working directory for test execution (optional)
            - capture_output: Whether to capture output (optional, default: true)
            - max_suggestions: Maximum suggestions to return (optional, default: 10)
            - environment_vars: Environment variables for test execution (optional)
        facade: MCPAnalyzerFacade instance for executing the analysis

    Returns:
        CallToolResult with test execution results and fix suggestions

    Raises:
        ValueError: If input validation fails
    """
    try:
        # Create request from arguments
        request = RunAndAnalyzeRequest(
            tool_name="run_and_analyze",
            test_pattern=arguments.get("test_pattern", ""),
            pytest_args=arguments.get("pytest_args", []),
            timeout=arguments.get("timeout", 300),
            working_directory=arguments.get("working_directory"),
            capture_output=arguments.get("capture_output", True),
            max_suggestions=arguments.get("max_suggestions", 10),
            environment_vars=arguments.get("environment_vars", {}),
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
            f"Running pytest with pattern: {request.test_pattern or 'all tests'}"
        )

        # Call facade to process the request
        response: RunAndAnalyzeResponse = await facade.run_and_analyze(request)

        # Format response as text content
        if response.success:
            content_text = _format_run_and_analyze_response(response)
        else:
            content_text = _format_error_response(response)

        return CallToolResult(
            content=[TextContent(type="text", text=content_text)],
            isError=not response.success,
        )

    except Exception as e:
        logger.error(f"Error in run_and_analyze tool: {e}")
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=f"Tool execution failed: {str(e)}",
                )
            ],
            isError=True,
        )


def _format_run_and_analyze_response(response: RunAndAnalyzeResponse) -> str:
    """Format successful run and analyze response as readable text."""
    lines = [
        "✅ Test Execution and Analysis Complete",
        "📊 Results Summary:",
        f"   • Request ID: {response.request_id}",
        f"   • Execution Time: {response.execution_time_ms}ms",
        f"   • Tests Run: {response.tests_run}",
        f"   • Tests Passed: {response.tests_passed}",
        f"   • Tests Failed: {response.tests_failed}",
        f"   • Tests Skipped: {response.tests_skipped}",
        f"   • Pass Rate: {response.pass_rate:.1f}%",
        "",
    ]

    if response.warnings:
        lines.extend(
            [
                "⚠️  Warnings:",
                *[f"   • {warning}" for warning in response.warnings],
                "",
            ]
        )

    if response.failures:
        lines.extend(
            [
                "🚨 Test Failures:",
                *[
                    f"   • {failure.test_name}: {failure.failure_message}"
                    for failure in response.failures[:5]
                ],
            ]
        )
        if len(response.failures) > 5:
            lines.append(f"   ... and {len(response.failures) - 5} more")
        lines.append("")

    if response.suggestions:
        lines.append("🔧 Fix Suggestions:")
        for i, suggestion in enumerate(response.suggestions, 1):
            lines.extend(
                [
                    f"   {i}. {suggestion.suggestion_text}",
                    f"      📄 File: {suggestion.file_path or 'N/A'}",
                    f"      📍 Line: {suggestion.line_number or 'N/A'}",
                    f"      🎯 Confidence: {suggestion.confidence_score:.2f}",
                ]
            )
            if suggestion.explanation:
                lines.append(f"      💡 Explanation: {suggestion.explanation}")
            lines.append("")
    else:
        lines.append("✨ All tests passed - no fixes needed!")

    return "\n".join(lines)


# Tool registration information
RUN_AND_ANALYZE_TOOL_INFO = {
    "name": "run_and_analyze",
    "description": "Run pytest and analyze results to generate fix suggestions",
    "input_schema": {
        "type": "object",
        "properties": {
            "test_pattern": {
                "type": "string",
                "description": "Path or pattern to run tests against",
                "default": "",
            },
            "pytest_args": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Additional pytest arguments",
                "default": [],
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds",
                "minimum": 1,
                "maximum": 3600,
                "default": 300,
            },
            "working_directory": {
                "type": "string",
                "description": "Working directory for test execution",
            },
            "capture_output": {
                "type": "boolean",
                "description": "Whether to capture output",
                "default": True,
            },
            "max_suggestions": {
                "type": "integer",
                "description": "Maximum suggestions to return",
                "minimum": 1,
                "maximum": 100,
                "default": 10,
            },
            "environment_vars": {
                "type": "object",
                "description": "Environment variables for test execution",
                "additionalProperties": {"type": "string"},
                "default": {},
            },
        },
    },
    "handler": run_and_analyze,
}


__all__ = [
    "suggest_fixes",
    "run_and_analyze",
    "SUGGEST_FIXES_TOOL_INFO",
    "RUN_AND_ANALYZE_TOOL_INFO",
]
