from pathlib import Path
import os
import logging
import atexit
import shutil
from typing import Optional, Union, Dict

logger = logging.getLogger(__name__)


class PathResolver:
    """Handles path resolution across different environments."""
    
    # Track all temporary directories created for cleanup
    _temp_dirs = []
    
    @classmethod
    def _cleanup_temp_dirs(cls):
        """Clean up all temporary directories on exit."""
        for temp_dir in cls._temp_dirs:
            try:
                if temp_dir.exists():
                    logger.info(f"Cleaning up temporary directory: {temp_dir}")
                    shutil.rmtree(temp_dir)
            except Exception as e:
                logger.warning(f"Error cleaning up temporary directory {temp_dir}: {e}")
    
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
        self.using_temp_dir = False
        
        # Ensure mock root exists
        try:
            self.mock_root.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            # If we can't create in the project root, fall back to a temp directory
            import tempfile
            temp_dir_path = Path(tempfile.mkdtemp(prefix="pytest_analyzer_"))
            self.mock_root = temp_dir_path
            self.using_temp_dir = True
            
            # Add to cleanup list
            PathResolver._temp_dirs.append(temp_dir_path)
            
            # Register cleanup at exit if this is the first temporary directory
            if len(PathResolver._temp_dirs) == 1:
                atexit.register(PathResolver._cleanup_temp_dirs)
                
            logger.info(f"Using temporary mock directory: {self.mock_root}")
        
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
        
        # First, check if the path is in a mock directory
        for prefix, mock_location in self.mock_dirs.items():
            try:
                # Use is_relative_to (Python 3.9+) to check if path is under mock_location
                if path.is_relative_to(mock_location):
                    rel_to_mock = path.relative_to(mock_location)
                    return Path(prefix) / rel_to_mock
            except ValueError:
                continue
                
        # If not in a mock directory, try to make it relative to the project root
        try:
            return path.relative_to(self.project_root)
        except ValueError:
            # Return the path as is if it can't be relativized
            return path