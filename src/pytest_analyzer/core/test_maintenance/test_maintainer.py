"""
Intelligent Test Maintenance System

Implements the TestMaintainer class for advanced test suite maintenance,
traceability, effectiveness scoring, and AI-driven suggestions.

Integrates with:
- TestCategorizer
- TestGenerator
- CoverageGapAnalyzer
- EfficiencyTracker
- LLMService
- Existing AST and metrics infrastructure
"""

import ast
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from pytest_analyzer.core.cross_cutting.monitoring.metrics import ApplicationMetrics
from pytest_analyzer.core.llm.llm_service import LLMService, LLMServiceError
from pytest_analyzer.core.test_categorization.categorizer import TestCategorizer
from pytest_analyzer.core.test_generation.coverage_analyzer import CoverageGapAnalyzer
from pytest_analyzer.core.test_generation.generator import TestGenerator
from pytest_analyzer.metrics.efficiency_tracker import EfficiencyTracker
from pytest_analyzer.utils.config_types import Settings

logger = logging.getLogger(__name__)


@dataclass
class TestEffectivenessScore:
    test_path: Path
    score: float
    details: Dict[str, Any] = field(default_factory=dict)


class TestMaintainerError(Exception):
    pass


class TestMaintainer:
    """
    Comprehensive Test Maintainer for intelligent test suite maintenance.

    Features:
    - Test-to-code traceability analysis
    - Automated test updating and deprecation detection
    - Test effectiveness scoring
    - LLM-driven maintenance/refactoring suggestions
    - Test suite health monitoring
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        test_categorizer: Optional[TestCategorizer] = None,
        test_generator: Optional[TestGenerator] = None,
        coverage_analyzer: Optional[CoverageGapAnalyzer] = None,
        efficiency_tracker: Optional[EfficiencyTracker] = None,
        llm_service: Optional[LLMService] = None,
        metrics: Optional[ApplicationMetrics] = None,
    ):
        self.settings = settings or Settings()
        self.test_categorizer = test_categorizer or TestCategorizer()
        self.test_generator = test_generator or TestGenerator(settings=self.settings)
        self.coverage_analyzer = coverage_analyzer or CoverageGapAnalyzer()
        self.efficiency_tracker = efficiency_tracker
        self.llm_service = llm_service or LLMService(settings=self.settings)
        self.metrics = metrics

    # --- 1. Test-to-Code Traceability Analysis ---

    def analyze_traceability(
        self, test_file: Union[str, Path], source_files: List[Union[str, Path]]
    ) -> Dict[str, Any]:
        """
        Analyze traceability between a test file and source files.

        Returns:
            {
                "tested_functions": set,
                "tested_classes": set,
                "orphaned_tests": set,
                "missing_coverage": set,
                "test_to_code_map": Dict[test_func, [source_func]],
                "code_to_test_map": Dict[source_func, [test_func]],
            }
        """
        try:
            test_ast = self._parse_ast(test_file)
            test_funcs = self._extract_test_functions(test_ast)
            # Note: test_imports and test_calls could be used for more sophisticated traceability analysis
            # test_imports = self._extract_imports(test_ast)
            # test_calls = self._extract_function_calls(test_ast)

            code_structs = {}
            for src in source_files:
                code_structs[src] = self.test_generator.analyze_code(src)

            tested_functions = set()
            tested_classes = set()
            test_to_code_map = {}
            code_to_test_map = {}

            for src, struct in code_structs.items():
                src_funcs = {f.name for f in struct.get("functions", [])}
                src_classes = {c.name for c in struct.get("classes", [])}
                for test_func in test_funcs:
                    # Heuristic: test function name contains source function/class name
                    covered = [f for f in src_funcs if f in test_func] + [
                        c for c in src_classes if c in test_func
                    ]
                    if covered:
                        tested_functions.update(
                            [f for f in src_funcs if f in test_func]
                        )
                        tested_classes.update(
                            [c for c in src_classes if c in test_func]
                        )
                        test_to_code_map.setdefault(test_func, []).extend(covered)
                        for cov in covered:
                            code_to_test_map.setdefault(cov, []).append(test_func)

            # Orphaned tests: test functions that do not map to any source function/class
            orphaned_tests = {t for t in test_funcs if t not in test_to_code_map}

            # Missing coverage: source functions/classes not covered by any test
            all_src_funcs = set()
            all_src_classes = set()
            for struct in code_structs.values():
                all_src_funcs.update(f.name for f in struct.get("functions", []))
                all_src_classes.update(c.name for c in struct.get("classes", []))
            missing_coverage = (all_src_funcs | all_src_classes) - set(
                code_to_test_map.keys()
            )

            return {
                "tested_functions": tested_functions,
                "tested_classes": tested_classes,
                "orphaned_tests": orphaned_tests,
                "missing_coverage": missing_coverage,
                "test_to_code_map": test_to_code_map,
                "code_to_test_map": code_to_test_map,
            }
        except Exception as e:
            logger.error(f"Traceability analysis failed: {e}")
            raise TestMaintainerError(f"Traceability analysis failed: {e}")

    def _parse_ast(self, file_path: Union[str, Path]) -> ast.AST:
        with open(file_path, "r", encoding="utf-8") as f:
            return ast.parse(f.read(), filename=str(file_path))

    def _extract_test_functions(self, tree: ast.AST) -> Set[str]:
        return {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test")
        }

    def _extract_imports(self, tree: ast.AST) -> Set[str]:
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for n in node.names:
                    imports.add(n.name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)
        return imports

    def _extract_function_calls(self, tree: ast.AST) -> Set[str]:
        calls = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if hasattr(node.func, "id"):
                    calls.add(node.func.id)
                elif hasattr(node.func, "attr"):
                    calls.add(node.func.attr)
        return calls

    # --- 2. Automated Test Updating and Deprecation Detection ---

    def update_tests_for_code_change(
        self,
        source_file: Union[str, Path],
        test_file: Union[str, Path],
        output_path: Optional[Union[str, Path]] = None,
    ) -> str:
        """
        Automatically update or regenerate tests for a changed source file.

        Returns:
            The updated test code as a string.
        """
        try:
            logger.info(f"Updating tests for {source_file} using {test_file}")
            # Analyze coverage gaps
            gap = self.coverage_analyzer.analyze_gap(test_file, source_file)
            if getattr(gap, "missing_functions", []):
                # Regenerate tests for missing functions
                updated_code = self.test_generator.generate_tests(
                    source_file, output_path=output_path
                )
                logger.info(f"Generated updated tests for {source_file}")
                return updated_code
            else:
                logger.info("No missing functions detected; no update needed.")
                return ""
        except Exception as e:
            logger.error(f"Test update failed: {e}")
            raise TestMaintainerError(f"Test update failed: {e}")

    def detect_deprecated_tests(
        self, test_file: Union[str, Path], source_files: List[Union[str, Path]]
    ) -> List[str]:
        """
        Detect tests that no longer correspond to any code (deprecated/orphaned).

        Returns:
            List of deprecated test function names.
        """
        try:
            trace = self.analyze_traceability(test_file, source_files)
            deprecated = list(trace["orphaned_tests"])
            if deprecated:
                logger.info(f"Deprecated/orphaned tests detected: {deprecated}")
            return deprecated
        except Exception as e:
            logger.error(f"Deprecation detection failed: {e}")
            raise TestMaintainerError(f"Deprecation detection failed: {e}")

    # --- 3. Test Effectiveness Scoring ---

    def score_test_effectiveness(
        self,
        test_file: Union[str, Path],
        source_files: List[Union[str, Path]],
        historical_failures: Optional[Dict[str, int]] = None,
        coverage_data: Optional[Dict[str, float]] = None,
        execution_times: Optional[Dict[str, float]] = None,
        maintenance_history: Optional[Dict[str, int]] = None,
        risk_map: Optional[Dict[str, float]] = None,
    ) -> List[TestEffectivenessScore]:
        """
        Score the effectiveness of each test in a test file.

        Returns:
            List of TestEffectivenessScore objects.
        """
        try:
            test_ast = self._parse_ast(test_file)
            test_funcs = self._extract_test_functions(test_ast)
            trace = self.analyze_traceability(test_file, source_files)
            scores = []
            for test_func in test_funcs:
                # Multi-dimensional scoring
                fail_rate = (historical_failures or {}).get(test_func, 0)
                coverage = (coverage_data or {}).get(test_func, 0.0)
                exec_time = (execution_times or {}).get(test_func, 1.0)
                maintenance = (maintenance_history or {}).get(test_func, 0)
                risk = 0.0
                for src_func in trace["test_to_code_map"].get(test_func, []):
                    risk += (risk_map or {}).get(src_func, 0.0)
                # Normalize and weight
                score = (
                    0.25 * min(fail_rate, 1.0)
                    + 0.25 * coverage
                    + 0.2 * (1.0 / max(exec_time, 0.01))
                    + 0.15 * (1.0 - min(maintenance / 10, 1.0))
                    + 0.15 * min(risk, 1.0)
                )
                scores.append(
                    TestEffectivenessScore(
                        test_path=Path(test_file),
                        score=round(score, 3),
                        details={
                            "fail_rate": fail_rate,
                            "coverage": coverage,
                            "exec_time": exec_time,
                            "maintenance": maintenance,
                            "risk": risk,
                        },
                    )
                )
            return scores
        except Exception as e:
            logger.error(f"Effectiveness scoring failed: {e}")
            raise TestMaintainerError(f"Effectiveness scoring failed: {e}")

    # --- 4. LLM-Driven Maintenance Suggestions ---

    def suggest_test_refactoring(
        self, test_file: Union[str, Path], context: Optional[str] = None
    ) -> List[str]:
        """
        Use LLM to suggest refactoring or improvements for a test file.

        Returns:
            List of suggestion strings.
        """
        try:
            prompt = (
                "You are an expert Python test engineer. "
                "Analyze the following test file and suggest improvements, refactorings, or consolidation opportunities. "
            )
            if context:
                prompt += f"Context: {context}\n"
            with open(test_file, "r", encoding="utf-8") as f:
                test_code = f.read()
            prompt += f"\nTest file content:\n{test_code}\n"
            response = self.llm_service.generate(prompt)
            # Try to parse as list, else fallback to lines
            import json

            try:
                suggestions = json.loads(response)
                if isinstance(suggestions, list):
                    return suggestions
            except Exception:
                pass
            return [line.strip() for line in response.splitlines() if line.strip()]
        except LLMServiceError as e:
            logger.warning(f"LLM suggestion failed: {e}")
            return []
        except Exception as e:
            logger.error(f"LLM suggestion failed: {e}")
            raise TestMaintainerError(f"LLM suggestion failed: {e}")

    # --- 5. Test Suite Health Monitoring ---

    def get_suite_health_metrics(
        self, test_files: List[Union[str, Path]], source_files: List[Union[str, Path]]
    ) -> Dict[str, Any]:
        """
        Gather health metrics for the test suite.

        Returns:
            Dict with health metrics.
        """
        try:
            metrics = {}
            # Test suite growth
            metrics["test_count"] = len(test_files)
            metrics["test_growth_trend"] = self._get_growth_trend()
            # Coverage evolution
            metrics["coverage"] = self._get_coverage_metrics(test_files, source_files)
            # Failure patterns
            metrics["failure_patterns"] = self._get_failure_patterns()
            # Performance
            metrics["performance"] = self._get_performance_metrics(test_files)
            # Stability
            metrics["stability"] = self._get_stability_metrics()
            return metrics
        except Exception as e:
            logger.error(f"Health metrics collection failed: {e}")
            raise TestMaintainerError(f"Health metrics collection failed: {e}")

    def _get_growth_trend(self) -> List[Tuple[str, int]]:
        # Placeholder: In real system, would use metrics DB or VCS history
        return []

    def _get_coverage_metrics(
        self, test_files: List[Union[str, Path]], source_files: List[Union[str, Path]]
    ) -> Dict[str, Any]:
        # Aggregate coverage gaps
        total_gaps = 0
        for test_file, src_file in zip(test_files, source_files):
            try:
                gap = self.coverage_analyzer.analyze_gap(test_file, src_file)
                total_gaps += len(getattr(gap, "missing_functions", []))
            except Exception:
                continue
        return {"total_gaps": total_gaps}

    def _get_failure_patterns(self) -> Dict[str, Any]:
        # Placeholder: Would use historical test run data
        return {}

    def _get_performance_metrics(
        self, test_files: List[Union[str, Path]]
    ) -> Dict[str, Any]:
        # Placeholder: Would use ApplicationMetrics or test run timing data
        return {}

    def _get_stability_metrics(self) -> Dict[str, Any]:
        # Placeholder: Would use flakiness/failure rate data
        return {}
