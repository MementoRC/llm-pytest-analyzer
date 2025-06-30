"""
Advanced Test Skip Marker Generation System

This module provides intelligent skip marker generation with natural language processing,
condition evaluation, conflict resolution, and analytics for test skipping patterns.
"""

import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from .categorizer import TestCategory


class SkipReason(Enum):
    """Common reasons for skipping tests."""

    MISSING_DEPENDENCY = auto()
    ENVIRONMENT_INCOMPATIBLE = auto()
    PLATFORM_SPECIFIC = auto()
    PERFORMANCE_INTENSIVE = auto()
    EXTERNAL_SERVICE_REQUIRED = auto()
    FLAKY_TEST = auto()
    REQUIRES_MANUAL_SETUP = auto()
    DEPRECATED_FEATURE = auto()
    SECURITY_SENSITIVE = auto()
    NETWORK_REQUIRED = auto()
    INTERACTIVE_TEST = auto()
    RESOURCE_INTENSIVE = auto()


@dataclass
class SkipCondition:
    """Represents a condition that determines if a test should be skipped."""

    name: str
    reason: SkipReason
    description: str
    evaluator: str  # Python expression or pattern to evaluate
    priority: int = 1  # Higher priority wins in conflicts
    platforms: Optional[Set[str]] = None  # Platforms this applies to
    environments: Optional[Set[str]] = None  # CI environments this applies to
    natural_language: Optional[str] = None  # Human-readable explanation

    def __post_init__(self):
        if not self.natural_language:
            self.natural_language = self._generate_natural_language()

    def _generate_natural_language(self) -> str:
        """Generate human-readable explanation for the skip condition."""
        reason_templates = {
            SkipReason.MISSING_DEPENDENCY: "requires {dependency} which is not available",
            SkipReason.ENVIRONMENT_INCOMPATIBLE: "is not compatible with the current environment",
            SkipReason.PLATFORM_SPECIFIC: "only runs on {platforms}",
            SkipReason.PERFORMANCE_INTENSIVE: "requires significant computational resources",
            SkipReason.EXTERNAL_SERVICE_REQUIRED: "depends on external services that are unavailable",
            SkipReason.FLAKY_TEST: "has been identified as unreliable",
            SkipReason.REQUIRES_MANUAL_SETUP: "requires manual configuration or setup",
            SkipReason.DEPRECATED_FEATURE: "tests deprecated functionality",
            SkipReason.SECURITY_SENSITIVE: "involves security-sensitive operations",
            SkipReason.NETWORK_REQUIRED: "requires network connectivity",
            SkipReason.INTERACTIVE_TEST: "requires user interaction",
            SkipReason.RESOURCE_INTENSIVE: "requires significant system resources",
        }

        template = reason_templates.get(self.reason, "meets skip condition: {name}")

        # Simple placeholder replacement
        return template.format(
            dependency=self.name.replace("_", " "),
            platforms=", ".join(self.platforms)
            if self.platforms
            else "specific platforms",
            name=self.name,
        )

    def evaluate(self, context: Dict[str, Any]) -> bool:
        """Evaluate if this condition applies given the context."""
        try:
            # Simple evaluation based on pattern matching for now
            if "import_" in self.evaluator:
                imports = context.get("imports", set())
                dependency = self.evaluator.replace("import_", "")
                return dependency in imports

            if "platform_" in self.evaluator:
                platform = context.get("platform", "")
                required_platform = self.evaluator.replace("platform_", "")
                return platform != required_platform

            if "environment_" in self.evaluator:
                env = context.get("environment", "")
                required_env = self.evaluator.replace("environment_", "")
                return env != required_env

            # Add more evaluation logic as needed
            return False

        except Exception:
            return False


# Database of common skip conditions
COMMON_SKIP_CONDITIONS = [
    SkipCondition(
        name="selenium_missing",
        reason=SkipReason.MISSING_DEPENDENCY,
        description="Selenium WebDriver not available",
        evaluator="import_selenium",
        priority=2,
        environments={"ci"},
    ),
    SkipCondition(
        name="docker_missing",
        reason=SkipReason.MISSING_DEPENDENCY,
        description="Docker not available",
        evaluator="import_docker",
        priority=2,
        environments={"ci"},
    ),
    SkipCondition(
        name="network_required",
        reason=SkipReason.NETWORK_REQUIRED,
        description="Network access required",
        evaluator="import_requests",
        priority=1,
        environments={"offline"},
    ),
    SkipCondition(
        name="performance_test",
        reason=SkipReason.PERFORMANCE_INTENSIVE,
        description="Performance-intensive test",
        evaluator="category_performance",
        priority=1,
        environments={"ci", "minimal"},
    ),
    SkipCondition(
        name="windows_only",
        reason=SkipReason.PLATFORM_SPECIFIC,
        description="Windows-specific test",
        evaluator="platform_windows",
        priority=2,
        platforms={"linux", "darwin"},
    ),
    SkipCondition(
        name="interactive_test",
        reason=SkipReason.INTERACTIVE_TEST,
        description="Requires user interaction",
        evaluator="import_input",
        priority=3,
        environments={"ci", "automated"},
    ),
]


@dataclass
class SkipEvent:
    """Records when a test was skipped."""

    test_path: str
    condition: str
    reason: str
    timestamp: datetime = field(default_factory=datetime.now)
    environment: Optional[str] = None
    platform: Optional[str] = None


@dataclass
class SkipAnalytics:
    """Analytics for skip patterns and frequencies."""

    events: List[SkipEvent] = field(default_factory=list)

    def record_skip(
        self,
        test_path: str,
        condition: str,
        reason: str,
        environment: Optional[str] = None,
        platform: Optional[str] = None,
    ):
        """Record a skip event."""
        event = SkipEvent(
            test_path=test_path,
            condition=condition,
            reason=reason,
            environment=environment,
            platform=platform,
        )
        self.events.append(event)

    def get_frequently_skipped_tests(
        self, threshold: int = 5, days: int = 7
    ) -> List[Tuple[str, int]]:
        """Get tests that are frequently skipped."""
        cutoff = datetime.now() - timedelta(days=days)
        recent_events = [e for e in self.events if e.timestamp >= cutoff]

        skip_counts = defaultdict(int)
        for event in recent_events:
            skip_counts[event.test_path] += 1

        return [
            (test, count) for test, count in skip_counts.items() if count >= threshold
        ]

    def get_skip_reasons_summary(self, days: int = 30) -> Dict[str, int]:
        """Get summary of skip reasons over the specified period."""
        cutoff = datetime.now() - timedelta(days=days)
        recent_events = [e for e in self.events if e.timestamp >= cutoff]

        reason_counts = defaultdict(int)
        for event in recent_events:
            reason_counts[event.reason] += 1

        return dict(reason_counts)

    def generate_alerts(self) -> List[str]:
        """Generate alerts for concerning skip patterns."""
        alerts = []

        # Alert for frequently skipped tests
        frequent = self.get_frequently_skipped_tests(threshold=3, days=7)
        for test_path, count in frequent:
            alerts.append(
                f"⚠️ Test '{test_path}' has been skipped {count} times in the last 7 days"
            )

        # Alert for high skip rates
        total_events = len(
            [
                e
                for e in self.events
                if e.timestamp >= datetime.now() - timedelta(days=7)
            ]
        )
        if total_events > 20:
            alerts.append(
                f"⚠️ High skip rate: {total_events} tests skipped in the last 7 days"
            )

        return alerts


class AdvancedSkipMarkerGenerator:
    """Advanced system for generating intelligent skip markers."""

    def __init__(
        self,
        conditions: Optional[List[SkipCondition]] = None,
        analytics: Optional[SkipAnalytics] = None,
    ):
        """Initialize the skip marker generator."""
        self.conditions = conditions or COMMON_SKIP_CONDITIONS.copy()
        self.analytics = analytics or SkipAnalytics()

    def add_condition(self, condition: SkipCondition):
        """Add a new skip condition."""
        self.conditions.append(condition)

    def evaluate_test(
        self, test_path: Path, context: Dict[str, Any]
    ) -> List[SkipCondition]:
        """Evaluate which skip conditions apply to a test."""
        applicable_conditions = []

        for condition in self.conditions:
            if condition.evaluate(context):
                applicable_conditions.append(condition)

        return applicable_conditions

    def resolve_conflicts(self, conditions: List[SkipCondition]) -> SkipCondition:
        """Resolve conflicts when multiple conditions apply."""
        if not conditions:
            return None

        if len(conditions) == 1:
            return conditions[0]

        # Sort by priority (higher priority wins)
        sorted_conditions = sorted(conditions, key=lambda c: c.priority, reverse=True)
        return sorted_conditions[0]

    def generate_skip_marker(
        self, test_path: Path, context: Dict[str, Any]
    ) -> Optional[str]:
        """Generate an appropriate skip marker for a test."""
        applicable_conditions = self.evaluate_test(test_path, context)

        if not applicable_conditions:
            return None

        # Resolve conflicts if multiple conditions apply
        primary_condition = self.resolve_conflicts(applicable_conditions)

        # Record the skip event
        self.analytics.record_skip(
            test_path=str(test_path),
            condition=primary_condition.name,
            reason=primary_condition.natural_language,
            environment=context.get("environment"),
            platform=context.get("platform"),
        )

        # Generate the actual marker with natural language reason
        marker = f'@pytest.mark.skip(reason="{primary_condition.natural_language}")'

        return marker

    def suggest_skip_conditions(
        self, test_path: Path, context: Dict[str, Any]
    ) -> List[str]:
        """Suggest skip conditions for ambiguous cases."""
        suggestions = []

        # Check for common patterns that might indicate skip needs
        imports = context.get("imports", set())
        test_category = context.get("category", TestCategory.FUNCTIONAL)

        # Suggest based on imports
        if "selenium" in imports and not any(
            c.name == "selenium_missing" for c in self.conditions
        ):
            suggestions.append("Consider adding selenium dependency check")

        if "docker" in imports and not any(
            c.name == "docker_missing" for c in self.conditions
        ):
            suggestions.append("Consider adding docker availability check")

        # Suggest based on test category
        if test_category == TestCategory.PERFORMANCE:
            suggestions.append("Consider skipping in resource-constrained environments")

        if test_category == TestCategory.E2E:
            suggestions.append("Consider skipping in headless CI environments")

        return suggestions

    def get_analytics_summary(self) -> Dict[str, Any]:
        """Get comprehensive analytics summary."""
        return {
            "total_skip_events": len(self.analytics.events),
            "frequently_skipped": self.analytics.get_frequently_skipped_tests(),
            "skip_reasons": self.analytics.get_skip_reasons_summary(),
            "alerts": self.analytics.generate_alerts(),
            "conditions_count": len(self.conditions),
        }

    def export_configuration(self, path: Path):
        """Export skip conditions configuration to JSON."""
        config_data = {
            "conditions": [
                {
                    "name": c.name,
                    "reason": c.reason.name,
                    "description": c.description,
                    "evaluator": c.evaluator,
                    "priority": c.priority,
                    "platforms": list(c.platforms) if c.platforms else None,
                    "environments": list(c.environments) if c.environments else None,
                    "natural_language": c.natural_language,
                }
                for c in self.conditions
            ],
            "analytics": {
                "events": [
                    {
                        "test_path": e.test_path,
                        "condition": e.condition,
                        "reason": e.reason,
                        "timestamp": e.timestamp.isoformat(),
                        "environment": e.environment,
                        "platform": e.platform,
                    }
                    for e in self.analytics.events
                ]
            },
        }

        with open(path, "w") as f:
            json.dump(config_data, f, indent=2)

    def import_configuration(self, path: Path):
        """Import skip conditions configuration from JSON."""
        with open(path, "r") as f:
            config_data = json.load(f)

        # Import conditions
        self.conditions = []
        for cond_data in config_data.get("conditions", []):
            condition = SkipCondition(
                name=cond_data["name"],
                reason=SkipReason[cond_data["reason"]],
                description=cond_data["description"],
                evaluator=cond_data["evaluator"],
                priority=cond_data["priority"],
                platforms=set(cond_data["platforms"])
                if cond_data["platforms"]
                else None,
                environments=set(cond_data["environments"])
                if cond_data["environments"]
                else None,
                natural_language=cond_data.get("natural_language"),
            )
            self.conditions.append(condition)

        # Import analytics events
        self.analytics = SkipAnalytics()
        for event_data in config_data.get("analytics", {}).get("events", []):
            event = SkipEvent(
                test_path=event_data["test_path"],
                condition=event_data["condition"],
                reason=event_data["reason"],
                timestamp=datetime.fromisoformat(event_data["timestamp"]),
                environment=event_data.get("environment"),
                platform=event_data.get("platform"),
            )
            self.analytics.events.append(event)
