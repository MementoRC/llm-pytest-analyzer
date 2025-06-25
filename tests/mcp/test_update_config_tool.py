"""Tests for the update_config MCP tool."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from pytest_analyzer.mcp.facade import MCPAnalyzerFacade
from pytest_analyzer.mcp.schemas.update_config import (
    UpdateConfigRequest,
    UpdateConfigResponse,
)
from pytest_analyzer.mcp.tools.configuration import update_config


class TestUpdateConfigTool:
    """Test suite for update_config MCP tool."""

    @pytest.fixture
    def mock_facade(self):
        """Create a mock MCPAnalyzerFacade."""
        facade = MagicMock(spec=MCPAnalyzerFacade)
        facade.update_config = AsyncMock()
        return facade

    @pytest.fixture
    def valid_arguments(self):
        """Valid arguments for update_config tool."""
        return {
            "config_updates": {
                "llm": {
                    "temperature": 0.8,
                    "max_tokens": 2000,
                }
            },
            "validate_only": False,
            "create_backup": True,
            "merge_strategy": "merge",
        }

    @pytest.fixture
    def success_response(self):
        """Mock successful update response."""
        return UpdateConfigResponse(
            success=True,
            request_id="test-request-123",
            execution_time_ms=150,
            updated_fields=["llm.temperature", "llm.max_tokens"],
            applied_changes={
                "llm": {
                    "temperature": 0.8,
                    "max_tokens": 2000,
                }
            },
            backup_path="/path/to/config.yaml.bak",
            rollback_available=True,
        )

    @pytest.mark.asyncio
    async def test_update_config_success(
        self, mock_facade, valid_arguments, success_response
    ):
        """Test successful configuration update."""
        # Setup
        mock_facade.update_config.return_value = success_response

        # Execute
        result = await update_config(valid_arguments, mock_facade)

        # Verify
        assert result.isError is False
        assert len(result.content) == 1
        content_text = result.content[0].text

        # Check response formatting
        assert "✅ Configuration Update Successful" in content_text
        assert "Request ID: test-request-123" in content_text
        assert "Execution Time: 150ms" in content_text
        assert "Updated Fields: llm.temperature, llm.max_tokens" in content_text
        assert "Backup Path: /path/to/config.yaml.bak" in content_text
        assert "🔧 Applied Changes:" in content_text
        assert "↩️ Rollback is available." in content_text

        # Verify facade was called correctly
        mock_facade.update_config.assert_called_once()
        call_args = mock_facade.update_config.call_args[0][0]
        assert isinstance(call_args, UpdateConfigRequest)
        assert call_args.tool_name == "update_config"
        assert call_args.config_updates == valid_arguments["config_updates"]
        assert call_args.validate_only is False
        assert call_args.create_backup is True

    @pytest.mark.asyncio
    async def test_update_config_validation_errors(self, mock_facade):
        """Test handling of validation errors."""
        # Setup - empty config_updates (invalid)
        invalid_arguments = {
            "config_updates": {},
        }

        # Execute
        result = await update_config(invalid_arguments, mock_facade)

        # Verify
        assert result.isError is True
        assert len(result.content) == 1
        content_text = result.content[0].text
        assert "Validation errors:" in content_text
        assert "config_updates is required and cannot be empty" in content_text

        # Verify facade was not called
        mock_facade.update_config.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_config_facade_error_response(
        self, mock_facade, valid_arguments
    ):
        """Test handling of facade error response."""
        # Setup
        error_response = UpdateConfigResponse(
            success=False,
            request_id="test-request-123",
            execution_time_ms=50,
            validation_errors=["Invalid temperature value"],
            warnings=["Config file not found"],
        )
        mock_facade.update_config.return_value = error_response

        # Execute
        result = await update_config(valid_arguments, mock_facade)

        # Verify
        assert result.isError is True
        assert len(result.content) == 1
        content_text = result.content[0].text

        # Check error formatting
        assert "❌ Configuration Update Failed" in content_text
        assert "Request ID: test-request-123" in content_text
        assert "Execution Time: 50ms" in content_text
        assert "Validation Errors:" in content_text
        assert "Invalid temperature value" in content_text
        assert "⚠️ Warnings:" in content_text
        assert "Config file not found" in content_text

    @pytest.mark.asyncio
    async def test_update_config_validate_only(self, mock_facade, success_response):
        """Test validate_only mode."""
        # Setup
        arguments = {
            "config_updates": {"llm": {"temperature": 0.9}},
            "validate_only": True,
        }
        mock_facade.update_config.return_value = success_response

        # Execute
        result = await update_config(arguments, mock_facade)

        # Verify
        assert result.isError is False
        mock_facade.update_config.assert_called_once()
        call_args = mock_facade.update_config.call_args[0][0]
        assert call_args.validate_only is True

    @pytest.mark.asyncio
    async def test_update_config_section_filtering(self, mock_facade, success_response):
        """Test section filtering."""
        # Setup
        arguments = {
            "config_updates": {"temperature": 0.9},
            "section": "llm",
        }
        mock_facade.update_config.return_value = success_response

        # Execute
        result = await update_config(arguments, mock_facade)

        # Verify
        assert result.isError is False
        mock_facade.update_config.assert_called_once()
        call_args = mock_facade.update_config.call_args[0][0]
        assert call_args.section == "llm"

    @pytest.mark.asyncio
    async def test_update_config_merge_strategies(self, mock_facade, success_response):
        """Test different merge strategies."""
        strategies = ["merge", "replace", "append"]

        for strategy in strategies:
            # Setup
            arguments = {
                "config_updates": {"llm": {"temperature": 0.9}},
                "merge_strategy": strategy,
            }
            mock_facade.update_config.return_value = success_response

            # Execute
            result = await update_config(arguments, mock_facade)

            # Verify
            assert result.isError is False
            call_args = mock_facade.update_config.call_args[0][0]
            assert call_args.merge_strategy == strategy

    @pytest.mark.asyncio
    async def test_update_config_exception_handling(self, mock_facade, valid_arguments):
        """Test exception handling."""
        # Setup
        mock_facade.update_config.side_effect = Exception("Facade error")

        # Execute
        result = await update_config(valid_arguments, mock_facade)

        # Verify
        assert result.isError is True
        assert len(result.content) == 1
        content_text = result.content[0].text
        assert "Tool execution failed: Facade error" in content_text

    @pytest.mark.asyncio
    async def test_update_config_with_metadata(self, mock_facade, success_response):
        """Test update with metadata."""
        # Setup
        arguments = {
            "config_updates": {"llm": {"temperature": 0.9}},
            "metadata": {"user": "test_user", "reason": "performance_tuning"},
        }
        mock_facade.update_config.return_value = success_response

        # Execute
        result = await update_config(arguments, mock_facade)

        # Verify
        assert result.isError is False
        call_args = mock_facade.update_config.call_args[0][0]
        assert call_args.metadata == arguments["metadata"]

    @pytest.mark.asyncio
    async def test_update_config_response_formatting_with_warnings(
        self, mock_facade, valid_arguments
    ):
        """Test response formatting when warnings are present."""
        # Setup
        response_with_warnings = UpdateConfigResponse(
            success=True,
            request_id="test-request-123",
            execution_time_ms=150,
            updated_fields=["llm.temperature"],
            applied_changes={"llm": {"temperature": 0.8}},
            warnings=["Config file was created", "Backup location changed"],
            rollback_available=False,
        )
        mock_facade.update_config.return_value = response_with_warnings

        # Execute
        result = await update_config(valid_arguments, mock_facade)

        # Verify
        assert result.isError is False
        content_text = result.content[0].text
        assert "⚠️ Warnings:" in content_text
        assert "Config file was created" in content_text
        assert "Backup location changed" in content_text

    @pytest.mark.asyncio
    async def test_update_config_empty_updates_with_defaults(self, mock_facade):
        """Test behavior with minimal arguments using defaults."""
        # Setup
        arguments = {
            "config_updates": {"llm": {"temperature": 0.5}},
        }
        success_response = UpdateConfigResponse(
            success=True,
            request_id="test-request-123",
            execution_time_ms=100,
        )
        mock_facade.update_config.return_value = success_response

        # Execute
        result = await update_config(arguments, mock_facade)

        # Verify
        assert result.isError is False
        call_args = mock_facade.update_config.call_args[0][0]
        # Check defaults are applied
        assert call_args.validate_only is False
        assert call_args.create_backup is True
        assert call_args.merge_strategy == "merge"
        assert call_args.section is None
