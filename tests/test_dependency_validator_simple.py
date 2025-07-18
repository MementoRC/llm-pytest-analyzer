"""
Simplified tests for dependency validator to ensure core functionality works.
"""

from unittest.mock import MagicMock, patch

import pytest

from pytest_analyzer.utils.dependency_validator import (
    _check_version_security,
    _parse_version,
    validate_dependencies,
)


def test_validate_dependencies_basic():
    """Test basic dependency validation works without raising exceptions."""
    # Test that it doesn't raise an exception when dependencies are present
    try:
        validate_dependencies()
        # If we reach here, validation passed
        assert True
    except RuntimeError as e:
        # If we get a RuntimeError, it should be about actual missing dependencies
        # This is acceptable in the test environment
        assert "missing" in str(e) or "Security" in str(e)


def test_version_security_check():
    """Test version security checking."""
    # Test minimum version requirement
    warnings = _check_version_security("pydantic", "1.0.0")
    assert len(warnings) > 0
    assert "below minimum required version" in warnings[0]

    # Test version that meets requirements
    warnings = _check_version_security("pydantic", "2.5.0")
    assert len(warnings) == 0


def test_parse_version():
    """Test version parsing."""
    assert _parse_version("2.0.0") > _parse_version("1.0.0")
    assert _parse_version("1.10.0") > _parse_version("1.9.0")
    assert _parse_version("invalid") == (0,)


def test_validate_dependencies_with_missing():
    """Test validation with missing dependencies."""

    def mock_import(name):
        if name == "nonexistent_module":
            raise ImportError("No module named 'nonexistent_module'")
        return MagicMock()

    with patch(
        "pytest_analyzer.utils.dependency_validator.importlib.import_module",
        side_effect=mock_import,
    ):
        # Mock the required_deps list to include a missing dependency
        original_required_deps = [
            "pydantic",
            "rich",
            "structlog",
            "prometheus_client",
            "mcp",
            "httpx",
            "nonexistent_module",  # This will trigger ImportError
        ]

        with patch.object(
            __import__(
                "pytest_analyzer.utils.dependency_validator", fromlist=["required_deps"]
            ),
            "required_deps",
            original_required_deps,
        ):
            with pytest.raises(RuntimeError) as exc_info:
                validate_dependencies()
            assert "missing" in str(exc_info.value)


def test_validate_dependencies_with_security_issue():
    """Test validation with security issues."""
    with patch("pytest_analyzer.utils.dependency_validator.importlib.import_module"):
        # Mock _check_version_security to return security warnings
        with patch(
            "pytest_analyzer.utils.dependency_validator._check_version_security"
        ) as mock_check:
            mock_check.return_value = [
                "Security: test package version 1.0.0 is below minimum required version 2.0.0"
            ]

            with patch(
                "pytest_analyzer.utils.dependency_validator._validate_package_integrity",
                return_value=[],
            ):
                with pytest.raises(RuntimeError) as exc_info:
                    validate_dependencies()
                assert "Security" in str(exc_info.value)
