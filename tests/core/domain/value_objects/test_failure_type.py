from pytest_analyzer.core.domain.value_objects.failure_type import FailureType


class TestFailureType:
    """Test suite for FailureType value object."""

    def test_all_failure_types_exist(self):
        """Test that all expected failure types are defined."""
        expected_types = {
            "ASSERTION_ERROR",
            "EXCEPTION",
            "SYNTAX_ERROR",
            "IMPORT_ERROR",
            "TIMEOUT_ERROR",
            "COLLECTION_ERROR",
            "FIXTURE_ERROR",
            "UNKNOWN",
        }

        actual_types = {ft.name for ft in FailureType}
        assert actual_types == expected_types

    def test_from_error_type_assertion_error(self):
        """Test mapping assertion error types."""
        assert (
            FailureType.from_error_type("AssertionError") == FailureType.ASSERTION_ERROR
        )
        assert (
            FailureType.from_error_type("assertion failed")
            == FailureType.ASSERTION_ERROR
        )
        assert FailureType.from_error_type("ASSERTION") == FailureType.ASSERTION_ERROR

    def test_from_error_type_syntax_error(self):
        """Test mapping syntax error types."""
        assert FailureType.from_error_type("SyntaxError") == FailureType.SYNTAX_ERROR
        assert FailureType.from_error_type("syntax error") == FailureType.SYNTAX_ERROR
        assert FailureType.from_error_type("SYNTAX") == FailureType.SYNTAX_ERROR

    def test_from_error_type_import_error(self):
        """Test mapping import error types."""
        assert FailureType.from_error_type("ImportError") == FailureType.IMPORT_ERROR
        assert (
            FailureType.from_error_type("ModuleNotFoundError")
            == FailureType.IMPORT_ERROR
        )
        assert FailureType.from_error_type("import failed") == FailureType.IMPORT_ERROR
        assert FailureType.from_error_type("modulenotfound") == FailureType.IMPORT_ERROR

    def test_from_error_type_timeout_error(self):
        """Test mapping timeout error types."""
        assert FailureType.from_error_type("TimeoutError") == FailureType.TIMEOUT_ERROR
        assert (
            FailureType.from_error_type("timeout occurred") == FailureType.TIMEOUT_ERROR
        )
        assert FailureType.from_error_type("TIMEOUT") == FailureType.TIMEOUT_ERROR

    def test_from_error_type_collection_error(self):
        """Test mapping collection error types."""
        assert (
            FailureType.from_error_type("CollectionError")
            == FailureType.COLLECTION_ERROR
        )
        assert (
            FailureType.from_error_type("collection failed")
            == FailureType.COLLECTION_ERROR
        )
        assert FailureType.from_error_type("COLLECTION") == FailureType.COLLECTION_ERROR

    def test_from_error_type_fixture_error(self):
        """Test mapping fixture error types."""
        assert FailureType.from_error_type("FixtureError") == FailureType.FIXTURE_ERROR
        assert (
            FailureType.from_error_type("fixture failed") == FailureType.FIXTURE_ERROR
        )
        assert FailureType.from_error_type("FIXTURE") == FailureType.FIXTURE_ERROR

    def test_from_error_type_generic_exception(self):
        """Test mapping generic exception types."""
        assert FailureType.from_error_type("ValueError") == FailureType.EXCEPTION
        assert FailureType.from_error_type("TypeError") == FailureType.EXCEPTION
        assert FailureType.from_error_type("RuntimeError") == FailureType.EXCEPTION
        assert FailureType.from_error_type("CustomException") == FailureType.EXCEPTION

    def test_from_error_type_unknown(self):
        """Test mapping unknown error types."""
        assert FailureType.from_error_type("unknown") == FailureType.UNKNOWN
        assert FailureType.from_error_type("UNKNOWN") == FailureType.UNKNOWN
        assert (
            FailureType.from_error_type("") == FailureType.EXCEPTION
        )  # Empty string defaults to exception

    def test_from_error_type_case_insensitive(self):
        """Test that error type mapping is case insensitive."""
        assert (
            FailureType.from_error_type("assertionerror") == FailureType.ASSERTION_ERROR
        )
        assert FailureType.from_error_type("SYNTAXERROR") == FailureType.SYNTAX_ERROR
        assert FailureType.from_error_type("ImportError") == FailureType.IMPORT_ERROR
