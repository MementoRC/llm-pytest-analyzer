"""
Enhanced Coverage Gap Analyzer for Test Generation

This module analyzes test coverage gaps and suggests areas that need additional testing.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .ast_analyzer import ClassInfo, FunctionInfo


@dataclass
class CoverageGap:
    """Represents a gap in test coverage."""

    type: str  # function, class, branch, exception
    target: str  # name of the function/class/path
    severity: str  # low, medium, high, critical
    reason: str
    suggested_tests: List[str]
    file_path: str
    line_number: int


class CoverageGapAnalyzer:
    """
    Enhanced analyzer that identifies test coverage gaps and suggests additional tests.

    Identifies untested functions, uncovered branches, missing edge cases,
    and areas that would benefit from additional testing.
    """

    def __init__(self):
        self.coverage_gaps: List[CoverageGap] = []

    def analyze_coverage_gaps(
        self,
        analysis_result: Dict[str, Any],
        existing_tests: Optional[List[str]] = None,
    ) -> List[CoverageGap]:
        """
        Analyze code for coverage gaps and suggest additional tests.

        Args:
            analysis_result: Result from ASTAnalyzer.analyze()
            existing_tests: List of existing test function names

        Returns:
            List of identified coverage gaps
        """
        self.coverage_gaps = []
        existing_tests = existing_tests or []

        # Check for untested functions
        self._check_untested_functions(analysis_result, existing_tests)

        # Check for untested classes
        self._check_untested_classes(analysis_result, existing_tests)

        # Check for uncovered high-risk paths
        self._check_high_risk_paths(analysis_result)

        # Check for missing edge case tests
        self._check_missing_edge_cases(analysis_result, existing_tests)

        # Check for missing exception tests
        self._check_missing_exception_tests(analysis_result, existing_tests)

        return self.coverage_gaps

    def _check_untested_functions(
        self, analysis_result: Dict[str, Any], existing_tests: List[str]
    ):
        """Check for functions that don't have corresponding tests."""
        testable_functions = analysis_result.get("testable_functions", [])

        for func in testable_functions:
            # Simple heuristic: check if there's a test with the function name
            has_test = any(func.name in test_name for test_name in existing_tests)

            if not has_test:
                severity = self._assess_function_severity(func)

                gap = CoverageGap(
                    type="function",
                    target=func.name,
                    severity=severity,
                    reason=f"Function {func.name} has no corresponding tests",
                    suggested_tests=[
                        f"test_{func.name}_basic",
                        f"test_{func.name}_edge_cases",
                        f"test_{func.name}_error_handling",
                    ],
                    file_path=analysis_result.get("file_path", ""),
                    line_number=func.line_number,
                )
                self.coverage_gaps.append(gap)

    def _check_untested_classes(
        self, analysis_result: Dict[str, Any], existing_tests: List[str]
    ):
        """Check for classes that don't have corresponding tests."""
        classes = analysis_result.get("classes", [])

        for cls in classes:
            # Check if there are tests for the class
            has_class_test = any(
                cls.name.lower() in test_name.lower() for test_name in existing_tests
            )

            if not has_class_test:
                severity = self._assess_class_severity(cls)

                gap = CoverageGap(
                    type="class",
                    target=cls.name,
                    severity=severity,
                    reason=f"Class {cls.name} has no corresponding tests",
                    suggested_tests=[
                        f"test_{cls.name.lower()}_constructor",
                        f"test_{cls.name.lower()}_methods",
                        f"test_{cls.name.lower()}_state_management",
                    ],
                    file_path=analysis_result.get("file_path", ""),
                    line_number=cls.line_number,
                )
                self.coverage_gaps.append(gap)

    def _check_high_risk_paths(self, analysis_result: Dict[str, Any]):
        """Check for high-risk code paths that need additional testing."""
        high_risk_paths = analysis_result.get("high_risk_paths", [])

        for path in high_risk_paths:
            gap = CoverageGap(
                type="branch",
                target=path.path_id,
                severity="high",
                reason=f"High-risk code path with complexity {path.complexity}",
                suggested_tests=path.test_scenarios,
                file_path=analysis_result.get("file_path", ""),
                line_number=1,  # Would need more sophisticated line tracking
            )
            self.coverage_gaps.append(gap)

    def _check_missing_edge_cases(
        self, analysis_result: Dict[str, Any], existing_tests: List[str]
    ):
        """Check for missing edge case tests."""
        functions = analysis_result.get("testable_functions", [])

        for func in functions:
            if func.complexity > 2:  # Complex functions need edge case testing
                # Check if there are edge case tests
                has_edge_tests = any(
                    "edge" in test_name.lower() or "boundary" in test_name.lower()
                    for test_name in existing_tests
                    if func.name in test_name
                )

                if not has_edge_tests:
                    gap = CoverageGap(
                        type="edge_case",
                        target=func.name,
                        severity="medium",
                        reason=f"Complex function {func.name} missing edge case tests",
                        suggested_tests=[
                            f"test_{func.name}_empty_input",
                            f"test_{func.name}_null_input",
                            f"test_{func.name}_boundary_values",
                            f"test_{func.name}_large_input",
                        ],
                        file_path=analysis_result.get("file_path", ""),
                        line_number=func.line_number,
                    )
                    self.coverage_gaps.append(gap)

    def _check_missing_exception_tests(
        self, analysis_result: Dict[str, Any], existing_tests: List[str]
    ):
        """Check for missing exception handling tests."""
        functions = analysis_result.get("testable_functions", [])

        for func in functions:
            # Functions with multiple parameters or complex logic should have exception tests
            if len(func.args) > 1 or func.complexity > 2:
                has_exception_tests = any(
                    "raises" in test_name.lower()
                    or "exception" in test_name.lower()
                    or "error" in test_name.lower()
                    for test_name in existing_tests
                    if func.name in test_name
                )

                if not has_exception_tests:
                    gap = CoverageGap(
                        type="exception",
                        target=func.name,
                        severity="medium",
                        reason=f"Function {func.name} missing exception handling tests",
                        suggested_tests=[
                            f"test_{func.name}_raises_value_error",
                            f"test_{func.name}_raises_type_error",
                            f"test_{func.name}_invalid_input",
                        ],
                        file_path=analysis_result.get("file_path", ""),
                        line_number=func.line_number,
                    )
                    self.coverage_gaps.append(gap)

    def _assess_function_severity(self, func: FunctionInfo) -> str:
        """Assess the severity of missing tests for a function."""
        if func.complexity > 5:
            return "critical"
        elif func.complexity > 3:
            return "high"
        elif len(func.args) > 2:
            return "medium"
        else:
            return "low"

    def _assess_class_severity(self, cls: ClassInfo) -> str:
        """Assess the severity of missing tests for a class."""
        method_count = len(cls.methods)
        avg_complexity = sum(m.complexity for m in cls.methods) / max(method_count, 1)

        if method_count > 5 or avg_complexity > 3:
            return "high"
        elif method_count > 2 or avg_complexity > 2:
            return "medium"
        else:
            return "low"

    def get_gaps_by_severity(self, severity: str) -> List[CoverageGap]:
        """Get coverage gaps filtered by severity level."""
        return [gap for gap in self.coverage_gaps if gap.severity == severity]

    def get_gaps_by_type(self, gap_type: str) -> List[CoverageGap]:
        """Get coverage gaps filtered by type."""
        return [gap for gap in self.coverage_gaps if gap.type == gap_type]

    def generate_coverage_report(self) -> Dict[str, Any]:
        """Generate a comprehensive coverage gap report."""
        gaps_by_severity = {
            "critical": self.get_gaps_by_severity("critical"),
            "high": self.get_gaps_by_severity("high"),
            "medium": self.get_gaps_by_severity("medium"),
            "low": self.get_gaps_by_severity("low"),
        }

        gaps_by_type = {
            "function": self.get_gaps_by_type("function"),
            "class": self.get_gaps_by_type("class"),
            "branch": self.get_gaps_by_type("branch"),
            "edge_case": self.get_gaps_by_type("edge_case"),
            "exception": self.get_gaps_by_type("exception"),
        }

        return {
            "total_gaps": len(self.coverage_gaps),
            "gaps_by_severity": {k: len(v) for k, v in gaps_by_severity.items()},
            "gaps_by_type": {k: len(v) for k, v in gaps_by_type.items()},
            "detailed_gaps": self.coverage_gaps,
            "priority_recommendations": self._get_priority_recommendations(),
        }

    def _get_priority_recommendations(self) -> List[str]:
        """Get prioritized recommendations for improving test coverage."""
        recommendations = []

        critical_gaps = self.get_gaps_by_severity("critical")
        if critical_gaps:
            recommendations.append(
                f"Address {len(critical_gaps)} critical coverage gaps immediately"
            )

        high_gaps = self.get_gaps_by_severity("high")
        if high_gaps:
            recommendations.append(
                f"Plan tests for {len(high_gaps)} high-priority functions/classes"
            )

        function_gaps = self.get_gaps_by_type("function")
        if len(function_gaps) > 5:
            recommendations.append(
                "Consider implementing basic unit tests for untested functions"
            )

        exception_gaps = self.get_gaps_by_type("exception")
        if len(exception_gaps) > 3:
            recommendations.append("Add exception handling tests for error scenarios")

        edge_case_gaps = self.get_gaps_by_type("edge_case")
        if len(edge_case_gaps) > 3:
            recommendations.append("Implement edge case testing for complex functions")

        return recommendations

    def suggest_next_tests(self, limit: int = 5) -> List[CoverageGap]:
        """Suggest the next most important tests to implement."""
        # Sort by severity (critical -> high -> medium -> low)
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}

        sorted_gaps = sorted(
            self.coverage_gaps,
            key=lambda gap: (severity_order.get(gap.severity, 4), gap.target),
        )

        return sorted_gaps[:limit]

    # Legacy compatibility
    def analyze_gap(
        self, test_file: Union[str, Path], source_file: Union[str, Path]
    ) -> "CoverageGap":
        """Legacy method for backward compatibility."""
        from .ast_analyzer import ASTAnalyzer

        analyzer = ASTAnalyzer()
        source_struct = analyzer.analyze(source_file)
        test_struct = analyzer.analyze(test_file)

        source_funcs = {f.name for f in source_struct.get("functions", [])}
        test_funcs = set()
        for f in test_struct.get("functions", []):
            # Heuristic: test function names start with 'test_' and may reference source function
            for src_func in source_funcs:
                if src_func in f.name:
                    test_funcs.add(src_func)

        missing = list(source_funcs - test_funcs)

        # Return legacy CoverageGap format
        class LegacyCoverageGap:
            def __init__(self, missing_functions=None, missing_cases=None):
                self.missing_functions = missing_functions or []
                self.missing_cases = missing_cases or []

        return LegacyCoverageGap(missing_functions=missing, missing_cases=[])


# Alias for backward compatibility
CoverageAnalyzer = CoverageGapAnalyzer
