"""Environment management module for pytest-analyzer."""

from .detector import EnvironmentManagerDetector
from .protocol import EnvironmentManager

__all__ = ["EnvironmentManager", "EnvironmentManagerDetector"]
