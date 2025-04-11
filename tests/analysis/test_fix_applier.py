#!/usr/bin/env python3
"""
Unit tests for the FixApplier class.

These tests verify that the FixApplier:
1. Creates proper backups
2. Applies changes correctly
3. Validates changes
4. Rolls back changes when validation fails
"""

import os
import sys
import pytest
import subprocess
from unittest.mock import patch, MagicMock
from pathlib import Path

from pytest_analyzer.core.analysis.fix_applier import FixApplier, FixApplicationResult


class TestFixApplier:
    """Test suite for the FixApplier class."""
    
    def test_backup_creation(self, tmp_path):
        """Test that backups are created correctly."""
        # Create test file
        test_file = tmp_path / "test_file.py"
        test_file.write_text("original content")
        
        # Initialize FixApplier with test directory
        applier = FixApplier(project_root=tmp_path)
        
        # Mock validation to always succeed
        with patch.object(applier, '_run_validation_tests', return_value=True):
            # Apply changes
            result = applier.apply_fix(
                {str(test_file): "new content"},
                ["dummy_test"]
            )
            
            # Check backup was created
            backup_file = test_file.with_suffix(test_file.suffix + applier.backup_suffix)
            assert backup_file.exists(), "Backup file was not created"
            assert backup_file.read_text() == "original content", "Backup content is incorrect"
            
            # Check test file was updated
            assert test_file.read_text() == "new content", "File content was not updated"
            
            # Check result
            assert result.success, "Apply operation should succeed"
            assert test_file in result.applied_files, "Applied files should include the test file"
    
    def test_apply_fix_success(self, tmp_path):
        """Test successful application of changes."""
        # Create test files
        file1 = tmp_path / "file1.py"
        file2 = tmp_path / "file2.py"
        file1.write_text("file1 original")
        file2.write_text("file2 original")
        
        # Initialize FixApplier
        applier = FixApplier(project_root=tmp_path)
        
        # Mock validation to succeed
        with patch.object(applier, '_run_validation_tests', return_value=True):
            # Apply changes to both files
            result = applier.apply_fix(
                {
                    str(file1): "file1 modified",
                    str(file2): "file2 modified"
                },
                ["dummy_test"]
            )
            
            # Check files were updated
            assert file1.read_text() == "file1 modified", "File 1 not updated"
            assert file2.read_text() == "file2 modified", "File 2 not updated"
            
            # Check result
            assert result.success, "Apply operation should succeed"
            assert len(result.applied_files) == 2, "Should have applied changes to 2 files"
            assert file1 in result.applied_files, "Applied files should include file1"
            assert file2 in result.applied_files, "Applied files should include file2"
    
    def test_validation_success(self, tmp_path):
        """Test validation passes when tests succeed."""
        # Create test file
        test_file = tmp_path / "test_file.py"
        test_file.write_text("original content")
        
        # Initialize FixApplier
        applier = FixApplier(project_root=tmp_path)
        
        # Mock subprocess.run to simulate passing tests
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            
            # Apply changes
            result = applier.apply_fix(
                {str(test_file): "new content"},
                ["test_module::test_func"]
            )
            
            # Check validation was called correctly
            mock_run.assert_called_once()
            args, kwargs = mock_run.call_args
            assert args[0][0] == "pytest", "Should call pytest for validation"
            assert args[0][1] == "-v", "Should use verbose mode"
            assert args[0][2] == "test_module::test_func", "Should call the specified test"
            assert kwargs['cwd'] == tmp_path, "Should run in the project root"
            
            # Check result
            assert result.success, "Apply operation should succeed when validation passes"
    
    def test_validation_failure(self, tmp_path):
        """Test changes are rolled back when validation fails."""
        # Create test file
        test_file = tmp_path / "test_file.py"
        test_file.write_text("original content")
        
        # Initialize FixApplier
        applier = FixApplier(project_root=tmp_path)
        
        # Mock subprocess.run to simulate failing tests
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            
            # Apply changes
            result = applier.apply_fix(
                {str(test_file): "new content"},
                ["test_module::test_func"]
            )
            
            # Check validation was called
            mock_run.assert_called_once()
            
            # Check file was rolled back
            assert test_file.read_text() == "original content", "File should be rolled back to original content"
            
            # Check result
            assert not result.success, "Apply operation should fail when validation fails"
            assert len(result.rolled_back_files) == 1, "Should have rolled back 1 file"
    
    def test_file_not_found(self, tmp_path):
        """Test handling of non-existent files."""
        # Non-existent file
        non_existent_file = tmp_path / "non_existent.py"
        
        # Initialize FixApplier
        applier = FixApplier(project_root=tmp_path)
        
        # Apply changes to non-existent file
        result = applier.apply_fix(
            {str(non_existent_file): "new content"},
            ["dummy_test"]
        )
        
        # Check result
        assert not result.success, "Apply operation should fail for non-existent files"
        assert "not found" in result.message, "Error message should indicate file not found"
    
    def test_rollback_success(self, tmp_path):
        """Test rollback restores files correctly."""
        # Create test files
        file1 = tmp_path / "file1.py"
        file2 = tmp_path / "file2.py"
        file1.write_text("file1 original")
        file2.write_text("file2 original")
        
        # Initialize FixApplier
        applier = FixApplier(project_root=tmp_path)
        
        # Mock validation to fail
        with patch.object(applier, '_run_validation_tests', return_value=False):
            # Apply changes to both files
            result = applier.apply_fix(
                {
                    str(file1): "file1 modified",
                    str(file2): "file2 modified"
                },
                ["dummy_test"]
            )
            
            # Check files were rolled back
            assert file1.read_text() == "file1 original", "File 1 not rolled back"
            assert file2.read_text() == "file2 original", "File 2 not rolled back"
            
            # Check result
            assert not result.success, "Apply operation should fail"
            assert len(result.rolled_back_files) == 2, "Should have rolled back 2 files"
            assert file1 in result.rolled_back_files, "Rolled back files should include file1"
            assert file2 in result.rolled_back_files, "Rolled back files should include file2"
    
    def test_skip_metadata_keys(self, tmp_path):
        """Test that metadata keys in code_changes are skipped."""
        # Create test file
        test_file = tmp_path / "test_file.py"
        test_file.write_text("original content")
        
        # Initialize FixApplier
        applier = FixApplier(project_root=tmp_path)
        
        # Mock validation to succeed
        with patch.object(applier, '_run_validation_tests', return_value=True):
            # Apply changes including metadata
            result = applier.apply_fix(
                {
                    str(test_file): "new content",
                    "source": "llm",  # Metadata key
                    "fingerprint": "abcdef123456"  # Metadata key
                },
                ["dummy_test"]
            )
            
            # Check only the file was updated
            assert test_file.read_text() == "new content", "File not updated"
            assert not Path(tmp_path / "source").exists(), "Metadata key 'source' was treated as file"
            assert not Path(tmp_path / "fingerprint").exists(), "Metadata key 'fingerprint' was treated as file"
            
            # Check result
            assert result.success, "Apply operation should succeed"
            assert len(result.applied_files) == 1, "Should have applied changes to 1 file"
    
    def test_show_diff(self, tmp_path):
        """Test diff generation."""
        # Create test file
        test_file = tmp_path / "test_file.py"
        test_file.write_text("line1\nline2\nline3\n")
        
        # Initialize FixApplier
        applier = FixApplier(project_root=tmp_path)
        
        # Generate diff
        diff = applier.show_diff(test_file, "line1\nmodified line\nline3\n")
        
        # Check diff content
        assert "--- a/test_file.py" in diff, "Diff should include filename in 'from' line"
        assert "+++ b/test_file.py" in diff, "Diff should include filename in 'to' line"
        assert "-line2" in diff, "Diff should show removed line"
        assert "+modified line" in diff, "Diff should show added line"


if __name__ == "__main__":
    pytest.main(["-v", __file__])