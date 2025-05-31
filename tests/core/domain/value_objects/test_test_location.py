from pathlib import Path

import pytest

from pytest_analyzer.core.domain.value_objects.test_location import TestLocation


class TestTestLocation:
    """Test suite for TestLocation value object."""

    def test_creation_with_path_object(self):
        """Test creating TestLocation with Path object."""
        file_path = Path("tests/test_example.py")
        location = TestLocation(file_path=file_path, line_number=42)

        assert location.file_path == file_path
        assert location.line_number == 42
        assert location.function_name is None
        assert location.class_name is None

    def test_creation_with_string_path(self):
        """Test creating TestLocation with string path (should convert to Path)."""
        location = TestLocation(file_path="tests/test_example.py", line_number=42)

        assert isinstance(location.file_path, Path)
        assert location.file_path == Path("tests/test_example.py")
        assert location.line_number == 42

    def test_creation_with_all_fields(self):
        """Test creating TestLocation with all optional fields."""
        location = TestLocation(
            file_path=Path("tests/test_example.py"),
            line_number=42,
            function_name="test_function",
            class_name="TestClass",
        )

        assert location.file_path == Path("tests/test_example.py")
        assert location.line_number == 42
        assert location.function_name == "test_function"
        assert location.class_name == "TestClass"

    def test_immutability(self):
        """Test that TestLocation is immutable (frozen dataclass)."""
        location = TestLocation(file_path=Path("tests/test_example.py"))

        with pytest.raises(AttributeError):
            location.file_path = Path("other/path.py")

        with pytest.raises(AttributeError):
            location.line_number = 100

    def test_module_name_property(self):
        """Test the module_name property."""
        location = TestLocation(file_path=Path("tests/test_example.py"))
        assert location.module_name == "test_example"

        location = TestLocation(file_path=Path("src/analyzer/core.py"))
        assert location.module_name == "core"

    def test_package_path_property_with_src(self):
        """Test package_path property with src directory."""
        location = TestLocation(
            file_path=Path("src/pytest_analyzer/core/test_example.py")
        )
        assert location.package_path == "pytest_analyzer.core.test_example"

    def test_package_path_property_without_src(self):
        """Test package_path property without src directory."""
        location = TestLocation(file_path=Path("tests/unit/test_example.py"))
        assert location.package_path == "tests.unit.test_example"

    def test_package_path_property_removes_py_extension(self):
        """Test that package_path removes .py extension."""
        location = TestLocation(
            file_path=Path("src/pytest_analyzer/core/test_example.py")
        )
        assert location.package_path == "pytest_analyzer.core.test_example"

        # Test without .py extension
        location = TestLocation(file_path=Path("src/pytest_analyzer/core/test_example"))
        assert location.package_path == "pytest_analyzer.core.test_example"

    def test_full_test_id_file_only(self):
        """Test full_test_id with file only."""
        location = TestLocation(file_path=Path("tests/test_example.py"))
        assert location.full_test_id == "tests/test_example.py"

    def test_full_test_id_with_function(self):
        """Test full_test_id with function."""
        location = TestLocation(
            file_path=Path("tests/test_example.py"),
            function_name="test_function",
        )
        assert location.full_test_id == "tests/test_example.py::test_function"

    def test_full_test_id_with_class_and_function(self):
        """Test full_test_id with class and function."""
        location = TestLocation(
            file_path=Path("tests/test_example.py"),
            class_name="TestClass",
            function_name="test_method",
        )
        assert location.full_test_id == "tests/test_example.py::TestClass::test_method"

    def test_full_test_id_with_class_only(self):
        """Test full_test_id with class only."""
        location = TestLocation(
            file_path=Path("tests/test_example.py"),
            class_name="TestClass",
        )
        assert location.full_test_id == "tests/test_example.py::TestClass"

    def test_str_representation_file_only(self):
        """Test string representation with file only."""
        location = TestLocation(file_path=Path("tests/test_example.py"))
        assert str(location) == "tests/test_example.py"

    def test_str_representation_with_line_number(self):
        """Test string representation with line number."""
        location = TestLocation(
            file_path=Path("tests/test_example.py"),
            line_number=42,
        )
        assert str(location) == "tests/test_example.py:42"

    def test_str_representation_with_function(self):
        """Test string representation with function."""
        location = TestLocation(
            file_path=Path("tests/test_example.py"),
            line_number=42,
            function_name="test_function",
        )
        assert str(location) == "tests/test_example.py:42 (test_function)"

    def test_str_representation_with_class_and_function(self):
        """Test string representation with class and function."""
        location = TestLocation(
            file_path=Path("tests/test_example.py"),
            line_number=42,
            class_name="TestClass",
            function_name="test_method",
        )
        assert str(location) == "tests/test_example.py:42 (TestClass.test_method)"

    def test_str_representation_with_class_only(self):
        """Test string representation with class only."""
        location = TestLocation(
            file_path=Path("tests/test_example.py"),
            line_number=42,
            class_name="TestClass",
        )
        assert str(location) == "tests/test_example.py:42 (TestClass)"

    def test_equality(self):
        """Test equality comparison."""
        location1 = TestLocation(
            file_path=Path("tests/test_example.py"),
            line_number=42,
            function_name="test_function",
        )
        location2 = TestLocation(
            file_path=Path("tests/test_example.py"),
            line_number=42,
            function_name="test_function",
        )
        location3 = TestLocation(
            file_path=Path("tests/test_example.py"),
            line_number=43,
            function_name="test_function",
        )

        assert location1 == location2
        assert location1 != location3

    def test_hashable(self):
        """Test that TestLocation is hashable (can be used in sets/dicts)."""
        location1 = TestLocation(file_path=Path("tests/test_example.py"))
        location2 = TestLocation(file_path=Path("tests/test_other.py"))

        # Should be able to create a set
        location_set = {location1, location2}
        assert len(location_set) == 2

        # Should be able to use as dict key
        location_dict = {location1: "test1", location2: "test2"}
        assert len(location_dict) == 2
