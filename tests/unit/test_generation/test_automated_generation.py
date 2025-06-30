import os
import tempfile
from unittest.mock import Mock

import pytest

from src.pytest_analyzer.core.llm.llm_service import LLMService, LLMServiceError
from src.pytest_analyzer.core.test_generation.ast_analyzer import ASTAnalyzer
from src.pytest_analyzer.core.test_generation.coverage_analyzer import (
    CoverageGapAnalyzer,
)
from src.pytest_analyzer.core.test_generation.generator import TestGenerator
from src.pytest_analyzer.core.test_generation.templates import TestTemplateEngine

# --- Fixtures and helpers ---


@pytest.fixture
def simple_source_file(tmp_path):
    code = """
def add(a, b):
    \"\"\"Add two numbers.\"\"\"
    return a + b

def divide(a, b):
    \"\"\"Divide a by b. Raises ZeroDivisionError.\"\"\"
    if b == 0:
        raise ZeroDivisionError()
    return a / b
"""
    file = tmp_path / "mymodule.py"
    file.write_text(code)
    return file


@pytest.fixture
def simple_test_file(tmp_path):
    code = """
import pytest
from mymodule import add

def test_add_works():
    assert add(1, 2) == 3
"""
    file = tmp_path / "test_mymodule.py"
    file.write_text(code)
    return file


@pytest.fixture
def complex_source_file(tmp_path):
    """More complex source file with classes, methods, and error handling."""
    code = '''
class Calculator:
    """A calculator class with various operations."""

    def __init__(self, precision=2):
        self.precision = precision

    def add(self, a, b):
        """Add two numbers with precision handling."""
        if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
            raise TypeError("Arguments must be numbers")
        return round(a + b, self.precision)

    def divide(self, a, b):
        """Divide a by b. Raises ZeroDivisionError if b is zero."""
        if b == 0:
            raise ZeroDivisionError("Cannot divide by zero")
        return round(a / b, self.precision)

    def factorial(self, n):
        """Calculate factorial. Raises ValueError for negative numbers."""
        if not isinstance(n, int):
            raise TypeError("Argument must be integer")
        if n < 0:
            raise ValueError("Cannot calculate factorial of negative number")
        if n == 0 or n == 1:
            return 1
        result = 1
        for i in range(2, n + 1):
            result *= i
        return result

def process_list(items):
    """Process a list of items. Returns None if empty list."""
    if not items:
        return None
    return [item.upper() if isinstance(item, str) else str(item) for item in items]
'''
    file = tmp_path / "complex_module.py"
    file.write_text(code)
    return file


@pytest.fixture
def mock_llm_service():
    """Mock LLM service for testing."""
    mock = Mock(spec=LLMService)
    mock.generate.return_value = '[{"description": "Test with empty list", "args": {"items": []}, "type": "edge_case"}]'
    return mock


# --- Tests ---


def test_ast_analysis_extracts_functions_and_args(simple_source_file):
    analyzer = ASTAnalyzer()
    struct = analyzer.analyze(simple_source_file)
    func_names = {f.name for f in struct["functions"]}
    assert "add" in func_names
    assert "divide" in func_names
    add_func = next(f for f in struct["functions"] if f.name == "add")
    assert add_func.args == ["a", "b"]


def test_template_engine_generates_test_code(simple_source_file):
    analyzer = ASTAnalyzer()
    struct = analyzer.analyze(simple_source_file)
    scenarios = [
        {
            "function": "add",
            "class": None,
            "args": {"a": 1, "b": 2},
            "description": "simple add",
            "type": "normal",
        }
    ]
    engine = TestTemplateEngine()
    code = engine.render_tests(struct, scenarios)
    assert "def test_" in code
    assert "add" in code


def test_testgenerator_generates_tests_and_writes_file(simple_source_file, tmp_path):
    gen = TestGenerator()
    out_file = tmp_path / "test_generated.py"
    gen.generate_tests(simple_source_file, output_path=out_file)
    assert out_file.exists()
    assert "def test_add_" in out_file.read_text()


def test_coverage_analyzer_detects_missing_functions(
    simple_source_file, simple_test_file
):
    analyzer = CoverageGapAnalyzer()
    gap = analyzer.analyze_gap(simple_test_file, simple_source_file)
    assert "divide" in gap.missing_functions
    assert "add" not in gap.missing_functions


def test_testgenerator_suggests_improvements(
    monkeypatch, simple_source_file, simple_test_file
):
    gen = TestGenerator()

    # Patch analyze_coverage to simulate missing cases
    class DummyGap:
        missing_functions = []
        missing_cases = ["b is 0"]

    monkeypatch.setattr(gen, "analyze_coverage", lambda t, s: DummyGap())

    # Patch llm_service.generate to return a suggestion string
    gen.llm_service.generate = lambda prompt: "Consider property-based tests."

    suggestions = gen.suggest_improvements(simple_test_file, simple_source_file)
    assert any("edge case" in s or "property-based" in s for s in suggestions)


# --- Enhanced Integration Tests ---


def test_testgenerator_with_complex_class_analysis(complex_source_file):
    """Test that complex classes with methods are properly analyzed."""
    gen = TestGenerator()
    structure = gen.analyze_code(complex_source_file)

    # Check class detection
    assert len(structure["classes"]) == 1
    calculator_class = structure["classes"][0]
    assert calculator_class.name == "Calculator"

    # Check method detection
    method_names = {m.name for m in calculator_class.methods}
    assert "add" in method_names
    assert "divide" in method_names
    assert "factorial" in method_names

    # Check function detection
    func_names = {f.name for f in structure["functions"]}
    assert "process_list" in func_names


def test_testgenerator_identifies_comprehensive_scenarios(complex_source_file):
    """Test that edge cases and scenarios are properly identified."""
    gen = TestGenerator()
    structure = gen.analyze_code(complex_source_file)
    scenarios = gen.identify_test_scenarios(structure)

    # Should have scenarios for all functions and methods
    scenario_functions = {s["function"] for s in scenarios}
    assert "add" in scenario_functions
    assert "divide" in scenario_functions
    assert "factorial" in scenario_functions
    assert "process_list" in scenario_functions

    # Should have different types of scenarios
    scenario_types = {s["type"] for s in scenarios}
    assert "null" in scenario_types
    assert "boundary" in scenario_types
    assert "exception" in scenario_types


def test_testgenerator_with_llm_integration(complex_source_file, mock_llm_service):
    """Test TestGenerator with LLM service integration."""
    gen = TestGenerator(llm_service=mock_llm_service)

    # Generate tests with LLM enabled
    test_code = gen.generate_tests(complex_source_file, use_llm=True)

    # Verify LLM was called
    mock_llm_service.generate.assert_called_once()

    # Verify test code contains expected content
    assert "def test_" in test_code
    assert "Calculator" in test_code or "process_list" in test_code


def test_testgenerator_handles_llm_failures_gracefully(complex_source_file):
    """Test that LLM failures don't break test generation."""
    mock_llm = Mock(spec=LLMService)
    mock_llm.generate.side_effect = LLMServiceError("LLM service unavailable")

    gen = TestGenerator(llm_service=mock_llm)

    # Should still generate tests even with LLM failure
    test_code = gen.generate_tests(complex_source_file, use_llm=True)
    assert "def test_" in test_code
    assert len(test_code) > 100  # Should have substantial content


def test_testgenerator_property_based_tests(simple_source_file):
    """Test property-based test generation."""
    gen = TestGenerator()
    test_code = gen.generate_tests(simple_source_file, property_based=True)

    # Should contain hypothesis imports and strategies
    assert (
        "from hypothesis" in test_code
        or "@given" in test_code
        or "property" in test_code.lower()
    )


def test_testgenerator_error_handling():
    """Test error handling for invalid inputs."""
    gen = TestGenerator()

    # Test with non-existent file - should return error in result
    result = gen.analyze_code("/non/existent/file.py")
    assert "error" in result

    # Test with invalid Python code - should return error in result
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("invalid python syntax {{{")
        f.flush()

        try:
            result = gen.analyze_code(f.name)
            assert "error" in result
        finally:
            os.unlink(f.name)


def test_coverage_analysis_integration(complex_source_file, tmp_path):
    """Test coverage analysis with realistic test file."""
    # Create a partial test file
    test_code = """
import pytest
from complex_module import Calculator

def test_calculator_add():
    calc = Calculator()
    assert calc.add(1, 2) == 3

def test_calculator_init():
    calc = Calculator(precision=3)
    assert calc.precision == 3
"""

    test_file = tmp_path / "test_complex_module.py"
    test_file.write_text(test_code)

    gen = TestGenerator()
    gap = gen.analyze_coverage(test_file, complex_source_file)

    # Should identify missing functions/methods
    assert "divide" in gap.missing_functions or "factorial" in gap.missing_functions
    assert "process_list" in gap.missing_functions


def test_improvement_suggestions_integration(
    complex_source_file, tmp_path, mock_llm_service
):
    """Test improvement suggestions with realistic scenario."""
    # Create a basic test file
    test_code = """
import pytest
from complex_module import Calculator

def test_basic_add():
    calc = Calculator()
    assert calc.add(1, 1) == 2
"""

    test_file = tmp_path / "test_basic.py"
    test_file.write_text(test_code)

    gen = TestGenerator(llm_service=mock_llm_service)
    suggestions = gen.suggest_improvements(test_file, complex_source_file)

    # Should have coverage-based suggestions
    assert len(suggestions) > 0
    suggestion_text = " ".join(suggestions).lower()
    assert (
        "missing" in suggestion_text
        or "coverage" in suggestion_text
        or "test" in suggestion_text
    )


def test_full_workflow_integration(complex_source_file, tmp_path):
    """Test complete workflow from analysis to test generation."""
    gen = TestGenerator()

    # Step 1: Analyze code
    structure = gen.analyze_code(complex_source_file)
    assert len(structure["classes"]) > 0 or len(structure["functions"]) > 0

    # Step 2: Generate scenarios
    scenarios = gen.identify_test_scenarios(structure)
    assert len(scenarios) > 0

    # Step 3: Generate tests
    output_file = tmp_path / "test_generated_complex.py"
    test_code = gen.generate_tests(complex_source_file, output_path=output_file)

    # Verify output
    assert output_file.exists()
    assert len(test_code) > 200  # Should be substantial
    assert "def test_" in test_code
    assert "import" in test_code

    # Step 4: Analyze coverage (simulated)
    basic_test_file = tmp_path / "test_basic_coverage.py"
    basic_test_file.write_text("def test_dummy(): pass")

    gap = gen.analyze_coverage(basic_test_file, complex_source_file)
    assert len(gap.missing_functions) > 0

    # Step 5: Get improvement suggestions
    suggestions = gen.suggest_improvements(basic_test_file, complex_source_file)
    assert len(suggestions) > 0
