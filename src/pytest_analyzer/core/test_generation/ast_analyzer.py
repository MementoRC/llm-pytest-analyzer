"""
Enhanced AST Analyzer for Test Generation

This module provides comprehensive AST analysis capabilities for understanding
code structure and identifying test generation opportunities.
"""

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union


@dataclass
class FunctionInfo:
    """Information about a function extracted from AST analysis."""

    name: str
    args: List[str]
    defaults: List[Any]
    varargs: Optional[str]
    kwargs: Optional[str]
    return_annotation: Optional[str]
    docstring: Optional[str]
    decorators: List[str]
    complexity: int
    line_number: int
    is_async: bool = False


@dataclass
class ClassInfo:
    """Information about a class extracted from AST analysis."""

    name: str
    bases: List[str]
    methods: List[FunctionInfo]
    attributes: List[str]
    decorators: List[str]
    docstring: Optional[str]
    line_number: int


@dataclass
class CodePath:
    """Represents a code path that needs testing."""

    path_id: str
    conditions: List[str]
    variables: Set[str]
    complexity: int
    risk_level: str  # low, medium, high
    test_scenarios: List[str]


class ASTAnalyzer:
    """
    Enhanced AST analyzer that extracts comprehensive information for test generation.

    This analyzer identifies functions, classes, code paths, and potential test scenarios
    by examining the Abstract Syntax Tree of Python code.
    """

    def __init__(self):
        self.functions: List[FunctionInfo] = []
        self.classes: List[ClassInfo] = []
        self.imports: Set[str] = set()
        self.code_paths: List[CodePath] = []

    def analyze(self, source_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Analyze a Python source file and extract comprehensive information.

        Args:
            source_path: Path to the Python source file.

        Returns:
            Dictionary with detailed analysis results.
        """
        path = Path(source_path)

        try:
            source_code = path.read_text(encoding="utf-8")
            tree = ast.parse(source_code, filename=str(path))
        except Exception as e:
            return {
                "error": f"Failed to parse {path}: {e}",
                "functions": [],
                "classes": [],
                "imports": set(),
                "code_paths": [],
            }

        # Reset state
        self.functions = []
        self.classes = []
        self.imports = set()
        self.code_paths = []

        # Analyze the AST
        self._analyze_node(tree)

        # Generate code paths
        self._analyze_code_paths(tree)

        return {
            "file_path": str(path),
            "functions": self.functions,
            "classes": self.classes,
            "imports": list(self.imports),
            "code_paths": self.code_paths,
            "complexity_score": self._calculate_complexity_score(),
            "testable_functions": self.get_testable_functions(),
            "high_risk_paths": self.get_high_risk_paths(),
        }

    def _analyze_node(self, node: ast.AST) -> None:
        """Recursively analyze AST nodes."""
        if isinstance(node, ast.FunctionDef):
            self._analyze_function(node)
        elif isinstance(node, ast.AsyncFunctionDef):
            self._analyze_function(node, is_async=True)
        elif isinstance(node, ast.ClassDef):
            self._analyze_class(node)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            self._analyze_import(node)

        # Recursively analyze child nodes
        for child in ast.iter_child_nodes(node):
            self._analyze_node(child)

    def _analyze_function(
        self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef], is_async: bool = False
    ) -> None:
        """Analyze a function definition."""
        # Extract arguments
        args = [arg.arg for arg in node.args.args]
        defaults = [self._get_default_value(default) for default in node.args.defaults]

        # Extract decorators
        decorators = [self._get_decorator_name(dec) for dec in node.decorator_list]

        # Extract docstring
        docstring = ast.get_docstring(node)

        # Calculate complexity
        complexity = self._calculate_function_complexity(node)

        # Extract return annotation
        return_annotation = None
        if hasattr(node, "returns") and node.returns:
            return_annotation = self._get_annotation_string(node.returns)

        function_info = FunctionInfo(
            name=node.name,
            args=args,
            defaults=defaults,
            varargs=node.args.vararg.arg if node.args.vararg else None,
            kwargs=node.args.kwarg.arg if node.args.kwarg else None,
            return_annotation=return_annotation,
            docstring=docstring,
            decorators=decorators,
            complexity=complexity,
            line_number=node.lineno,
            is_async=is_async,
        )

        self.functions.append(function_info)

    def _analyze_class(self, node: ast.ClassDef) -> None:
        """Analyze a class definition."""
        bases = [self._get_base_name(base) for base in node.bases]
        decorators = [self._get_decorator_name(dec) for dec in node.decorator_list]
        docstring = ast.get_docstring(node)

        methods = []
        attributes = []

        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                temp_functions = self.functions
                self.functions = []

                self._analyze_function(item, isinstance(item, ast.AsyncFunctionDef))
                methods.extend(self.functions)
                self.functions = temp_functions

            elif isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        attributes.append(target.id)

        class_info = ClassInfo(
            name=node.name,
            bases=bases,
            methods=methods,
            attributes=attributes,
            decorators=decorators,
            docstring=docstring,
            line_number=node.lineno,
        )

        self.classes.append(class_info)

    def _analyze_import(self, node: Union[ast.Import, ast.ImportFrom]) -> None:
        """Analyze import statements."""
        if isinstance(node, ast.Import):
            for alias in node.names:
                self.imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            self.imports.add(node.module)

    def _analyze_code_paths(self, tree: ast.AST) -> None:
        """Analyze code paths for test scenario generation."""
        path_counter = 0

        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.While, ast.For)):
                path_id = f"path_{path_counter}"
                path_counter += 1

                conditions = self._extract_conditions(node)
                variables = self._extract_variables(node)
                complexity = self._calculate_path_complexity(node)
                risk_level = self._assess_risk_level(complexity, conditions)
                test_scenarios = self._generate_test_scenarios(conditions, variables)

                code_path = CodePath(
                    path_id=path_id,
                    conditions=conditions,
                    variables=variables,
                    complexity=complexity,
                    risk_level=risk_level,
                    test_scenarios=test_scenarios,
                )

                self.code_paths.append(code_path)

    def _get_default_value(self, node: ast.AST) -> Any:
        """Extract default value from AST node."""
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.Name):
            return node.id
        else:
            return None

    def _get_decorator_name(self, node: ast.AST) -> str:
        """Extract decorator name from AST node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_decorator_name(node.value)}.{node.attr}"
        elif isinstance(node, ast.Call):
            return self._get_decorator_name(node.func)
        else:
            return str(node)

    def _get_annotation_string(self, node: ast.AST) -> str:
        """Convert annotation AST node to string."""
        if hasattr(ast, "unparse"):
            return ast.unparse(node)
        else:
            return str(node)

    def _get_base_name(self, node: ast.AST) -> str:
        """Extract base class name from AST node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_base_name(node.value)}.{node.attr}"
        else:
            return str(node)

    def _calculate_function_complexity(self, node: ast.AST) -> int:
        """Calculate cyclomatic complexity for a function."""
        complexity = 1

        for child in ast.walk(node):
            if isinstance(
                child, (ast.If, ast.While, ast.For, ast.Try, ast.ExceptHandler)
            ):
                complexity += 1
            elif isinstance(child, (ast.BoolOp, ast.Compare)):
                complexity += 1

        return complexity

    def _extract_conditions(self, node: ast.AST) -> List[str]:
        """Extract conditions from control flow nodes."""
        conditions = []

        if isinstance(node, ast.If) and node.test:
            if hasattr(ast, "unparse"):
                conditions.append(ast.unparse(node.test))
            else:
                conditions.append(str(node.test))
        elif isinstance(node, ast.While) and node.test:
            if hasattr(ast, "unparse"):
                conditions.append(ast.unparse(node.test))
            else:
                conditions.append(str(node.test))
        elif isinstance(node, ast.For):
            if hasattr(ast, "unparse"):
                conditions.append(
                    f"for {ast.unparse(node.target)} in {ast.unparse(node.iter)}"
                )
            else:
                conditions.append("for loop")

        return conditions

    def _extract_variables(self, node: ast.AST) -> Set[str]:
        """Extract variables used in a code path."""
        variables = set()

        for child in ast.walk(node):
            if isinstance(child, ast.Name):
                variables.add(child.id)

        return variables

    def _calculate_path_complexity(self, node: ast.AST) -> int:
        """Calculate complexity of a code path."""
        complexity = 1

        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For)):
                complexity += 1

        return complexity

    def _assess_risk_level(self, complexity: int, conditions: List[str]) -> str:
        """Assess risk level based on complexity and conditions."""
        if complexity > 5 or len(conditions) > 3:
            return "high"
        elif complexity > 2 or len(conditions) > 1:
            return "medium"
        else:
            return "low"

    def _generate_test_scenarios(
        self, conditions: List[str], variables: Set[str]
    ) -> List[str]:
        """Generate test scenarios based on conditions and variables."""
        scenarios = []

        for condition in conditions:
            scenarios.append(f"Test when {condition} is True")
            scenarios.append(f"Test when {condition} is False")

        if variables:
            scenarios.append("Test with None values")
            scenarios.append("Test with empty values")
            scenarios.append("Test with boundary values")

        return scenarios

    def _calculate_complexity_score(self) -> int:
        """Calculate overall complexity score for the analyzed file."""
        total_complexity = 0

        for func in self.functions:
            total_complexity += func.complexity

        for cls in self.classes:
            for method in cls.methods:
                total_complexity += method.complexity

        return total_complexity

    def get_testable_functions(self) -> List[FunctionInfo]:
        """Get functions that are good candidates for test generation."""
        testable = []

        for func in self.functions:
            if not func.name.startswith("_") and not func.name.startswith("test_"):
                skip_decorators = {"property", "staticmethod", "classmethod"}
                if not any(dec in skip_decorators for dec in func.decorators):
                    testable.append(func)

        return testable

    def get_high_risk_paths(self) -> List[CodePath]:
        """Get code paths with high risk that need comprehensive testing."""
        return [path for path in self.code_paths if path.risk_level == "high"]

    def suggest_test_types(self, function_info: FunctionInfo) -> List[str]:
        """Suggest appropriate test types for a function."""
        suggestions = []

        suggestions.append("unit_test")

        if function_info.complexity > 3:
            suggestions.append("property_based")

        if function_info.is_async:
            suggestions.append("async_test")

        if any("except" in str(path.conditions) for path in self.code_paths):
            suggestions.append("exception_test")

        if len(function_info.args) > 2:
            suggestions.append("parametrized_test")

        return suggestions

    # Legacy method for backward compatibility
    def _extract_function_info(self, node: ast.FunctionDef) -> Dict[str, Any]:
        """Legacy method for backward compatibility."""
        return {
            "name": node.name,
            "args": [arg.arg for arg in node.args.args],
            "docstring": ast.get_docstring(node),
            "returns": getattr(node, "returns", None),
            "decorators": [
                ast.unparse(decorator) if hasattr(ast, "unparse") else str(decorator)
                for decorator in node.decorator_list
            ],
        }

    def _extract_class_info(self, node: ast.ClassDef) -> Dict[str, Any]:
        """Legacy method for backward compatibility."""
        return {
            "name": node.name,
            "docstring": ast.get_docstring(node),
            "methods": [
                self._extract_function_info(child)
                for child in node.body
                if isinstance(child, ast.FunctionDef)
            ],
            "class_variables": [
                target.id
                for child in node.body
                if isinstance(child, ast.Assign)
                for target in child.targets
                if isinstance(target, ast.Name)
            ],
        }
