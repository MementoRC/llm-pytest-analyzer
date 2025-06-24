from unittest.mock import MagicMock, patch

import pytest
from mcp.types import TextContent

from src.pytest_analyzer.mcp.security import CircuitBreakerState
from src.pytest_analyzer.mcp.server import PytestAnalyzerMCPServer
from src.pytest_analyzer.utils.config_types import SecuritySettings, Settings

# Fixtures


@pytest.fixture
def rate_limit_mcp_settings():
    security_settings = SecuritySettings(
        max_requests_per_window=2,
        rate_limit_window_seconds=10,
        enable_circuit_breaker=True,
        circuit_breaker_failures=2,
        circuit_breaker_timeout_seconds=20,
        circuit_breaker_successes_to_close=1,
    )
    # Create a complete Settings object
    settings = Settings()
    settings.mcp.security = security_settings
    return settings


@pytest.fixture
def mcp_server(rate_limit_mcp_settings):
    server = PytestAnalyzerMCPServer(settings=rate_limit_mcp_settings)

    # Mock tool handler
    mock_handler = MagicMock(return_value={"status": "ok"})
    server.register_tool(
        name="test_tool",
        description="A test tool",
        handler=mock_handler,
    )

    # Mock failing tool handler
    failing_handler = MagicMock(side_effect=ValueError("Tool failed!"))
    server.register_tool(
        name="failing_tool",
        description="A tool that always fails",
        handler=failing_handler,
    )

    # Setup handlers (list_tools, call_tool)
    server._setup_mcp_handlers()
    return server


# Tests


@pytest.mark.asyncio
async def test_call_tool_rate_limiting(mcp_server):
    call_tool_func = mcp_server.mcp_server.tool_handler

    # First two calls should succeed
    await call_tool_func(name="test_tool", arguments={})
    await call_tool_func(name="test_tool", arguments={})

    # Third call should be rate limited
    result = await call_tool_func(name="test_tool", arguments={})
    assert isinstance(result[0], TextContent)
    assert "Security error: Rate limit of 2 req/window exceeded" in result[0].text


@pytest.mark.asyncio
async def test_call_tool_rate_limit_window_resets(mcp_server):
    call_tool_func = mcp_server.mcp_server.tool_handler

    with patch("time.time") as mock_time:
        mock_time.return_value = 1000
        await call_tool_func(name="test_tool", arguments={})
        await call_tool_func(name="test_tool", arguments={})

        result = await call_tool_func(name="test_tool", arguments={})
        assert "Rate limit" in result[0].text

        mock_time.return_value = 1011  # Move time forward

        result = await call_tool_func(name="test_tool", arguments={})
        assert "Security error" not in str(result)
        assert mcp_server._registered_handlers["test_tool"].call_count == 3


@pytest.mark.asyncio
async def test_circuit_breaker_integration_opens(mcp_server):
    call_tool_func = mcp_server.mcp_server.tool_handler

    # First two calls fail, opening the circuit
    await call_tool_func(name="failing_tool", arguments={})
    result = await call_tool_func(name="failing_tool", arguments={})
    assert "Error executing tool" in result[0].text

    # Third call should be blocked by open circuit
    result = await call_tool_func(name="failing_tool", arguments={})
    assert isinstance(result[0], TextContent)
    assert (
        "Security error: Circuit breaker for tool 'failing_tool' is open"
        in result[0].text
    )


@pytest.mark.asyncio
async def test_circuit_breaker_integration_half_open_and_close(mcp_server):
    call_tool_func = mcp_server.mcp_server.tool_handler

    with patch("time.time") as mock_time:
        mock_time.return_value = 1000

        # Open the circuit with failing_tool
        await call_tool_func(name="failing_tool", arguments={})
        await call_tool_func(name="failing_tool", arguments={})

        # Move time forward to allow for HALF_OPEN state
        mock_time.return_value = 1021

        # Now, let's mock the handler to succeed
        mcp_server._registered_handlers["failing_tool"].side_effect = None
        mcp_server._registered_handlers["failing_tool"].return_value = {
            "status": "fixed"
        }

        # This call should be allowed in HALF_OPEN state and succeed
        result = await call_tool_func(name="failing_tool", arguments={})
        assert "Security error" not in str(result)

        # The breaker requires 1 success to close. It should be closed now.
        breaker = mcp_server.security_manager._get_breaker("failing_tool")
        assert breaker["state"] == CircuitBreakerState.CLOSED

        # The next call should also succeed
        result = await call_tool_func(name="failing_tool", arguments={})
        assert "Security error" not in str(result)


@pytest.mark.asyncio
async def test_input_sanitization_in_call_tool(mcp_server):
    call_tool_func = mcp_server.mcp_server.tool_handler
    mock_handler = mcp_server._registered_handlers["test_tool"]

    bad_input = {"param": "<script>alert(1)</script>"}
    await call_tool_func(name="test_tool", arguments=bad_input)

    # Check that the handler was called with sanitized input
    mock_handler.assert_called_once()
    call_args = mock_handler.call_args[0][0]
    assert call_args["param"] == "&lt;script&gt;alert(1)&lt;/script&gt;"
