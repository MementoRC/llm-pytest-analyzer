"""Utility functions for testing Aider integration with pytest-analyzer."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class AiderIntegrationStatus:
    """Status of Aider integration with pytest-analyzer."""

    project_root: Path
    config_found: bool
    test_directory: Optional[Path] = None


def get_integration_status(
    project_path: Optional[Path] = None,
) -> AiderIntegrationStatus:
    """
    Get the current status of Aider integration with pytest-analyzer.

    Args:
        project_path: Optional path to the project root. If None, uses current directory.

    Returns:
        AiderIntegrationStatus object containing integration details
    """
    if project_path is None:
        project_path = Path.cwd()

    config_found = (project_path / "pixi.toml").exists()
    test_dir = project_path / "tests" if (project_path / "tests").exists() else None

    return AiderIntegrationStatus(
        project_root=project_path, config_found=config_found, test_directory=test_dir
    )
