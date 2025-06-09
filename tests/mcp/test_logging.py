"""Test suite for MCP logging functionality."""

import json
import logging

import pytest

from pytest_analyzer.mcp.logging import MCPLogger, log_tool_execution


@pytest.fixture
def mcp_logger():
    """Fixture providing configured MCPLogger instance."""
    return MCPLogger("test_mcp")


@pytest.fixture
def captured_logs(caplog):
    """Fixture for capturing log output."""
    caplog.set_level(logging.DEBUG)
    return caplog


class TestMCPLogger:
    def test_initialization(self):
        """Test logger initialization."""
        logger = MCPLogger("test")
        assert logger.logger.name == "test"
        assert isinstance(logger.metrics, dict)

    def test_sanitize_message(self, mcp_logger):
        """Test message sanitization."""
        sensitive_data = {
            "username": "test",
            "password": "secret123",
            "token": "abc123",
            "data": {"key": "sensitive"},
        }

        sanitized = json.loads(mcp_logger.sanitize_message(sensitive_data))

        assert sanitized["password"] == "***"
        assert sanitized["token"] == "***"
        assert sanitized["data"]["key"] == "***"
        assert sanitized["username"] == "test"

    def test_log_protocol_message(self, mcp_logger, captured_logs):
        """Test protocol message logging."""
        test_message = {"command": "test", "token": "secret"}
        mcp_logger.log_protocol_message("SEND", test_message)

        assert len(captured_logs.records) == 1
        record = captured_logs.records[0]

        assert "MCP SEND" in record.message
        assert "secret" not in record.message
        assert "***" in record.message
        assert record.levelno == logging.DEBUG

    def test_log_tool_execution(self, mcp_logger, captured_logs):
        """Test tool execution logging."""
        mcp_logger.log_tool_execution(
            tool_name="test_tool", duration_ms=100.0, success=True
        )

        assert len(captured_logs.records) == 1
        record = captured_logs.records[0]

        assert "test_tool" in record.message
        assert "success" in record.message
        assert "100" in record.message
        assert record.levelno == logging.INFO

        # Check metrics
        metrics = mcp_logger.get_metrics()
        assert "test_tool" in metrics
        assert metrics["test_tool"].duration_ms == 100.0
        assert metrics["test_tool"].success is True

    def test_log_tool_execution_failure(self, mcp_logger, captured_logs):
        """Test tool execution logging with failure."""
        error_msg = "Test error"
        mcp_logger.log_tool_execution(
            tool_name="failed_tool", duration_ms=50.0, success=False, error=error_msg
        )

        assert len(captured_logs.records) == 1
        record = captured_logs.records[0]

        assert "failed_tool" in record.message
        assert "failed" in record.message
        assert error_msg in record.message
        assert record.levelno == logging.ERROR

    def test_log_security_event(self, mcp_logger, captured_logs):
        """Test security event logging."""
        event_details = {
            "user": "test_user",
            "action": "login",
            "token": "secret_token",
        }

        mcp_logger.log_security_event("AUTH", event_details)

        assert len(captured_logs.records) == 1
        record = captured_logs.records[0]

        assert "Security event: AUTH" in record.message
        assert "secret_token" not in str(record.__dict__)
        assert record.levelno == logging.INFO

    @pytest.mark.asyncio
    async def test_log_tool_execution_decorator(self, mcp_logger, captured_logs):
        """Test the log_tool_execution decorator."""

        @log_tool_execution(logger=mcp_logger)
        async def test_tool():
            return "success"

        result = await test_tool()

        assert result == "success"
        assert len(captured_logs.records) == 1
        assert "test_tool" in captured_logs.records[0].message

        metrics = mcp_logger.get_metrics()
        assert "test_tool" in metrics
        assert metrics["test_tool"].success is True

    @pytest.mark.asyncio
    async def test_log_tool_execution_decorator_failure(
        self, mcp_logger, captured_logs
    ):
        """Test the log_tool_execution decorator with failure."""

        @log_tool_execution(logger=mcp_logger)
        async def failing_tool():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            await failing_tool()

        assert len(captured_logs.records) == 1
        assert "failing_tool" in captured_logs.records[0].message
        assert "Test error" in captured_logs.records[0].message

        metrics = mcp_logger.get_metrics()
        assert "failing_tool" in metrics
        assert metrics["failing_tool"].success is False
        assert "Test error" in str(metrics["failing_tool"].error)
