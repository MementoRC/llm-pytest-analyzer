#!/usr/bin/env python3
"""
Integration tests for the PytestAnalyzerService fix application feature.

These tests verify that:
1. The service correctly applies fixes from FixSuggestion objects
2. It handles error cases gracefully
3. It properly integrates with the FixApplier
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from pytest_analyzer.core.analyzer_service import PytestAnalyzerService
from pytest_analyzer.core.models.pytest_failure import PytestFailure, FixSuggestion
from pytest_analyzer.core.analysis.fix_applier import FixApplier, FixApplicationResult
from pytest_analyzer.utils.settings import Settings


class TestAnalyzerServiceFixIntegration:
    """Test suite for PytestAnalyzerService fix application integration."""
    
    @pytest.fixture
    def analyzer_service(self, tmp_path):
        """Create a PytestAnalyzerService with a mocked project root."""
        settings = Settings()
        settings.project_root = tmp_path
        return PytestAnalyzerService(settings=settings)
    
    @pytest.fixture
    def failure(self):
        """Create a dummy PytestFailure for testing."""
        return PytestFailure(
            test_name="test_module::test_function",
            test_file="/path/to/test_file.py",
            error_type="AssertionError",
            error_message="assert 1 == 2",
            traceback="...",
            line_number=10,
            relevant_code="assert value == expected"
        )
    
    @pytest.fixture
    def fix_suggestion(self, failure):
        """Create a FixSuggestion with code changes for testing."""
        return FixSuggestion(
            failure=failure,
            suggestion="Fix the assertion by correcting the expected value",
            confidence=0.9,
            code_changes={
                "/path/to/source_file.py": "corrected code content",
                "fingerprint": "abcdef123456",  # Metadata key
                "source": "llm"  # Metadata key
            },
            explanation="The test expected 2 but the function returns 1"
        )
    
    def test_apply_suggestion_success(self, analyzer_service, fix_suggestion, tmp_path):
        """Test that apply_suggestion successfully applies changes when validation passes."""
        # Set up test file
        source_file = tmp_path / "source_file.py"
        source_file.write_text("original code")
        
        # Update file path in suggestion to point to test file
        fix_suggestion.code_changes[str(source_file)] = "corrected code content"
        
        # Mock FixApplier.apply_fix to succeed
        with patch.object(FixApplier, 'apply_fix') as mock_apply_fix:
            mock_apply_fix.return_value = FixApplicationResult(
                success=True,
                message="Fix applied successfully",
                applied_files=[source_file],
                rolled_back_files=[]
            )
            
            # Apply suggestion
            result = analyzer_service.apply_suggestion(fix_suggestion)
            
            # Check that FixApplier was called correctly
            mock_apply_fix.assert_called_once()
            code_changes_arg = mock_apply_fix.call_args[0][0]
            tests_arg = mock_apply_fix.call_args[0][1]
            
            # Check arguments passed to FixApplier
            assert str(source_file) in code_changes_arg, "Source file path should be in code_changes"
            assert "fingerprint" not in code_changes_arg, "Metadata key 'fingerprint' should be filtered out"
            assert "source" not in code_changes_arg, "Metadata key 'source' should be filtered out"
            assert tests_arg == ["test_module::test_function"], "Test name should be passed for validation"
            
            # Check result
            assert result.success, "Should return success status from FixApplier"
            assert source_file in result.applied_files, "Applied files should include source file"
    
    def test_apply_suggestion_failure(self, analyzer_service, fix_suggestion, tmp_path):
        """Test that apply_suggestion handles validation failures correctly."""
        # Set up test file
        source_file = tmp_path / "source_file.py"
        source_file.write_text("original code")
        
        # Update file path in suggestion to point to test file
        fix_suggestion.code_changes[str(source_file)] = "corrected code content"
        
        # Mock FixApplier.apply_fix to fail
        with patch.object(FixApplier, 'apply_fix') as mock_apply_fix:
            mock_apply_fix.return_value = FixApplicationResult(
                success=False,
                message="Validation failed",
                applied_files=[],
                rolled_back_files=[source_file]
            )
            
            # Apply suggestion
            result = analyzer_service.apply_suggestion(fix_suggestion)
            
            # Check result
            assert not result.success, "Should return failure status from FixApplier"
            assert source_file in result.rolled_back_files, "Rolled back files should include source file"
    
    def test_apply_suggestion_no_failure(self, analyzer_service):
        """Test handling of suggestion without failure information."""
        # Create suggestion without failure
        suggestion = FixSuggestion(
            failure=None,
            suggestion="Fix without failure info",
            confidence=0.8,
            code_changes={"/path/to/file.py": "code"}
        )
        
        # Apply suggestion
        result = analyzer_service.apply_suggestion(suggestion)
        
        # Check result
        assert not result.success, "Should fail when suggestion has no failure info"
        assert "Missing original failure information" in result.message
    
    def test_apply_suggestion_no_code_changes(self, analyzer_service, failure):
        """Test handling of suggestion without code changes."""
        # Create suggestion without code changes
        suggestion = FixSuggestion(
            failure=failure,
            suggestion="Fix without code changes",
            confidence=0.8,
            code_changes={}
        )
        
        # Apply suggestion
        result = analyzer_service.apply_suggestion(suggestion)
        
        # Check result
        assert not result.success, "Should fail when suggestion has no code changes"
        assert "No code changes provided" in result.message
    
    def test_apply_suggestion_metadata_only(self, analyzer_service, failure):
        """Test handling of suggestion with only metadata in code changes."""
        # Create suggestion with only metadata
        suggestion = FixSuggestion(
            failure=failure,
            suggestion="Fix with only metadata",
            confidence=0.8,
            code_changes={"source": "llm", "fingerprint": "abcdef123456"}
        )
        
        # Apply suggestion
        result = analyzer_service.apply_suggestion(suggestion)
        
        # Check result
        assert not result.success, "Should fail when suggestion has only metadata"
        assert "No valid file changes found" in result.message
    
    def test_apply_suggestion_custom_validation_tests(self, analyzer_service, fix_suggestion, tmp_path):
        """Test using custom validation tests instead of the failure test."""
        # Set up test file
        source_file = tmp_path / "source_file.py"
        source_file.write_text("original code")
        
        # Update file path in suggestion to point to test file
        fix_suggestion.code_changes[str(source_file)] = "corrected code content"
        
        # Add custom validation tests
        fix_suggestion.validation_tests = ["custom_test1", "custom_test2"]
        
        # Mock FixApplier.apply_fix
        with patch.object(FixApplier, 'apply_fix') as mock_apply_fix:
            mock_apply_fix.return_value = FixApplicationResult(
                success=True,
                message="Fix applied successfully",
                applied_files=[source_file],
                rolled_back_files=[]
            )
            
            # Apply suggestion
            analyzer_service.apply_suggestion(fix_suggestion)
            
            # Check that custom tests were used
            tests_arg = mock_apply_fix.call_args[0][1]
            assert tests_arg == ["custom_test1", "custom_test2"], "Custom validation tests should be used"


if __name__ == "__main__":
    pytest.main(["-v", __file__])