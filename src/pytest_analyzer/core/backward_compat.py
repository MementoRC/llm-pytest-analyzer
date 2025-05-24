"""
Backward compatibility module for legacy API access.

This module provides aliases and compatibility layers to ensure that code using
the original API continues to work with the new architecture. It follows the
Adapter design pattern to maintain compatibility with the original API while
leveraging the new architecture's improved design.

Key components:
- PytestAnalyzerService: Legacy class name that inherits from PytestAnalyzerFacade,
  providing the same interface as the original service but using the new implementation.
- Backward compatibility warnings to encourage migration to the new API.
- Transparent redirection of calls to the new implementation.

This implementation allows:
1. Gradual migration from old API to new API
2. Immediate benefits from architectural improvements
3. Minimal changes to existing code
4. A clear migration path for users

For more details on the architectural approach, see docs/facade_architecture.md.
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
    uses the original PytestAnalyzerService class. It inherits all functionality
    from PytestAnalyzerFacade and simply issues a deprecation warning when instantiated.

    This implementation allows:
    - Existing code to continue working without modifications
    - A clear migration path with deprecation warnings
    - Full feature parity with the original service
    - The benefits of the new architecture without API changes

    Example usage:
        # Legacy code continues to work
        from pytest_analyzer.core.analyzer_service import PytestAnalyzerService
        service = PytestAnalyzerService()
        suggestions = service.analyze_pytest_output("test_results.xml")
    """

    def __init__(self, settings: Optional[Settings] = None, llm_client: Optional[Any] = None):
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
