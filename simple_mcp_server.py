#!/usr/bin/env python3
"""
Simple entry point for pytest-analyzer MCP server compatible with Claude Code.
This uses the simplified server pattern from aider.
"""

if __name__ == "__main__":
    from src.pytest_analyzer.mcp.simple_server import main

    main()
