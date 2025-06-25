from typing import List, Optional, Tuple

import Levenshtein


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
        Calculates the Jaro-Winkler similarity between two strings.
        Jaro-Winkler is generally good for short strings like error messages.
        """
        return Levenshtein.jaro_winkler(s1.lower(), s2.lower())

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
