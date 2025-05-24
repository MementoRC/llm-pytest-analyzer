"""
Project management models for the Pytest Analyzer GUI.

This module contains the Project class and related functionality for managing
multiple projects with their own settings and configurations.
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import QObject, pyqtSignal

from ...utils.config_types import Settings

logger = logging.getLogger(__name__)


@dataclass
class ProjectMetadata:
    """Metadata for a project."""

    name: str
    path: Path
    description: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    tags: List[str] = field(default_factory=list)
    test_patterns: List[str] = field(default_factory=lambda: ["test_*.py", "*_test.py"])
    custom_config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Project:
    """Represents a project with its settings and metadata."""

    metadata: ProjectMetadata
    settings: Settings
    _config_file: Optional[Path] = None

    @property
    def name(self) -> str:
        """Get project name."""
        return self.metadata.name

    @property
    def path(self) -> Path:
        """Get project path."""
        return self.metadata.path

    @property
    def config_file(self) -> Path:
        """Get path to project configuration file."""
        if self._config_file is None:
            self._config_file = self.path / ".pytest-analyzer.json"
        return self._config_file

    def save_config(self) -> None:
        """Save project configuration to file."""
        try:
            config_data = {
                "metadata": {
                    "name": self.metadata.name,
                    "description": self.metadata.description,
                    "created_at": self.metadata.created_at.isoformat(),
                    "last_accessed": self.metadata.last_accessed.isoformat(),
                    "tags": self.metadata.tags,
                    "test_patterns": self.metadata.test_patterns,
                    "custom_config": self.metadata.custom_config,
                },
                "settings": self._settings_to_dict(),
            }

            self.config_file.write_text(json.dumps(config_data, indent=2))
            logger.info(f"Saved project config: {self.config_file}")

        except Exception as e:
            logger.error(f"Failed to save project config: {e}")
            raise

    def _settings_to_dict(self) -> Dict[str, Any]:
        """Convert settings to dictionary, handling Path objects."""
        settings_dict = asdict(self.settings)

        # Convert Path objects to strings
        if "project_root" in settings_dict and settings_dict["project_root"]:
            settings_dict["project_root"] = str(settings_dict["project_root"])

        return settings_dict

    @classmethod
    def load_config(cls, project_path: Path) -> "Project":
        """Load project configuration from file."""
        config_file = project_path / ".pytest-analyzer.json"

        if not config_file.exists():
            # Create default project
            return cls.create_default(project_path)

        try:
            config_data = json.loads(config_file.read_text())

            # Load metadata
            metadata_data = config_data.get("metadata", {})
            metadata = ProjectMetadata(
                name=metadata_data.get("name", project_path.name),
                path=project_path,
                description=metadata_data.get("description", ""),
                created_at=datetime.fromisoformat(
                    metadata_data.get("created_at", datetime.now().isoformat())
                ),
                last_accessed=datetime.fromisoformat(
                    metadata_data.get("last_accessed", datetime.now().isoformat())
                ),
                tags=metadata_data.get("tags", []),
                test_patterns=metadata_data.get("test_patterns", ["test_*.py", "*_test.py"]),
                custom_config=metadata_data.get("custom_config", {}),
            )

            # Load settings
            settings_data = config_data.get("settings", {})
            settings = Settings()

            # Apply loaded settings
            for key, value in settings_data.items():
                if hasattr(settings, key):
                    if key == "project_root" and value:
                        setattr(settings, key, Path(value))
                    else:
                        setattr(settings, key, value)

            # Ensure project_root is set to this project's path
            settings.project_root = project_path

            project = cls(metadata=metadata, settings=settings, _config_file=config_file)
            logger.info(f"Loaded project: {project.name} from {config_file}")
            return project

        except Exception as e:
            logger.error(f"Failed to load project config from {config_file}: {e}")
            # Return default project on error
            return cls.create_default(project_path)

    @classmethod
    def create_default(cls, project_path: Path) -> "Project":
        """Create a default project for the given path."""
        metadata = ProjectMetadata(
            name=project_path.name,
            path=project_path,
            description=f"Default project for {project_path.name}",
        )

        settings = Settings()
        settings.project_root = project_path

        return cls(metadata=metadata, settings=settings)

    def update_last_accessed(self) -> None:
        """Update the last accessed timestamp."""
        self.metadata.last_accessed = datetime.now()

    def is_valid_project(self) -> bool:
        """Check if this is a valid project directory."""
        if not self.path.exists() or not self.path.is_dir():
            return False

        # Check for common Python project indicators
        indicators = [
            "pyproject.toml",
            "setup.py",
            "requirements.txt",
            "pytest.ini",
            "tox.ini",
            ".git",
            "tests",
            "test",
        ]

        return any((self.path / indicator).exists() for indicator in indicators)


class ProjectManager(QObject):
    """Manages multiple projects and recent project list."""

    project_changed = pyqtSignal(Project)
    recent_projects_updated = pyqtSignal(list)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._current_project: Optional[Project] = None
        self._recent_projects: List[Path] = []
        self._max_recent = 10
        self._load_recent_projects()

    @property
    def current_project(self) -> Optional[Project]:
        """Get the currently active project."""
        return self._current_project

    def set_current_project(self, project: Project) -> None:
        """Set the current project."""
        if self._current_project != project:
            if self._current_project:
                # Save current project before switching
                try:
                    self._current_project.save_config()
                except Exception as e:
                    logger.error(f"Failed to save current project: {e}")

            self._current_project = project
            project.update_last_accessed()

            # Update recent projects
            self._add_to_recent(project.path)

            self.project_changed.emit(project)
            logger.info(f"Switched to project: {project.name}")

    def open_project(self, project_path: Path) -> Project:
        """Open a project from the given path."""
        project = Project.load_config(project_path)
        self.set_current_project(project)
        return project

    def create_project(self, project_path: Path, name: Optional[str] = None) -> Project:
        """Create a new project in the given path."""
        project_path.mkdir(parents=True, exist_ok=True)

        metadata = ProjectMetadata(
            name=name or project_path.name,
            path=project_path,
            description=f"New project: {name or project_path.name}",
        )

        settings = Settings()
        settings.project_root = project_path

        project = Project(metadata=metadata, settings=settings)
        project.save_config()

        self.set_current_project(project)
        return project

    def get_recent_projects(self) -> List[Path]:
        """Get list of recent projects."""
        return self._recent_projects.copy()

    def _add_to_recent(self, project_path: Path) -> None:
        """Add project to recent list."""
        # Remove if already exists
        if project_path in self._recent_projects:
            self._recent_projects.remove(project_path)

        # Add to beginning
        self._recent_projects.insert(0, project_path)

        # Limit size
        if len(self._recent_projects) > self._max_recent:
            self._recent_projects = self._recent_projects[: self._max_recent]

        self._save_recent_projects()
        self.recent_projects_updated.emit(self._recent_projects.copy())

    def _load_recent_projects(self) -> None:
        """Load recent projects from settings."""
        # This will be implemented to use QSettings
        # For now, we'll start with an empty list
        pass

    def _save_recent_projects(self) -> None:
        """Save recent projects to settings."""
        # This will be implemented to use QSettings
        # For now, we'll just log
        logger.debug(f"Recent projects updated: {len(self._recent_projects)} projects")

    def discover_projects(self, root_path: Path, max_depth: int = 3) -> List[Path]:
        """Discover potential project directories."""
        projects = []

        def _scan_directory(path: Path, depth: int) -> None:
            if depth > max_depth:
                return

            try:
                # Check if current directory is a project
                temp_project = Project.create_default(path)
                if temp_project.is_valid_project():
                    projects.append(path)
                    return  # Don't scan subdirectories of found projects

                # Scan subdirectories
                for item in path.iterdir():
                    if item.is_dir() and not item.name.startswith("."):
                        _scan_directory(item, depth + 1)

            except (PermissionError, OSError):
                # Skip directories we can't access
                pass

        _scan_directory(root_path, 0)
        return projects
