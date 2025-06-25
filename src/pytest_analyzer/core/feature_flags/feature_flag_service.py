"""Feature flag service implementation using Flagsmith."""

import logging
from typing import Any, Dict, Optional

from flagsmith import Flagsmith

from ...utils.config_types import FeatureFlagSettings
from .protocols import FeatureFlagServiceProtocol

logger = logging.getLogger(__name__)


class FlagsmithFeatureFlagService(FeatureFlagServiceProtocol):
    """
    Feature flag service implementation using the Flagsmith SDK.

    This service initializes the Flagsmith client and provides methods to check
    feature flags, get their values, and manage user identities. It supports
    local evaluation for performance and resilience.
    """

    def __init__(self, settings: FeatureFlagSettings):
        """
        Initialize the Flagsmith feature flag service.

        Args:
            settings: Configuration settings for the feature flag service.
        """
        self.settings = settings
        self._flagsmith_client: Optional[Flagsmith] = None

        if self.settings.enabled and self.settings.environment_key:
            try:
                self._flagsmith_client = Flagsmith(
                    environment_key=self.settings.environment_key,
                    api_url=self.settings.api_url,
                    enable_local_evaluation=self.settings.enable_local_evaluation,
                    environment_refresh_interval_seconds=self.settings.environment_refresh_interval_seconds,
                    enable_analytics=self.settings.enable_analytics,
                )
                logger.info("Flagsmith client initialized successfully.")
            except Exception as e:
                logger.error(f"Failed to initialize Flagsmith client: {e}")
                self._flagsmith_client = None
        elif self.settings.enabled and not self.settings.environment_key:
            logger.warning(
                "Feature flags are enabled, but no environment key was provided. "
                "The service will be disabled."
            )
        else:
            logger.info("Feature flags are disabled.")

    def is_feature_enabled(
        self, feature_key: str, identity: Optional[str] = None
    ) -> bool:
        """
        Check if a feature is enabled.

        Args:
            feature_key: The feature flag key to check
            identity: Optional user identity for personalized flags

        Returns:
            True if the feature is enabled, False otherwise
        """
        if not self._flagsmith_client:
            return False

        try:
            if identity:
                flags = self._flagsmith_client.get_identity_flags(identifier=identity)
            else:
                flags = self._flagsmith_client.get_environment_flags()

            return flags.is_feature_enabled(feature_key)
        except Exception as e:
            logger.warning(f"Error checking feature flag '{feature_key}': {e}")
            return False

    def get_feature_value(
        self, feature_key: str, identity: Optional[str] = None
    ) -> Any:
        """
        Get the value of a feature flag.

        Args:
            feature_key: The feature flag key to get value for
            identity: Optional user identity for personalized flags

        Returns:
            The value of the feature flag, or None if not found
        """
        if not self._flagsmith_client:
            return None

        try:
            if identity:
                flags = self._flagsmith_client.get_identity_flags(identifier=identity)
            else:
                flags = self._flagsmith_client.get_environment_flags()

            feature = flags.get_feature(feature_key)
            return feature.value if feature else None
        except Exception as e:
            logger.warning(f"Error getting feature flag value '{feature_key}': {e}")
            return None

    def get_all_flags(self, identity: Optional[str] = None) -> Dict[str, Any]:
        """
        Get all feature flags.

        Args:
            identity: Optional user identity for personalized flags

        Returns:
            Dictionary of all feature flags and their values
        """
        if not self._flagsmith_client:
            return {}

        try:
            if identity:
                flags = self._flagsmith_client.get_identity_flags(identifier=identity)
            else:
                flags = self._flagsmith_client.get_environment_flags()

            # The Flagsmith SDK returns an iterable Flags object, but to satisfy
            # static analysis (pylint E1133), we explicitly handle cases where
            # the returned object might not be iterable by using a fallback.
            iterable_flags = flags if hasattr(flags, "__iter__") else []

            return {
                flag.feature.name: {
                    "enabled": flag.enabled,
                    "value": flag.feature_state_value,
                }
                for flag in iterable_flags
            }
        except Exception as e:
            logger.warning(f"Error getting all feature flags: {e}")
            return {}
