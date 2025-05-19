"""
Tests for the PromptBuilder class.
"""

import pytest

from pytest_analyzer.core.models.pytest_failure import PytestFailure
from pytest_analyzer.core.prompts.prompt_builder import PromptBuilder


@pytest.fixture
def sample_failure():
    """Create a sample PytestFailure for testing."""
    return PytestFailure(
        test_name="test_example",
        test_file="test_module.py",
        error_type="AssertionError",
        error_message="assert 1 == 2",
        traceback="Traceback line 1\nTraceback line 2",
        line_number=42,
        relevant_code="def test_example():\n    assert 1 == 2",
    )


def test_prompt_builder_initialization():
    """Test prompt builder initialization with default values."""
    builder = PromptBuilder()
    assert builder.max_prompt_size == 4000
    assert builder.templates_dir is None
    assert builder.analysis_template == PromptBuilder._DEFAULT_ANALYSIS_TEMPLATE
    assert builder.suggestion_template == PromptBuilder._DEFAULT_SUGGESTION_TEMPLATE


def test_prompt_builder_custom_initialization():
    """Test prompt builder initialization with custom values."""
    custom_analysis = "Custom analysis template"
    custom_suggestion = "Custom suggestion template"
    custom_max_size = 2000

    builder = PromptBuilder(
        analysis_template=custom_analysis,
        suggestion_template=custom_suggestion,
        max_prompt_size=custom_max_size,
    )

    assert builder.max_prompt_size == custom_max_size
    assert builder.analysis_template == custom_analysis
    assert builder.suggestion_template == custom_suggestion


def test_build_analysis_prompt(sample_failure):
    """Test building an analysis prompt from a failure."""
    builder = PromptBuilder()
    prompt = builder.build_analysis_prompt(sample_failure)

    # Check that the prompt contains key information from the failure
    assert sample_failure.test_name in prompt
    assert sample_failure.error_type in prompt
    assert sample_failure.error_message in prompt
    assert sample_failure.traceback in prompt
    assert sample_failure.relevant_code in prompt
    assert "Root Cause" in prompt


def test_build_suggestion_prompt(sample_failure):
    """Test building a suggestion prompt from a failure."""
    builder = PromptBuilder()
    root_cause = "Comparison between incompatible types"
    prompt = builder.build_suggestion_prompt(sample_failure, root_cause)

    # Check that the prompt contains key information
    assert sample_failure.test_name in prompt
    assert sample_failure.error_type in prompt
    assert sample_failure.error_message in prompt
    assert sample_failure.traceback in prompt
    assert sample_failure.relevant_code in prompt
    assert root_cause in prompt
    assert "suggest specific fixes" in prompt.lower()


def test_build_batch_analysis_prompt():
    """Test building a prompt for multiple failures."""
    failures = [
        PytestFailure(
            test_name=f"test_example_{i}",
            test_file=f"test_module_{i}.py",
            error_type="AssertionError",
            error_message=f"Error message {i}",
            traceback=f"Traceback for test {i}",
        )
        for i in range(3)
    ]

    builder = PromptBuilder()
    prompt = builder.build_batch_analysis_prompt(failures)

    # Check that the prompt contains information about all failures
    for i, failure in enumerate(failures):
        assert failure.test_name in prompt
        assert failure.error_type in prompt
        assert failure.error_message in prompt

    assert "Common Root Cause" in prompt


def test_truncate_prompt_if_needed():
    """Test that long prompts get truncated."""
    builder = PromptBuilder(max_prompt_size=100)
    long_prompt = "A" * 200  # Much longer than the max size

    truncated = builder._truncate_prompt_if_needed(long_prompt)

    assert len(truncated) <= 100
    assert "TRUNCATED" in truncated
    assert truncated.startswith("A")
    assert truncated.endswith("A")


def test_load_templates_from_dir(tmp_path):
    """Test loading templates from a directory."""
    # Create temporary template files
    template_dir = tmp_path / "templates"
    template_dir.mkdir()

    analysis_file = template_dir / "analysis_template.txt"
    suggestion_file = template_dir / "suggestion_template.txt"

    analysis_content = "CUSTOM ANALYSIS TEMPLATE"
    suggestion_content = "CUSTOM SUGGESTION TEMPLATE"

    analysis_file.write_text(analysis_content)
    suggestion_file.write_text(suggestion_content)

    # Create prompt builder with template directory
    builder = PromptBuilder(templates_dir=str(template_dir))

    # Check that templates were loaded
    assert builder.analysis_template == analysis_content
    assert builder.suggestion_template == suggestion_content


def test_empty_batch_prompt():
    """Test building a batch prompt with no failures."""
    builder = PromptBuilder()
    prompt = builder.build_batch_analysis_prompt([])
    assert prompt == ""
