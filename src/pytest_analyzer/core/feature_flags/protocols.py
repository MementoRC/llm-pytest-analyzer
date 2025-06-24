"""Protocols for feature flag services."""

from typing import Any, Dict, Optional, Protocol


class FeatureFlagServiceProtocol(Protocol):
    """Protocol for feature flag services."""

    def is_feature_enabled(
        self, feature_key: str, identity: Optional[str] = None
    ) -> bool:
        """Check if a feature is enabled.

        Args:
            feature_key: The feature flag key to check
            identity: Optional user identity for personalized flags

        Returns:
            True if the feature is enabled, False otherwise
        """
        ...

    def get_feature_value(
        self, feature_key: str, identity: Optional[str] = None
    ) -> Any:
        """Get the value of a feature flag.

        Args:
            feature_key: The feature flag key to get value for
            identity: Optional user identity for personalized flags

        Returns:
            The value of the feature flag, or None if not found
        """
        ...

    def get_all_flags(self, identity: Optional[str] = None) -> Dict[str, Any]:
        """Get all feature flags.

        Args:
            identity: Optional user identity for personalized flags

        Returns:
            Dictionary of all feature flags and their values
        """
        ...
