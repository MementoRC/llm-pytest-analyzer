"""
Backward compatibility module for legacy API access.

This module provides aliases and compatibility layers to ensure that code using
the original API continues to work with the new architecture.
"""

import warnings
from typing import Any, Optional

from ..utils.settings import Settings

# Import the facade
from .analyzer_facade import PytestAnalyzerFacade


# For backwards compatibility, we provide the original class name
# that just forwards to our new facade implementation
class PytestAnalyzerService(PytestAnalyzerFacade):
    """
    Legacy class name that redirects to the new implementation.

    This class is provided for backward compatibility with existing code that
    uses the original PytestAnalyzerService class.
    """

    def __init__(
        self, settings: Optional[Settings] = None, llm_client: Optional[Any] = None
    ):
        """
        Initialize the service with a deprecation warning.

        Args:
            settings: Settings object
            llm_client: Optional client for language model API
        """
        warnings.warn(
            "PytestAnalyzerService is deprecated. Use PytestAnalyzerFacade instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(settings, llm_client)
