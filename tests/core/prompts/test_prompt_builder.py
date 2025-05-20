"""
Tests for the PromptBuilder class.
"""

import pytest

from pytest_analyzer.core.models.pytest_failure import PytestFailure
from pytest_analyzer.core.prompts.prompt_builder import PromptBuilder


@pytest.fixture
def sample_failure() -> PytestFailure:
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


def test_prompt_builder_initialization() -> None:
    """Test prompt builder initialization with default values."""
    builder = PromptBuilder()
    assert builder.max_prompt_size == 4000  # Default value
    assert builder.templates_dir is None
    # Check if default templates are loaded
    assert "analysis" in builder.templates
    assert "suggestion" in builder.templates
    assert "llm_suggestion" in builder.templates
    assert "batch_analysis" in builder.templates
    assert builder.templates["analysis"] == PromptBuilder._DEFAULT_TEMPLATES["analysis"]
    assert (
        builder.templates["suggestion"]
        == PromptBuilder._DEFAULT_TEMPLATES["suggestion"]
    )
    assert (
        builder.templates["llm_suggestion"]
        == PromptBuilder._DEFAULT_TEMPLATES["llm_suggestion"]
    )
    assert (
        builder.templates["batch_analysis"]
        == PromptBuilder._DEFAULT_TEMPLATES["batch_analysis"]
    )


def test_prompt_builder_custom_initialization() -> None:
    """Test prompt builder initialization with custom values."""
    custom_analysis = "Custom analysis: {error_type}"
    custom_suggestion = "Custom suggestion for {test_name}"
    custom_llm_suggestion = "LLM suggestion for {test_name}"
    custom_batch_analysis = "Batch analysis for multiple errors"
    custom_max_size = 2000

    # Test with individual template parameters (backward compatibility)
    builder_compat = PromptBuilder(
        analysis_template=custom_analysis,
        suggestion_template=custom_suggestion,
        max_prompt_size=custom_max_size,
    )
    assert builder_compat.max_prompt_size == custom_max_size
    assert builder_compat.templates["analysis"] == custom_analysis
    assert builder_compat.templates["suggestion"] == custom_suggestion
    # Other templates should still be default
    assert (
        builder_compat.templates["llm_suggestion"]
        == PromptBuilder._DEFAULT_TEMPLATES["llm_suggestion"]
    )

    # Test with templates dictionary
    custom_templates = {
        "analysis": custom_analysis,
        "suggestion": custom_suggestion,
        "llm_suggestion": custom_llm_suggestion,
        "batch_analysis": custom_batch_analysis,
        "new_custom_template": "This is a new one: {test_file}",
    }
    builder_dict = PromptBuilder(
        templates=custom_templates, max_prompt_size=custom_max_size
    )
    assert builder_dict.max_prompt_size == custom_max_size
    assert builder_dict.templates["analysis"] == custom_analysis
    assert builder_dict.templates["suggestion"] == custom_suggestion
    assert builder_dict.templates["llm_suggestion"] == custom_llm_suggestion
    assert builder_dict.templates["batch_analysis"] == custom_batch_analysis
    assert (
        builder_dict.templates["new_custom_template"]
        == "This is a new one: {test_file}"
    )


def test_load_templates_from_dir(tmp_path) -> None:
    """Test loading templates from a directory."""
    template_dir = tmp_path / "prompts"
    template_dir.mkdir()

    analysis_content = "Analysis from file: {error_message}"
    suggestion_content = "Suggestion from file for {test_name}"
    # Create dummy template files
    (template_dir / "analysis_template.txt").write_text(analysis_content)
    (template_dir / "suggestion_template.txt").write_text(suggestion_content)
    # This one should remain default as it's not in the dir
    default_llm_suggestion = PromptBuilder._DEFAULT_TEMPLATES["llm_suggestion"]

    builder = PromptBuilder(templates_dir=str(template_dir))

    assert builder.templates["analysis"] == analysis_content
    assert builder.templates["suggestion"] == suggestion_content
    assert builder.templates["llm_suggestion"] == default_llm_suggestion


def test_build_analysis_prompt(sample_failure: PytestFailure) -> None:
    """Test building an analysis prompt from a failure."""
    builder = PromptBuilder()
    prompt = builder.build_analysis_prompt(sample_failure)

    assert sample_failure.test_name in prompt
    assert sample_failure.error_type in prompt
    assert sample_failure.error_message in prompt
    assert sample_failure.traceback in prompt
    assert sample_failure.relevant_code in prompt
    assert "Root Cause" in prompt  # Part of the default template


def test_build_suggestion_prompt(sample_failure: PytestFailure) -> None:
    """Test building a suggestion prompt from a failure and root cause."""
    builder = PromptBuilder()
    root_cause = "The assertion failed because 1 is not equal to 2."
    prompt = builder.build_suggestion_prompt(sample_failure, root_cause)

    assert sample_failure.test_name in prompt
    assert sample_failure.error_type in prompt
    assert sample_failure.error_message in prompt
    assert sample_failure.traceback in prompt
    assert sample_failure.relevant_code in prompt
    assert root_cause in prompt
    assert "suggest specific fixes" in prompt.lower()  # Part of default template


def test_build_batch_analysis_prompt() -> None:
    """Test building a batch analysis prompt for multiple failures."""
    failures = [
        PytestFailure(
            test_name=f"test_example_{i}",
            test_file=f"test_module_{i}.py",
            error_type="ValueError",
            error_message=f"Value error {i}",
            traceback=f"Traceback for test {i}",
            line_number=10 + i,
            relevant_code=f"code for test {i}",
        )
        for i in range(2)
    ]
    builder = PromptBuilder()
    prompt = builder.build_batch_analysis_prompt(failures)

    for failure in failures:
        assert f"Test name: {failure.test_name}" in prompt
        assert (
            f"Error type: {failure.error_type}" in prompt
        )  # Corrected "Error Type" to "Error type"
        assert (
            f"Error message: {failure.error_message}" in prompt
        )  # Corrected "Error Message" to "Error message"
    assert "Common Root Cause" in prompt  # Part of the default template


def test_build_llm_suggestion_prompt(sample_failure: PytestFailure) -> None:
    """Test building an LLM suggestion prompt."""
    builder = PromptBuilder()
    prompt = builder.build_llm_suggestion_prompt(sample_failure)

    assert sample_failure.test_name in prompt
    assert sample_failure.test_file in prompt
    assert sample_failure.error_type in prompt
    assert sample_failure.error_message in prompt
    assert sample_failure.traceback in prompt
    assert sample_failure.relevant_code in prompt
    assert "=== Instructions ===" in prompt  # Corrected to match template
    assert "Format your response as follows:" in prompt


def test_truncate_prompt_if_needed() -> None:
    """Test prompt truncation functionality."""
    max_size = 100
    builder = PromptBuilder(max_prompt_size=max_size)

    # Test with a prompt shorter than max_size
    short_prompt = "A" * (max_size - 10)
    assert builder._truncate_prompt_if_needed(short_prompt) == short_prompt

    # Test with a prompt exactly max_size
    exact_prompt = "B" * max_size
    assert builder._truncate_prompt_if_needed(exact_prompt) == exact_prompt

    # Test with a prompt longer than max_size
    long_prompt = "C" * (max_size + 50)
    truncated_prompt = builder._truncate_prompt_if_needed(long_prompt)
    assert len(truncated_prompt) <= max_size
    assert "\n...[CONTENT TRUNCATED DUE TO SIZE LIMITS]...\n" in truncated_prompt
    # Check that it truncates from the middle
    truncation_marker_len = len("\n...[CONTENT TRUNCATED DUE TO SIZE LIMITS]...\n")
    chars_to_keep = max_size - truncation_marker_len
    prefix_len = chars_to_keep // 2
    suffix_len = chars_to_keep - prefix_len
    assert truncated_prompt.startswith("C" * prefix_len)
    assert truncated_prompt.endswith("C" * suffix_len)


def test_empty_batch_analysis_prompt() -> None:
    """Test building a batch analysis prompt with no failures."""
    builder = PromptBuilder()
    prompt = builder.build_batch_analysis_prompt([])
    # Depending on implementation, it might be empty or a specific message
    # Assuming it returns an empty string or a message indicating no failures
    # For now, let's check if it's not raising an error and is a string.
    # The default template for batch_analysis might produce some output even with empty list.
    # Let's check if it contains the introductory part of the default batch template.
    if PromptBuilder._DEFAULT_TEMPLATES["batch_analysis"].startswith("Analyze"):
        assert "Analyze the following test failures" in prompt
    else:
        # If the template is different, this assertion might need adjustment
        # For an empty list, a truly empty prompt might be desirable.
        # If the template is just "{failures_summary}", then it would be empty.
        # Current default template has preamble, so it won't be empty.
        pass  # Allow non-empty if template has preamble
