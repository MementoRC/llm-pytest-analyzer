import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Optional, Type, TypeVar

from ...utils.config_types import Settings

T = TypeVar("T")


class BaseFactory(ABC):
    """Base factory class to eliminate duplication across factory implementations."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        self.logger = logging.getLogger(self.__class__.__name__)
        self._registry: Dict[str, Type[T]] = {}

    def register(self, key: str, implementation: Type[T]) -> None:
        """Register an implementation with a specific key."""
        self.logger.debug(f"Registering {implementation.__name__} with key '{key}'")
        self._registry[key] = implementation

    def get_implementation(self, key: str) -> Type[T]:
        """Get the implementation for a specific key."""
        if key not in self._registry:
            self.logger.error(f"No implementation registered for key '{key}'")
            raise KeyError(f"No implementation registered for key '{key}'")
        return self._registry[key]

    def _detect_file_type(self, file_path: str) -> str:
        """Common file detection logic based on file extension or content."""
        path = Path(file_path)
        return path.suffix.lower()[1:] if path.suffix else ""

    @abstractmethod
    def create(self, *args, **kwargs) -> T:
        """Create an instance of the appropriate implementation."""
        pass
