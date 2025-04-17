# This file defines the structure of configuration objects, like the Settings dataclass.
# It helps avoid circular dependencies by separating the type definition from its usage.

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict

# --- Settings Dataclass Definition ---
# Moved here from settings.py
@dataclass
class Settings:
    """Configuration settings for the pytest analyzer."""

    # Pytest execution settings
    pytest_timeout: int = 300  # Maximum time in seconds for pytest execution
    pytest_args: List[str] = field(default_factory=list)  # Additional pytest arguments

    # Resource limits
    max_memory_mb: int = 1024  # Memory limit in MB
    parser_timeout: int = 30   # Timeout for parsing operations
    analyzer_timeout: int = 60  # Timeout for analysis operations

    # Extraction settings
    max_failures: int = 100    # Maximum number of failures to process
    preferred_format: str = "json"  # Preferred output format: json, xml, or text

    # Analysis settings
    max_suggestions: int = 3   # Maximum suggestions overall
    max_suggestions_per_failure: int = 3  # Maximum suggestions per failure
    min_confidence: float = 0.5  # Minimum confidence for suggestions

    # LLM settings
    use_llm: bool = True      # Whether to use LLM-based suggestions
    llm_timeout: int = 60      # Timeout for LLM requests in seconds
    llm_api_key: Optional[str] = None  # API key for LLM service
    llm_model: str = "auto"    # Model to use (auto selects available models)

    # Git integration settings
    check_git: bool = True     # Whether to check for Git compatibility
    auto_init_git: bool = False  # Whether to auto-initialize Git without prompting
    use_git_branches: bool = True  # Whether to create branches for fix suggestions

    # Path settings
    project_root: Optional[Path] = None  # Root directory of the project
    mock_directories: Dict[str, str] = field(default_factory=dict)  # Absolute path mappings

    def __post_init__(self):
        # Convert project_root to Path if it's a string
        if self.project_root and isinstance(self.project_root, str):
            self.project_root = Path(self.project_root)

        # Set default project root if not provided
        if not self.project_root:
            self.project_root = Path.cwd()
