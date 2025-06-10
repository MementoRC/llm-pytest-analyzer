"""Tests for apply_suggestion MCP tool."""

import os
import tempfile
from unittest.mock import AsyncMock, MagicMock

import pytest

from pytest_analyzer.mcp.facade import MCPAnalyzerFacade
from pytest_analyzer.mcp.schemas.apply_suggestion import (
    ApplySuggestionRequest,
    ApplySuggestionResponse,
)
from pytest_analyzer.mcp.tools.fixes import apply_suggestion


class TestApplySuggestionTool:
    """Test suite for apply_suggestion MCP tool."""

    @pytest.fixture
    def mock_facade(self):
        """Create a mock MCPAnalyzerFacade."""
        facade = MagicMock(spec=MCPAnalyzerFacade)
        facade.apply_suggestion = AsyncMock()
        return facade

    @pytest.fixture
    def temp_file(self):
        """Create a temporary file for testing."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def test_function():\n    return True\n")
            temp_path = f.name

        yield temp_path

        # Clean up
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        backup_path = temp_path + ".backup"
        if os.path.exists(backup_path):
            os.unlink(backup_path)

    @pytest.mark.asyncio
    async def test_apply_suggestion_success(self, mock_facade, temp_file):
        """Test successful suggestion application."""
        # Mock facade response
        mock_response = ApplySuggestionResponse(
            success=True,
            request_id="test-request",
            suggestion_id="test-suggestion",
            target_file=temp_file,
            backup_path=temp_file + ".backup",
            changes_applied=[temp_file],
            syntax_valid=True,
            rollback_available=True,
            execution_time_ms=100,
        )
        mock_facade.apply_suggestion.return_value = mock_response

        # Test arguments
        arguments = {
            "suggestion_id": "test-suggestion",
            "target_file": temp_file,
            "create_backup": True,
            "validate_syntax": True,
        }

        # Call tool
        result = await apply_suggestion(arguments, mock_facade)

        # Verify results
        assert not result.isError
        assert len(result.content) == 1
        content = result.content[0].text
        assert "✅ Fix Suggestion Applied" in content
        assert "test-suggestion" in content
        assert temp_file in content

        # Verify facade was called correctly
        mock_facade.apply_suggestion.assert_called_once()
        call_args = mock_facade.apply_suggestion.call_args[0][0]
        assert call_args.suggestion_id == "test-suggestion"
        assert call_args.target_file == temp_file
        assert call_args.create_backup is True
        assert call_args.validate_syntax is True

    @pytest.mark.asyncio
    async def test_apply_suggestion_validation_error(self, mock_facade):
        """Test apply_suggestion with validation errors."""
        arguments = {
            "suggestion_id": "",  # Missing required field
            "target_file": "",  # Missing required field
        }

        result = await apply_suggestion(arguments, mock_facade)

        assert result.isError
        assert len(result.content) == 1
        assert "Validation errors" in result.content[0].text

        # Facade should not be called due to validation failure
        mock_facade.apply_suggestion.assert_not_called()

    @pytest.mark.asyncio
    async def test_apply_suggestion_facade_failure(self, mock_facade, temp_file):
        """Test apply_suggestion when facade returns failure."""
        # Mock facade response - failure case
        mock_response = ApplySuggestionResponse(
            success=False,
            request_id="test-request",
            suggestion_id="test-suggestion",
            target_file=temp_file,
            warnings=["File could not be modified"],
            execution_time_ms=50,
        )
        mock_facade.apply_suggestion.return_value = mock_response

        arguments = {
            "suggestion_id": "test-suggestion",
            "target_file": temp_file,
        }

        result = await apply_suggestion(arguments, mock_facade)

        assert result.isError
        assert len(result.content) == 1
        content = result.content[0].text
        assert "❌ Failed to Apply Suggestion" in content
        assert "File could not be modified" in content

    @pytest.mark.asyncio
    async def test_apply_suggestion_with_security_validation(
        self, mock_facade, temp_file
    ):
        """Test apply_suggestion with security manager validation."""
        # Mock server with security manager
        mock_server = MagicMock()
        mock_security_manager = MagicMock()
        mock_server.security_manager = mock_security_manager
        mock_facade.server = mock_server

        # Mock successful validation
        mock_security_manager.validate_tool_input.return_value = None

        # Mock facade response
        mock_response = ApplySuggestionResponse(
            success=True,
            request_id="test-request",
            suggestion_id="test-suggestion",
            target_file=temp_file,
            execution_time_ms=100,
        )
        mock_facade.apply_suggestion.return_value = mock_response

        arguments = {
            "suggestion_id": "test-suggestion",
            "target_file": temp_file,
        }

        result = await apply_suggestion(arguments, mock_facade)

        # Verify security validation was called
        mock_security_manager.validate_tool_input.assert_called_once_with(
            "apply_suggestion", arguments, read_only=False
        )

        assert not result.isError

    @pytest.mark.asyncio
    async def test_apply_suggestion_security_error(self, mock_facade, temp_file):
        """Test apply_suggestion when security validation fails."""
        from pytest_analyzer.mcp.security import SecurityError

        # Mock server with security manager that raises error
        mock_server = MagicMock()
        mock_security_manager = MagicMock()
        mock_server.security_manager = mock_security_manager
        mock_facade.server = mock_server

        mock_security_manager.validate_tool_input.side_effect = SecurityError(
            "Security violation"
        )

        arguments = {
            "suggestion_id": "test-suggestion",
            "target_file": temp_file,
        }

        result = await apply_suggestion(arguments, mock_facade)

        assert result.isError
        assert "Security error: Security violation" in result.content[0].text

        # Facade should not be called due to security failure
        mock_facade.apply_suggestion.assert_not_called()

    @pytest.mark.asyncio
    async def test_apply_suggestion_exception_handling(self, mock_facade, temp_file):
        """Test apply_suggestion exception handling."""
        # Mock facade to raise exception
        mock_facade.apply_suggestion.side_effect = Exception("Unexpected error")

        arguments = {
            "suggestion_id": "test-suggestion",
            "target_file": temp_file,
        }

        result = await apply_suggestion(arguments, mock_facade)

        assert result.isError
        assert "Tool execution failed: Unexpected error" in result.content[0].text

    @pytest.mark.asyncio
    async def test_apply_suggestion_with_all_options(self, mock_facade, temp_file):
        """Test apply_suggestion with all optional parameters."""
        mock_response = ApplySuggestionResponse(
            success=True,
            request_id="test-request",
            suggestion_id="test-suggestion",
            target_file=temp_file,
            backup_path=temp_file + ".custom",
            changes_applied=[temp_file],
            syntax_valid=True,
            syntax_errors=[],
            rollback_available=True,
            diff_preview="@@ -1,2 +1,2 @@\n-def test_function():\n+def updated_function():",
            warnings=["Minor formatting adjusted"],
            execution_time_ms=150,
        )
        mock_facade.apply_suggestion.return_value = mock_response

        arguments = {
            "suggestion_id": "test-suggestion",
            "target_file": temp_file,
            "create_backup": True,
            "validate_syntax": True,
            "dry_run": False,
            "backup_suffix": ".custom",
        }

        result = await apply_suggestion(arguments, mock_facade)

        assert not result.isError
        content = result.content[0].text
        assert "✅ Fix Suggestion Applied" in content
        assert "Backup Created:" in content
        assert ".custom" in content
        assert "Changes Applied:" in content
        assert "Syntax check passed" in content
        assert "Changes Preview:" in content
        assert "def updated_function" in content
        assert "Minor formatting adjusted" in content

    @pytest.mark.asyncio
    async def test_apply_suggestion_syntax_error_response(self, mock_facade, temp_file):
        """Test apply_suggestion handling syntax errors in response."""
        mock_response = ApplySuggestionResponse(
            success=False,
            request_id="test-request",
            suggestion_id="test-suggestion",
            target_file=temp_file,
            backup_path=temp_file + ".backup",
            syntax_valid=False,
            syntax_errors=["SyntaxError: invalid syntax at line 5"],
            rollback_available=True,
            warnings=["Suggestion applied but syntax invalid"],
            execution_time_ms=120,
        )
        mock_facade.apply_suggestion.return_value = mock_response

        arguments = {
            "suggestion_id": "test-suggestion",
            "target_file": temp_file,
        }

        result = await apply_suggestion(arguments, mock_facade)

        assert result.isError
        content = result.content[0].text
        assert "❌ Failed to Apply Suggestion" in content
        assert "Syntax Errors:" in content
        assert "SyntaxError: invalid syntax at line 5" in content
        assert "Rollback Possible: Yes" in content


class TestApplySuggestionRequest:
    """Test ApplySuggestionRequest validation."""

    def test_valid_request(self):
        """Test valid request creation and validation."""
        request = ApplySuggestionRequest(
            tool_name="apply_suggestion",
            suggestion_id="test-suggestion",
            target_file="/path/to/file.py",
        )

        errors = request.validate()
        assert len(errors) == 0

    def test_missing_required_fields(self):
        """Test validation with missing required fields."""
        request = ApplySuggestionRequest(
            tool_name="apply_suggestion",
            suggestion_id="",  # Empty
            target_file="",  # Empty
        )

        errors = request.validate()
        assert len(errors) >= 2
        assert any("suggestion_id is required" in error for error in errors)
        assert any("target_file is required" in error for error in errors)

    def test_request_defaults(self):
        """Test request default values."""
        request = ApplySuggestionRequest(
            tool_name="apply_suggestion",
            suggestion_id="test-suggestion",
            target_file="/path/to/file.py",
        )

        assert request.create_backup is True
        assert request.validate_syntax is True
        assert request.dry_run is False
        assert request.backup_suffix == ".backup"
        assert request.request_id is not None

    def test_request_to_dict(self):
        """Test request serialization to dictionary."""
        request = ApplySuggestionRequest(
            tool_name="apply_suggestion",
            suggestion_id="test-suggestion",
            target_file="/path/to/file.py",
            create_backup=False,
        )

        data = request.to_dict()
        assert data["tool_name"] == "apply_suggestion"
        assert data["suggestion_id"] == "test-suggestion"
        assert data["target_file"] == "/path/to/file.py"
        assert data["create_backup"] is False


class TestApplySuggestionResponse:
    """Test ApplySuggestionResponse functionality."""

    def test_response_properties(self):
        """Test response computed properties."""
        # Response with syntax errors
        response = ApplySuggestionResponse(
            success=False,
            request_id="test-request",
            syntax_valid=False,
            syntax_errors=["SyntaxError: invalid syntax"],
            backup_path="/path/to/backup",
            rollback_available=True,
        )

        assert response.has_syntax_errors is True
        assert response.can_rollback is True

        # Response without syntax errors
        response2 = ApplySuggestionResponse(
            success=True,
            request_id="test-request",
            syntax_valid=True,
            syntax_errors=[],
            backup_path=None,
            rollback_available=False,
        )

        assert response2.has_syntax_errors is False
        assert response2.can_rollback is False

    def test_response_serialization(self):
        """Test response serialization methods."""
        response = ApplySuggestionResponse(
            success=True,
            request_id="test-request",
            suggestion_id="test-suggestion",
            target_file="/path/to/file.py",
            execution_time_ms=100,
        )

        # Test to_dict
        data = response.to_dict()
        assert data["success"] is True
        assert data["request_id"] == "test-request"
        assert data["execution_time_ms"] == 100

        # Test to_json
        json_str = response.to_json()
        assert "test-request" in json_str
        assert "true" in json_str.lower()  # JSON boolean
