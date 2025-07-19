"""
Tests for the dependency validator module.

This module tests the security-enhanced dependency validation functionality
including version checks, integrity validation, and vulnerability detection.
"""

import sys
from unittest.mock import MagicMock, Mock, patch

import pytest

from pytest_analyzer.utils.dependency_validator import (
    MIN_VERSIONS,
    VULNERABLE_VERSIONS,
    _check_version_security,
    _get_import_name,
    _parse_version,
    _validate_package_integrity,
    get_dependency_report,
    validate_dependencies,
)


class TestGetImportName:
    """Test the _get_import_name function."""

    def test_mapped_packages(self):
        """Test packages with explicit mappings."""
        assert _get_import_name("pyyaml") == "yaml"
        assert _get_import_name("python-dotenv") == "dotenv"
        assert _get_import_name("prometheus_client") == "prometheus_client"

    def test_unmapped_packages(self):
        """Test packages without explicit mappings."""
        assert _get_import_name("some-package") == "some_package"
        assert _get_import_name("another-pkg") == "another_pkg"
        assert _get_import_name("simple") == "simple"


class TestParseVersion:
    """Test the _parse_version function."""

    def test_standard_versions(self):
        """Test parsing standard version strings."""
        assert _parse_version("1.0.0") == (1, 0, 0)
        assert _parse_version("2.3.4") == (2, 3, 4)
        assert _parse_version("10.20.30") == (10, 20, 30)

    def test_prerelease_versions(self):
        """Test parsing pre-release version strings."""
        assert _parse_version("1.0.0.dev0") == (1, 0, 0)
        assert _parse_version("2.0.0rc1") == (2, 0, 0)
        assert _parse_version("3.0.0a1") == (3, 0, 0)
        assert _parse_version("4.0.0b2") == (4, 0, 0)

    def test_invalid_versions(self):
        """Test parsing invalid version strings."""
        assert _parse_version("invalid") == (0,)
        assert _parse_version("1.x.3") == (0,)
        assert _parse_version("") == (0,)

    def test_version_comparison(self):
        """Test that parsed versions can be compared correctly."""
        assert _parse_version("2.0.0") > _parse_version("1.9.9")
        assert _parse_version("1.10.0") > _parse_version("1.9.0")
        assert _parse_version("1.0.10") > _parse_version("1.0.9")


class TestCheckVersionSecurity:
    """Test the _check_version_security function."""

    def test_no_security_issues(self):
        """Test package with no security issues."""
        warnings = _check_version_security("some_package", "1.0.0")
        assert warnings == []

    def test_below_minimum_version(self):
        """Test package below minimum required version."""
        # Use a real package from MIN_VERSIONS
        warnings = _check_version_security("pydantic", "1.10.0")
        assert len(warnings) == 1
        assert "below minimum required version" in warnings[0]
        assert "2.0.0" in warnings[0]  # Min version from MIN_VERSIONS

    def test_meets_minimum_version(self):
        """Test package that meets minimum version."""
        warnings = _check_version_security("pydantic", "2.0.0")
        assert warnings == []

        warnings = _check_version_security("pydantic", "2.5.0")
        assert warnings == []

    @patch.dict(VULNERABLE_VERSIONS, {"test_package": ["1.0.0", "1.0.1"]})
    def test_vulnerable_version(self):
        """Test detection of vulnerable versions."""
        warnings = _check_version_security("test_package", "1.0.0")
        assert len(warnings) == 1
        assert "CRITICAL" in warnings[0]
        assert "known vulnerabilities" in warnings[0]

        # Non-vulnerable version
        warnings = _check_version_security("test_package", "1.0.2")
        assert warnings == []


class TestValidatePackageIntegrity:
    """Test the _validate_package_integrity function."""

    def test_package_not_found(self):
        """Test validation when package is not found."""
        with patch(
            "importlib.metadata.distribution", side_effect=Exception("Not found")
        ):
            warnings = _validate_package_integrity("nonexistent_package")
            assert warnings == []  # Should handle gracefully

    def test_package_no_files(self):
        """Test package with no files."""
        mock_dist = Mock()
        mock_dist.files = None

        with patch("importlib.metadata.distribution", return_value=mock_dist):
            warnings = _validate_package_integrity("test_package")
            assert len(warnings) == 1
            assert "No files found" in warnings[0]

    def test_package_with_normal_files(self):
        """Test package with normal file locations."""
        mock_file = Mock()
        mock_file.is_absolute.return_value = False
        mock_file.__str__ = lambda x: "site-packages/test_package/module.py"

        mock_dist = Mock()
        mock_dist.files = [mock_file]

        with patch("importlib.metadata.distribution", return_value=mock_dist):
            with patch("pathlib.Path", return_value=mock_file):
                warnings = _validate_package_integrity("test_package")
                assert warnings == []

    def test_package_with_suspicious_files(self):
        """Test package with files in suspicious locations."""
        # Create string representations of suspicious paths
        suspicious_file_abs = "/etc/passwd"
        suspicious_file_sys = "etc/malicious/config"

        # Create mock distribution with file paths as strings
        mock_dist = Mock()
        mock_dist.files = [suspicious_file_abs, suspicious_file_sys]

        with patch("importlib.metadata.distribution", return_value=mock_dist):
            warnings = _validate_package_integrity("test_package")
            assert len(warnings) >= 1
            assert "suspicious locations" in warnings[0]


class TestValidateDependencies:
    """Test the validate_dependencies function."""

    def test_all_dependencies_present_and_secure(self):
        """Test when all dependencies are present and secure."""
        # Mock successful imports
        with patch("importlib.import_module"):
            # Mock version checks to return valid versions
            with patch("importlib.metadata.version", return_value="2.5.0"):
                # Mock integrity checks to return no warnings
                with patch(
                    "pytest_analyzer.utils.dependency_validator._validate_package_integrity",
                    return_value=[],
                ):
                    # Should not raise any exceptions
                    validate_dependencies()

    def test_missing_required_dependency(self):
        """Test when a required dependency is missing."""

        def mock_import(name):
            if name == "pydantic":
                raise ImportError("No module named 'pydantic'")
            return MagicMock()

        with patch("importlib.import_module", side_effect=mock_import):
            with pytest.raises(RuntimeError) as exc_info:
                validate_dependencies()
            assert "pydantic" in str(exc_info.value)
            assert "Critical" in str(exc_info.value)

    def test_security_issue_in_dependency(self):
        """Test when a dependency has security issues."""
        # Mock import_module to succeed for all dependencies
        with patch(
            "pytest_analyzer.utils.dependency_validator.importlib.import_module"
        ):
            with patch(
                "pytest_analyzer.utils.dependency_validator.importlib.metadata.version",
                return_value="1.0.0",
            ):
                # Mock _check_version_security to return security warnings for pydantic
                def mock_security_check(dep, version):
                    if dep == "pydantic":  # First required dependency
                        return [
                            f"Security: {dep} version {version} is below minimum required version 2.0.0"
                        ]
                    return []

                with patch(
                    "pytest_analyzer.utils.dependency_validator._check_version_security",
                    side_effect=mock_security_check,
                ):
                    with patch(
                        "pytest_analyzer.utils.dependency_validator._validate_package_integrity",
                        return_value=[],
                    ):
                        with pytest.raises(RuntimeError) as exc_info:
                            validate_dependencies()
                        assert "Security" in str(exc_info.value)
                        assert "security issues were found" in str(exc_info.value)

    def test_integrity_issue_in_dependency(self):
        """Test when a dependency has integrity issues."""
        with patch("importlib.import_module"):
            with patch("importlib.metadata.version", return_value="2.5.0"):
                # Mock integrity check to return warnings
                with patch(
                    "pytest_analyzer.utils.dependency_validator._validate_package_integrity",
                    return_value=["Security: Package contains suspicious files"],
                ):
                    with pytest.raises(RuntimeError) as exc_info:
                        validate_dependencies()
                    assert "Security" in str(exc_info.value)
                    assert "suspicious" in str(exc_info.value)

    def test_missing_optional_dependency(self):
        """Test when optional dependencies are missing."""

        def mock_import(name):
            if name == "yaml":  # pyyaml
                raise ImportError("No module named 'yaml'")
            return MagicMock()

        with patch("importlib.import_module", side_effect=mock_import):
            with patch("importlib.metadata.version", return_value="2.5.0"):
                with patch(
                    "pytest_analyzer.utils.dependency_validator._validate_package_integrity",
                    return_value=[],
                ):
                    # Should not raise exception for optional deps
                    validate_dependencies()


class TestGetDependencyReport:
    """Test the get_dependency_report function."""

    def test_report_structure(self):
        """Test that the report has the expected structure."""
        with patch("importlib.import_module"):
            with patch("importlib.metadata.version", return_value="2.5.0"):
                report = get_dependency_report()

        assert "required" in report
        assert "optional" in report
        assert "security_warnings" in report
        assert "python_version" in report
        assert report["python_version"] == sys.version

    def test_report_with_mixed_dependencies(self):
        """Test report with some installed and some missing dependencies."""

        def mock_import(name):
            if name in ["yaml", "dotenv"]:  # Mock missing optional deps
                raise ImportError(f"No module named '{name}'")
            return MagicMock()

        with patch("importlib.import_module", side_effect=mock_import):
            with patch("importlib.metadata.version", return_value="2.5.0"):
                report = get_dependency_report()

        # Check required dependencies
        assert "pydantic" in report["required"]
        assert report["required"]["pydantic"]["installed"] is True
        # Just verify that some version was returned
        assert report["required"]["pydantic"]["version"] is not None

        # Check optional dependencies
        assert "pyyaml" in report["optional"]
        assert report["optional"]["pyyaml"]["installed"] is False
        assert report["optional"]["pyyaml"]["version"] is None

    def test_report_with_security_warnings(self):
        """Test report includes security warnings."""
        with patch("importlib.import_module"):
            # Mock a version below minimum
            with patch("importlib.metadata.version", return_value="1.0.0"):
                report = get_dependency_report()

        # Should have security warnings
        assert len(report["security_warnings"]) > 0
        assert any(
            "below minimum required version" in warning
            for warning in report["security_warnings"]
        )

        # Individual packages should also show their issues
        for dep_type in ["required", "optional"]:
            for dep_name, dep_info in report[dep_type].items():
                if dep_name in MIN_VERSIONS and dep_info["installed"]:
                    assert len(dep_info["security_issues"]) > 0
