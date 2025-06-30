import ast
import re
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import List

from pytest_analyzer.core.infrastructure.ci_detection import CIEnvironment


class TestCategory(Enum):
    UNIT = auto()
    INTEGRATION = auto()
    FUNCTIONAL = auto()
    E2E = auto()
    PERFORMANCE = auto()
    SECURITY = auto()


@dataclass
class TestCategorizer:
    """
    Categorizes test files, extracts dependencies, checks CI compatibility, and generates skip markers.
    """

    def categorize_test(self, test_file: Path) -> TestCategory:
        """
        Categorize a test file using AST heuristics.
        """
        try:
            source = test_file.read_text(encoding="utf-8")
        except Exception:
            return TestCategory.FUNCTIONAL

        # Heuristics - check for markers first in raw source
        # E2E: marker or selenium/playwright/cypress
        if re.search(r"@pytest\.mark\.e2e", source):
            return TestCategory.E2E

        # Performance: pytest.mark.performance first
        if re.search(r"@pytest\.mark\.performance", source):
            return TestCategory.PERFORMANCE

        # Security: pytest.mark.security first
        if re.search(r"@pytest\.mark\.security", source):
            return TestCategory.SECURITY

        # Try to parse AST for imports analysis
        try:
            tree = ast.parse(source, filename=str(test_file))
        except Exception:
            # If parsing fails, fallback to regex analysis
            return self._categorize_by_regex(source)

        # Extract imports from AST
        imports = {
            node.names[0].name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
        }
        import_froms = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        all_imports = imports | import_froms

        # Check for tool-based categorization
        if any(dep in all_imports for dep in ("selenium", "playwright", "cypress")):
            return TestCategory.E2E

        # Performance: timeit/pytest-benchmark
        if "pytest_benchmark" in all_imports or "timeit" in all_imports:
            return TestCategory.PERFORMANCE

        # Security: bandit, security
        if any(dep in all_imports for dep in ("bandit", "security")):
            return TestCategory.SECURITY

        # Integration: test_*.py importing app modules, or using database/requests
        if any(
            dep in all_imports
            for dep in (
                "requests",
                "sqlalchemy",
                "psycopg2",
                "pymongo",
                "django",
                "flask",
            )
        ):
            return TestCategory.INTEGRATION

        # Unit: only imports stdlib, pytest, or test modules
        stdlib = {"os", "sys", "re", "math", "unittest", "pytest"}
        if all(dep in stdlib or dep.startswith("test") for dep in all_imports):
            return TestCategory.UNIT

        # Fallback
        return TestCategory.FUNCTIONAL

    def _categorize_by_regex(self, source: str) -> TestCategory:
        """
        Fallback categorization using regex when AST parsing fails.
        """
        # Extract imports using regex
        import_pattern = re.compile(
            r"^\s*(?:import|from)\s+([a-zA-Z0-9_\.]+)", re.MULTILINE
        )
        matches = import_pattern.findall(source)
        all_imports = {m.split(".")[0] for m in matches}

        # Check for tool-based categorization
        if any(dep in all_imports for dep in ("selenium", "playwright", "cypress")):
            return TestCategory.E2E

        # Performance: timeit/pytest-benchmark
        if "pytest_benchmark" in all_imports or "timeit" in all_imports:
            return TestCategory.PERFORMANCE

        # Security: bandit, security
        if any(dep in all_imports for dep in ("bandit", "security")):
            return TestCategory.SECURITY

        # Integration: using database/requests
        if any(
            dep in all_imports
            for dep in (
                "requests",
                "sqlalchemy",
                "psycopg2",
                "pymongo",
                "django",
                "flask",
            )
        ):
            return TestCategory.INTEGRATION

        # Unit: only imports stdlib, pytest, or test modules
        stdlib = {"os", "sys", "re", "math", "unittest", "pytest"}
        if all(dep in stdlib or dep.startswith("test") for dep in all_imports):
            return TestCategory.UNIT

        # Fallback
        return TestCategory.FUNCTIONAL

    def extract_tool_dependencies(self, test_file: Path) -> List[str]:
        """
        Extract dependencies from import statements using regex.
        """
        try:
            source = test_file.read_text(encoding="utf-8")
        except Exception:
            return []

        # Find all import statements
        import_pattern = re.compile(
            r"^\s*(?:import|from)\s+([a-zA-Z0-9_\.]+)", re.MULTILINE
        )
        matches = import_pattern.findall(source)
        # Remove duplicates and stdlib
        stdlib = {"os", "sys", "re", "math", "unittest", "pytest"}
        deps = sorted(
            {m.split(".")[0] for m in matches if m.split(".")[0] not in stdlib}
        )
        return deps

    def assess_ci_compatibility(self, test_file: Path, ci_env: CIEnvironment) -> bool:
        """
        Assess if the test is compatible with the given CI environment.
        """
        category = self.categorize_test(test_file)
        # E2E and PERFORMANCE tests may require tools not present in minimal CI
        if category in (TestCategory.E2E, TestCategory.PERFORMANCE):
            # Check if required tools are available in CI
            deps = self.extract_tool_dependencies(test_file)
            missing = [dep for dep in deps if dep not in ci_env.available_tools]
            return not missing
        # Assume other categories are compatible
        return True

    def generate_skip_marker(self, test_file: Path, reason: str) -> str:
        """
        Generate a pytest skip marker for the given test file and reason.
        """
        return f'@pytest.mark.skip(reason="{reason}")'
