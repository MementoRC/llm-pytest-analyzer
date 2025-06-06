"""Tests for MCP schema definitions."""

import pytest
from dataclasses import asdict

from pytest_analyzer.mcp.schemas import (
    MCPRequest,
    MCPResponse,
    MCPError,
    FixSuggestionData,
    PytestFailureData,
    validate_file_path,
    validate_output_format,
    validate_timeout,
)
from pytest_analyzer.mcp.schemas.analyze_pytest_output import (
    AnalyzePytestOutputRequest,
    AnalyzePytestOutputResponse,
)
from pytest_analyzer.mcp.schemas.run_and_analyze import (
    RunAndAnalyzeRequest,
    RunAndAnalyzeResponse,
)
from pytest_analyzer.mcp.schemas.suggest_fixes import (
    SuggestFixesRequest,
    SuggestFixesResponse,
)


class TestBaseSchemas:
    """Test base MCP schema classes."""

    def test_mcp_request_creation(self):
        """Test MCPRequest creation and validation."""
        request = MCPRequest(tool_name="test_tool")
        
        assert request.tool_name == "test_tool"
        assert request.request_id  # Should be auto-generated
        assert request.metadata == {}
        
        # Test validation
        errors = request.validate()
        assert len(errors) == 0
        
        # Test invalid request
        invalid_request = MCPRequest(tool_name="")
        errors = invalid_request.validate()
        assert len(errors) == 1
        assert "tool_name is required" in errors[0]

    def test_mcp_response_creation(self):
        """Test MCPResponse creation."""
        response = MCPResponse(success=True, request_id="test-123")
        
        assert response.success is True
        assert response.request_id == "test-123"
        assert response.execution_time_ms == 0
        assert response.metadata == {}
        
        # Test JSON conversion
        json_str = response.to_json()
        assert "test-123" in json_str
        assert "true" in json_str.lower()

    def test_fix_suggestion_data_validation(self):
        """Test FixSuggestionData validation."""
        suggestion = FixSuggestionData(
            id="test-id",
            failure_id="failure-id",
            suggestion_text="Fix this issue",
            confidence_score=0.85
        )
        
        errors = suggestion.validate()
        assert len(errors) == 0
        
        # Test invalid confidence score
        invalid_suggestion = FixSuggestionData(
            id="test-id",
            failure_id="failure-id", 
            suggestion_text="Fix this issue",
            confidence_score=1.5  # Invalid
        )
        
        errors = invalid_suggestion.validate()
        assert len(errors) == 1
        assert "confidence_score must be between 0.0 and 1.0" in errors[0]


class TestAnalyzePytestOutput:
    """Test analyze_pytest_output schema."""

    def test_request_validation(self, tmp_path):
        """Test request validation."""
        # Create a test file
        test_file = tmp_path / "test_output.json"
        test_file.write_text('{"test": "data"}')
        
        request = AnalyzePytestOutputRequest(
            tool_name="analyze_pytest_output",
            file_path=str(test_file),
            format="json"
        )
        
        errors = request.validate()
        assert len(errors) == 0

    def test_request_validation_invalid_file(self):
        """Test request validation with invalid file."""
        request = AnalyzePytestOutputRequest(
            tool_name="analyze_pytest_output",
            file_path="/nonexistent/file.json",
            format="json"
        )
        
        errors = request.validate()
        assert len(errors) > 0
        assert any("does not exist" in error for error in errors)

    def test_response_creation(self):
        """Test response creation and computed properties."""
        suggestion = FixSuggestionData(
            id="s1",
            failure_id="f1",
            suggestion_text="Fix assertion",
            confidence_score=0.9
        )
        
        failure = PytestFailureData(
            id="f1",
            test_name="test_example",
            file_path="test.py",
            failure_message="AssertionError",
            failure_type="assertion_error"
        )
        
        response = AnalyzePytestOutputResponse(
            success=True,
            request_id="test-123",
            suggestions=[suggestion],
            failures=[failure]
        )
        
        assert response.success is True
        assert len(response.suggestions) == 1
        assert len(response.failures) == 1
        assert response.summary["total_failures"] == 1
        assert response.summary["total_suggestions"] == 1
        assert response.summary["average_confidence"] == 0.9


class TestRunAndAnalyze:
    """Test run_and_analyze schema."""

    def test_request_validation(self):
        """Test request validation."""
        request = RunAndAnalyzeRequest(
            tool_name="run_and_analyze",
            test_pattern="tests/",
            timeout=300
        )
        
        errors = request.validate()
        assert len(errors) == 0

    def test_response_properties(self):
        """Test response computed properties."""
        response = RunAndAnalyzeResponse(
            success=True,
            request_id="test-123",
            pytest_success=False,
            tests_run=10,
            tests_passed=7,
            tests_failed=2,
            tests_skipped=1
        )
        
        assert response.pass_rate == 70.0
        assert response.has_failures is True


class TestSuggestFixes:
    """Test suggest_fixes schema."""

    def test_request_validation(self):
        """Test request validation."""
        request = SuggestFixesRequest(
            tool_name="suggest_fixes",
            raw_output="FAILED test.py::test_func - AssertionError: expected 5, got 3"
        )
        
        errors = request.validate()
        assert len(errors) == 0

    def test_request_validation_empty_output(self):
        """Test validation with empty output."""
        request = SuggestFixesRequest(
            tool_name="suggest_fixes",
            raw_output=""
        )
        
        errors = request.validate()
        assert len(errors) > 0
        assert any("raw_output is required" in error for error in errors)


class TestValidationUtilities:
    """Test validation utility functions."""

    def test_validate_file_path(self, tmp_path):
        """Test file path validation."""
        # Valid file
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        
        errors = validate_file_path(str(test_file))
        assert len(errors) == 0
        
        # Nonexistent file
        errors = validate_file_path("/nonexistent/file.txt")
        assert len(errors) == 1
        assert "does not exist" in errors[0]

    def test_validate_output_format(self):
        """Test output format validation."""
        # Valid formats
        for format_type in ["json", "xml", "text", "junit"]:
            errors = validate_output_format(format_type)
            assert len(errors) == 0
        
        # Invalid format
        errors = validate_output_format("invalid")
        assert len(errors) == 1
        assert "Invalid format" in errors[0]

    def test_validate_timeout(self):
        """Test timeout validation."""
        # Valid timeouts
        for timeout in [1, 300, 3600]:
            errors = validate_timeout(timeout)
            assert len(errors) == 0
        
        # Invalid timeouts
        errors = validate_timeout(0)
        assert len(errors) == 1
        assert "must be positive" in errors[0]
        
        errors = validate_timeout(7200)  # > 1 hour
        assert len(errors) == 1
        assert "cannot exceed 3600" in errors[0]


class TestSerialization:
    """Test schema serialization capabilities."""

    def test_to_dict_conversion(self):
        """Test conversion to dictionary for JSON serialization."""
        request = MCPRequest(tool_name="test_tool")
        data = request.to_dict()
        
        assert isinstance(data, dict)
        assert data["tool_name"] == "test_tool"
        assert "request_id" in data
        assert data["metadata"] == {}

    def test_complex_schema_serialization(self):
        """Test serialization of complex schemas."""
        suggestion = FixSuggestionData(
            id="s1",
            failure_id="f1",
            suggestion_text="Fix assertion",
            confidence_score=0.9,
            code_changes=["line 1", "line 2"]
        )
        
        data = suggestion.to_dict()
        assert isinstance(data, dict)
        assert data["id"] == "s1"
        assert data["confidence_score"] == 0.9
        assert len(data["code_changes"]) == 2