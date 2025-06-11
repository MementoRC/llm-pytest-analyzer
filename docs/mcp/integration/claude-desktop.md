# Claude Desktop Integration

Complete guide for integrating Pytest Analyzer MCP Server with Claude Desktop.

## Configuration

Add to your Claude Desktop configuration file:

```json
{
  "mcpServers": {
    "pytest-analyzer": {
      "command": "python",
      "args": ["-m", "pytest_analyzer.mcp"],
      "cwd": "/path/to/your/project"
    }
  }
}
```

## Usage

Once configured, you can ask Claude to:

- Analyze pytest failures
- Suggest and apply fixes
- Generate test reports
- Check test coverage

Example conversation:
```
"Please run my tests and analyze any failures"
```

Claude will use the MCP server to execute pytest and provide intelligent analysis and suggestions.
