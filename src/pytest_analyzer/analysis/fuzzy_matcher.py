import difflib
import logging
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

_LEVENSHTEIN_AVAILABLE = False
try:
    import Levenshtein

    _LEVENSHTEIN_AVAILABLE = True
    _jaro_winkler_func = Levenshtein.jaro_winkler
except ImportError:
    logger.warning(
        "Levenshtein module not found. Falling back to difflib.SequenceMatcher for fuzzy matching. "
        "Install 'python-Levenshtein' for better performance and accuracy."
    )

    def _fallback_jaro_winkler(s1: str, s2: str) -> float:
        """
        A simple fallback similarity calculation using difflib.SequenceMatcher.
        Note: This is NOT Jaro-Winkler and may yield different results.
        """
        return difflib.SequenceMatcher(None, s1.lower(), s2.lower()).ratio()

    _jaro_winkler_func = _fallback_jaro_winkler


class FuzzyMatcher:
    """
    Provides fuzzy string matching capabilities.
    """

    def __init__(self, threshold: float = 0.7):
        """
        Initializes the FuzzyMatcher with a similarity threshold.
        threshold: Minimum similarity score (0.0 to 1.0) for a match.
        """
        self.threshold = threshold

    def calculate_similarity(self, s1: str, s2: str) -> float:
        """
        Calculates the Jaro-Winkler similarity between two strings if Levenshtein is available,
        otherwise uses a fallback (difflib.SequenceMatcher ratio).
        """
        return _jaro_winkler_func(s1, s2)

    def find_best_match(
        self, target_string: str, candidates: List[str]
    ) -> Tuple[Optional[str], float]:
        """
        Finds the best matching candidate string from a list.
        Returns the best matching string and its similarity score, or (None, 0.0) if no match above threshold.
        """
        best_match = None
        highest_score = 0.0

        for candidate in candidates:
            score = self.calculate_similarity(target_string, candidate)
            if score > highest_score:
                highest_score = score
                best_match = candidate

        if highest_score >= self.threshold:
            return best_match, highest_score
        else:
            return None, 0.0
