"""
Dependency validation utility for pytest-analyzer.

This module provides functionality to validate that all required and optional
dependencies are properly installed and secure before the application starts.
Includes security checks for dependency integrity and version compatibility.
"""

import importlib
import importlib.metadata
import logging
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Configure logging for this module
logger = logging.getLogger(__name__)

# Map package names to their importable module names if they differ
DEPENDENCY_MAP = {
    "pyyaml": "yaml",
    "python-dotenv": "dotenv",
    "prometheus_client": "prometheus_client",
    "pytest-asyncio": "pytest_asyncio",
    "pytest-cov": "pytest_cov",
    "pytest-json-report": "pytest_json_report",
    "httpx-sse": "httpx_sse",
    "sse-starlette": "sse_starlette",
}

# Security: Minimum required versions for critical dependencies
MIN_VERSIONS = {
    "pydantic": "2.0.0",  # For security fixes and v2 validation
    "structlog": "22.0.0",  # For security logging features
    "httpx": "0.24.0",  # For security headers support
    "mcp": "1.0.0",  # Minimum MCP protocol version
}

# Security: Known vulnerable versions to block
VULNERABLE_VERSIONS = {
    # Format: "package": ["vulnerable_version1", "vulnerable_version2"]
    # Add specific vulnerable versions as they are discovered
}

# Security: Allowed dependency sources (for future enhancement)
ALLOWED_SOURCES = {
    "pypi.org",
    "files.pythonhosted.org",
}


def _get_import_name(package_name: str) -> str:
    """
    Returns the importable module name for a given package name.
    Defaults to replacing hyphens with underscores if no specific mapping exists.
    """
    return DEPENDENCY_MAP.get(package_name, package_name.replace("-", "_"))


def _parse_version(version_str: str) -> Tuple[int, ...]:
    """
    Parse a version string into a tuple of integers for comparison.

    Args:
        version_str: Version string like "2.0.1" or "1.2.3.dev0"

    Returns:
        Tuple of integers for version comparison
    """
    # Remove any pre-release/dev suffixes for basic comparison
    clean_version = (
        version_str.split(".dev")[0].split("rc")[0].split("a")[0].split("b")[0]
    )
    try:
        return tuple(int(x) for x in clean_version.split("."))
    except ValueError:
        logger.warning(f"Could not parse version: {version_str}")
        return (0,)


def _check_version_security(package_name: str, version: str) -> List[str]:
    """
    Check if a package version meets security requirements.

    Args:
        package_name: Name of the package
        version: Installed version

    Returns:
        List of security warnings (empty if secure)
    """
    warnings = []

    # Check for known vulnerable versions
    if package_name in VULNERABLE_VERSIONS:
        if version in VULNERABLE_VERSIONS[package_name]:
            warnings.append(
                f"CRITICAL: {package_name} version {version} has known vulnerabilities"
            )

    # Check minimum version requirements
    if package_name in MIN_VERSIONS:
        min_version = MIN_VERSIONS[package_name]
        if _parse_version(version) < _parse_version(min_version):
            warnings.append(
                f"Security: {package_name} version {version} is below minimum "
                f"required version {min_version}"
            )

    return warnings


def _validate_package_integrity(package_name: str) -> List[str]:
    """
    Validate the integrity of an installed package.

    Args:
        package_name: Name of the package to validate

    Returns:
        List of integrity warnings (empty if valid)
    """
    warnings = []

    try:
        # Get package metadata
        dist = importlib.metadata.distribution(package_name)

        # Check if package has files (basic integrity check)
        files = dist.files
        if not files:
            warnings.append(f"Warning: No files found for package {package_name}")

        # Check for suspicious file locations
        if files:
            suspicious_paths = []
            for file in files:
                file_path = Path(file)
                # Check for files outside site-packages
                if file_path.is_absolute():
                    suspicious_paths.append(str(file_path))
                # Check for files in system directories
                # Skip legitimate bin directory installations (common for CLI tools)
                elif any(
                    part in str(file_path) for part in ["etc", "usr"]
                ) and "bin" not in str(file_path):
                    suspicious_paths.append(str(file_path))

            if suspicious_paths:
                warnings.append(
                    f"Security: Package {package_name} contains files in suspicious "
                    f"locations: {suspicious_paths[:3]}"  # Limit output
                )

    except Exception as e:
        logger.debug(f"Could not validate integrity of {package_name}: {e}")

    return warnings


def validate_dependencies() -> None:
    """
    Validates that all required dependencies are installed and secure.

    Performs the following security checks:
    1. Verifies all required dependencies are installed
    2. Checks for known vulnerable versions
    3. Validates minimum version requirements
    4. Performs basic package integrity checks
    5. Logs security warnings for optional dependencies

    Raises:
        RuntimeError: If any critical required dependency is missing or insecure.

    Issues:
        UserWarning: For any missing optional dependencies or security concerns.
    """
    # Core required dependencies for basic functionality
    required_deps = [
        "pydantic",
        "rich",
        "structlog",
        "prometheus_client",
        "mcp",
        "httpx",
    ]

    # Optional dependencies that enhance functionality
    optional_deps = [
        "pyyaml",
        "python-dotenv",
        "pytest-asyncio",
        "pytest-cov",
        "pytest-json-report",
        "httpx-sse",
        "sse-starlette",
    ]

    missing_required: List[str] = []
    security_issues: List[str] = []
    missing_optional: List[str] = []

    # Check required dependencies
    for dep in required_deps:
        import_name = _get_import_name(dep)
        try:
            # Try to import the module
            importlib.import_module(import_name)

            # Get version info for security checks
            try:
                version = importlib.metadata.version(dep)
                logger.debug(f"Found {dep} version {version}")

                # Security checks
                version_warnings = _check_version_security(dep, version)
                if version_warnings:
                    security_issues.extend(version_warnings)

                # Integrity checks
                integrity_warnings = _validate_package_integrity(dep)
                if integrity_warnings:
                    security_issues.extend(integrity_warnings)

            except Exception as e:
                logger.warning(f"Could not check version of {dep}: {e}")

        except ImportError:
            missing_required.append(dep)
            logger.debug(
                f"Required dependency '{dep}' (import '{import_name}') is missing."
            )

    # Check optional dependencies
    for dep in optional_deps:
        import_name = _get_import_name(dep)
        try:
            importlib.import_module(import_name)

            # Version and integrity checks for optional deps too
            try:
                version = importlib.metadata.version(dep)
                version_warnings = _check_version_security(dep, version)
                if version_warnings:
                    for warning in version_warnings:
                        logger.warning(f"Optional dependency: {warning}")

            except Exception:
                pass

        except ImportError:
            missing_optional.append(dep)
            logger.info(f"Optional dependency '{dep}' is not installed.")

    # Report results
    if missing_required:
        error_msg = (
            f"Critical: The following required dependencies are missing: "
            f"{', '.join(missing_required)}. "
            "Please install them to use pytest-analyzer."
        )
        logger.critical(error_msg)
        raise RuntimeError(error_msg)

    if security_issues:
        error_msg = "Security: The following security issues were found:\n" + "\n".join(
            f"  - {issue}" for issue in security_issues
        )
        logger.critical(error_msg)
        raise RuntimeError(error_msg)

    # Log successful validation
    logger.info("All required dependencies are installed and secure.")

    if missing_optional:
        logger.info(
            f"Optional dependencies not installed: {', '.join(missing_optional)}. "
            "Some features may be limited."
        )


def get_dependency_report() -> Dict[str, any]:
    """
    Generate a detailed dependency security report.

    Returns:
        Dictionary containing dependency information and security status
    """
    report = {
        "required": {},
        "optional": {},
        "security_warnings": [],
        "python_version": sys.version,
    }

    # Combine all known dependencies
    all_deps = list(
        set(
            ["pydantic", "rich", "structlog", "prometheus_client", "mcp", "httpx"]
            + list(DEPENDENCY_MAP.keys())
        )
    )

    for dep in all_deps:
        import_name = _get_import_name(dep)
        try:
            importlib.import_module(import_name)
            version = "unknown"

            try:
                version = importlib.metadata.version(dep)
            except Exception:
                pass

            dep_info = {
                "installed": True,
                "version": version,
                "import_name": import_name,
                "security_issues": _check_version_security(dep, version),
            }

            # Categorize as required or optional
            if dep in [
                "pydantic",
                "rich",
                "structlog",
                "prometheus_client",
                "mcp",
                "httpx",
            ]:
                report["required"][dep] = dep_info
            else:
                report["optional"][dep] = dep_info

            # Collect all security warnings
            if dep_info["security_issues"]:
                report["security_warnings"].extend(dep_info["security_issues"])

        except ImportError:
            dep_info = {
                "installed": False,
                "version": None,
                "import_name": import_name,
                "security_issues": [],
            }

            if dep in [
                "pydantic",
                "rich",
                "structlog",
                "prometheus_client",
                "mcp",
                "httpx",
            ]:
                report["required"][dep] = dep_info
            else:
                report["optional"][dep] = dep_info

    return report
