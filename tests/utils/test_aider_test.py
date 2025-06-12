"""Tests for Aider integration utilities."""

from pathlib import Path

from pytest_analyzer.utils.aider_test import get_integration_status


def test_get_integration_status(tmp_path: Path):
    """Test that integration status detection works correctly."""
    # Create a mock project structure
    (tmp_path / "pixi.toml").touch()
    (tmp_path / "tests").mkdir()

    status = get_integration_status(tmp_path)

    assert status.project_root == tmp_path
    assert status.config_found is True
    assert status.test_directory == tmp_path / "tests"


def test_get_integration_status_no_config(tmp_path: Path):
    """Test integration status when config is missing."""
    status = get_integration_status(tmp_path)

    assert status.project_root == tmp_path
    assert status.config_found is False
    assert status.test_directory is None
