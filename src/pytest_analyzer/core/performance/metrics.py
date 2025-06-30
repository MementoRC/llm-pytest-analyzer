"""
Performance metrics data structures and definitions.

This module defines the core data structures for performance benchmarking.
"""

import statistics
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Dict, List, Optional


class MetricType(Enum):
    """Types of performance metrics that can be measured."""

    EXECUTION_TIME = auto()
    MEMORY_USAGE = auto()
    TOKEN_EFFICIENCY = auto()
    ANALYSIS_ACCURACY = auto()
    CACHE_HIT_RATE = auto()
    API_LATENCY = auto()
    THROUGHPUT = auto()
    ERROR_RATE = auto()


class BenchmarkStatus(Enum):
    """Status of a benchmark run."""

    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()


@dataclass
class BenchmarkMetric:
    """A single performance metric measurement."""

    name: str
    value: float
    unit: str
    metric_type: MetricType
    timestamp: datetime = field(default_factory=datetime.now)
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert metric to dictionary representation."""
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "metric_type": self.metric_type.name,
            "timestamp": self.timestamp.isoformat(),
            "context": self.context,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BenchmarkMetric":
        """Create metric from dictionary representation."""
        return cls(
            name=data["name"],
            value=data["value"],
            unit=data["unit"],
            metric_type=MetricType[data["metric_type"]],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            context=data.get("context", {}),
        )


@dataclass
class BenchmarkResult:
    """Results from a single benchmark run."""

    benchmark_id: str
    suite_name: str
    test_name: str
    metrics: List[BenchmarkMetric]
    status: BenchmarkStatus
    duration: float
    start_time: datetime
    end_time: Optional[datetime] = None
    error_message: Optional[str] = None
    environment: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_metric(self, name: str) -> Optional[BenchmarkMetric]:
        """Get a specific metric by name."""
        for metric in self.metrics:
            if metric.name == name:
                return metric
        return None

    def get_metrics_by_type(self, metric_type: MetricType) -> List[BenchmarkMetric]:
        """Get all metrics of a specific type."""
        return [m for m in self.metrics if m.metric_type == metric_type]

    def calculate_summary_stats(self, metric_name: str) -> Dict[str, float]:
        """Calculate summary statistics for a metric across multiple measurements."""
        values = [m.value for m in self.metrics if m.name == metric_name]

        if not values:
            return {}

        return {
            "mean": statistics.mean(values),
            "median": statistics.median(values),
            "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
            "min": min(values),
            "max": max(values),
            "count": len(values),
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary representation."""
        return {
            "benchmark_id": self.benchmark_id,
            "suite_name": self.suite_name,
            "test_name": self.test_name,
            "metrics": [m.to_dict() for m in self.metrics],
            "status": self.status.name,
            "duration": self.duration,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "error_message": self.error_message,
            "environment": self.environment,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BenchmarkResult":
        """Create result from dictionary representation."""
        return cls(
            benchmark_id=data["benchmark_id"],
            suite_name=data["suite_name"],
            test_name=data["test_name"],
            metrics=[BenchmarkMetric.from_dict(m) for m in data["metrics"]],
            status=BenchmarkStatus[data["status"]],
            duration=data["duration"],
            start_time=datetime.fromisoformat(data["start_time"]),
            end_time=datetime.fromisoformat(data["end_time"])
            if data["end_time"]
            else None,
            error_message=data.get("error_message"),
            environment=data.get("environment", {}),
            metadata=data.get("metadata", {}),
        )


@dataclass
class BenchmarkSuite:
    """A collection of related benchmark tests."""

    name: str
    description: str
    tests: List[str]
    baseline_results: Dict[str, BenchmarkResult] = field(default_factory=dict)
    thresholds: Dict[str, Dict[str, float]] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    tags: List[str] = field(default_factory=list)

    def add_baseline(self, test_name: str, result: BenchmarkResult):
        """Add a baseline result for comparison."""
        self.baseline_results[test_name] = result

    def get_baseline(self, test_name: str) -> Optional[BenchmarkResult]:
        """Get baseline result for a test."""
        return self.baseline_results.get(test_name)

    def set_threshold(self, test_name: str, metric_name: str, threshold: float):
        """Set performance threshold for a test metric."""
        if test_name not in self.thresholds:
            self.thresholds[test_name] = {}
        self.thresholds[test_name][metric_name] = threshold

    def get_threshold(self, test_name: str, metric_name: str) -> Optional[float]:
        """Get performance threshold for a test metric."""
        return self.thresholds.get(test_name, {}).get(metric_name)

    def check_regression(
        self, result: BenchmarkResult, baseline: Optional[BenchmarkResult] = None
    ) -> Dict[str, bool]:
        """Check if result represents a performance regression."""
        if baseline is None:
            baseline = self.get_baseline(result.test_name)

        if baseline is None:
            return {}

        regressions = {}

        for metric in result.metrics:
            baseline_metric = baseline.get_metric(metric.name)
            if baseline_metric is None:
                continue

            threshold = self.get_threshold(result.test_name, metric.name)
            if threshold is None:
                # Default threshold: 10% increase is considered regression
                threshold = 1.1

            # For metrics where lower is better (e.g., execution time)
            if metric.metric_type in [
                MetricType.EXECUTION_TIME,
                MetricType.API_LATENCY,
            ]:
                is_regression = metric.value > baseline_metric.value * threshold
            # For metrics where higher is better (e.g., cache hit rate)
            elif metric.metric_type in [
                MetricType.CACHE_HIT_RATE,
                MetricType.THROUGHPUT,
            ]:
                is_regression = metric.value < baseline_metric.value / threshold
            else:
                # Default: assume lower is better
                is_regression = metric.value > baseline_metric.value * threshold

            regressions[metric.name] = is_regression

        return regressions

    def to_dict(self) -> Dict[str, Any]:
        """Convert suite to dictionary representation."""
        return {
            "name": self.name,
            "description": self.description,
            "tests": self.tests,
            "baseline_results": {
                k: v.to_dict() for k, v in self.baseline_results.items()
            },
            "thresholds": self.thresholds,
            "created_at": self.created_at.isoformat(),
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BenchmarkSuite":
        """Create suite from dictionary representation."""
        return cls(
            name=data["name"],
            description=data["description"],
            tests=data["tests"],
            baseline_results={
                k: BenchmarkResult.from_dict(v)
                for k, v in data.get("baseline_results", {}).items()
            },
            thresholds=data.get("thresholds", {}),
            created_at=datetime.fromisoformat(data["created_at"]),
            tags=data.get("tags", []),
        )


class PerformanceRegression:
    """Utility class for detecting and analyzing performance regressions."""

    @staticmethod
    def detect_trend_regression(
        historical_results: List[BenchmarkResult],
        metric_name: str,
        sensitivity: float = 0.15,
    ) -> Dict[str, Any]:
        """
        Detect trend-based performance regression using statistical analysis.

        Args:
            historical_results: List of historical benchmark results
            metric_name: Name of the metric to analyze
            sensitivity: Sensitivity threshold for regression detection (0.0-1.0)

        Returns:
            Dictionary containing regression analysis results
        """
        if len(historical_results) < 3:
            return {
                "status": "insufficient_data",
                "message": "Need at least 3 data points",
            }

        # Extract metric values with timestamps
        data_points = []
        for result in historical_results:
            metric = result.get_metric(metric_name)
            if metric:
                data_points.append(
                    {"timestamp": result.start_time, "value": metric.value}
                )

        if len(data_points) < 3:
            return {
                "status": "insufficient_data",
                "message": f"No data for metric {metric_name}",
            }

        # Sort by timestamp
        data_points.sort(key=lambda x: x["timestamp"])
        values = [dp["value"] for dp in data_points]

        # Calculate moving averages and trends
        window_size = min(5, len(values) // 2)
        if window_size < 2:
            window_size = 2

        recent_avg = statistics.mean(values[-window_size:])
        baseline_avg = statistics.mean(values[:window_size])

        # Calculate percentage change
        if baseline_avg != 0:
            percentage_change = (recent_avg - baseline_avg) / baseline_avg
        else:
            percentage_change = 0.0

        # Determine if this is a regression based on metric type
        is_regression = abs(percentage_change) > sensitivity

        return {
            "status": "analysis_complete",
            "is_regression": is_regression,
            "percentage_change": percentage_change,
            "recent_average": recent_avg,
            "baseline_average": baseline_avg,
            "data_points": len(data_points),
            "confidence": min(
                1.0, len(data_points) / 10.0
            ),  # More data = higher confidence
        }

    @staticmethod
    def compare_results(
        current: BenchmarkResult,
        baseline: BenchmarkResult,
        thresholds: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Compare two benchmark results for performance changes.

        Args:
            current: Current benchmark result
            baseline: Baseline benchmark result to compare against
            thresholds: Optional custom thresholds for regression detection

        Returns:
            Dictionary mapping metric names to comparison results
        """
        if thresholds is None:
            thresholds = {}

        comparisons = {}

        for metric in current.metrics:
            baseline_metric = baseline.get_metric(metric.name)
            if baseline_metric is None:
                continue

            # Calculate percentage change
            if baseline_metric.value != 0:
                change_percent = (
                    (metric.value - baseline_metric.value) / baseline_metric.value * 100
                )
            else:
                change_percent = 0.0 if metric.value == 0 else float("inf")

            # Get threshold for this metric
            threshold = thresholds.get(metric.name, 10.0)  # Default 10% threshold

            # Determine if this is a significant change
            is_significant = abs(change_percent) > threshold

            # Determine direction based on metric type
            if metric.metric_type in [
                MetricType.EXECUTION_TIME,
                MetricType.API_LATENCY,
                MetricType.ERROR_RATE,
            ]:
                # Lower is better
                is_improvement = change_percent < 0
                is_regression = change_percent > threshold
            elif metric.metric_type in [
                MetricType.CACHE_HIT_RATE,
                MetricType.THROUGHPUT,
                MetricType.ANALYSIS_ACCURACY,
            ]:
                # Higher is better
                is_improvement = change_percent > 0
                is_regression = change_percent < -threshold
            else:
                # Neutral - any significant change is notable
                is_improvement = False
                is_regression = is_significant

            comparisons[metric.name] = {
                "current_value": metric.value,
                "baseline_value": baseline_metric.value,
                "change_percent": change_percent,
                "change_absolute": metric.value - baseline_metric.value,
                "is_significant": is_significant,
                "is_improvement": is_improvement,
                "is_regression": is_regression,
                "threshold": threshold,
                "metric_type": metric.metric_type.name,
                "unit": metric.unit,
            }

        return comparisons
