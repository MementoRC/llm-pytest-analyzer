"""
TokenEfficientAnalyzer for pytest-analyzer.

This module implements a token-efficient analyzer for pytest output,
detecting failure patterns, ranking failures, identifying bulk fixes,
and generating structured summaries optimized for LLM token usage.
"""

import logging  # Added import for logging
import re
from collections import Counter
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
        self,
        ranked_failures: List[RankedFailure],
        codebase_paths: Optional[List[str]] = None,
    ) -> List[BulkFix]:
        """
        Advanced bulk fix identification using clustering, static code analysis, heuristics, and confidence scoring.

        - Uses DBSCAN clustering (if available) to group related failures by multiple features.
        - Applies static code analysis (AST) to correlate failures with code structure.
        - Generates fix suggestions using a decision tree and assigns confidence scores.
        - Predicts fix impact.
        - Optionally builds a graph visualization of failure relationships.
        - Maintains backward compatibility with the previous grouping logic if clustering is unavailable.

        Args:
            ranked_failures: List of RankedFailure objects.
            codebase_paths: Optional list of file paths for static code analysis.

        Returns:
            List of BulkFix objects with enhanced metadata.
        """
        import math

        # --- 1. Feature Extraction for Clustering ---
        # Features: failure_type, message similarity, location (file), complexity, suggested_fix
        feature_vectors = []
        failure_indices = []
        failure_locations = []
        for idx, rf in enumerate(ranked_failures):
            # Use hash of failure_type and suggested_fix for categorical encoding
            type_hash = hash(rf.failure_type) % 1000
            fix_hash = hash(rf.suggested_fix or "") % 1000
            # Use file path as a categorical feature (if available)
            file_path = (
                rf.location.split("::")[0] if "::" in rf.location else rf.location
            )
            file_hash = hash(file_path) % 1000
            # Message length as a proxy for similarity
            msg_len = len(rf.message)
            # Complexity and priority as numeric features
            feature_vectors.append(
                [
                    type_hash,
                    fix_hash,
                    file_hash,
                    msg_len,
                    rf.complexity_score,
                    rf.priority_score,
                ]
            )
            failure_indices.append(idx)
            failure_locations.append(file_path)

        # --- 2. Clustering with DBSCAN (if available) ---
        clusters = None
        dbscan_available = False
        try:
            import numpy as np
            from sklearn.cluster import DBSCAN

            dbscan_available = True
        except ImportError:
            logger.warning(
                "scikit-learn not available, falling back to legacy grouping for bulk fix identification."
            )

        if dbscan_available and feature_vectors:
            X = np.array(feature_vectors)
            # DBSCAN: eps and min_samples can be tuned
            db = DBSCAN(eps=300, min_samples=2, metric="euclidean")
            labels = db.fit_predict(X)
            clusters = {}
            for label, idx in zip(labels, failure_indices):
                if label == -1:
                    continue  # Noise, treat as singleton
                clusters.setdefault(label, []).append(ranked_failures[idx])
        else:
            # Fallback: legacy grouping by (failure_type, suggested_fix)
            clusters = {}
            for rf in ranked_failures:
                group_key = (rf.failure_type, rf.suggested_fix)
                clusters.setdefault(group_key, []).append(rf)

        # --- 3. Static Code Analysis (AST) for Failure Correlation ---
        ast_analysis = {}
        if codebase_paths:
            import ast

            for path in codebase_paths:
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        source = f.read()
                    tree = ast.parse(source, filename=path)
                    # Collect function/class definitions and their line numbers
                    defs = []
                    for node in ast.walk(tree):
                        if isinstance(
                            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                        ):
                            defs.append(
                                {
                                    "name": node.name,
                                    "type": type(node).__name__,
                                    "lineno": getattr(node, "lineno", None),
                                    "end_lineno": getattr(node, "end_lineno", None),
                                }
                            )
                    ast_analysis[path] = defs
                except Exception as e:
                    logger.warning(f"AST analysis failed for {path}: {e}")

        # --- 4. Heuristics & Decision Tree for Fix Suggestion and Confidence ---
        def suggest_fix_and_confidence(failure_group):
            # Simple decision tree for fix suggestion and confidence scoring
            # (Extendable for more sophisticated logic)
            sf = failure_group[0].suggested_fix or ""
            freq = len(failure_group)
            # Heuristic: higher frequency, known pattern, and similar locations = higher confidence
            locations = [f.location for f in failure_group]
            unique_files = set(loc.split("::")[0] for loc in locations)
            confidence = 0.5
            if freq > 3:
                confidence += 0.2
            if len(unique_files) == 1:
                confidence += 0.1
            if "assert" in sf.lower() or "import" in sf.lower():
                confidence += 0.1
            if any("test" in loc for loc in locations):
                confidence += 0.05
            confidence = min(confidence, 1.0)
            # Fix suggestion: use most common suggested_fix or fallback
            fix_suggestion = max(
                (f.suggested_fix for f in failure_group if f.suggested_fix),
                default="Review related code.",
                key=lambda x: len(x),
            )
            return fix_suggestion, confidence

        # --- 5. Impact Prediction ---
        def predict_impact(failure_group):
            # Simple impact: sum of priority scores, scaled
            total_priority = sum(f.priority_score for f in failure_group)
            impact = math.log1p(total_priority)  # log scale for large numbers
            return round(impact, 2)

        # --- 6. Visualization (Graph) ---
        graph = None
        networkx_available = False
        try:
            import networkx as nx

            networkx_available = True
        except ImportError:
            logger.info(
                "networkx not available, skipping failure relationship visualization."
            )

        if networkx_available:
            graph = nx.Graph()
            # Nodes: failures, Edges: same cluster/group
            for group in clusters.values():
                node_ids = [f"{f.failure_type}:{f.location}" for f in group]
                for node in node_ids:
                    graph.add_node(node)
                for i in range(len(node_ids)):
                    for j in range(i + 1, len(node_ids)):
                        graph.add_edge(node_ids[i], node_ids[j])

        # --- 7. Build BulkFix objects ---
        bulk_fixes = []
        for group_key, group in clusters.items():
            if len(group) < 2:
                continue  # Only bulk fixes for groups of 2+
            fix_suggestion, confidence = suggest_fix_and_confidence(group)
            impact = predict_impact(group)
            description = (
                f"Bulk fix for {group[0].failure_type} ({fix_suggestion}) "
                f"[Confidence: {confidence:.2f}, Impact: {impact}]"
            )
            affected_failures = [f.location for f in group]
            estimated_effort = (
                sum(f.complexity_score for f in group) * 0.15 + len(group) * 0.1
            )
            # Attach extra metadata for advanced use
            bulk_fix = BulkFix(
                fix_type=group[0].failure_type,
                description=description,
                affected_failures=affected_failures,
                affected_count=len(group),
                estimated_effort=estimated_effort,
            )
            # Attach advanced fields for downstream use (not in dataclass, but can be added as attributes)
            setattr(bulk_fix, "confidence_score", confidence)
            setattr(bulk_fix, "impact_prediction", impact)
            setattr(bulk_fix, "fix_suggestion", fix_suggestion)
            setattr(
                bulk_fix, "visualization_graph", graph if networkx_available else None
            )
            setattr(bulk_fix, "ast_analysis", ast_analysis if ast_analysis else None)
            bulk_fixes.append(bulk_fix)

        # Sort by affected_count and impact
        bulk_fixes.sort(
            key=lambda b: (b.affected_count, getattr(b, "impact_prediction", 0)),
            reverse=True,
        )
        return bulk_fixes

    # --- API for programmatic bulk fix application ---
    def apply_bulk_fix(
        self, bulk_fix: BulkFix, codebase_paths: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Programmatic API to apply a bulk fix suggestion.

        Args:
            bulk_fix: The BulkFix object to apply.
            codebase_paths: Optional list of file paths to apply fixes to.

        Returns:
            Dict with results, including success, details, and any errors.
        """
        # This is a stub for integration with actual fix application logic.
        # In a real system, this would use FixApplier or GitFixApplier, etc.
        try:
            # Example: log the fix and affected files
            logger.info(f"Applying bulk fix: {bulk_fix.description}")
            logger.info(f"Affected files: {bulk_fix.affected_failures}")
            # Here, you would integrate with the actual fix application system.
            # For now, just return a simulated result.
            return {
                "success": True,
                "applied_fix_type": bulk_fix.fix_type,
                "affected_count": bulk_fix.affected_count,
                "description": bulk_fix.description,
                "confidence_score": getattr(bulk_fix, "confidence_score", None),
                "impact_prediction": getattr(bulk_fix, "impact_prediction", None),
                "details": "Bulk fix application simulated. Integrate with FixApplier for real changes.",
            }
        except Exception as e:
            logger.error(f"Bulk fix application failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "description": bulk_fix.description,
            }

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
