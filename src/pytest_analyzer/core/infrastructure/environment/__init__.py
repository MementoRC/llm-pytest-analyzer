"""Environment manager implementations.

Contains concrete implementations for different Python environment
managers like Poetry, Pipenv, Hatch, UV, and Pixi.
"""

from .base_manager import BaseEnvironmentManager

__all__ = ["BaseEnvironmentManager"]
