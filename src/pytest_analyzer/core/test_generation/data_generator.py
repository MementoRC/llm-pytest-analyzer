"""
Intelligent Test Data Generation System

This module provides the TestDataGenerator class, which integrates statistical modeling,
constraint-based validation, LLM-driven edge case generation, and property-based testing
to produce high-quality, production-like test data for automated test generation.

Features:
- Statistical models for realistic data distributions
- Constraint-based data generation and validation
- Mock data for external services (LLM, CI, package managers)
- Data anonymization for privacy
- Integration with AST analysis, template engine, and DI system
- Hypothesis strategies for property-based testing
- LLM-powered edge case and scenario generation
- Data quality metrics and performance benchmarking

Follows established codebase patterns and integrates with the DI system.
"""

import logging
import random
import string
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

import hypothesis.strategies as st

from ..infrastructure.llm.mock_service import MockLLMService
from .ast_analyzer import ASTAnalyzer, FunctionInfo
from .templates import TestTemplateEngine

logger = logging.getLogger(__name__)


class DataGenerationError(Exception):
    """Custom exception for data generation errors."""


class TestDataGenerator:
    """
    Intelligent Test Data Generator for automated and property-based testing.

    Integrates statistical modeling, constraint validation, LLM-driven edge case
    generation, and anonymization for high-quality, production-like test data.
    """

    def __init__(
        self,
        ast_analyzer: Optional[ASTAnalyzer] = None,
        template_engine: Optional[TestTemplateEngine] = None,
        llm_service: Optional[Any] = None,
        anonymize: bool = True,
        use_mock_services: bool = True,
    ):
        self.ast_analyzer = ast_analyzer or ASTAnalyzer()
        self.template_engine = template_engine or TestTemplateEngine()
        self.llm_service = llm_service or MockLLMService()
        self.anonymize = anonymize
        self.use_mock_services = use_mock_services

    # --- Statistical and Constraint-based Data Generation ---

    def generate_for_function(
        self,
        function_info: FunctionInfo,
        constraints: Optional[Dict[str, Callable[[Any], bool]]] = None,
        num_samples: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Generate test data dictionaries for a function, satisfying constraints.

        Args:
            function_info: FunctionInfo object from AST analysis.
            constraints: Dict of arg name -> validation function.
            num_samples: Number of data samples to generate.

        Returns:
            List of argument dictionaries for test cases.
        """
        logger.info(f"Generating data for function: {function_info.name}")
        samples = []
        for _ in range(num_samples):
            args = {}
            for arg in function_info.args:
                if arg == "self":
                    continue
                value = self._sample_value_for_arg(arg, function_info)
                if self.anonymize:
                    value = self._anonymize_value(arg, value)
                args[arg] = value
            if constraints:
                if not all(
                    constraints.get(arg, lambda v: True)(args[arg]) for arg in args
                ):
                    continue  # Skip if constraints not satisfied
            samples.append(args)
        logger.debug(f"Generated {len(samples)} samples for {function_info.name}")
        return samples

    def _sample_value_for_arg(self, arg: str, function_info: FunctionInfo) -> Any:
        """
        Sample a value for a function argument using statistical heuristics.
        """
        arg_lower = arg.lower()
        if "id" in arg_lower or "count" in arg_lower or "number" in arg_lower:
            return random.randint(0, 100)
        elif "name" in arg_lower or "text" in arg_lower or "message" in arg_lower:
            return self._random_string(8)
        elif "flag" in arg_lower or "enabled" in arg_lower or "active" in arg_lower:
            return random.choice([True, False])
        elif "list" in arg_lower or "items" in arg_lower:
            return [random.randint(0, 10) for _ in range(random.randint(0, 5))]
        elif "dict" in arg_lower or "config" in arg_lower:
            return {self._random_string(4): random.randint(0, 10)}
        elif "path" in arg_lower or "file" in arg_lower:
            return f"/tmp/{self._random_string(6)}.txt"
        else:
            return random.choice([None, 0, 1, self._random_string(5)])

    def _random_string(self, length: int) -> str:
        return "".join(random.choices(string.ascii_letters, k=length))

    def _anonymize_value(self, arg: str, value: Any) -> Any:
        """
        Anonymize sensitive data for production-like test data.
        """
        if isinstance(value, str) and ("name" in arg or "user" in arg):
            return f"anon_{self._random_string(6)}"
        return value

    # --- Mock Data Generation for External Services ---

    def generate_mock_external_data(self, service: str) -> Any:
        """
        Generate mock data for external services (LLM, CI, package managers).
        """
        logger.info(f"Generating mock data for external service: {service}")
        if service == "llm":
            return {"response": "Mock LLM output", "confidence": 0.5}
        elif service == "ci":
            return {"status": "success", "build_id": self._random_string(8)}
        elif service == "package_manager":
            return {"package": "example", "version": "1.0.0"}
        else:
            return {"mock": True}

    # --- Property-Based Testing Integration (Hypothesis) ---

    def hypothesis_strategy_for_pytest_failure(self) -> st.SearchStrategy:
        """
        Return a Hypothesis strategy for generating PytestFailure instances.
        Note: Returns a simple dictionary strategy if domain entities are not available.
        """
        try:
            import uuid
            from pathlib import Path

            from ..domain.entities.pytest_failure import (
                PytestFailure as PytestFailureEntity,
            )
            from ..domain.value_objects.failure_type import FailureType
            from ..domain.value_objects.test_location import TestLocation

            def make_location():
                return TestLocation(
                    file_path=Path(f"/tmp/{self._random_string(6)}.py"),
                    line_number=random.randint(1, 100),
                    function_name=self._random_string(8),
                    class_name=random.choice([self._random_string(6), None]),
                )

            return st.builds(
                PytestFailureEntity,
                id=st.just(str(uuid.uuid4())),
                test_name=st.text(min_size=1, max_size=30),
                location=st.builds(make_location),
                failure_message=st.text(min_size=1, max_size=100),
                failure_type=st.sampled_from(list(FailureType)),
                traceback=st.lists(st.text(min_size=1, max_size=80), max_size=5),
                source_code=st.one_of(st.none(), st.text(min_size=1, max_size=200)),
                raw_output_section=st.one_of(
                    st.none(), st.text(min_size=1, max_size=200)
                ),
                related_project_files=st.lists(
                    st.text(min_size=1, max_size=50), max_size=3
                ),
                group_fingerprint=st.one_of(
                    st.none(), st.text(min_size=1, max_size=32)
                ),
            )
        except ImportError:
            # Fallback to a simple dictionary strategy if domain entities are not available
            return st.dictionaries(
                st.text(min_size=1, max_size=20),
                st.one_of(st.text(), st.integers(), st.booleans()),
                max_size=5,
            )

    def hypothesis_strategy_for_function(
        self, function_info: FunctionInfo
    ) -> st.SearchStrategy:
        """
        Return a Hypothesis strategy for generating argument dictionaries for a function.
        """
        arg_strategies = {}
        for arg in function_info.args:
            if arg == "self":
                continue
            arg_strategies[arg] = self._hypothesis_strategy_for_arg(arg)
        return st.fixed_dictionaries(arg_strategies)

    def _hypothesis_strategy_for_arg(self, arg: str) -> st.SearchStrategy:
        arg_lower = arg.lower()
        if "id" in arg_lower or "count" in arg_lower or "number" in arg_lower:
            return st.integers(min_value=0, max_value=100)
        elif "name" in arg_lower or "text" in arg_lower or "message" in arg_lower:
            return st.text(min_size=1, max_size=20)
        elif "flag" in arg_lower or "enabled" in arg_lower or "active" in arg_lower:
            return st.booleans()
        elif "list" in arg_lower or "items" in arg_lower:
            return st.lists(st.integers(), max_size=5)
        elif "dict" in arg_lower or "config" in arg_lower:
            return st.dictionaries(
                st.text(min_size=1, max_size=5), st.integers(), max_size=3
            )
        elif "path" in arg_lower or "file" in arg_lower:
            return st.text(min_size=5, max_size=30)
        else:
            return st.one_of(st.none(), st.integers(), st.text(min_size=1, max_size=10))

    # --- LLM-Driven Edge Case Generation ---

    def generate_llm_edge_cases(
        self,
        function_info: FunctionInfo,
        context: Optional[str] = None,
        num_cases: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Use LLM to generate realistic and challenging edge case test data.

        Args:
            function_info: FunctionInfo object.
            context: Optional code context for LLM prompt.
            num_cases: Number of edge cases to generate.

        Returns:
            List of argument dictionaries for edge cases.
        """
        prompt = self._build_llm_prompt(function_info, context)
        logger.info(f"Requesting LLM for edge cases: {function_info.name}")
        try:
            llm_response = self.llm_service.generate(prompt)
            edge_cases = self._parse_llm_edge_cases(
                llm_response, function_info, num_cases
            )
            logger.debug(f"LLM edge cases: {edge_cases}")
            return edge_cases
        except Exception as e:
            logger.warning(f"LLM edge case generation failed: {e}")
            return []

    def _build_llm_prompt(
        self, function_info: FunctionInfo, context: Optional[str]
    ) -> str:
        prompt = (
            f"Given the following function signature and context, generate {function_info.name} edge case test inputs "
            f"as JSON argument dictionaries. "
            f"Function: {function_info.name}({', '.join(function_info.args)})\n"
        )
        if context:
            prompt += f"Context:\n{context}\n"
        prompt += "Return a list of JSON objects, each representing a test case."
        return prompt

    def _parse_llm_edge_cases(
        self, llm_response: str, function_info: FunctionInfo, num_cases: int
    ) -> List[Dict[str, Any]]:
        """
        Parse LLM response into argument dictionaries.
        """
        import json

        try:
            # Try to extract JSON from the response
            data = json.loads(llm_response)
            if isinstance(data, list):
                return data[:num_cases]
            elif isinstance(data, dict):
                return [data]
            else:
                return []
        except Exception:
            # Fallback: return empty or mock edge cases
            logger.warning("Failed to parse LLM edge case JSON, using mock edge cases.")
            return [self._mock_edge_case(function_info) for _ in range(num_cases)]

    def _mock_edge_case(self, function_info: FunctionInfo) -> Dict[str, Any]:
        """
        Generate a mock edge case for a function.
        """
        return {
            arg: self._sample_value_for_arg(arg, function_info)
            for arg in function_info.args
            if arg != "self"
        }

    # --- Data Quality and Performance Metrics ---

    def validate_data_distribution(
        self, samples: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Validate the distribution of generated data for quality metrics.
        """
        metrics = {}
        if not samples:
            return metrics
        for key in samples[0]:
            values = [s[key] for s in samples if key in s]
            metrics[key] = {
                "unique": len(set(values)),
                "nulls": sum(1 for v in values if v is None),
                "type_counts": {type(v).__name__: values.count(v) for v in set(values)},
            }
        return metrics

    def verify_constraints(
        self,
        samples: List[Dict[str, Any]],
        constraints: Dict[str, Callable[[Any], bool]],
    ) -> float:
        """
        Check what fraction of samples satisfy all constraints.
        """
        if not samples or not constraints:
            return 1.0
        valid = 0
        for s in samples:
            if all(constraints.get(k, lambda v: True)(v) for k, v in s.items()):
                valid += 1
        return valid / len(samples)

    def benchmark_generation(
        self, function_info: FunctionInfo, num_samples: int = 100
    ) -> float:
        """
        Benchmark the speed of data generation for a function.
        Returns: samples per second.
        """
        start = time.time()
        self.generate_for_function(function_info, num_samples=num_samples)
        end = time.time()
        duration = end - start
        if duration == 0:
            return float("inf")
        return num_samples / duration

    # --- Integration with DI and Factory Patterns ---

    @classmethod
    def from_container(cls, container: Any) -> "TestDataGenerator":
        """
        Factory method to create TestDataGenerator from DI container.
        """
        ast_analyzer = container.resolve(ASTAnalyzer)
        template_engine = container.resolve(TestTemplateEngine)
        try:
            llm_service = container.resolve("LLMServiceProtocol")
        except Exception:
            llm_service = MockLLMService()
        return cls(
            ast_analyzer=ast_analyzer,
            template_engine=template_engine,
            llm_service=llm_service,
        )

    # --- Pytest Fixture Integration ---

    def pytest_parametrize_cases(
        self, function_info: FunctionInfo, num_samples: int = 5
    ) -> List[Any]:
        """
        Generate test cases for use with pytest.mark.parametrize.
        """
        samples = self.generate_for_function(function_info, num_samples=num_samples)
        param_names = [arg for arg in function_info.args if arg != "self"]
        return [tuple(sample[arg] for arg in param_names) for sample in samples]

    # --- Utility: Generate for all testable functions in a module ---

    def generate_for_module(
        self, source_path: Union[str, Path], num_samples: int = 5
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Generate test data for all testable functions in a module.
        """
        analysis = self.ast_analyzer.analyze(source_path)
        results = {}
        for func in analysis.get("testable_functions", []):
            results[func.name] = self.generate_for_function(
                func, num_samples=num_samples
            )
        return results
