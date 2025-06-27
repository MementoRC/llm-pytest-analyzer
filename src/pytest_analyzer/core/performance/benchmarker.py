"""
Core performance benchmarking system.

This module provides the main PerformanceBenchmarker class that orchestrates
benchmark execution, result collection, and analysis.
"""

import asyncio
import logging
import platform
import time
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

import psutil

from ..cross_cutting.monitoring.metrics import ApplicationMetrics
from .metrics import (
    BenchmarkMetric,
    BenchmarkResult,
    BenchmarkStatus,
    BenchmarkSuite,
    MetricType,
    PerformanceRegression,
)
from .storage import BenchmarkStorage

logger = logging.getLogger(__name__)


class PerformanceBenchmarker:
    """
    Comprehensive performance benchmarking system.

    Provides standardized benchmark execution, result collection,
    trend analysis, and regression detection.
    """

    def __init__(
        self,
        storage_path: Union[str, Path],
        metrics_client: Optional[ApplicationMetrics] = None,
        default_suite: Optional[str] = None,
    ):
        """
        Initialize the performance benchmarker.

        Args:
            storage_path: Path to store benchmark results
            metrics_client: Optional metrics client for monitoring
            default_suite: Default benchmark suite name
        """
        self.storage = BenchmarkStorage(storage_path)
        self.metrics_client = metrics_client
        self.default_suite = default_suite or "default"
        self._active_benchmarks: Dict[str, BenchmarkResult] = {}

        # System information for environment context
        self.system_info = {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "cpu_count": psutil.cpu_count(),
            "memory_total": psutil.virtual_memory().total,
            "hostname": platform.node(),
        }

    def create_suite(
        self,
        name: str,
        description: str,
        tests: List[str],
        thresholds: Optional[Dict[str, Dict[str, float]]] = None,
        tags: Optional[List[str]] = None,
    ) -> BenchmarkSuite:
        """
        Create a new benchmark suite.

        Args:
            name: Unique name for the suite
            description: Human-readable description
            tests: List of test names in the suite
            thresholds: Performance thresholds for regression detection
            tags: Optional tags for categorization

        Returns:
            Created benchmark suite
        """
        suite = BenchmarkSuite(
            name=name,
            description=description,
            tests=tests,
            thresholds=thresholds or {},
            tags=tags or [],
        )

        self.storage.store_suite(suite)
        logger.info(f"Created benchmark suite '{name}' with {len(tests)} tests")

        return suite

    def run_benchmark(
        self,
        test_name: str,
        benchmark_func: Callable[[], Any],
        suite_name: Optional[str] = None,
        iterations: int = 1,
        warmup_iterations: int = 0,
        timeout: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> BenchmarkResult:
        """
        Run a benchmark test with the specified function.

        Args:
            test_name: Name of the test being benchmarked
            benchmark_func: Function to benchmark
            suite_name: Name of the benchmark suite
            iterations: Number of times to run the benchmark
            warmup_iterations: Number of warmup runs (not measured)
            timeout: Maximum time to allow for the benchmark
            metadata: Additional metadata to store with results

        Returns:
            Benchmark result containing all metrics
        """
        suite_name = suite_name or self.default_suite
        benchmark_id = str(uuid.uuid4())
        start_time = datetime.now()

        # Create initial result object
        result = BenchmarkResult(
            benchmark_id=benchmark_id,
            suite_name=suite_name,
            test_name=test_name,
            metrics=[],
            status=BenchmarkStatus.RUNNING,
            duration=0.0,
            start_time=start_time,
            environment=self.system_info.copy(),
            metadata=metadata or {},
        )

        self._active_benchmarks[benchmark_id] = result

        try:
            logger.info(f"Starting benchmark '{test_name}' (ID: {benchmark_id})")

            # Perform warmup runs
            if warmup_iterations > 0:
                logger.debug(f"Performing {warmup_iterations} warmup iterations")
                for _ in range(warmup_iterations):
                    benchmark_func()

            # Collect baseline system metrics
            initial_memory = psutil.virtual_memory().used

            metrics = []

            # Run benchmark iterations
            execution_times = []
            for i in range(iterations):
                logger.debug(f"Running iteration {i + 1}/{iterations}")

                with self._measure_execution_time() as timer:
                    with self._measure_memory_usage() as memory_tracker:
                        benchmark_func()

                # Record execution time
                execution_time = timer.elapsed
                execution_times.append(execution_time)

                metrics.append(
                    BenchmarkMetric(
                        name="execution_time",
                        value=execution_time,
                        unit="seconds",
                        metric_type=MetricType.EXECUTION_TIME,
                        context={"iteration": i + 1},
                    )
                )

                # Record memory usage if available
                if memory_tracker.peak_usage is not None:
                    metrics.append(
                        BenchmarkMetric(
                            name="memory_usage",
                            value=memory_tracker.peak_usage,
                            unit="bytes",
                            metric_type=MetricType.MEMORY_USAGE,
                            context={"iteration": i + 1},
                        )
                    )

            # Calculate aggregate metrics
            if execution_times:
                import statistics

                metrics.extend(
                    [
                        BenchmarkMetric(
                            name="execution_time_mean",
                            value=statistics.mean(execution_times),
                            unit="seconds",
                            metric_type=MetricType.EXECUTION_TIME,
                            context={"aggregate": "mean", "iterations": iterations},
                        ),
                        BenchmarkMetric(
                            name="execution_time_median",
                            value=statistics.median(execution_times),
                            unit="seconds",
                            metric_type=MetricType.EXECUTION_TIME,
                            context={"aggregate": "median", "iterations": iterations},
                        ),
                    ]
                )

                if len(execution_times) > 1:
                    metrics.append(
                        BenchmarkMetric(
                            name="execution_time_stdev",
                            value=statistics.stdev(execution_times),
                            unit="seconds",
                            metric_type=MetricType.EXECUTION_TIME,
                            context={"aggregate": "stdev", "iterations": iterations},
                        )
                    )

            # Add system resource metrics
            final_cpu_percent = psutil.cpu_percent(interval=0.1)
            final_memory = psutil.virtual_memory().used

            metrics.extend(
                [
                    BenchmarkMetric(
                        name="cpu_usage",
                        value=final_cpu_percent,
                        unit="percent",
                        metric_type=MetricType.THROUGHPUT,
                        context={"measurement": "final"},
                    ),
                    BenchmarkMetric(
                        name="memory_change",
                        value=final_memory - initial_memory,
                        unit="bytes",
                        metric_type=MetricType.MEMORY_USAGE,
                        context={"measurement": "delta"},
                    ),
                ]
            )

            # Update result with success
            end_time = datetime.now()
            result.metrics = metrics
            result.status = BenchmarkStatus.COMPLETED
            result.end_time = end_time
            result.duration = (end_time - start_time).total_seconds()

            logger.info(
                f"Benchmark '{test_name}' completed successfully in {result.duration:.3f}s"
            )

        except Exception as e:
            # Update result with failure
            end_time = datetime.now()
            result.status = BenchmarkStatus.FAILED
            result.end_time = end_time
            result.duration = (end_time - start_time).total_seconds()
            result.error_message = str(e)

            logger.error(f"Benchmark '{test_name}' failed: {e}")

        finally:
            # Clean up and store result
            del self._active_benchmarks[benchmark_id]

            # Store result
            self.storage.store_result(result)

            # Update metrics client if available
            if self.metrics_client:
                self.metrics_client.analyses_completed.labels(
                    result="benchmark_complete"
                    if result.status == BenchmarkStatus.COMPLETED
                    else "benchmark_failed"
                ).inc()

        return result

    async def run_async_benchmark(
        self,
        test_name: str,
        benchmark_func: Callable[[], Any],
        suite_name: Optional[str] = None,
        iterations: int = 1,
        **kwargs,
    ) -> BenchmarkResult:
        """
        Run an asynchronous benchmark test.

        Args:
            test_name: Name of the test being benchmarked
            benchmark_func: Async function to benchmark
            suite_name: Name of the benchmark suite
            iterations: Number of times to run the benchmark
            **kwargs: Additional arguments passed to run_benchmark

        Returns:
            Benchmark result containing all metrics
        """

        def sync_wrapper():
            if asyncio.iscoroutinefunction(benchmark_func):
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(benchmark_func())
                finally:
                    loop.close()
            else:
                return benchmark_func()

        return self.run_benchmark(
            test_name=test_name,
            benchmark_func=sync_wrapper,
            suite_name=suite_name,
            iterations=iterations,
            **kwargs,
        )

    def compare_with_baseline(
        self, result: BenchmarkResult, baseline: Optional[BenchmarkResult] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Compare a benchmark result with its baseline.

        Args:
            result: Current benchmark result
            baseline: Baseline result to compare against (auto-detected if None)

        Returns:
            Comparison analysis for each metric
        """
        if baseline is None:
            baseline = self.storage.get_baseline_result(
                result.suite_name, result.test_name
            )

        if baseline is None:
            logger.warning(
                f"No baseline found for {result.suite_name}.{result.test_name}"
            )
            return {}

        # Get suite for thresholds
        suite = self.storage.load_suite(result.suite_name)
        thresholds = suite.thresholds.get(result.test_name, {}) if suite else {}

        return PerformanceRegression.compare_results(result, baseline, thresholds)

    def detect_regression(
        self,
        suite_name: str,
        test_name: str,
        metric_name: str,
        days: int = 30,
        sensitivity: float = 0.15,
    ) -> Dict[str, Any]:
        """
        Detect performance regression using trend analysis.

        Args:
            suite_name: Name of the benchmark suite
            test_name: Name of the test
            metric_name: Name of the metric to analyze
            days: Number of days of history to analyze
            sensitivity: Sensitivity threshold for regression detection

        Returns:
            Regression analysis results
        """
        # Get historical results
        historical_results = self.storage.get_recent_results(
            suite_name, test_name, days=days
        )

        if not historical_results:
            return {"status": "no_data", "message": "No historical data available"}

        return PerformanceRegression.detect_trend_regression(
            historical_results, metric_name, sensitivity
        )

    def generate_report(
        self,
        suite_name: str,
        days: int = 7,
        include_trends: bool = True,
        include_regressions: bool = True,
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive performance report.

        Args:
            suite_name: Name of the benchmark suite
            days: Number of days to include in the report
            include_trends: Whether to include trend analysis
            include_regressions: Whether to include regression detection

        Returns:
            Comprehensive performance report
        """
        suite = self.storage.load_suite(suite_name)
        if not suite:
            return {"error": f"Suite '{suite_name}' not found"}

        # Get recent results
        recent_results = self.storage.get_recent_results(suite_name, days=days)

        # Organize results by test
        results_by_test = {}
        for result in recent_results:
            if result.test_name not in results_by_test:
                results_by_test[result.test_name] = []
            results_by_test[result.test_name].append(result)

        report = {
            "suite_name": suite_name,
            "generated_at": datetime.now().isoformat(),
            "period_days": days,
            "summary": {
                "total_tests": len(suite.tests),
                "total_results": len(recent_results),
                "tests_with_results": len(results_by_test),
            },
            "test_results": {},
        }

        # Analyze each test
        for test_name in suite.tests:
            test_results = results_by_test.get(test_name, [])

            test_report = {
                "test_name": test_name,
                "results_count": len(test_results),
                "latest_result": None,
                "baseline_comparison": None,
            }

            if test_results:
                # Latest result
                latest = test_results[0]  # Results are ordered by time DESC
                test_report["latest_result"] = {
                    "status": latest.status.name,
                    "duration": latest.duration,
                    "start_time": latest.start_time.isoformat(),
                    "metrics_count": len(latest.metrics),
                }

                # Baseline comparison
                if latest.status == BenchmarkStatus.COMPLETED:
                    comparison = self.compare_with_baseline(latest)
                    test_report["baseline_comparison"] = comparison

            # Trend analysis
            if include_trends and test_results:
                trends = {}
                # Analyze key metrics
                for metric_name in ["execution_time_mean", "memory_usage", "cpu_usage"]:
                    trend_analysis = self.detect_regression(
                        suite_name, test_name, metric_name, days, sensitivity=0.1
                    )
                    if trend_analysis.get("status") == "analysis_complete":
                        trends[metric_name] = trend_analysis

                if trends:
                    test_report["trends"] = trends

            # Regression alerts
            if include_regressions and test_report.get("baseline_comparison"):
                regressions = []
                for metric_name, comparison in test_report[
                    "baseline_comparison"
                ].items():
                    if comparison.get("is_regression"):
                        regressions.append(
                            {
                                "metric": metric_name,
                                "change_percent": comparison["change_percent"],
                                "current_value": comparison["current_value"],
                                "baseline_value": comparison["baseline_value"],
                            }
                        )

                if regressions:
                    test_report["regressions"] = regressions

            report["test_results"][test_name] = test_report

        # Overall summary statistics
        summary_stats = self.storage.get_summary_stats(suite_name)
        report["summary"].update(summary_stats)

        return report

    def get_active_benchmarks(self) -> List[Dict[str, Any]]:
        """Get information about currently running benchmarks."""
        return [
            {
                "benchmark_id": benchmark_id,
                "test_name": result.test_name,
                "suite_name": result.suite_name,
                "start_time": result.start_time.isoformat(),
                "duration_so_far": (datetime.now() - result.start_time).total_seconds(),
            }
            for benchmark_id, result in self._active_benchmarks.items()
        ]

    def cleanup_old_data(self, days: int = 90) -> int:
        """Clean up old benchmark data."""
        return self.storage.cleanup_old_results(days)

    @contextmanager
    def _measure_execution_time(self):
        """Context manager for measuring execution time."""

        class Timer:
            def __init__(self):
                self.elapsed = 0.0

        timer = Timer()
        start_time = time.perf_counter()
        try:
            yield timer
        finally:
            timer.elapsed = time.perf_counter() - start_time

    @contextmanager
    def _measure_memory_usage(self):
        """Context manager for measuring memory usage."""

        class MemoryTracker:
            def __init__(self):
                self.peak_usage = None

        tracker = MemoryTracker()
        try:
            # Get baseline memory
            process = psutil.Process()
            baseline_memory = process.memory_info().rss

            yield tracker

            # Calculate peak usage
            current_memory = process.memory_info().rss
            tracker.peak_usage = current_memory - baseline_memory
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            # Memory tracking not available
            yield tracker
