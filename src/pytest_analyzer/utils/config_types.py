# This file defines the structure of configuration objects, like the Settings dataclass.
# It helps avoid circular dependencies by separating the type definition from its usage.

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


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
    llm_provider: str = "auto"  # Provider to use (anthropic, openai, azure, etc.)
    use_fallback: bool = True  # Whether to try fallback providers if primary fails
    auto_apply: bool = False  # Whether to automatically apply suggested fixes

    # Provider-specific settings
    anthropic_api_key: Optional[str] = None  # Anthropic API key
    openai_api_key: Optional[str] = None  # OpenAI API key
    azure_api_key: Optional[str] = None  # Azure OpenAI API key
    azure_endpoint: Optional[str] = None  # Azure OpenAI endpoint
    azure_api_version: str = "2023-05-15"  # Azure OpenAI API version
    together_api_key: Optional[str] = None  # Together.ai API key
    ollama_host: str = "localhost"  # Ollama host
    ollama_port: int = 11434  # Ollama port

    # Git integration settings
    check_git: bool = True  # Whether to check for Git compatibility
    auto_init_git: bool = False  # Whether to auto-initialize Git without prompting
    use_git_branches: bool = True  # Whether to create branches for fix suggestions

    # Path settings
    project_root: Optional[Path] = None  # Root directory of the project
    mock_directories: Dict[str, str] = field(
        default_factory=dict
    )  # Absolute path mappings

    # Async processing settings
    batch_size: int = 5  # Number of failures to process in each batch in async mode
    max_concurrency: int = 10  # Maximum concurrent LLM requests in async mode

    # Logging settings
    log_level: str = "INFO"  # Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    # Backward compatibility properties
    debug: bool = False  # Enable debug mode (backward compatibility)

    def __post_init__(self):
        # Convert project_root to Path if it's a string
        if self.project_root and isinstance(self.project_root, str):
            self.project_root = Path(self.project_root)

        # Set default project root if not provided
        if not self.project_root:
            self.project_root = Path.cwd()

        # Synchronize debug and log_level for backward compatibility
        if self.debug and self.log_level != "DEBUG":
            self.log_level = "DEBUG"
        elif self.log_level == "DEBUG" and not self.debug:
            self.debug = True
