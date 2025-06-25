"""Feature flag system for pytest-analyzer.

This module provides feature flag functionality using Flagsmith for:
- A/B testing different configurations
- Remote feature toggles
- Gradual rollouts
- Safe deployments
"""

from .feature_flag_service import FlagsmithFeatureFlagService
from .protocols import FeatureFlagServiceProtocol

__all__ = ["FlagsmithFeatureFlagService", "FeatureFlagServiceProtocol"]
