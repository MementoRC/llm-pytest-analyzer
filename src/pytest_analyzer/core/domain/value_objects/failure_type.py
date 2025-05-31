from enum import Enum


class FailureType(Enum):
    """Enumeration of different types of test failures."""

    ASSERTION_ERROR = "assertion_error"
    EXCEPTION = "exception"
    SYNTAX_ERROR = "syntax_error"
    IMPORT_ERROR = "import_error"
    TIMEOUT_ERROR = "timeout_error"
    COLLECTION_ERROR = "collection_error"
    FIXTURE_ERROR = "fixture_error"
    UNKNOWN = "unknown"

    @classmethod
    def from_error_type(cls, error_type: str) -> "FailureType":
        """Create FailureType from string error type."""
        error_type_lower = error_type.lower()

        if "assertion" in error_type_lower:
            return cls.ASSERTION_ERROR
        elif "syntax" in error_type_lower:
            return cls.SYNTAX_ERROR
        elif "import" in error_type_lower or "modulenotfound" in error_type_lower:
            return cls.IMPORT_ERROR
        elif "timeout" in error_type_lower:
            return cls.TIMEOUT_ERROR
        elif "collection" in error_type_lower:
            return cls.COLLECTION_ERROR
        elif "fixture" in error_type_lower:
            return cls.FIXTURE_ERROR
        else:
            return cls.EXCEPTION if error_type_lower != "unknown" else cls.UNKNOWN
