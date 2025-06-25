"""
TokenEfficientAnalyzer for pytest-analyzer.

This module implements a token-efficient analyzer for pytest output,
detecting failure patterns, ranking failures, identifying bulk fixes,
and generating structured summaries optimized for LLM token usage.
"""

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class FailurePattern:
    failure_type: str
    message: str
    location: str
    frequency: int
    complexity_score: float


@dataclass
class RankedFailure:
    failure_type: str
    message: str
    location: str
    frequency: int
    complexity_score: float
    priority_score: float
    suggested_fix: Optional[str] = None


@dataclass
class BulkFix:
    fix_type: str
    description: str
    affected_failures: List[str]
    affected_count: int
    estimated_effort: float


@dataclass
class AnalysisResult:
    failure_patterns: List[FailurePattern]
    ranked_failures: List[RankedFailure]
    bulk_fixes: List[BulkFix]
    summary: Dict[str, Any]


class TokenEfficientAnalyzer:
    def __init__(self):
        pass

    def detect_failure_patterns(self, pytest_output: str) -> List[FailurePattern]:
        """
        Parses pytest output and returns a list of FailurePattern objects.
        """
        # Example regex for pytest failure lines
        # Example: tests/test_module.py::TestClass::test_func FAILED AssertionError: something
        pattern = re.compile(
            r"^(?P<location>[\w/\\\.-]+::[\w\.-]+)\s+FAILED\s+(?P<failure_type>\w+Error|Exception|Failure):\s*(?P<message>.+)$",
            re.MULTILINE,
        )
        matches = pattern.findall(pytest_output)
        counter = Counter()
        details = defaultdict(list)
        for match in matches:
            location, failure_type, message = match
            key = (failure_type, message, location)
            counter[key] += 1
            details[key].append(message)
        patterns = []
        for (failure_type, message, location), freq in counter.items():
            # Simple complexity score: message length + 1 per "::" in location
            complexity_score = len(message) * 0.1 + location.count("::") * 0.5
            patterns.append(
                FailurePattern(
                    failure_type=failure_type,
                    message=message,
                    location=location,
                    frequency=freq,
                    complexity_score=complexity_score,
                )
            )
        return patterns

    def rank_failures(
        self, failure_patterns: List[FailurePattern]
    ) -> List[RankedFailure]:
        """
        Ranks failures and returns RankedFailure objects with priority_score and suggested_fix.
        """
        ranked = []
        for fp in failure_patterns:
            # Example: priority_score = frequency * complexity_score
            priority_score = fp.frequency * fp.complexity_score
            # Example: suggest a fix if AssertionError in failure_type
            suggested_fix = None
            if "AssertionError" in fp.failure_type:
                suggested_fix = "Check test assertions and expected values."
            elif "ImportError" in fp.failure_type:
                suggested_fix = "Check import statements and dependencies."
            ranked.append(
                RankedFailure(
                    failure_type=fp.failure_type,
                    message=fp.message,
                    location=fp.location,
                    frequency=fp.frequency,
                    complexity_score=fp.complexity_score,
                    priority_score=priority_score,
                    suggested_fix=suggested_fix,
                )
            )
        # Sort by priority_score descending
        ranked.sort(key=lambda r: r.priority_score, reverse=True)
        return ranked

    def identify_bulk_fixes(
        self, ranked_failures: List[RankedFailure]
    ) -> List[BulkFix]:
        """
        Identifies bulk fixes and returns BulkFix objects.
        """
        # Group by failure_type for bulk fixes
        grouped = defaultdict(list)
        for rf in ranked_failures:
            grouped[rf.failure_type].append(rf)
        bulk_fixes = []
        for failure_type, failures in grouped.items():
            if len(failures) > 1:
                description = f"Bulk fix for {failure_type} failures"
                affected_failures = [f.location for f in failures]
                estimated_effort = len(failures) * 0.5  # Example: 0.5 per failure
                bulk_fixes.append(
                    BulkFix(
                        fix_type=failure_type,
                        description=description,
                        affected_failures=affected_failures,
                        affected_count=len(failures),
                        estimated_effort=estimated_effort,
                    )
                )
        return bulk_fixes

    def generate_structured_summary(
        self, analysis_result: AnalysisResult
    ) -> Dict[str, Any]:
        """
        Returns a structured summary dictionary.
        """
        return {
            "failure_patterns": [
                {
                    "failure_type": fp.failure_type,
                    "message": fp.message,
                    "location": fp.location,
                    "frequency": fp.frequency,
                    "complexity_score": fp.complexity_score,
                }
                for fp in analysis_result.failure_patterns
            ],
            "ranked_failures": [
                {
                    "failure_type": rf.failure_type,
                    "message": rf.message,
                    "location": rf.location,
                    "frequency": rf.frequency,
                    "complexity_score": rf.complexity_score,
                    "priority_score": rf.priority_score,
                    "suggested_fix": rf.suggested_fix,
                }
                for rf in analysis_result.ranked_failures
            ],
            "bulk_fixes": [
                {
                    "fix_type": bf.fix_type,
                    "description": bf.description,
                    "affected_failures": bf.affected_failures,
                    "affected_count": bf.affected_count,
                    "estimated_effort": bf.estimated_effort,
                }
                for bf in analysis_result.bulk_fixes
            ],
            "summary": analysis_result.summary,
        }

    def analyze(self, pytest_output: str) -> AnalysisResult:
        """
        Full analysis pipeline.
        """
        failure_patterns = self.detect_failure_patterns(pytest_output)
        ranked_failures = self.rank_failures(failure_patterns)
        bulk_fixes = self.identify_bulk_fixes(ranked_failures)
        summary = {
            "total_failures": sum(fp.frequency for fp in failure_patterns),
            "unique_failure_types": list({fp.failure_type for fp in failure_patterns}),
            "bulk_fix_count": len(bulk_fixes),
        }
        return AnalysisResult(
            failure_patterns=failure_patterns,
            ranked_failures=ranked_failures,
            bulk_fixes=bulk_fixes,
            summary=summary,
        )
