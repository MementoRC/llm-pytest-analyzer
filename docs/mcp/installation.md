# Installation Guide

This guide covers installing and setting up the Pytest Analyzer MCP Server for use with Claude Desktop and other MCP clients.

## Prerequisites

- **Python 3.10+** (required for MCP SDK compatibility)
- **pytest** installed in your project
- **Claude Desktop** or another MCP client

## Installation Methods

### Method 1: PyPI Installation (Recommended)

```bash
# Install with MCP support
pip install pytest-analyzer[mcp]

# Verify installation
python -m pytest_analyzer.mcp --version
```

### Method 2: Development Installation

```bash
# Clone the repository
git clone https://github.com/MementoRC/llm-pytest-analyzer.git
cd llm-pytest-analyzer

# Install with pixi (recommended)
pixi install
pixi shell

# Or with pip
pip install -e .[mcp]
```

## Claude Desktop Configuration

### Step 1: Locate Configuration File

The Claude Desktop configuration file location depends on your operating system:

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/claude/claude_desktop_config.json`

### Step 2: Add MCP Server Configuration

Create or edit the configuration file:

```json
{
  "mcpServers": {
    "pytest-analyzer": {
      "command": "python",
      "args": ["-m", "pytest_analyzer.mcp"],
      "cwd": "/path/to/your/project",
      "env": {
        "PYTEST_ANALYZER_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

## Testing the Installation

### Test Claude Desktop Integration

1. **Restart Claude Desktop** after configuration changes
2. **Start a new conversation**
3. **Test the connection**:

```
Hi Claude! Can you help me analyze my pytest failures using the pytest-analyzer MCP server?
```

If configured correctly, Claude should respond with access to pytest analysis tools.

---

**Need help?** Check the [Troubleshooting Guide](troubleshooting.md) or [FAQ](faq.md)
