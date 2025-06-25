"""
TokenEfficientAnalyzer for pytest-analyzer.

This module implements a token-efficient analyzer for pytest output,
detecting failure patterns, ranking failures, identifying bulk fixes,
and generating structured summaries optimized for LLM token usage.
"""

import logging  # Added import for logging
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from pytest_analyzer.analysis.fuzzy_matcher import FuzzyMatcher
from pytest_analyzer.analysis.pattern_database import (
    FailurePatternDatabase,
    KnownPattern,
)

# Import new components
from pytest_analyzer.analysis.pattern_detector import AhoCorasickPatternDetector

logger = logging.getLogger(__name__)  # Initialize logger


@dataclass
class FailurePattern:
    failure_type: str
    message: str
    location: str
    frequency: int
    complexity_score: float
    # New fields for known patterns and enhanced analysis
    is_known_pattern: bool = False
    known_pattern_id: Optional[str] = None
    impact_score: float = 0.0  # Default, will be updated if known
    suggested_fix: Optional[str] = None  # Default, will be updated if known


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
    def __init__(self, fuzzy_match_threshold: float = 0.8):
        self.pattern_db = FailurePatternDatabase()
        self.fuzzy_matcher = FuzzyMatcher(threshold=fuzzy_match_threshold)

        self.aho_corasick_detector: Optional[AhoCorasickPatternDetector] = None
        self._is_aho_corasick_available = (
            False  # Flag to track if Aho-Corasick is successfully initialized
        )

        # Initial attempt to build the automaton
        self._build_aho_corasick_automaton()

        # Regex for parsing individual failure lines (still useful for initial extraction)
        self._failure_line_pattern = re.compile(
            r"^(?P<location>[\w/\\\.-]+::[\w\.-]+)\s+FAILED\s+(?P<failure_type>\w+Error|Exception|Failure):\s*(?P<message>.+)$",
            re.MULTILINE,
        )

    def _build_aho_corasick_automaton(self):
        """Helper to build/rebuild the Aho-Corasick automaton.
        Handles graceful degradation if pyahocorasick is not available.
        """
        try:
            # Always attempt to re-initialize to clear previous patterns and add new ones
            temp_detector = AhoCorasickPatternDetector()
            for pattern in self.pattern_db.get_all_patterns():
                temp_detector.add_pattern(pattern.id, pattern.pattern_string)
            temp_detector.build()
            self.aho_corasick_detector = temp_detector
            self._is_aho_corasick_available = True
        except RuntimeError as e:
            if (
                self._is_aho_corasick_available
            ):  # Log if it was previously available and now failed
                logger.warning(
                    f"Failed to rebuild AhoCorasickPatternDetector: {e}. "
                    "Aho-Corasick functionality will be disabled."
                )
            else:  # Log only once on initial failure
                logger.warning(
                    f"AhoCorasickPatternDetector could not be initialized: {e}. "
                    "Falling back to fuzzy matching for pattern detection. "
                    "Install 'pyahocorasick' for optimal performance."
                )
            self.aho_corasick_detector = None
            self._is_aho_corasick_available = False

    def update_pattern_database(self, new_patterns: List[KnownPattern]):
        """
        Updates the internal pattern database and rebuilds the Aho-Corasick automaton.
        This allows for dynamic updates to known failure patterns.
        """
        self.pattern_db.update_from_list(new_patterns)
        self._build_aho_corasick_automaton()

    def detect_failure_patterns(self, pytest_output: str) -> List[FailurePattern]:
        """
        Parses pytest output and returns a list of FailurePattern objects,
        using Aho-Corasick for known patterns and fuzzy matching for similar ones.
        """
        raw_matches = self._failure_line_pattern.findall(pytest_output)

        # Group raw matches by their full message for frequency counting
        # (location, failure_type, message) -> count
        grouped_failures: Dict[Tuple[str, str, str], int] = Counter()
        for location, failure_type, message in raw_matches:
            grouped_failures[(location, failure_type, message)] += 1

        detected_patterns: List[FailurePattern] = []

        # Process each unique failure occurrence
        for (location, failure_type, message), freq in grouped_failures.items():
            # 1. Try Aho-Corasick for exact known pattern matching on the full message
            matched_known_pattern: Optional[KnownPattern] = None

            # Only attempt Aho-Corasick search if the detector is available
            if self.aho_corasick_detector and self._is_aho_corasick_available:
                # Aho-Corasick search on the full failure line (type: message)
                # We search for "failure_type: message_start"
                search_string = f"{failure_type}: {message}"

                ac_matches = self.aho_corasick_detector.search(search_string)

                best_ac_match_id = None
                longest_match_len = 0

                for _, (pattern_id, pattern_string) in ac_matches:
                    # Ensure the matched pattern string is actually a prefix or contained in the relevant part
                    # and that it's the longest match found so far.
                    if (
                        pattern_string in search_string
                        and len(pattern_string) > longest_match_len
                    ):
                        best_ac_match_id = pattern_id
                        longest_match_len = len(pattern_string)

                if best_ac_match_id:
                    matched_known_pattern = self.pattern_db.get_pattern(
                        best_ac_match_id
                    )

            if matched_known_pattern:
                # Found an exact or near-exact match via Aho-Corasick
                complexity_score = len(message) * 0.1 + location.count("::") * 0.5
                detected_patterns.append(
                    FailurePattern(
                        failure_type=failure_type,
                        message=message,
                        location=location,
                        frequency=freq,
                        complexity_score=complexity_score,
                        is_known_pattern=True,
                        known_pattern_id=matched_known_pattern.id,
                        impact_score=matched_known_pattern.impact_score,
                        suggested_fix=matched_known_pattern.suggested_fix,
                    )
                )
            else:
                # 2. If no exact Aho-Corasick match (or Aho-Corasick not available), try fuzzy matching against known patterns' base messages
                best_fuzzy_pattern: Optional[KnownPattern] = None
                best_fuzzy_score = 0.0

                # Filter known patterns by failure type for context-aware fuzzy matching
                candidate_patterns = [
                    p
                    for p in self.pattern_db.get_all_patterns()
                    if p.failure_type == failure_type
                ]

                if (
                    not candidate_patterns
                ):  # If no known patterns for this failure type, try all
                    candidate_patterns = self.pattern_db.get_all_patterns()

                # Extract base messages for fuzzy matching
                candidate_base_messages = {
                    p.base_message: p for p in candidate_patterns
                }

                best_match_message, best_fuzzy_score = (
                    self.fuzzy_matcher.find_best_match(
                        message, list(candidate_base_messages.keys())
                    )
                )

                if best_match_message:
                    best_fuzzy_pattern = candidate_base_messages[best_match_message]

                if (
                    best_fuzzy_pattern
                    and best_fuzzy_score >= self.fuzzy_matcher.threshold
                ):
                    # Found a fuzzy match
                    complexity_score = len(message) * 0.1 + location.count("::") * 0.5
                    detected_patterns.append(
                        FailurePattern(
                            failure_type=failure_type,
                            message=message,
                            location=location,
                            frequency=freq,
                            complexity_score=complexity_score,
                            is_known_pattern=True,  # Mark as known via fuzzy match
                            known_pattern_id=best_fuzzy_pattern.id,
                            impact_score=best_fuzzy_pattern.impact_score
                            * best_fuzzy_score,  # Scale impact by similarity
                            suggested_fix=best_fuzzy_pattern.suggested_fix,
                        )
                    )
                else:
                    # 3. No known pattern match (exact or fuzzy), treat as a new/unknown pattern
                    complexity_score = len(message) * 0.1 + location.count("::") * 0.5
                    detected_patterns.append(
                        FailurePattern(
                            failure_type=failure_type,
                            message=message,
                            location=location,
                            frequency=freq,
                            complexity_score=complexity_score,
                            is_known_pattern=False,
                            impact_score=complexity_score
                            * 0.2,  # Assign a low default impact for unknown
                            suggested_fix=None,  # No specific fix for unknown
                        )
                    )
        return detected_patterns

    def rank_failures(
        self, failure_patterns: List[FailurePattern]
    ) -> List[RankedFailure]:
        """
        Ranks failures and returns RankedFailure objects with priority_score and suggested_fix.
        Priority score now incorporates impact_score from known patterns.
        """
        ranked = []
        for fp in failure_patterns:
            # Priority score: frequency * (complexity_score + impact_score)
            # Impact score is 0 for unknown patterns, so it doesn't inflate them.
            priority_score = fp.frequency * (fp.complexity_score + fp.impact_score)

            # Use suggested_fix directly from FailurePattern (which comes from DB or is None)
            suggested_fix = fp.suggested_fix

            # Fallback for unknown patterns or generic types if no specific fix from DB
            if suggested_fix is None:
                if "AssertionError" in fp.failure_type:
                    suggested_fix = "Check test assertions and expected values."
                elif "ImportError" in fp.failure_type:
                    suggested_fix = "Check import statements and dependencies."
                elif "TypeError" in fp.failure_type:
                    suggested_fix = "Review variable types and function signatures."
                elif "NameError" in fp.failure_type:
                    suggested_fix = "Verify variable/function names and scope."
                elif "ValueError" in fp.failure_type:
                    suggested_fix = "Ensure input values are valid for the operation."
                elif "IndexError" in fp.failure_type or "KeyError" in fp.failure_type:
                    suggested_fix = (
                        "Check collection access (list indices, dictionary keys)."
                    )
                else:
                    suggested_fix = (
                        "Investigate the traceback for the root cause of this error."
                    )

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
        Prioritizes bulk fixes for known patterns.
        """
        # Group by failure_type and known_pattern_id for more precise bulk fixes
        grouped = defaultdict(list)
        for rf in ranked_failures:
            # Use a composite key for grouping: (failure_type, known_pattern_id or message_hash)
            # This allows grouping similar fuzzy-matched errors or exact known errors.
            group_key = (
                rf.failure_type,
                rf.suggested_fix,
            )  # Group by suggested fix for broader bulk fixes
            if (
                group_key[1] is None
            ):  # If no specific suggested fix, group by message for uniqueness
                group_key = (rf.failure_type, rf.message)
            grouped[group_key].append(rf)

        bulk_fixes = []
        for (failure_type, fix_identifier), failures in grouped.items():
            if len(failures) > 1:
                # Use the most common suggested fix or a generic one
                common_suggested_fix = (
                    failures[0].suggested_fix
                    if failures[0].suggested_fix
                    else f"Address multiple instances of {failure_type}."
                )

                description = (
                    f"Bulk fix for {failure_type} failures ({common_suggested_fix})"
                )
                affected_failures = [f.location for f in failures]

                # Estimated effort can be refined: e.g., based on average complexity of affected failures
                estimated_effort = (
                    sum(f.complexity_score for f in failures) * 0.2
                    + len(failures) * 0.1
                )  # Example: 0.1 per failure + 0.2 per complexity point

                bulk_fixes.append(
                    BulkFix(
                        fix_type=failure_type,
                        description=description,
                        affected_failures=affected_failures,
                        affected_count=len(failures),
                        estimated_effort=estimated_effort,
                    )
                )
        # Sort bulk fixes by affected count or estimated effort
        bulk_fixes.sort(key=lambda b: b.affected_count, reverse=True)
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
                    "is_known_pattern": fp.is_known_pattern,
                    "known_pattern_id": fp.known_pattern_id,
                    "impact_score": fp.impact_score,
                    "suggested_fix_from_pattern": fp.suggested_fix,  # Original suggested fix from pattern
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
                    "suggested_fix": rf.suggested_fix,  # Final suggested fix after ranking logic
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

        total_failures = sum(fp.frequency for fp in failure_patterns)
        unique_failure_types = list({fp.failure_type for fp in failure_patterns})
        known_pattern_count = sum(
            fp.frequency for fp in failure_patterns if fp.is_known_pattern
        )

        summary = {
            "total_failures": total_failures,
            "unique_failure_types": unique_failure_types,
            "bulk_fix_count": len(bulk_fixes),
            "known_pattern_matches": known_pattern_count,
            "unknown_pattern_count": total_failures - known_pattern_count,
        }
        return AnalysisResult(
            failure_patterns=failure_patterns,
            ranked_failures=ranked_failures,
            bulk_fixes=bulk_fixes,
            summary=summary,
        )
