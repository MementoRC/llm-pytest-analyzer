"""
MCP tool for natural language queries to pytest-analyzer.
"""

from typing import Any, Dict

from mcp.types import CallToolResult, TextContent

from ...core.nlp.query_processor import NLQueryProcessor
from ...core.nlp.response_generator import NLResponseGenerator

NL_QUERY_TOOL_INFO = {
    "name": "nl_query",
    "description": "Query pytest-analyzer using natural language.",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Natural language query"},
            "context": {
                "type": "object",
                "description": "Conversation context",
                "default": {},
            },
        },
        "required": ["query"],
    },
    "handler": "nl_query_tool",
}


async def nl_query_tool(arguments: Dict[str, Any], facade) -> CallToolResult:
    """
    MCP tool handler for natural language queries.
    """
    query = arguments.get("query", "")
    context = arguments.get("context", {})

    processor = NLQueryProcessor()
    responder = NLResponseGenerator()
    result = processor.process_query(query, context)
    text = responder.generate(result)
    return CallToolResult(
        content=[TextContent(type="text", text=text)],
        isError=False if result.get("intent") != "unknown" else True,
    )
