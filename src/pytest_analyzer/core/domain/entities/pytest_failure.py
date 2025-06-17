import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from ..value_objects.failure_type import FailureType
from ..value_objects.test_location import TestLocation


@dataclass
class PytestFailure:
    """
    Domain entity representing a test failure from a pytest execution.

    This entity follows DDD principles:
    - Has an identity (id)
    - Contains business logic related to test failures
    - Is mutable (failure state can change during analysis)
    """

    id: str
    test_name: str
    location: TestLocation
    failure_message: str
    failure_type: FailureType
    traceback: str = ""
    source_code: Optional[str] = None
    raw_output_section: Optional[str] = None
    related_project_files: List[str] = field(default_factory=list)
    group_fingerprint: Optional[str] = None

    @classmethod
    def create(
        cls,
        test_name: str,
        file_path: Path,
        failure_message: str,
        error_type: str,
        traceback: Optional[List[str]] = None,
        line_number: Optional[int] = None,
        function_name: Optional[str] = None,
        class_name: Optional[str] = None,
    ) -> "PytestFailure":
        """
        Factory method to create a PytestFailure with proper defaults.

        This method ensures proper initialization and follows DDD patterns
        for entity creation.
        """
        location = TestLocation(
            file_path=file_path,
            line_number=line_number,
            function_name=function_name,
            class_name=class_name,
        )

        failure_type = FailureType.from_error_type(error_type)

        return cls(
            id=str(uuid.uuid4()),
            test_name=test_name,
            location=location,
            failure_message=failure_message,
            failure_type=failure_type,
            traceback="\n".join(traceback) if traceback else "",
        )

    @property
    def is_assertion_error(self) -> bool:
        """Check if this failure is an assertion error."""
        return self.failure_type == FailureType.ASSERTION_ERROR

    @property
    def is_exception(self) -> bool:
        """Check if this failure is an exception."""
        return self.failure_type == FailureType.EXCEPTION

    @property
    def is_import_error(self) -> bool:
        """Check if this failure is an import error."""
        return self.failure_type == FailureType.IMPORT_ERROR

    @property
    def is_syntax_error(self) -> bool:
        """Check if this failure is a syntax error."""
        return self.failure_type == FailureType.SYNTAX_ERROR

    @property
    def file_path(self) -> Path:
        """Get the file path of the test."""
        return self.location.file_path

    @property
    def error_type(self) -> str:
        """Get the error type as a string for backward compatibility."""
        return self.failure_type.value

    @property
    def error_message(self) -> str:
        """Get the error message for backward compatibility."""
        return self.failure_message

    @property
    def relevant_code(self) -> Optional[str]:
        """Get the relevant code for backward compatibility."""
        return self.source_code

    @property
    def short_error_message(self) -> str:
        """Get a shortened version of the error message."""
        lines = self.failure_message.split("\n")
        return lines[0] if lines else ""

    @property
    def full_test_id(self) -> str:
        """Get the full test identifier in pytest format."""
        return self.location.full_test_id

    def add_related_file(self, file_path: str) -> None:
        """Add a related project file to this failure."""
        if file_path not in self.related_project_files:
            self.related_project_files.append(file_path)

    def set_group_fingerprint(self, fingerprint: str) -> None:
        """Set the group fingerprint for failure grouping."""
        self.group_fingerprint = fingerprint

    def is_same_failure_type(self, other: "PytestFailure") -> bool:
        """Check if this failure has the same type as another failure."""
        return self.failure_type == other.failure_type

    def has_similar_error_message(
        self, other: "PytestFailure", threshold: float = 0.8
    ) -> bool:
        """
        Check if this failure has a similar error message to another.

        This is a simple implementation - in practice you might want to use
        more sophisticated text similarity algorithms.
        """
        if not self.failure_message or not other.failure_message:
            return False

        # Simple similarity check based on common words
        words1 = set(self.failure_message.lower().split())
        words2 = set(other.failure_message.lower().split())

        if not words1 or not words2:
            return False

        intersection = words1.intersection(words2)
        union = words1.union(words2)

        similarity = len(intersection) / len(union)
        return similarity >= threshold

    def __eq__(self, other) -> bool:
        """Equality based on entity identity (id)."""
        if not isinstance(other, PytestFailure):
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        """Hash based on entity identity (id)."""
        return hash(self.id)
