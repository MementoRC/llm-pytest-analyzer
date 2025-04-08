from pathlib import Path
import os
import logging
from typing import Optional, Union, Dict

logger = logging.getLogger(__name__)


class PathResolver:
    """Handles path resolution across different environments."""
    
    def __init__(self, project_root: Optional[Path] = None, 
                 mock_dirs: Optional[Dict[str, Path]] = None):
        """
        Initialize the path resolver.
        
        Args:
            project_root: Root directory of the project
            mock_dirs: Dictionary mapping absolute path prefixes to mock locations
        """
        self.project_root = project_root or Path.cwd()
        self.mock_dirs = mock_dirs or {}
        self.mock_root = self.project_root / "mocked"
        
        # Ensure mock root exists
        self.mock_root.mkdir(parents=True, exist_ok=True)
        
    def resolve_path(self, path_str: str) -> Path:
        """
        Resolve a path string to an absolute Path object.
        
        For absolute paths that might cause permission issues,
        creates a mock path inside the project root.
        
        Args:
            path_str: String representation of the path
            
        Returns:
            Resolved Path object
        """
        # Handle empty or None paths
        if not path_str:
            return self.project_root
            
        path = Path(path_str)
        
        if path.is_absolute():
            # Check if this path matches any of our mock directory mappings
            for prefix, mock_location in self.mock_dirs.items():
                if str(path).startswith(prefix):
                    relative_path = os.path.relpath(str(path), prefix)
                    return mock_location / relative_path
            
            # For absolute paths, create a mock path inside the project root
            path_parts = path.parts[1:]  # Skip the root part
            mock_path = self.mock_root.joinpath(*path_parts)
            mock_path.parent.mkdir(parents=True, exist_ok=True)
            
            logger.debug(f"Mapped absolute path {path} to mock path {mock_path}")
            return mock_path
            
        # For relative paths, resolve against project root
        return (self.project_root / path).resolve()
        
    def relativize(self, path: Union[str, Path]) -> Path:
        """
        Get path relative to project root if possible.
        
        Args:
            path: Path to relativize
            
        Returns:
            Path relative to project root, or the original path if not possible
        """
        path = Path(path) if isinstance(path, str) else path
        
        try:
            return path.relative_to(self.project_root)
        except ValueError:
            # If the path cannot be made relative to the project root,
            # check if it's in a mock directory
            for prefix, mock_location in self.mock_dirs.items():
                try:
                    if str(path).startswith(str(mock_location)):
                        rel_to_mock = path.relative_to(mock_location)
                        return Path(prefix) / rel_to_mock
                except ValueError:
                    continue
                    
            # Return the path as is if it can't be relativized
            return path