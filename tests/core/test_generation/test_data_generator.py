from src.pytest_analyzer.core.test_generation.ast_analyzer import FunctionInfo
from src.pytest_analyzer.core.test_generation.data_generator import TestDataGenerator


def sample_function_info():
    return FunctionInfo(
        name="add",
        args=["a", "b"],
        defaults=[0, 0],
        varargs=None,
        kwargs=None,
        return_annotation="int",
        docstring="Add two numbers.",
        decorators=[],
        complexity=1,
        line_number=1,
        is_async=False,
    )


def test_generate_for_function_basic():
    gen = TestDataGenerator()
    func_info = sample_function_info()
    samples = gen.generate_for_function(func_info, num_samples=5)
    assert len(samples) == 5
    for s in samples:
        assert "a" in s and "b" in s


def test_constraint_satisfaction():
    gen = TestDataGenerator()
    func_info = sample_function_info()
    constraint = {"a": lambda x: isinstance(x, int) and x > 10}
    samples = gen.generate_for_function(
        func_info, constraints=constraint, num_samples=20
    )
    for s in samples:
        assert s["a"] > 10 or not isinstance(s["a"], int)


def test_mock_external_data():
    gen = TestDataGenerator()
    llm_data = gen.generate_mock_external_data("llm")
    assert "response" in llm_data
    ci_data = gen.generate_mock_external_data("ci")
    assert "status" in ci_data


def test_hypothesis_strategy_for_function():
    gen = TestDataGenerator()
    func_info = sample_function_info()
    strat = gen.hypothesis_strategy_for_function(func_info)
    # Use hypothesis to safely generate examples with controlled settings
    import hypothesis

    @hypothesis.given(strat)
    @hypothesis.settings(max_examples=1, deadline=1000)
    def check_example(example):
        assert "a" in example and "b" in example
        assert isinstance(example, dict)

    # Run the test just once to verify the strategy works
    check_example()


def test_llm_edge_case_generation(monkeypatch):
    gen = TestDataGenerator()
    func_info = sample_function_info()
    # Patch LLM service to return a valid JSON list
    monkeypatch.setattr(
        gen.llm_service,
        "generate",
        lambda prompt: '[{"a": 0, "b": 0}, {"a": 100, "b": -1}]',
    )
    cases = gen.generate_llm_edge_cases(func_info, num_cases=2)
    assert isinstance(cases, list)
    assert len(cases) == 2
    assert all("a" in c and "b" in c for c in cases)


def test_data_distribution_and_benchmark():
    gen = TestDataGenerator()
    func_info = sample_function_info()
    samples = gen.generate_for_function(func_info, num_samples=20)
    metrics = gen.validate_data_distribution(samples)
    assert "a" in metrics and "b" in metrics
    speed = gen.benchmark_generation(func_info, num_samples=10)
    assert speed > 0


def test_pytest_parametrize_cases():
    gen = TestDataGenerator()
    func_info = sample_function_info()
    cases = gen.pytest_parametrize_cases(func_info, num_samples=3)
    assert isinstance(cases, list)
    assert all(isinstance(t, tuple) for t in cases)
    assert all(len(t) == 2 for t in cases)


def test_generate_for_module(tmp_path):
    # Create a simple python file
    code = '''
def add(a, b):
    """Add two numbers."""
    return a + b

def _private(x):
    return x
'''
    file_path = tmp_path / "mod.py"
    file_path.write_text(code)
    gen = TestDataGenerator()
    results = gen.generate_for_module(str(file_path), num_samples=2)
    assert "add" in results
    assert isinstance(results["add"], list)
    assert len(results["add"]) == 2
