from pathlib import Path

from pytest_analyzer.core.domain.entities.pytest_failure import PytestFailure
from pytest_analyzer.core.domain.value_objects.failure_type import FailureType
from pytest_analyzer.core.domain.value_objects.test_location import TestLocation


class TestPytestFailure:
    """Test suite for PytestFailure domain entity."""

    def test_create_factory_method(self):
        """Test the create factory method."""
        failure = PytestFailure.create(
            test_name="test_example",
            file_path=Path("tests/test_example.py"),
            failure_message="AssertionError: expected True but got False",
            error_type="AssertionError",
            traceback=["line 1", "line 2"],
            line_number=42,
            function_name="test_example",
        )

        assert failure.test_name == "test_example"
        assert failure.location.file_path == Path("tests/test_example.py")
        assert failure.location.line_number == 42
        assert failure.location.function_name == "test_example"
        assert failure.failure_message == "AssertionError: expected True but got False"
        assert failure.failure_type == FailureType.ASSERTION_ERROR
        assert failure.traceback == ["line 1", "line 2"]
        assert isinstance(failure.id, str)
        assert len(failure.id) == 36  # UUID4 length

    def test_create_with_minimal_params(self):
        """Test create with minimal required parameters."""
        failure = PytestFailure.create(
            test_name="test_example",
            file_path=Path("tests/test_example.py"),
            failure_message="Error occurred",
            error_type="ValueError",
        )

        assert failure.test_name == "test_example"
        assert failure.location.file_path == Path("tests/test_example.py")
        assert failure.failure_message == "Error occurred"
        assert failure.failure_type == FailureType.EXCEPTION
        assert failure.traceback == []
        assert failure.source_code is None

    def test_direct_construction(self):
        """Test direct construction of PytestFailure."""
        location = TestLocation(
            file_path=Path("tests/test_example.py"),
            line_number=42,
            function_name="test_example",
        )

        failure = PytestFailure(
            id="test-id-123",
            test_name="test_example",
            location=location,
            failure_message="Test failed",
            failure_type=FailureType.ASSERTION_ERROR,
            traceback=["traceback line"],
        )

        assert failure.id == "test-id-123"
        assert failure.test_name == "test_example"
        assert failure.location == location
        assert failure.failure_message == "Test failed"
        assert failure.failure_type == FailureType.ASSERTION_ERROR
        assert failure.traceback == ["traceback line"]

    def test_is_assertion_error_property(self):
        """Test is_assertion_error property."""
        assertion_failure = PytestFailure.create(
            test_name="test",
            file_path=Path("test.py"),
            failure_message="AssertionError",
            error_type="AssertionError",
        )

        exception_failure = PytestFailure.create(
            test_name="test",
            file_path=Path("test.py"),
            failure_message="ValueError",
            error_type="ValueError",
        )

        assert assertion_failure.is_assertion_error is True
        assert exception_failure.is_assertion_error is False

    def test_is_exception_property(self):
        """Test is_exception property."""
        exception_failure = PytestFailure.create(
            test_name="test",
            file_path=Path("test.py"),
            failure_message="ValueError",
            error_type="ValueError",
        )

        assertion_failure = PytestFailure.create(
            test_name="test",
            file_path=Path("test.py"),
            failure_message="AssertionError",
            error_type="AssertionError",
        )

        assert exception_failure.is_exception is True
        assert assertion_failure.is_exception is False

    def test_is_import_error_property(self):
        """Test is_import_error property."""
        import_failure = PytestFailure.create(
            test_name="test",
            file_path=Path("test.py"),
            failure_message="ImportError",
            error_type="ImportError",
        )

        other_failure = PytestFailure.create(
            test_name="test",
            file_path=Path("test.py"),
            failure_message="ValueError",
            error_type="ValueError",
        )

        assert import_failure.is_import_error is True
        assert other_failure.is_import_error is False

    def test_is_syntax_error_property(self):
        """Test is_syntax_error property."""
        syntax_failure = PytestFailure.create(
            test_name="test",
            file_path=Path("test.py"),
            failure_message="SyntaxError",
            error_type="SyntaxError",
        )

        other_failure = PytestFailure.create(
            test_name="test",
            file_path=Path("test.py"),
            failure_message="ValueError",
            error_type="ValueError",
        )

        assert syntax_failure.is_syntax_error is True
        assert other_failure.is_syntax_error is False

    def test_file_path_property(self):
        """Test file_path property."""
        failure = PytestFailure.create(
            test_name="test",
            file_path=Path("tests/test_example.py"),
            failure_message="Error",
            error_type="ValueError",
        )

        assert failure.file_path == Path("tests/test_example.py")

    def test_short_error_message_property(self):
        """Test short_error_message property."""
        # Multi-line message
        failure = PytestFailure.create(
            test_name="test",
            file_path=Path("test.py"),
            failure_message="First line\\nSecond line\\nThird line",
            error_type="ValueError",
        )

        assert failure.short_error_message == "First line\\nSecond line\\nThird line"

        # Single line message
        failure2 = PytestFailure.create(
            test_name="test",
            file_path=Path("test.py"),
            failure_message="Single line error",
            error_type="ValueError",
        )

        assert failure2.short_error_message == "Single line error"

        # Empty message
        failure3 = PytestFailure.create(
            test_name="test",
            file_path=Path("test.py"),
            failure_message="",
            error_type="ValueError",
        )

        assert failure3.short_error_message == ""

    def test_full_test_id_property(self):
        """Test full_test_id property."""
        failure = PytestFailure.create(
            test_name="test_example",
            file_path=Path("tests/test_example.py"),
            failure_message="Error",
            error_type="ValueError",
            function_name="test_example",
            class_name="TestClass",
        )

        assert failure.full_test_id == "tests/test_example.py::TestClass::test_example"

    def test_add_related_file(self):
        """Test add_related_file method."""
        failure = PytestFailure.create(
            test_name="test",
            file_path=Path("test.py"),
            failure_message="Error",
            error_type="ValueError",
        )

        failure.add_related_file("src/module.py")
        failure.add_related_file("src/other.py")

        assert "src/module.py" in failure.related_project_files
        assert "src/other.py" in failure.related_project_files
        assert len(failure.related_project_files) == 2

        # Adding duplicate should not increase list size
        failure.add_related_file("src/module.py")
        assert len(failure.related_project_files) == 2

    def test_set_group_fingerprint(self):
        """Test set_group_fingerprint method."""
        failure = PytestFailure.create(
            test_name="test",
            file_path=Path("test.py"),
            failure_message="Error",
            error_type="ValueError",
        )

        assert failure.group_fingerprint is None

        failure.set_group_fingerprint("fingerprint-123")
        assert failure.group_fingerprint == "fingerprint-123"

    def test_is_same_failure_type(self):
        """Test is_same_failure_type method."""
        failure1 = PytestFailure.create(
            test_name="test1",
            file_path=Path("test1.py"),
            failure_message="AssertionError",
            error_type="AssertionError",
        )

        failure2 = PytestFailure.create(
            test_name="test2",
            file_path=Path("test2.py"),
            failure_message="AssertionError: different message",
            error_type="AssertionError",
        )

        failure3 = PytestFailure.create(
            test_name="test3",
            file_path=Path("test3.py"),
            failure_message="ValueError",
            error_type="ValueError",
        )

        assert failure1.is_same_failure_type(failure2) is True
        assert failure1.is_same_failure_type(failure3) is False
        assert failure2.is_same_failure_type(failure3) is False

    def test_has_similar_error_message(self):
        """Test has_similar_error_message method."""
        failure1 = PytestFailure.create(
            test_name="test1",
            file_path=Path("test1.py"),
            failure_message="expected value but got different value",
            error_type="AssertionError",
        )

        failure2 = PytestFailure.create(
            test_name="test2",
            file_path=Path("test2.py"),
            failure_message="expected different value but got value",
            error_type="AssertionError",
        )

        failure3 = PytestFailure.create(
            test_name="test3",
            file_path=Path("test3.py"),
            failure_message="completely unrelated error message",
            error_type="AssertionError",
        )

        # Should have high similarity due to common words
        assert failure1.has_similar_error_message(failure2, threshold=0.5) is True

        # Should have low similarity
        assert failure1.has_similar_error_message(failure3, threshold=0.5) is False

        # Test with empty messages
        failure4 = PytestFailure.create(
            test_name="test4",
            file_path=Path("test4.py"),
            failure_message="",
            error_type="ValueError",
        )

        assert failure1.has_similar_error_message(failure4) is False

    def test_equality_based_on_id(self):
        """Test that equality is based on entity identity (id)."""
        location = TestLocation(file_path=Path("test.py"))

        failure1 = PytestFailure(
            id="same-id",
            test_name="test1",
            location=location,
            failure_message="Error 1",
            failure_type=FailureType.ASSERTION_ERROR,
        )

        failure2 = PytestFailure(
            id="same-id",
            test_name="test2",  # Different content
            location=location,
            failure_message="Error 2",  # Different content
            failure_type=FailureType.EXCEPTION,  # Different content
        )

        failure3 = PytestFailure(
            id="different-id",
            test_name="test1",  # Same content as failure1
            location=location,
            failure_message="Error 1",
            failure_type=FailureType.ASSERTION_ERROR,
        )

        # Same ID means equal, regardless of content
        assert failure1 == failure2

        # Different ID means not equal, even with same content
        assert failure1 != failure3
        assert failure2 != failure3

    def test_hash_based_on_id(self):
        """Test that hash is based on entity identity (id)."""
        location = TestLocation(file_path=Path("test.py"))

        failure1 = PytestFailure(
            id="same-id",
            test_name="test1",
            location=location,
            failure_message="Error 1",
            failure_type=FailureType.ASSERTION_ERROR,
        )

        failure2 = PytestFailure(
            id="same-id",
            test_name="test2",  # Different content
            location=location,
            failure_message="Error 2",
            failure_type=FailureType.EXCEPTION,
        )

        failure3 = PytestFailure(
            id="different-id",
            test_name="test1",
            location=location,
            failure_message="Error 1",
            failure_type=FailureType.ASSERTION_ERROR,
        )

        # Same ID means same hash
        assert hash(failure1) == hash(failure2)

        # Different ID means different hash
        assert hash(failure1) != hash(failure3)

        # Can be used in sets
        failure_set = {failure1, failure2, failure3}
        assert len(failure_set) == 2  # failure1 and failure2 are the same

    def test_mutable_fields(self):
        """Test that entity fields can be modified (unlike value objects)."""
        failure = PytestFailure.create(
            test_name="test",
            file_path=Path("test.py"),
            failure_message="Error",
            error_type="ValueError",
        )

        # Should be able to modify fields
        failure.source_code = "def test(): pass"
        failure.raw_output_section = "raw output"
        failure.traceback.append("new traceback line")

        assert failure.source_code == "def test(): pass"
        assert failure.raw_output_section == "raw output"
        assert "new traceback line" in failure.traceback
