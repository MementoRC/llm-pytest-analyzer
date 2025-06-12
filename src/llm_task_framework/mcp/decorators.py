"""@mcp_tool decorator for registering MCP tools."""

import inspect
from functools import wraps
from typing import Any, Callable, Dict, Optional


def mcp_tool(name: Optional[str] = None):
    """
    Decorator to mark a function or class as an MCP tool endpoint.

    Adds metadata for auto-discovery and generates input/output schemas from the function signature.
    Wraps the function with error handling.

    Args:
        name: Optional tool name override.

    Returns:
        Decorated function or class with MCP tool metadata.
    """

    def decorator(obj: Callable):
        tool_name = name or obj.__name__
        setattr(obj, "__mcp_tool__", True)
        setattr(obj, "__mcp_tool_name__", tool_name)
        setattr(obj, "__mcp_tool_schema__", _generate_schema(obj))

        @wraps(obj)
        def wrapper(*args, **kwargs):
            try:
                return obj(*args, **kwargs)
            except Exception as e:
                # Attach error info for MCP server to handle
                return {"error": str(e), "tool": tool_name}

        wrapper.__mcp_tool__ = True
        wrapper.__mcp_tool_name__ = tool_name
        wrapper.__mcp_tool_schema__ = getattr(obj, "__mcp_tool_schema__", None)
        return wrapper

    return decorator


def _generate_schema(func: Callable) -> Dict[str, Any]:
    """
    Generate a simple schema from the function signature.
    """
    sig = inspect.signature(func)
    params = []
    for name, param in sig.parameters.items():
        param_type = (
            str(param.annotation)
            if param.annotation != inspect.Parameter.empty
            else "Any"
        )
        params.append(
            {
                "name": name,
                "type": param_type,
                "default": param.default
                if param.default != inspect.Parameter.empty
                else None,
            }
        )
    return {
        "name": func.__name__,
        "parameters": params,
        "doc": func.__doc__,
    }
