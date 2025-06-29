"""
Test Execution Order Optimization Module

Provides intelligent test execution order optimization based on dependencies,
historical failure rates, code changes, and parallel execution capabilities.
"""

import json
import logging
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class TestExecutionGraph:
    """Represents a dependency graph of test execution."""

    nodes: List[str]
    dependencies: Dict[str, List[str]] = field(default_factory=dict)
    metadata: Dict[str, Dict[str, Any]] = field(default_factory=dict)


@dataclass
class ExecutionPlan:
    """Represents an optimized test execution plan."""

    ordered_tests: List[str]
    parallel_groups: Optional[List[List[str]]] = None
    optimization_strategy: Optional[str] = None
    estimated_duration: Optional[float] = None
    optimization_benefits: Optional[Dict[str, Any]] = None


class TestImpactAnalyzer:
    """Analyzes the impact of code changes on test execution."""

    def __init__(self):
        self.cache_lock = threading.Lock()
        self._cache: Dict[str, Any] = {}

    def get_changed_files(self, base_ref: str = "HEAD") -> List[str]:
        """Get list of changed files from git."""
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", base_ref],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return [f.strip() for f in result.stdout.split("\n") if f.strip()]
            return []
        except Exception as e:
            logger.warning(f"Failed to get changed files: {e}")
            return []

    def analyze_impact(
        self, tests: List[str], changed_files: List[str]
    ) -> Dict[str, float]:
        """Analyze impact of changed files on tests."""
        impact_scores = {}

        for test in tests:
            score = 0.5  # Default impact score
            test_path = Path(test)

            # Direct test file changes have highest impact
            if test in changed_files:
                score = 1.0
            else:
                # Analyze indirect impact based on file patterns
                for changed_file in changed_files:
                    if self._files_related(test_path, Path(changed_file)):
                        score = max(score, 0.8)
                    elif changed_file.endswith(".py"):
                        # Source code changes have medium impact
                        score = max(score, 0.6)

            impact_scores[test] = score

        return impact_scores

    def _files_related(self, test_file: Path, source_file: Path) -> bool:
        """Check if a test file is related to a source file."""
        # Simple heuristic: test file name contains source file name
        test_name = test_file.stem.replace("test_", "")
        source_name = source_file.stem
        return test_name in source_name or source_name in test_name


class HistoricalDataCollector:
    """Collects and manages historical test execution data."""

    def __init__(self, data_path: Optional[Path] = None):
        self.data_path = data_path or Path(".pytest_cache/execution_history.json")
        self.historical_data: Dict[str, Dict[str, float]] = {}
        self._load_lock = threading.Lock()

    def collect_data(self, tests: List[str]) -> Dict[str, Dict[str, float]]:
        """Collect historical data for given tests."""
        with self._load_lock:
            if not self.historical_data:
                self.historical_data = self._load_historical_data()

        test_data = {}
        for test in tests:
            test_data[test] = self.historical_data.get(
                test,
                {
                    "failure_rate": 0.5,  # Default failure rate
                    "avg_duration": 5.0,  # Default duration in seconds
                    "last_failure": None,
                },
            )

        return test_data

    def get_failure_rate(self, test: str) -> float:
        """Get failure rate for a specific test."""
        return self.historical_data.get(test, {}).get("failure_rate", 0.5)

    def get_avg_duration(self, test: str) -> float:
        """Get average duration for a specific test."""
        return self.historical_data.get(test, {}).get("avg_duration", 5.0)

    def _load_historical_data(self) -> Dict[str, Dict[str, float]]:
        """Load historical data from storage."""
        try:
            if self.data_path.exists():
                with open(self.data_path, "r") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load historical data: {e}")
        return {}

    def save_data(self, test_results: Dict[str, Any]):
        """Save test execution results for future use."""
        try:
            self.data_path.parent.mkdir(parents=True, exist_ok=True)
            current_data = self._load_historical_data()

            # Update with new results
            for test, result in test_results.items():
                if test not in current_data:
                    current_data[test] = {"failure_rate": 0.5, "avg_duration": 5.0}

                # Update failure rate with exponential moving average
                current_rate = current_data[test]["failure_rate"]
                failed = result.get("failed", False)
                current_data[test]["failure_rate"] = 0.9 * current_rate + 0.1 * (
                    1.0 if failed else 0.0
                )

                # Update duration
                duration = result.get("duration", 5.0)
                current_data[test]["avg_duration"] = (
                    0.9 * current_data[test]["avg_duration"] + 0.1 * duration
                )

            with open(self.data_path, "w") as f:
                json.dump(current_data, f, indent=2)

        except Exception as e:
            logger.warning(f"Failed to save historical data: {e}")


class ParallelExecutionPlanner:
    """Plans parallel execution groups considering dependencies."""

    def __init__(self, max_parallel_groups: int = 4):
        self.max_parallel_groups = max_parallel_groups

    def plan_parallel_groups(
        self, dependency_graph: TestExecutionGraph
    ) -> List[List[str]]:
        """Plan parallel execution groups based on dependency graph."""
        groups = []
        remaining_tests = set(dependency_graph.nodes)
        completed_tests: Set[str] = set()

        while remaining_tests:
            # Find tests that can run in parallel (no outstanding dependencies)
            current_group = []

            for test in list(remaining_tests):
                dependencies = dependency_graph.dependencies.get(test, [])
                if all(dep in completed_tests for dep in dependencies):
                    current_group.append(test)
                    if len(current_group) >= self.max_parallel_groups:
                        break

            if not current_group:
                # Circular dependency or other issue - just add remaining tests
                current_group = list(remaining_tests)
                logger.warning(
                    "Potential circular dependency detected in test execution graph"
                )

            groups.append(current_group)
            completed_tests.update(current_group)
            remaining_tests -= set(current_group)

        return groups

    def validate_dependencies(self, dependencies: Dict[str, List[str]]) -> bool:
        """Validate that dependencies don't contain cycles."""

        def has_cycle(node: str, visited: Set[str], rec_stack: Set[str]) -> bool:
            visited.add(node)
            rec_stack.add(node)

            for neighbor in dependencies.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor, visited, rec_stack):
                        return True
                elif neighbor in rec_stack:
                    return True

            rec_stack.remove(node)
            return False

        visited: Set[str] = set()
        for node in dependencies:
            if node not in visited:
                if has_cycle(node, visited, set()):
                    return False
        return True


class TestExecutionOrderOptimizer:
    """Main optimizer for test execution order."""

    def __init__(
        self,
        impact_analyzer: Optional[TestImpactAnalyzer] = None,
        historical_collector: Optional[HistoricalDataCollector] = None,
        parallel_planner: Optional[ParallelExecutionPlanner] = None,
    ):
        self.impact_analyzer = impact_analyzer or TestImpactAnalyzer()
        self.historical_collector = historical_collector or HistoricalDataCollector()
        self.parallel_planner = parallel_planner or ParallelExecutionPlanner()
        self.dependency_graph: Optional[TestExecutionGraph] = None

    def build_dependency_graph(
        self, tests: List[str], categorized_tests: Dict[str, List[str]]
    ) -> TestExecutionGraph:
        """Build dependency graph based on test categories and heuristics."""
        dependencies = {}
        metadata = {}

        # Simple heuristic: integration tests depend on unit tests,
        # e2e tests depend on integration tests
        unit_tests = categorized_tests.get("unit", [])
        integration_tests = categorized_tests.get("integration", [])

        for test in tests:
            metadata[test] = {
                "category": self._get_test_category(test, categorized_tests)
            }

            # Add dependencies based on category
            if test in integration_tests and unit_tests:
                # Integration tests depend on unit tests
                dependencies[test] = [t for t in unit_tests if t != test]
            elif test in categorized_tests.get("e2e", []) and integration_tests:
                # E2E tests depend on integration tests
                dependencies[test] = [t for t in integration_tests if t != test]

        graph = TestExecutionGraph(
            nodes=tests, dependencies=dependencies, metadata=metadata
        )
        self.dependency_graph = graph
        return graph

    def analyze_code_impact(self, tests: List[str]) -> Dict[str, float]:
        """Analyze code change impact on tests."""
        changed_files = self.impact_analyzer.get_changed_files()
        return self.impact_analyzer.analyze_impact(tests, changed_files)

    def collect_historical_data(self, tests: List[str]) -> Dict[str, Dict[str, float]]:
        """Collect historical execution data for tests."""
        return self.historical_collector.collect_data(tests)

    def optimize_execution_order(
        self,
        tests: List[str],
        strategy: str = "balanced",
        historical_data: Optional[Dict[str, Dict[str, float]]] = None,
        impact_scores: Optional[Dict[str, float]] = None,
        dependency_graph: Optional[TestExecutionGraph] = None,
    ) -> List[str]:
        """Optimize test execution order based on strategy."""

        if strategy == "fast_fail":
            return self._optimize_fast_fail(tests, historical_data)
        elif strategy == "dependency_based":
            return self._optimize_dependency_based(tests, dependency_graph)
        elif strategy == "impact_based":
            return self._optimize_impact_based(tests, impact_scores)
        elif strategy == "balanced":
            return self._optimize_balanced(
                tests, historical_data, impact_scores, dependency_graph
            )
        else:
            return tests.copy()  # Default order

    def plan_parallel_execution(
        self, tests: List[str], dependency_graph: TestExecutionGraph
    ) -> List[List[str]]:
        """Plan parallel execution groups."""
        return self.parallel_planner.plan_parallel_groups(dependency_graph)

    def generate_execution_plan(
        self,
        tests: List[str],
        categorized_tests: Dict[str, List[str]],
        options: Dict[str, Any],
    ) -> ExecutionPlan:
        """Generate comprehensive execution plan."""
        if not tests:
            return ExecutionPlan(ordered_tests=[])

        # Build dependency graph
        dependency_graph = self.build_dependency_graph(tests, categorized_tests)

        # Collect data based on options
        historical_data = None
        impact_scores = None

        if options.get("historical_data", False):
            try:
                historical_data = self.collect_historical_data(tests)
            except Exception as e:
                logger.warning(f"Failed to collect historical data: {e}")

        if options.get("fast_fail", False) or options.get("impact_based", False):
            try:
                impact_scores = self.analyze_code_impact(tests)
            except Exception as e:
                logger.warning(f"Failed to analyze code impact: {e}")

        # Determine strategy
        strategy = "balanced"
        if options.get("fast_fail", False):
            strategy = "fast_fail"
        elif options.get("dependency_based", False):
            strategy = "dependency_based"

        # Optimize order
        ordered_tests = self.optimize_execution_order(
            tests,
            strategy=strategy,
            historical_data=historical_data,
            impact_scores=impact_scores,
            dependency_graph=dependency_graph,
        )

        # Plan parallel execution if requested
        parallel_groups = None
        if options.get("parallel", False):
            try:
                parallel_groups = self.plan_parallel_execution(
                    ordered_tests, dependency_graph
                )
            except Exception as e:
                logger.warning(f"Failed to plan parallel execution: {e}")

        # Calculate benefits
        optimization_benefits = None
        if historical_data:
            try:
                optimization_benefits = self._calculate_optimization_benefits(
                    tests, ordered_tests, historical_data
                )
            except Exception as e:
                logger.warning(f"Failed to calculate optimization benefits: {e}")

        # Estimate duration
        estimated_duration = None
        if historical_data:
            try:
                estimated_duration = self._estimate_execution_time(
                    ordered_tests, historical_data
                )
            except Exception as e:
                logger.warning(f"Failed to estimate execution time: {e}")

        return ExecutionPlan(
            ordered_tests=ordered_tests,
            parallel_groups=parallel_groups,
            optimization_strategy=strategy,
            estimated_duration=estimated_duration,
            optimization_benefits=optimization_benefits,
        )

    def _get_test_category(
        self, test: str, categorized_tests: Dict[str, List[str]]
    ) -> str:
        """Get category for a test."""
        for category, test_list in categorized_tests.items():
            if test in test_list:
                return category
        return "unknown"

    def _optimize_fast_fail(
        self, tests: List[str], historical_data: Optional[Dict[str, Dict[str, float]]]
    ) -> List[str]:
        """Optimize for fast failure detection."""
        if not historical_data:
            return tests.copy()

        # Sort by failure rate (highest first)
        return sorted(
            tests,
            key=lambda t: historical_data.get(t, {}).get("failure_rate", 0.5),
            reverse=True,
        )

    def _optimize_dependency_based(
        self, tests: List[str], dependency_graph: Optional[TestExecutionGraph]
    ) -> List[str]:
        """Optimize based on dependencies (topological sort)."""
        if not dependency_graph:
            return tests.copy()

        # Simple topological sort
        ordered = []
        remaining = set(tests)
        completed = set()

        while remaining:
            # Find tests with no outstanding dependencies
            ready = [
                t
                for t in remaining
                if all(
                    dep in completed for dep in dependency_graph.dependencies.get(t, [])
                )
            ]

            if not ready:
                # Add remaining tests (circular dependency case)
                ready = list(remaining)

            # Sort ready tests by some criteria (e.g., name)
            ready.sort()
            ordered.extend(ready)
            completed.update(ready)
            remaining -= set(ready)

        return ordered

    def _optimize_impact_based(
        self, tests: List[str], impact_scores: Optional[Dict[str, float]]
    ) -> List[str]:
        """Optimize based on code change impact."""
        if not impact_scores:
            return tests.copy()

        # Sort by impact score (highest first)
        return sorted(tests, key=lambda t: impact_scores.get(t, 0.5), reverse=True)

    def _optimize_balanced(
        self,
        tests: List[str],
        historical_data: Optional[Dict[str, Dict[str, float]]],
        impact_scores: Optional[Dict[str, float]],
        dependency_graph: Optional[TestExecutionGraph],
    ) -> List[str]:
        """Balanced optimization considering multiple factors."""
        # Start with dependency-based ordering
        ordered = self._optimize_dependency_based(tests, dependency_graph)

        # Within each dependency level, sort by failure rate and impact
        if historical_data or impact_scores:

            def sort_key(test: str) -> Tuple[float, float]:
                failure_rate = (
                    historical_data.get(test, {}).get("failure_rate", 0.5)
                    if historical_data
                    else 0.5
                )
                impact = impact_scores.get(test, 0.5) if impact_scores else 0.5
                return (failure_rate, impact)

            # This is a simplified balanced approach
            # In a more sophisticated implementation, we'd maintain dependency constraints
            # while optimizing within each level
            ordered.sort(key=sort_key, reverse=True)

        return ordered

    def _estimate_execution_time(
        self, tests: List[str], historical_data: Dict[str, Dict[str, float]]
    ) -> float:
        """Estimate total execution time."""
        total_time = 0.0
        for test in tests:
            avg_duration = historical_data.get(test, {}).get("avg_duration", 5.0)
            total_time += avg_duration
        return total_time

    def _calculate_optimization_benefits(
        self,
        original_order: List[str],
        optimized_order: List[str],
        historical_data: Dict[str, Dict[str, float]],
    ) -> Dict[str, Any]:
        """Calculate optimization benefits."""
        benefits = {
            "strategy": "applied",
            "reordered": original_order != optimized_order,
        }

        if historical_data:
            # Calculate expected time to first failure
            original_ttf = self._calculate_time_to_failure(
                original_order, historical_data
            )
            optimized_ttf = self._calculate_time_to_failure(
                optimized_order, historical_data
            )

            if original_ttf and optimized_ttf:
                benefits["time_to_failure_improvement"] = original_ttf - optimized_ttf
                benefits["efficiency_gain"] = (
                    (original_ttf - optimized_ttf) / original_ttf
                    if original_ttf > 0
                    else 0
                )

        return benefits

    def _calculate_time_to_failure(
        self, test_order: List[str], historical_data: Dict[str, Dict[str, float]]
    ) -> Optional[float]:
        """Calculate expected time to first failure."""
        cumulative_time = 0.0
        for test in test_order:
            test_data = historical_data.get(test, {})
            failure_rate = test_data.get("failure_rate", 0.5)
            duration = test_data.get("avg_duration", 5.0)

            if failure_rate > 0.7:  # High probability of failure
                return cumulative_time + duration * 0.5  # Expected time within the test

            cumulative_time += duration

        return cumulative_time  # No high-probability failures found
