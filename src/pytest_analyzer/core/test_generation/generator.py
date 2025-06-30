"""
Automated Test Generation System

This module provides the TestGenerator class for automated test generation,
including AST-based code analysis, code path analysis, template-based and
LLM-powered test generation, coverage analysis, and test improvement suggestions.

Architecture follows the project's dependency injection and abstraction patterns.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ...utils.settings import load_settings
from ..llm.llm_service import LLMService, LLMServiceError
from .ast_analyzer import ASTAnalyzer
from .coverage_analyzer import CoverageGap, CoverageGapAnalyzer
from .templates import TestTemplateEngine

logger = logging.getLogger(__name__)


class TestGenerationError(Exception):
    """Raised when automated test generation fails."""


class TestGenerator:
    """
    Automated Test Generator for Python codebases.

    Features:
    - AST-based code structure analysis (functions, classes, dependencies)
    - Code path and edge case analysis
    - Template-based test generation for common patterns
    - LLM integration for intelligent test scenario generation
    - Coverage gap analysis and improvement suggestions
    - Property-based test (hypothesis) support
    """

    def __init__(
        self,
        llm_service: Optional[LLMService] = None,
        template_engine: Optional[TestTemplateEngine] = None,
        ast_analyzer: Optional[ASTAnalyzer] = None,
        coverage_analyzer: Optional[CoverageGapAnalyzer] = None,
        settings: Optional[Any] = None,
    ):
        """
        Initialize the TestGenerator.

        Args:
            llm_service: LLMService for AI-powered test generation.
            template_engine: Template engine for test code generation.
            ast_analyzer: ASTAnalyzer for code structure analysis.
            coverage_analyzer: CoverageAnalyzer for coverage gap detection.
            settings: Optional settings object.
        """
        self.settings = settings or load_settings()
        self.llm_service = llm_service or LLMService(settings=self.settings)
        self.template_engine = template_engine or TestTemplateEngine()
        self.ast_analyzer = ast_analyzer or ASTAnalyzer()
        self.coverage_analyzer = coverage_analyzer or CoverageGapAnalyzer()

    def analyze_code(self, source_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Analyze Python source code to extract functions, classes, and dependencies.

        Args:
            source_path: Path to the Python source file.

        Returns:
            Dictionary with code structure information.
        """
        try:
            return self.ast_analyzer.analyze(source_path)
        except Exception as e:
            logger.error(f"AST analysis failed: {e}")
            raise TestGenerationError(f"AST analysis failed: {e}")

    def identify_test_scenarios(
        self, code_structure: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Identify test scenarios and code paths for the given code structure.

        Args:
            code_structure: Output from analyze_code.

        Returns:
            List of test scenario dicts.
        """
        scenarios = []
        # Analyze functions
        for func in code_structure.get("functions", []):
            scenarios.extend(self._analyze_function_paths(func))
        # Analyze classes and their methods
        for cls in code_structure.get("classes", []):
            for method in cls.methods:
                scenarios.extend(
                    self._analyze_function_paths(method, class_name=cls.name)
                )
        return scenarios

    def _analyze_function_paths(
        self, func_info, class_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Analyze a function/method for testable paths and edge cases.

        Args:
            func_info: Function or method info object.
            class_name: Optional class name if method.

        Returns:
            List of test scenario dicts.
        """
        scenarios = []
        name = func_info.name
        args = func_info.args
        docstring = func_info.docstring or ""
        # Edge cases: nulls, boundaries, exceptions
        edge_cases = self._detect_edge_cases(args, docstring)
        for case in edge_cases:
            scenario = {
                "function": name,
                "class": class_name,
                "args": case["args"],
                "description": case["description"],
                "type": case["type"],
            }
            scenarios.append(scenario)
        return scenarios

    def _detect_edge_cases(
        self, args: List[str], docstring: str
    ) -> List[Dict[str, Any]]:
        """
        Detect edge cases for function arguments.

        Args:
            args: List of argument names.
            docstring: Function docstring.

        Returns:
            List of edge case scenario dicts.
        """
        cases = []
        # Null/None cases
        for arg in args:
            cases.append(
                {
                    "args": {a: None if a == arg else "..." for a in args},
                    "description": f"Argument '{arg}' is None",
                    "type": "null",
                }
            )
        # Boundary cases (simple heuristic)
        for arg in args:
            cases.append(
                {
                    "args": {a: 0 if a == arg else "..." for a in args},
                    "description": f"Argument '{arg}' is 0 (boundary)",
                    "type": "boundary",
                }
            )
            cases.append(
                {
                    "args": {a: -1 if a == arg else "..." for a in args},
                    "description": f"Argument '{arg}' is -1 (negative boundary)",
                    "type": "boundary",
                }
            )
        # Exception cases (if mentioned in docstring)
        if "raise" in (docstring or "").lower():
            cases.append(
                {
                    "args": {a: "exception_trigger" for a in args},
                    "description": "Trigger exception path",
                    "type": "exception",
                }
            )
        return cases

    def generate_tests(
        self,
        source_path: Union[str, Path],
        output_path: Optional[Union[str, Path]] = None,
        use_llm: bool = False,
        property_based: bool = False,
    ) -> str:
        """
        Generate test code for the given source file.

        Args:
            source_path: Path to the Python source file.
            output_path: Optional path to write generated tests.
            use_llm: Whether to use LLM for scenario generation.
            property_based: Whether to generate property-based tests.

        Returns:
            Generated test code as a string.
        """
        code_structure = self.analyze_code(source_path)
        scenarios = self.identify_test_scenarios(code_structure)

        # Optionally use LLM to generate additional scenarios
        if use_llm:
            try:
                llm_scenarios = self._generate_llm_scenarios(
                    source_path, code_structure
                )
                scenarios.extend(llm_scenarios)
            except LLMServiceError as e:
                logger.warning(f"LLM scenario generation failed: {e}")

        # Generate test code using templates
        test_code = self.template_engine.render_tests(
            code_structure, scenarios, property_based=property_based
        )

        # Optionally write to file
        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(test_code)

        return test_code

    def _generate_llm_scenarios(
        self, source_path: Union[str, Path], code_structure: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Use LLM to generate additional test scenarios.

        Args:
            source_path: Path to the source file.
            code_structure: Output from analyze_code.

        Returns:
            List of LLM-generated test scenario dicts.
        """
        prompt = self._build_llm_prompt(source_path, code_structure)
        response = self.llm_service.generate(prompt)
        # Parse LLM response (expecting JSON or structured text)
        try:
            import json

            scenarios = json.loads(response)
            if isinstance(scenarios, list):
                return scenarios
            return []
        except Exception:
            logger.warning(
                "Failed to parse LLM response, falling back to text extraction."
            )
            # Fallback: extract scenarios from text lines
            return [
                {"description": line, "args": {}, "type": "llm"}
                for line in response.splitlines()
                if line.strip()
            ]

    def _build_llm_prompt(
        self, source_path: Union[str, Path], code_structure: Dict[str, Any]
    ) -> str:
        """
        Build a prompt for the LLM to generate test scenarios.

        Args:
            source_path: Path to the source file.
            code_structure: Output from analyze_code.

        Returns:
            Prompt string.
        """
        return (
            "You are an expert Python test engineer. "
            "Given the following code structure, generate a list of test scenarios "
            "covering edge cases, error conditions, and typical usage. "
            "Respond in JSON list format, each item with 'description', 'args', and 'type'.\n\n"
            f"File: {source_path}\n"
            f"Code Structure: {code_structure}\n"
        )

    def analyze_coverage(
        self, test_file: Union[str, Path], source_file: Union[str, Path]
    ) -> CoverageGap:
        """
        Analyze test coverage and identify gaps.

        Args:
            test_file: Path to the test file.
            source_file: Path to the source file.

        Returns:
            CoverageGap object with missing test info.
        """
        try:
            return self.coverage_analyzer.analyze_gap(test_file, source_file)
        except Exception as e:
            logger.error(f"Coverage analysis failed: {e}")
            raise TestGenerationError(f"Coverage analysis failed: {e}")

    def suggest_improvements(
        self, test_file: Union[str, Path], source_file: Union[str, Path]
    ) -> List[str]:
        """
        Suggest improvements for existing tests.

        Args:
            test_file: Path to the test file.
            source_file: Path to the source file.

        Returns:
            List of suggestion strings.
        """
        suggestions = []
        # Analyze coverage gaps
        try:
            gap = self.analyze_coverage(test_file, source_file)
            if gap.missing_functions:
                suggestions.append(
                    f"Add tests for missing functions: {', '.join(gap.missing_functions)}"
                )
            if gap.missing_cases:
                suggestions.append(
                    f"Add edge case tests: {', '.join(gap.missing_cases)}"
                )
        except Exception as e:
            logger.warning(f"Coverage gap analysis failed: {e}")

        # Optionally use LLM for further suggestions
        try:
            prompt = (
                "You are a Python testing expert. "
                "Suggest improvements for the following test file to increase coverage and quality. "
                f"Test file: {test_file}\nSource file: {source_file}\n"
            )
            llm_suggestions = self.llm_service.generate(prompt)
            suggestions.append(llm_suggestions)
        except Exception as e:
            logger.warning(f"LLM improvement suggestion failed: {e}")

        return suggestions
