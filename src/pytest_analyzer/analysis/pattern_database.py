from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class KnownPattern:
    """
    Represents a known failure pattern in the database.
    """

    id: str
    pattern_string: str  # The exact string to match (e.g., "AssertionError: assert")
    failure_type: str  # e.g., "AssertionError", "ImportError"
    base_message: str  # A canonical message for fuzzy matching (e.g., "assert failed")
    suggested_fix: str  # The suggested fix for this pattern
    impact_score: (
        float  # A predefined score indicating the severity/impact of this pattern
    )


class FailurePatternDatabase:
    """
    Manages a database of known failure patterns.
    """

    def __init__(self):
        self._patterns: Dict[str, KnownPattern] = {}
        self._load_default_patterns()

    def _load_default_patterns(self):
        """
        Loads a set of default, common pytest failure patterns.
        """
        default_patterns = [
            KnownPattern(
                id="assertion_error_general",
                pattern_string="AssertionError: assert",
                failure_type="AssertionError",
                base_message="assertion failed",
                suggested_fix="Review the test's assertion logic and expected values.",
                impact_score=0.7,
            ),
            KnownPattern(
                id="import_error_no_module",
                pattern_string="ImportError: No module named",
                failure_type="ImportError",
                base_message="no module named",
                suggested_fix="Check import paths, virtual environment, and install missing dependencies.",
                impact_score=0.9,
            ),
            KnownPattern(
                id="type_error_unsupported_operand",
                pattern_string="TypeError: unsupported operand type(s) for",
                failure_type="TypeError",
                base_message="unsupported operand type",
                suggested_fix="Ensure correct data types are used in operations.",
                impact_score=0.6,
            ),
            KnownPattern(
                id="name_error_name_not_defined",
                pattern_string="NameError: name",
                failure_type="NameError",
                base_message="name not defined",
                suggested_fix="Check variable and function names for typos or scope issues.",
                impact_score=0.5,
            ),
            KnownPattern(
                id="value_error_invalid_literal",
                pattern_string="ValueError: invalid literal for int() with base 10:",
                failure_type="ValueError",
                base_message="invalid literal for int",
                suggested_fix="Ensure string can be converted to integer.",
                impact_score=0.6,
            ),
            KnownPattern(
                id="index_error_list_index_out_of_range",
                pattern_string="IndexError: list index out of range",
                failure_type="IndexError",
                base_message="list index out of range",
                suggested_fix="Check list indexing and boundary conditions.",
                impact_score=0.7,
            ),
            KnownPattern(
                id="key_error_missing_key",
                pattern_string="KeyError:",
                failure_type="KeyError",
                base_message="missing key in dictionary",
                suggested_fix="Verify dictionary keys or handle missing keys gracefully.",
                impact_score=0.6,
            ),
        ]
        for pattern in default_patterns:
            self.add_pattern(pattern)

    def add_pattern(self, pattern: KnownPattern):
        """
        Adds or updates a known pattern in the database.
        """
        self._patterns[pattern.id] = pattern

    def get_pattern(self, pattern_id: str) -> Optional[KnownPattern]:
        """
        Retrieves a known pattern by its ID.
        """
        return self._patterns.get(pattern_id)

    def get_all_patterns(self) -> List[KnownPattern]:
        """
        Returns a list of all known patterns.
        """
        return list(self._patterns.values())

    def update_from_list(self, new_patterns: List[KnownPattern]):
        """
        Updates the database with a list of new or modified patterns.
        """
        for pattern in new_patterns:
            self.add_pattern(pattern)
