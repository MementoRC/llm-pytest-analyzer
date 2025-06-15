"""Tests for the MCP Facade implementation."""

import logging
from unittest.mock import MagicMock

import pytest

from pytest_analyzer.core.analyzer_facade import PytestAnalyzerFacade
from pytest_analyzer.core.errors import (
    AnalysisError,
    ExtractionError,
    LLMServiceError,
)
from pytest_analyzer.mcp.facade import MCPAnalyzerFacade
from pytest_analyzer.mcp.schemas.analyze_pytest_output import AnalyzePytestOutputRequest
from pytest_analyzer.mcp.schemas.apply_suggestion import ApplySuggestionRequest
from pytest_analyzer.mcp.schemas.get_config import GetConfigRequest
from pytest_analyzer.mcp.schemas.get_failure_summary import GetFailureSummaryRequest
from pytest_analyzer.mcp.schemas.get_test_coverage import GetTestCoverageRequest
from pytest_analyzer.mcp.schemas.run_and_analyze import RunAndAnalyzeRequest
from pytest_analyzer.mcp.schemas.suggest_fixes import SuggestFixesRequest
from pytest_analyzer.mcp.schemas.update_config import UpdateConfigRequest
from pytest_analyzer.mcp.schemas.validate_suggestion import ValidateSuggestionRequest


@pytest.fixture
def mock_analyzer():
    """Create a mock PytestAnalyzerFacade."""
    return MagicMock(spec=PytestAnalyzerFacade)


@pytest.fixture
def mcp_facade(mock_analyzer):
    """Create an MCPAnalyzerFacade with a mock analyzer."""
    return MCPAnalyzerFacade(mock_analyzer)


@pytest.fixture
def sample_failure(test_failure):
    """Create a sample test failure."""
    return test_failure


@pytest.fixture
def sample_suggestion(test_suggestion):
    """Create a sample fix suggestion."""
    return test_suggestion


class TestMCPAnalyzerFacade:
    """Test suite for MCPAnalyzerFacade."""

    def test_constructor_injection(self, mock_analyzer):
        """Test constructor injection of analyzer facade."""
        facade = MCPAnalyzerFacade(mock_analyzer)
        assert facade.analyzer == mock_analyzer

    async def test_analyze_pytest_output_success(
        self, mcp_facade, tmp_path, sample_suggestion
    ):
        """Test successful pytest output analysis."""
        # Create test file
        test_file = tmp_path / "pytest_output.txt"
        test_file.write_text("test output")

        # Setup mock
        mcp_facade.analyzer.analyze_pytest_output.return_value = [sample_suggestion]

        # Create request
        request = AnalyzePytestOutputRequest(
            tool_name="analyze_pytest_output", file_path=str(test_file)
        )

        # Execute
        response = await mcp_facade.analyze_pytest_output(request)

        # Verify
        assert response.success is True
        assert len(response.suggestions) == 1
        assert response.execution_time_ms > 0
        mcp_facade.analyzer.analyze_pytest_output.assert_called_once_with(
            str(test_file)
        )

    async def test_analyze_pytest_output_validation_error(self, mcp_facade):
        """Test analysis with invalid file path."""
        request = AnalyzePytestOutputRequest(
            tool_name="analyze_pytest_output", file_path="/nonexistent/file.txt"
        )

        response = await mcp_facade.analyze_pytest_output(request)

        assert response.success is False
        assert len(response.parsing_errors) > 0
        assert not mcp_facade.analyzer.analyze_pytest_output.called

    async def test_run_and_analyze_success(self, mcp_facade, sample_suggestion):
        """Test successful run and analyze operation."""
        mcp_facade.analyzer.run_and_analyze.return_value = [sample_suggestion]

        request = RunAndAnalyzeRequest(
            tool_name="run_and_analyze", test_pattern="tests/", pytest_args=[]
        )

        response = await mcp_facade.run_and_analyze(request)

        assert response.success is True
        assert len(response.suggestions) == 1
        assert response.execution_time_ms > 0
        mcp_facade.analyzer.run_and_analyze.assert_called_once()

    async def test_suggest_fixes_success(self, mcp_facade, sample_suggestion):
        """Test successful fix suggestion generation."""
        mcp_facade.analyzer.suggest_fixes.return_value = [sample_suggestion]

        request = SuggestFixesRequest(
            tool_name="suggest_fixes", raw_output="test output"
        )

        response = await mcp_facade.suggest_fixes(request)

        assert response.success is True
        assert len(response.suggestions) == 1
        assert response.confidence_score > 0
        mcp_facade.analyzer.suggest_fixes.assert_called_once_with("test output")

    async def test_apply_suggestion_success(self, mcp_facade):
        """Test successful suggestion application."""
        mcp_facade.analyzer.apply_suggestion.return_value = {
            "success": True,
            "applied_files": ["test.py"],
            "rolled_back_files": [],
        }

        request = ApplySuggestionRequest(
            tool_name="apply_suggestion",
            suggestion_id="test-id",
            target_file="test.py",
            dry_run=True,
        )

        response = await mcp_facade.apply_suggestion(request)

        assert response.success is True
        assert len(response.changes_applied) == 1
        assert response.rollback_available is False
        # Dry run should not call the analyzer

    async def test_validate_suggestion_success(self, mcp_facade, tmp_path):
        """Test successful suggestion validation."""
        # Create a real test file
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hello world')")

        request = ValidateSuggestionRequest(
            tool_name="validate_suggestion",
            suggestion_id="test-id",
            target_file=str(test_file),
        )

        response = await mcp_facade.validate_suggestion(request)

        assert response.success is True
        assert response.is_valid is True

    async def test_get_failure_summary_success(self, mcp_facade):
        """Test successful failure summary retrieval."""
        request = GetFailureSummaryRequest(tool_name="get_failure_summary")

        response = await mcp_facade.get_failure_summary(request)

        assert response.success is True
        assert isinstance(response.total_failures, int)

    async def test_get_test_coverage_success(self, mcp_facade):
        """Test successful test coverage retrieval."""
        request = GetTestCoverageRequest(tool_name="get_test_coverage")

        response = await mcp_facade.get_test_coverage(request)

        assert response.success is True
        assert isinstance(response.percentage, float)

    async def test_get_config_success(self, mcp_facade):
        """Test successful config retrieval."""
        request = GetConfigRequest(tool_name="get_config")

        response = await mcp_facade.get_config(request)

        assert response.success is True
        assert isinstance(response.config_data, dict)

    async def test_update_config_success(self, mcp_facade):
        """Test successful config update."""
        request = UpdateConfigRequest(
            tool_name="update_config",
            config_updates={
                "pytest_timeout": 180,
                "max_suggestions": 8,
            },  # Use unique values
        )

        response = await mcp_facade.update_config(request)

        assert response.success is True
        assert isinstance(response.updated_fields, list)

    async def test_get_config_section_not_found(self, mcp_facade):
        """Test get_config with a section that does not exist."""
        request = GetConfigRequest(tool_name="get_config", section="nonexistent")
        response = await mcp_facade.get_config(request)
        assert response.success is False
        assert "Section 'nonexistent' not found." in response.warnings[0]

    async def test_get_config_sensitive_data_masked(self, mcp_facade):
        """Test that sensitive data is masked in get_config response."""
        request = GetConfigRequest(tool_name="get_config")
        response = await mcp_facade.get_config(request)
        assert response.success is True
        assert "llm" in response.config_data
        if "llm_api_key" in response.config_data["llm"]:
            assert response.config_data["llm"]["llm_api_key"]["value"] == "***"

    async def test_update_config_section_not_found(self, mcp_facade):
        """Test update_config with a section that does not exist."""
        request = UpdateConfigRequest(
            tool_name="update_config",
            section="nonexistent",
            config_updates={"test_key": "test_value"},
        )
        response = await mcp_facade.update_config(request)
        assert response.success is False
        assert "Section 'nonexistent' not found" in response.validation_errors[0]

    async def test_update_config_validation_error(self, mcp_facade):
        """Test update_config with invalid config updates."""
        request = UpdateConfigRequest(
            tool_name="update_config", config_updates={"pytest_timeout": "invalid"}
        )
        response = await mcp_facade.update_config(request)
        assert response.success is False
        assert len(response.validation_errors) > 0

    async def test_update_config_success_validate_only(self, mcp_facade):
        """Test successful config update with validate_only=True."""
        request = UpdateConfigRequest(
            tool_name="update_config",
            config_updates={
                "pytest_timeout": 250
            },  # Use unique value to ensure change detection
            validate_only=True,
        )
        response = await mcp_facade.update_config(request)
        assert response.success is True
        assert response.updated_fields == ["pytest_timeout"]
        assert response.applied_changes == {"pytest_timeout": 250}

    async def test_update_config_success_with_section(self, mcp_facade):
        """Test successful config update with a specific section."""
        request = UpdateConfigRequest(
            tool_name="update_config",
            section="llm",
            config_updates={
                "llm_timeout": 600
            },  # Use unique value to ensure change detection
        )
        response = await mcp_facade.update_config(request)
        assert response.success is True
        assert "llm_timeout" in response.updated_fields
        assert response.applied_changes == {"llm_timeout": 600}

    @pytest.mark.parametrize(
        "method_name,request_class,expected_exception",
        [
            ("analyze_pytest_output", AnalyzePytestOutputRequest, AnalysisError),
            ("run_and_analyze", RunAndAnalyzeRequest, AnalysisError),
            ("suggest_fixes", SuggestFixesRequest, LLMServiceError),
            ("apply_suggestion", ApplySuggestionRequest, ExtractionError),
        ],
    )
    async def test_error_handling_analyzer_methods(
        self,
        mcp_facade,
        method_name,
        request_class,
        expected_exception,
        caplog,
        tmp_path,
    ):
        """Test error handling for methods that call the underlying analyzer."""
        # Setup
        caplog.set_level(logging.ERROR)
        mock_method = getattr(mcp_facade.analyzer, method_name)
        mock_method.side_effect = expected_exception("Test error")

        # Create minimal valid request based on class requirements
        if request_class == ApplySuggestionRequest:
            # Create valid file to pass validation and test error handling
            test_file = tmp_path / "test.py"
            test_file.write_text("print('hello')")
            request = request_class(
                tool_name=method_name,
                suggestion_id="test-id",
                target_file=str(test_file),
                dry_run=False,  # Need to call analyzer to test error handling
            )
        elif request_class == AnalyzePytestOutputRequest:
            # Create valid file to pass validation
            test_file = tmp_path / "test.json"
            test_file.write_text('{"test": "data"}')
            request = request_class(tool_name=method_name, file_path=str(test_file))
        elif request_class == SuggestFixesRequest:
            request = request_class(tool_name=method_name, raw_output="test output")
        elif request_class == RunAndAnalyzeRequest:
            request = request_class(tool_name=method_name, test_pattern="test_*.py")

        # Execute
        method = getattr(mcp_facade, method_name)
        response = await method(request)

        # Verify
        assert any("Test error" in record.message for record in caplog.records)
        if method_name == "apply_suggestion":
            # apply_suggestion returns ApplySuggestionResponse with success=False
            from pytest_analyzer.mcp.schemas.apply_suggestion import (
                ApplySuggestionResponse,
            )

            assert isinstance(response, ApplySuggestionResponse)
            assert response.success is False
        else:
            # MCP facade should catch and convert to MCPError, not re-raise
            from pytest_analyzer.mcp.schemas import MCPError as MCPErrorType

            assert isinstance(response, MCPErrorType)
            assert response.code.endswith("_FAILED")
            assert "Test error" in response.message

    @pytest.mark.parametrize(
        "method_name,request_class",
        [
            ("validate_suggestion", ValidateSuggestionRequest),
            ("get_failure_summary", GetFailureSummaryRequest),
            ("get_test_coverage", GetTestCoverageRequest),
            ("get_config", GetConfigRequest),
            ("update_config", UpdateConfigRequest),
        ],
    )
    async def test_standalone_methods_success(
        self, mcp_facade, method_name, request_class, tmp_path
    ):
        """Test standalone methods that don't call the underlying analyzer."""
        # Create minimal valid request based on class requirements
        if request_class == ValidateSuggestionRequest:
            # Create a real test file
            test_file = tmp_path / "test.py"
            test_file.write_text("print('hello world')")
            request = request_class(
                tool_name=method_name,
                suggestion_id="test-id",
                target_file=str(test_file),
            )
        elif request_class == UpdateConfigRequest:
            request = request_class(
                tool_name=method_name,
                config_updates={"pytest_timeout": 150},  # Use unique value
            )
        else:
            request = request_class(tool_name=method_name)

        # Execute
        method = getattr(mcp_facade, method_name)
        response = await method(request)

        # Verify - these methods should succeed as they're implemented directly
        assert response.success is True

    def test_transform_suggestion_to_mcp(self, mcp_facade, sample_suggestion):
        """Test transformation of domain suggestion to MCP format."""
        mcp_suggestion = mcp_facade._transform_suggestion_to_mcp(sample_suggestion)

        # Handle legacy model attributes (test fixtures use legacy FixSuggestion)
        expected_id = str(getattr(sample_suggestion, "id", "unknown"))
        expected_text = getattr(sample_suggestion, "suggestion", "")
        expected_confidence = float(getattr(sample_suggestion, "confidence", 0.0))

        assert mcp_suggestion.id == expected_id
        assert mcp_suggestion.suggestion_text == expected_text
        assert mcp_suggestion.confidence_score == expected_confidence

    def test_transform_failure_to_mcp(self, mcp_facade, sample_failure):
        """Test transformation of domain failure to MCP format."""
        mcp_failure = mcp_facade._transform_failure_to_mcp(sample_failure)

        # Handle legacy model attributes (test fixtures use legacy PytestFailure)
        expected_id = str(getattr(sample_failure, "id", "unknown"))
        expected_test_name = getattr(sample_failure, "test_name", "")
        expected_message = getattr(sample_failure, "error_message", "")

        assert mcp_failure.id == expected_id
        assert mcp_failure.test_name == expected_test_name
        assert mcp_failure.failure_message == expected_message

    @pytest.mark.parametrize(
        "method_name",
        [
            "analyze_pytest_output",
            "run_and_analyze",
            "suggest_fixes",
            "apply_suggestion",
            "validate_suggestion",
            "get_failure_summary",
            "get_test_coverage",
            "get_config",
            "update_config",
        ],
    )
    async def test_execution_time_tracking(self, mcp_facade, method_name, tmp_path):
        """Test execution time tracking for all methods."""
        # Create minimal valid request for each method
        request_class = globals()[f"{method_name.title().replace('_', '')}Request"]

        # Create request with required parameters based on method
        if method_name == "analyze_pytest_output":
            # Create a test file for analysis
            test_file = tmp_path / "test_output.json"
            test_file.write_text('{"test": "data"}')
            request = request_class(tool_name=method_name, file_path=str(test_file))
        elif method_name == "suggest_fixes":
            request = request_class(tool_name=method_name, raw_output="test output")
        elif method_name == "apply_suggestion":
            request = request_class(
                tool_name=method_name,
                suggestion_id="test-id",
                target_file="test.py",
                dry_run=True,
            )
        elif method_name == "validate_suggestion":
            # Create a test file for validation
            test_file = tmp_path / "test.py"
            test_file.write_text("print('hello')")
            request = request_class(
                tool_name=method_name,
                suggestion_id="test-id",
                target_file=str(test_file),
            )
        elif method_name == "run_and_analyze":
            request = request_class(tool_name=method_name, test_pattern="test_*.py")
        elif method_name == "update_config":
            request = request_class(
                tool_name=method_name,
                config_updates={"test_key": "test_value"},  # Use unique key-value
            )
        else:
            # For methods that only need tool_name
            request = request_class(tool_name=method_name)

        # Execute
        method = getattr(mcp_facade, method_name)
        response = await method(request)

        # Verify execution time is tracked
        assert hasattr(response, "execution_time_ms")
        assert response.execution_time_ms >= 0
