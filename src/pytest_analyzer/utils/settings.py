from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Union


@dataclass
class Settings:
    """Configuration settings for the pytest analyzer."""

    # Pytest execution settings
    pytest_timeout: int = 300  # Maximum time in seconds for pytest execution
    pytest_args: List[str] = field(default_factory=list)  # Additional pytest arguments

    # Resource limits
    max_memory_mb: int = 1024  # Memory limit in MB
    parser_timeout: int = 30  # Timeout for parsing operations
    analyzer_timeout: int = 60  # Timeout for analysis operations

    # Extraction settings
    max_failures: int = 100  # Maximum number of failures to process
    preferred_format: str = "json"  # Preferred output format: json, xml, or text

    # Analysis settings
    max_suggestions: int = 3  # Maximum suggestions overall
    max_suggestions_per_failure: int = 3  # Maximum suggestions per failure
    min_confidence: float = 0.5  # Minimum confidence for suggestions

    # LLM settings
    use_llm: bool = True  # Whether to use LLM-based suggestions
    llm_timeout: int = 60  # Timeout for LLM requests in seconds
    llm_api_key: Optional[str] = None  # API key for LLM service
    llm_model: str = "auto"  # Model to use (auto selects available models)

    # Path settings
    project_root: Optional[Path] = None  # Root directory of the project
    mock_directories: Dict[str, str] = field(
        default_factory=dict
    )  # Absolute path mappings

    def __post_init__(self):
        # Convert project_root to Path if it's a string
        if self.project_root and isinstance(self.project_root, str):
            self.project_root = Path(self.project_root)

        # Set default project root if not provided
        if not self.project_root:
            self.project_root = Path.cwd()


def load_settings(config_file: Optional[Union[str, Path]] = None) -> Settings:
    """
    Load settings from a configuration file.

    Args:
        config_file: Path to the configuration file

    Returns:
        Settings object
    """
    # Default settings
    settings = Settings()

    # If a config file is provided, load settings from it
    if config_file:
        config_path = Path(config_file)
        if config_path.exists():
            # This is a simplified version. In a real implementation,
            # we would parse the config file (e.g., YAML, JSON, TOML)
            # and update the settings accordingly.
            pass

    return settings
