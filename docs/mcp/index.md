# MCP Server Integration

> **🚀 Transform your pytest debugging with AI-powered analysis through Claude AI's Model Context Protocol (MCP)**

## Overview

The pytest-analyzer MCP server provides intelligent test failure analysis capabilities directly within Claude AI environments. This integration enables seamless pytest debugging workflows with AI-powered fix suggestions, comprehensive failure analysis, and automated code improvements.

## Features

### 🔍 **Core Analysis Tools**
- **`analyze_pytest_output`**: Parse pytest reports and generate intelligent fix suggestions
- **`run_and_analyze`**: Execute pytest and analyze results in a single operation
- **`suggest_fixes`**: Generate targeted fixes from raw pytest output

### 🛠️ **Fix Application**
- **`apply_suggestion`**: Safely apply fixes with backup/rollback
- **`validate_suggestion`**: Test fixes in isolated environments before applying

### 📊 **Information Tools**
- **`get_failure_summary`**: Statistical analysis and failure categorization
- **`get_test_coverage`**: Coverage analysis and reporting

### ⚙️ **Configuration**
- **`get_config`**: Retrieve current analyzer settings
- **`update_config`**: Safely modify configuration

## Architecture

```

   Claude AI     →  ←   MCP Server     →  ←  Pytest Suite
   Assistant           (This Package)        & Test Files

                               ↓
                               ↓

                         Analysis Engine
                         • LLM Analysis
                         • Pattern Recog
                         • Fix Synthesis

```

## Quick Start

### 1. Installation

```bash
# Install with MCP support
pip install pytest-analyzer[mcp]

# Or with pixi
pixi add pytest-analyzer[mcp]
```

### 2. Configuration

Create `~/.config/claude/config.json`:

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

### 3. Basic Usage

In Claude AI:

```
Can you analyze my failing tests and suggest fixes?
```

The MCP server will automatically:
1. Run your pytest suite
2. Analyze any failures
3. Generate intelligent fix suggestions
4. Optionally apply fixes with your approval

## Advanced Configuration

### Environment Variables

```bash
# LLM Service Configuration
export ANTHROPIC_API_KEY="your-key"
export OPENAI_API_KEY="your-key"

# Analysis Settings
export PYTEST_ANALYZER_MAX_SUGGESTIONS=5
export PYTEST_ANALYZER_CONFIDENCE_THRESHOLD=0.7
```

### Project Configuration

Create `pytest-analyzer.yaml` in your project root:

```yaml
llm:
  provider: "anthropic"  # or "openai"
  model: "claude-3-sonnet-20240229"

analysis:
  max_suggestions_per_failure: 3
  min_confidence_threshold: 0.6

fixes:
  backup_before_apply: true
  validate_before_apply: true
```

## Tool Reference

### Core Analysis

#### `analyze_pytest_output`

Analyze pytest output files and generate fix suggestions.

**Parameters:**
- `output_file`: Path to pytest output file (JSON/XML)
- `max_suggestions`: Maximum suggestions per failure (default: 3)
- `min_confidence`: Minimum confidence threshold (default: 0.6)

#### `run_and_analyze`

Execute pytest and analyze results in one operation.

**Parameters:**
- `test_pattern`: Test patterns to run (optional)
- `pytest_args`: Additional pytest arguments
- `timeout`: Execution timeout in seconds

#### `suggest_fixes`

Generate fix suggestions from raw pytest output.

**Parameters:**
- `pytest_output`: Raw pytest output text
- `context_files`: Additional files for context
- `max_suggestions`: Maximum suggestions to generate

### Fix Application

#### `apply_suggestion`

Apply fix suggestions with safety measures.

**Parameters:**
- `suggestion_id`: ID of suggestion to apply
- `dry_run`: Preview changes without applying (default: false)
- `backup`: Create backup before applying (default: true)

#### `validate_suggestion`

Test fix suggestions in isolated environment.

**Parameters:**
- `suggestion_id`: ID of suggestion to validate
- `test_command`: Custom test command (optional)

### Information

#### `get_failure_summary`

Get statistical summary of test failures.

**Parameters:**
- `group_by`: Grouping method ("file", "type", "location")
- `time_range`: Time range for analysis (optional)
- `include_trends`: Include trend analysis (default: false)

#### `get_test_coverage`

Retrieve test coverage information.

**Parameters:**
- `format`: Output format ("json", "html", "text")
- `include_missing`: Include missing coverage (default: true)

### Configuration

#### `get_config`

Retrieve current configuration.

**Parameters:**
- `section`: Specific config section (optional)
- `format`: Output format ("json", "yaml")

#### `update_config`

Update configuration settings.

**Parameters:**
- `updates`: Configuration updates as JSON
- `validate`: Validate before applying (default: true)
- `backup`: Backup current config (default: true)

## Integration Patterns

### Workflow Integration

```python
# Example: Automated test-fix cycle
async def auto_fix_workflow():
    # 1. Run tests and analyze
    result = await run_and_analyze(
        test_pattern="tests/",
        max_suggestions=3
    )

    # 2. Review suggestions
    for suggestion in result.suggestions:
        if suggestion.confidence > 0.8:
            # 3. Validate in isolation
            validation = await validate_suggestion(
                suggestion_id=suggestion.id
            )

            if validation.success:
                # 4. Apply with backup
                await apply_suggestion(
                    suggestion_id=suggestion.id,
                    backup=True
                )
```

### Error Handling

The MCP server provides structured error responses:

```json
{
  "error": {
    "code": "ANALYSIS_FAILED",
    "message": "Unable to parse pytest output",
    "details": {
      "file": "report.xml",
      "line": 45,
      "suggestion": "Check file format and permissions"
    }
  }
}
```

## Troubleshooting

### Common Issues

**Connection Problems:**
- Verify MCP server configuration in Claude AI settings
- Check that pytest-analyzer is installed with MCP support
- Ensure working directory is set correctly

**Analysis Failures:**
- Confirm pytest output format is supported (JSON/XML)
- Check file permissions and accessibility
- Verify LLM API keys are configured

**Performance Issues:**
- Reduce `max_suggestions` for large test suites
- Use `test_pattern` to limit analysis scope
- Consider increasing timeout for complex projects

### Debug Mode

Enable debug logging:

```bash
export PYTEST_ANALYZER_DEBUG=true
export PYTEST_ANALYZER_LOG_LEVEL=DEBUG
```

### Support

For issues and questions:
- GitHub Issues: [Report bugs and feature requests](https://github.com/MementoRC/llm-pytest-analyzer/issues)
- Documentation: [Full documentation](https://memento.gitbook.io/llm-pytest-analyzer/)
- Examples: [Usage examples](https://github.com/MementoRC/llm-pytest-analyzer/tree/main/examples)

## Security

The MCP server implements comprehensive security measures:

- **File Access Control**: Limited to project directory
- **Command Validation**: Sanitized pytest arguments
- **API Key Protection**: Secure credential handling
- **Backup Safety**: Automatic backup before modifications

See [Security Guide](security.md) for detailed information.

---

**🎯 Ready to transform your pytest debugging experience with AI-powered analysis!**
