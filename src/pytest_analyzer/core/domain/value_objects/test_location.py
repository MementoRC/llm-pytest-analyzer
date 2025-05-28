from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class TestLocation:
    """Value object representing the location of a test in the codebase."""

    file_path: Path
    line_number: Optional[int] = None
    function_name: Optional[str] = None
    class_name: Optional[str] = None

    def __post_init__(self):
        """Validate that file_path is a Path object."""
        if not isinstance(self.file_path, Path):
            object.__setattr__(self, "file_path", Path(self.file_path))

    @property
    def module_name(self) -> str:
        """Get the module name from the file path."""
        return self.file_path.stem

    @property
    def package_path(self) -> str:
        """Get the package path as a dot-separated string."""
        parts = self.file_path.parts
        if "src" in parts:
            # Find src directory and build path from there
            src_index = parts.index("src")
            package_parts = parts[src_index + 1 :]
        else:
            package_parts = parts

        # Remove .py extension if present
        if package_parts and package_parts[-1].endswith(".py"):
            package_parts = package_parts[:-1] + (package_parts[-1][:-3],)

        return ".".join(package_parts)

    @property
    def full_test_id(self) -> str:
        """Get the full test identifier in pytest format."""
        test_id = str(self.file_path)

        if self.class_name:
            test_id += f"::{self.class_name}"

        if self.function_name:
            test_id += f"::{self.function_name}"

        return test_id

    def __str__(self) -> str:
        """String representation of the test location."""
        location = str(self.file_path)

        if self.line_number:
            location += f":{self.line_number}"

        if self.class_name and self.function_name:
            location += f" ({self.class_name}.{self.function_name})"
        elif self.function_name:
            location += f" ({self.function_name})"
        elif self.class_name:
            location += f" ({self.class_name})"

        return location
