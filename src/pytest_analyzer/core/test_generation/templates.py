"""
Enhanced Test Template Engine

This module provides comprehensive template-based test generation capabilities for creating
structured and consistent test cases.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .ast_analyzer import ClassInfo, FunctionInfo


@dataclass
class TestTemplate:
    """Template for generating test cases."""

    name: str
    template: str
    variables: List[str]
    description: str
    test_type: str  # unit, integration, parametrized, etc.


class TestTemplateEngine:
    """
    Enhanced template engine that generates test code from templates based on function
    and class analysis. Provides various templates for different testing scenarios.
    """

    def __init__(self):
        self.templates = self._load_templates()

    def _load_templates(self) -> Dict[str, TestTemplate]:
        """Load predefined test templates."""
        templates = {}

        # Basic unit test template
        templates["unit_test"] = TestTemplate(
            name="unit_test",
            template='''def test_{function_name}():
    """Test {function_name} function."""
    # Arrange
    {arrange_code}

    # Act
    result = {function_call}

    # Assert
    {assert_code}''',
            variables=["function_name", "arrange_code", "function_call", "assert_code"],
            description="Basic unit test template",
            test_type="unit",
        )

        # Parametrized test template
        templates["parametrized_test"] = TestTemplate(
            name="parametrized_test",
            template='''@pytest.mark.parametrize("{param_names}", [
    {test_cases}
])
def test_{function_name}_parametrized({param_names}, expected):
    """Test {function_name} with various parameters."""
    # Act
    result = {function_call}

    # Assert
    assert result == expected''',
            variables=["function_name", "param_names", "test_cases", "function_call"],
            description="Parametrized test template for multiple input scenarios",
            test_type="parametrized",
        )

        # Exception test template
        templates["exception_test"] = TestTemplate(
            name="exception_test",
            template='''def test_{function_name}_raises_{exception_type}():
    """Test that {function_name} raises {exception_type} for invalid input."""
    # Arrange
    {arrange_code}

    # Act & Assert
    with pytest.raises({exception_type}):
        {function_call}''',
            variables=[
                "function_name",
                "exception_type",
                "arrange_code",
                "function_call",
            ],
            description="Test template for exception scenarios",
            test_type="exception",
        )

        # Async test template
        templates["async_test"] = TestTemplate(
            name="async_test",
            template='''@pytest.mark.asyncio
async def test_{function_name}_async():
    """Test async {function_name} function."""
    # Arrange
    {arrange_code}

    # Act
    result = await {function_call}

    # Assert
    {assert_code}''',
            variables=["function_name", "arrange_code", "function_call", "assert_code"],
            description="Template for async function testing",
            test_type="async",
        )

        # Class method test template
        templates["class_method_test"] = TestTemplate(
            name="class_method_test",
            template='''def test_{class_name}_{method_name}():
    """Test {class_name}.{method_name} method."""
    # Arrange
    instance = {class_name}({constructor_args})
    {arrange_code}

    # Act
    result = instance.{method_call}

    # Assert
    {assert_code}''',
            variables=[
                "class_name",
                "method_name",
                "constructor_args",
                "arrange_code",
                "method_call",
                "assert_code",
            ],
            description="Template for testing class methods",
            test_type="class_method",
        )

        # Property-based test template
        templates["property_based"] = TestTemplate(
            name="property_based",
            template='''@given({strategy_params})
def test_{function_name}_property({param_names}):
    """Property-based test for {function_name}."""
    # Assume
    assume({assumptions})

    # Act
    result = {function_call}

    # Assert
    {property_assertions}''',
            variables=[
                "function_name",
                "strategy_params",
                "param_names",
                "assumptions",
                "function_call",
                "property_assertions",
            ],
            description="Template for property-based testing with Hypothesis",
            test_type="property_based",
        )

        return templates

    def render_tests(
        self,
        code_structure: Dict[str, Any],
        scenarios: List[Dict[str, Any]],
        property_based: bool = False,
    ) -> str:
        """
        Render test code for the given code structure and scenarios.
        Legacy method for backward compatibility.

        Args:
            code_structure: Output from ASTAnalyzer.
            scenarios: List of test scenarios.
            property_based: Whether to use hypothesis for property-based tests.

        Returns:
            Test code as a string.
        """
        lines = [
            "import pytest",
        ]
        if property_based:
            lines.append("from hypothesis import given, strategies as st")

        # Map scenarios to functions/classes
        for scenario in scenarios:
            func = scenario.get("function")
            cls = scenario.get("class")
            args = scenario.get("args", {})
            desc = scenario.get("description", "")
            test_name = self._make_test_name(func, cls, desc)
            lines.append("")
            lines.append(f"def {test_name}():")
            # Docstring
            lines.append(f'    """{desc}"""')
            # Arrange
            if cls:
                lines.append(f"    obj = {cls}()")
                call = f"obj.{func}({self._format_args(args)})"
            else:
                call = f"{func}({self._format_args(args)})"
            # Act/Assert
            lines.append("    # TODO: Add assertions")
            lines.append(f"    result = {call}")
            lines.append("    assert result is not None")

        return "\n".join(lines)

    def generate_test(self, template_name: str, variables: Dict[str, Any]) -> str:
        """
        Generate test code from a template.

        Args:
            template_name: Name of the template to use
            variables: Dictionary of variables to substitute in the template

        Returns:
            Generated test code as a string
        """
        if template_name not in self.templates:
            raise ValueError(f"Template '{template_name}' not found")

        template = self.templates[template_name]

        # Validate that all required variables are provided
        missing_vars = set(template.variables) - set(variables.keys())
        if missing_vars:
            raise ValueError(
                f"Missing variables for template '{template_name}': {missing_vars}"
            )

        # Generate the test code by substituting variables
        test_code = template.template.format(**variables)
        return test_code

    def generate_function_tests(
        self, function_info: FunctionInfo, test_types: Optional[List[str]] = None
    ) -> List[str]:
        """
        Generate test cases for a function based on its characteristics.

        Args:
            function_info: Information about the function to test
            test_types: List of test types to generate (if None, auto-detect)

        Returns:
            List of generated test code strings
        """
        if test_types is None:
            test_types = self._determine_test_types(function_info)

        generated_tests = []

        for test_type in test_types:
            if test_type == "unit_test":
                test_code = self._generate_unit_test(function_info)
            elif test_type == "parametrized_test":
                test_code = self._generate_parametrized_test(function_info)
            elif test_type == "exception_test":
                test_code = self._generate_exception_test(function_info)
            elif test_type == "async_test" and function_info.is_async:
                test_code = self._generate_async_test(function_info)
            elif test_type == "property_based":
                test_code = self._generate_property_based_test(function_info)
            else:
                continue  # Skip unsupported test types

            if test_code:
                generated_tests.append(test_code)

        return generated_tests

    def generate_class_tests(self, class_info: ClassInfo) -> List[str]:
        """
        Generate test cases for a class and its methods.

        Args:
            class_info: Information about the class to test

        Returns:
            List of generated test code strings
        """
        generated_tests = []

        # Generate constructor test
        constructor_test = self._generate_constructor_test(class_info)
        if constructor_test:
            generated_tests.append(constructor_test)

        # Generate tests for each method
        for method in class_info.methods:
            if not method.name.startswith("_"):  # Skip private methods
                method_test = self._generate_method_test(class_info, method)
                if method_test:
                    generated_tests.append(method_test)

        return generated_tests

    def _determine_test_types(self, function_info: FunctionInfo) -> List[str]:
        """Determine appropriate test types for a function."""
        test_types = ["unit_test"]

        if len(function_info.args) > 1:
            test_types.append("parametrized_test")

        if function_info.complexity > 2:
            test_types.append("exception_test")

        if function_info.is_async:
            test_types.append("async_test")

        if function_info.complexity > 3:
            test_types.append("property_based")

        return test_types

    def _generate_unit_test(self, function_info: FunctionInfo) -> str:
        """Generate a basic unit test."""
        variables = {
            "function_name": function_info.name,
            "arrange_code": self._generate_arrange_code(function_info),
            "function_call": self._generate_function_call(function_info),
            "assert_code": self._generate_assert_code(function_info),
        }
        return self.generate_test("unit_test", variables)

    def _generate_parametrized_test(self, function_info: FunctionInfo) -> str:
        """Generate a parametrized test."""
        if len(function_info.args) < 2:
            return ""

        param_names = ", ".join(function_info.args)
        test_cases = self._generate_test_cases(function_info)

        variables = {
            "function_name": function_info.name,
            "param_names": param_names,
            "test_cases": test_cases,
            "function_call": f"{function_info.name}({param_names})",
        }
        return self.generate_test("parametrized_test", variables)

    def _generate_exception_test(self, function_info: FunctionInfo) -> str:
        """Generate an exception test."""
        variables = {
            "function_name": function_info.name,
            "exception_type": "ValueError",  # Could be made smarter
            "arrange_code": "invalid_input = None",
            "function_call": f"{function_info.name}(invalid_input)",
        }
        return self.generate_test("exception_test", variables)

    def _generate_async_test(self, function_info: FunctionInfo) -> str:
        """Generate an async test."""
        variables = {
            "function_name": function_info.name,
            "arrange_code": self._generate_arrange_code(function_info),
            "function_call": self._generate_function_call(function_info),
            "assert_code": self._generate_assert_code(function_info),
        }
        return self.generate_test("async_test", variables)

    def _generate_property_based_test(self, function_info: FunctionInfo) -> str:
        """Generate a property-based test using Hypothesis."""
        strategy_params = self._generate_hypothesis_strategies(function_info)
        param_names = ", ".join(function_info.args)

        variables = {
            "function_name": function_info.name,
            "strategy_params": strategy_params,
            "param_names": param_names,
            "assumptions": "True",  # Could be made smarter based on function analysis
            "function_call": f"{function_info.name}({param_names})",
            "property_assertions": "assert result is not None",  # Basic property
        }
        return self.generate_test("property_based", variables)

    def _generate_constructor_test(self, class_info: ClassInfo) -> str:
        """Generate a constructor test for a class."""
        test_code = f'''def test_{class_info.name.lower()}_constructor():
    """Test {class_info.name} constructor."""
    # Act
    instance = {class_info.name}()

    # Assert
    assert isinstance(instance, {class_info.name})'''

        return test_code

    def _generate_method_test(
        self, class_info: ClassInfo, method_info: FunctionInfo
    ) -> str:
        """Generate a test for a class method."""
        variables = {
            "class_name": class_info.name,
            "method_name": method_info.name,
            "constructor_args": "",
            "arrange_code": self._generate_arrange_code(method_info),
            "method_call": self._generate_function_call(method_info),
            "assert_code": self._generate_assert_code(method_info),
        }
        return self.generate_test("class_method_test", variables)

    def _generate_arrange_code(self, function_info: FunctionInfo) -> str:
        """Generate arrange section code based on function parameters."""
        if not function_info.args:
            return "# No parameters needed"

        arrange_lines = []
        for arg in function_info.args:
            if arg == "self":
                continue
            arrange_lines.append(f"{arg} = {self._get_default_value_for_arg(arg)}")

        return (
            "\n    ".join(arrange_lines) if arrange_lines else "# No parameters needed"
        )

    def _generate_function_call(self, function_info: FunctionInfo) -> str:
        """Generate function call code."""
        args = [arg for arg in function_info.args if arg != "self"]
        if args:
            return f"{function_info.name}({', '.join(args)})"
        else:
            return f"{function_info.name}()"

    def _generate_assert_code(self, function_info: FunctionInfo) -> str:
        """Generate assert code based on function return type."""
        if function_info.return_annotation:
            return_type = function_info.return_annotation.lower()
            if "bool" in return_type:
                return "assert isinstance(result, bool)"
            elif "int" in return_type:
                return "assert isinstance(result, int)"
            elif "str" in return_type:
                return "assert isinstance(result, str)"
            elif "list" in return_type:
                return "assert isinstance(result, list)"
            elif "dict" in return_type:
                return "assert isinstance(result, dict)"

        return "assert result is not None"

    def _generate_test_cases(self, function_info: FunctionInfo) -> str:
        """Generate test cases for parametrized tests."""
        if len(function_info.args) == 2:  # Assuming one param + expected
            return """(1, 1),
    (2, 2),
    (0, 0),
    (-1, -1)"""
        elif len(function_info.args) == 3:  # Two params + expected
            return """(1, 2, 3),
    (0, 0, 0),
    (-1, 1, 0)"""
        else:
            # Generate generic test cases
            return """("test", "expected"),
    (None, None),
    ("", "")"""

    def _generate_hypothesis_strategies(self, function_info: FunctionInfo) -> str:
        """Generate Hypothesis strategies based on function parameters."""
        strategies = []
        for arg in function_info.args:
            if arg == "self":
                continue
            strategies.append(f"{arg}=st.text()")  # Default to text strategy

        return ", ".join(strategies) if strategies else "x=st.integers()"

    def _get_default_value_for_arg(self, arg_name: str) -> str:
        """Get a default value for a function argument based on name heuristics."""
        arg_lower = arg_name.lower()

        if "id" in arg_lower or "count" in arg_lower or "number" in arg_lower:
            return "1"
        elif "name" in arg_lower or "text" in arg_lower or "message" in arg_lower:
            return '"test"'
        elif "flag" in arg_lower or "enabled" in arg_lower or "active" in arg_lower:
            return "True"
        elif "list" in arg_lower or "items" in arg_lower:
            return "[]"
        elif "dict" in arg_lower or "config" in arg_lower:
            return "{}"
        else:
            return "None"

    def get_available_templates(self) -> List[str]:
        """Get list of available template names."""
        return list(self.templates.keys())

    def get_template_info(self, template_name: str) -> Optional[TestTemplate]:
        """Get information about a specific template."""
        return self.templates.get(template_name)

    # Legacy methods for backward compatibility
    def _make_test_name(self, func: str, cls: str, desc: str) -> str:
        base = f"test_{cls + '_' if cls else ''}{func}"
        # Add a hash of the description for uniqueness if needed
        import hashlib

        h = hashlib.sha1(desc.encode()).hexdigest()[:6]
        return f"{base}_{h}"

    def _format_args(self, args: Any) -> str:
        if isinstance(args, dict):
            return ", ".join(f"{k}={repr(v)}" for k, v in args.items())
        return ""
