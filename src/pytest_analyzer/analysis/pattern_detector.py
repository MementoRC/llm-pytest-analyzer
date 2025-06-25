from typing import List, Tuple

try:
    import ahocorasick

    AHOCORASICK_AVAILABLE = True
except ImportError:
    AHOCORASICK_AVAILABLE = False


class AhoCorasickPatternDetector:
    """
    A multi-pattern string matching detector using the Aho-Corasick algorithm.
    """

    def __init__(self):
        if not AHOCORASICK_AVAILABLE:
            raise RuntimeError(
                "The 'pyahocorasick' library is required for pattern detection "
                "but is not installed. Please install it with 'pip install pyahocorasick'."
            )
        self._automaton = ahocorasick.Automaton()
        self._patterns_added = False

    def add_pattern(self, pattern_id: str, pattern_string: str):
        """
        Adds a pattern string to the automaton.
        pattern_id: A unique identifier for the pattern.
        pattern_string: The string to search for.
        """
        if self._patterns_added:
            raise RuntimeError("Cannot add patterns after building the automaton.")
        # Store the pattern_string itself as the value, so iter returns it directly
        self._automaton.add_word(pattern_string, (pattern_id, pattern_string))

    def build(self):
        """
        Builds the Aho-Corasick automaton. Must be called after all patterns are added.
        """
        self._automaton.make_automaton()
        self._patterns_added = True

    def search(self, text: str) -> List[Tuple[int, Tuple[str, str]]]:
        """
        Searches the text for all added patterns.
        Returns a list of (end_index, (pattern_id, pattern_string)) tuples.
        """
        if not self._patterns_added:
            raise RuntimeError("Automaton must be built before searching.")

        results = []
        for end_index, value in self._automaton.iter(text):
            # value is the tuple (pattern_id, pattern_string) that we passed to add_word
            results.append((end_index, value))
        return results
