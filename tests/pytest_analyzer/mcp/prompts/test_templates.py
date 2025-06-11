"""Tests for MCP prompt templates."""

from unittest.mock import patch

import pytest

from pytest_analyzer.mcp.prompts.templates import (
    CIFailureInvestigationPrompt,
    FlakyTestDiagnosisPrompt,
    MCPPromptTemplate,
    PerformanceTestingPrompt,
    PromptRegistry,
    PytestDebugSessionPrompt,
    TestConfigurationPrompt,
    get_prompt_registry,
    handle_get_prompt,
    handle_list_prompts,
    initialize_default_prompts,
    register_custom_prompt,
)


class TestMCPPromptTemplate:
    """Test the base MCPPromptTemplate class."""

    def test_creation(self):
        """Test creating a prompt template."""
        template = MCPPromptTemplate(
            name="test_prompt",
            title="Test Prompt",
            description="A test prompt",
            content="Hello {name}!",
            suggested_tools=["tool1", "tool2"],
        )

        assert template.name == "test_prompt"
        assert template.title == "Test Prompt"
        assert template.description == "A test prompt"
        assert template.content == "Hello {name}!"
        assert template.suggested_tools == ["tool1", "tool2"]

    def test_to_dict(self):
        """Test converting template to dictionary."""
        template = MCPPromptTemplate(
            name="test_prompt",
            title="Test Prompt",
            description="A test prompt",
            content="Hello {name}!",
            suggested_tools=["tool1"],
            metadata={"category": "test"},
        )

        result = template.to_dict()
        assert isinstance(result, dict)
        assert result["name"] == "test_prompt"
        assert result["title"] == "Test Prompt"
        assert result["description"] == "A test prompt"
        assert result["content"] == "Hello {name}!"
        assert result["suggested_tools"] == ["tool1"]
        assert result["metadata"] == {"category": "test"}

    def test_format(self):
        """Test formatting template content."""
        template = MCPPromptTemplate(
            name="test",
            title="Test",
            description="Test",
            content="Hello {name}, you have {count} messages!",
        )

        result = template.format(name="Alice", count=5)
        assert result == "Hello Alice, you have 5 messages!"

    def test_format_missing_params(self):
        """Test formatting with missing parameters."""
        template = MCPPromptTemplate(
            name="test", title="Test", description="Test", content="Hello {name}!"
        )

        # Should return original content when formatting fails
        result = template.format(wrong_param="value")
        assert result == "Hello {name}!"


class TestPytestDebugSessionPrompt:
    """Test the pytest debug session prompt."""

    def test_initialization(self):
        """Test that the prompt initializes correctly."""
        prompt = PytestDebugSessionPrompt()

        assert prompt.name == "pytest_debug_session"
        assert prompt.title == "Debug Pytest Failure"
        assert (
            "Analyze and fix pytest test failures systematically" in prompt.description
        )
        assert "analyze_pytest_output" in prompt.suggested_tools
        assert "suggest_fixes" in prompt.suggested_tools
        assert "validate_suggestion" in prompt.suggested_tools
        assert "get_failure_summary" in prompt.suggested_tools
        assert prompt.metadata["category"] == "debugging"

    def test_content(self):
        """Test that the prompt content is comprehensive."""
        prompt = PytestDebugSessionPrompt()

        assert "Paste your pytest output here" in prompt.content
        assert "analyze_pytest_output" in prompt.content
        assert "Additional context" in prompt.content


class TestCIFailureInvestigationPrompt:
    """Test the CI failure investigation prompt."""

    def test_initialization(self):
        """Test that the prompt initializes correctly."""
        prompt = CIFailureInvestigationPrompt()

        assert prompt.name == "ci_failure_investigation"
        assert prompt.title == "Investigate CI Pipeline Failure"
        assert "CI pipelines" in prompt.description
        assert "analyze_pytest_output" in prompt.suggested_tools
        assert "get_failure_summary" in prompt.suggested_tools
        assert "suggest_fixes" in prompt.suggested_tools
        assert "run_and_analyze" in prompt.suggested_tools
        assert prompt.metadata["category"] == "ci_debugging"

    def test_content_structure(self):
        """Test that the prompt content covers CI-specific concerns."""
        prompt = CIFailureInvestigationPrompt()

        assert "CI failure output" in prompt.content
        assert "environment-specific issues" in prompt.content
        assert "race conditions" in prompt.content
        assert "configuration differences" in prompt.content


class TestFlakyTestDiagnosisPrompt:
    """Test the flaky test diagnosis prompt."""

    def test_initialization(self):
        """Test that the prompt initializes correctly."""
        prompt = FlakyTestDiagnosisPrompt()

        assert prompt.name == "flaky_test_diagnosis"
        assert prompt.title == "Diagnose Flaky Test"
        assert "intermittently failing tests" in prompt.description
        assert "get_failure_summary" in prompt.suggested_tools
        assert "analyze_pytest_output" in prompt.suggested_tools
        assert "suggest_fixes" in prompt.suggested_tools
        assert "validate_suggestion" in prompt.suggested_tools
        assert prompt.metadata["category"] == "flaky_tests"

    def test_content_structure(self):
        """Test that the prompt content addresses flaky test concerns."""
        prompt = FlakyTestDiagnosisPrompt()

        assert "intermittently" in prompt.content
        assert "race conditions" in prompt.content
        assert "timing issues" in prompt.content
        assert "deterministic" in prompt.content


class TestPerformanceTestingPrompt:
    """Test the performance testing prompt."""

    def test_initialization(self):
        """Test that the prompt initializes correctly."""
        prompt = PerformanceTestingPrompt()

        assert prompt.name == "performance_test_diagnosis"
        assert prompt.title == "Diagnose Performance Test Issues"
        assert "performance-related test failures" in prompt.description
        assert "analyze_pytest_output" in prompt.suggested_tools
        assert "suggest_fixes" in prompt.suggested_tools
        assert "get_test_coverage" in prompt.suggested_tools
        assert "run_and_analyze" in prompt.suggested_tools
        assert prompt.metadata["category"] == "performance"

    def test_content_structure(self):
        """Test that the prompt content addresses performance concerns."""
        prompt = PerformanceTestingPrompt()

        assert "timeout failures" in prompt.content
        assert "performance bottlenecks" in prompt.content
        assert "Optimizing test performance" in prompt.content


class TestTestConfigurationPrompt:
    """Test the test configuration prompt."""

    def test_initialization(self):
        """Test that the prompt initializes correctly."""
        prompt = TestConfigurationPrompt()

        assert prompt.name == "test_configuration_debug"
        assert prompt.title == "Debug Test Configuration Issues"
        assert "configuration, fixtures, and setup" in prompt.description
        assert "get_config" in prompt.suggested_tools
        assert "analyze_pytest_output" in prompt.suggested_tools
        assert "suggest_fixes" in prompt.suggested_tools
        assert "update_config" in prompt.suggested_tools
        assert prompt.metadata["category"] == "configuration"

    def test_content_structure(self):
        """Test that the prompt content addresses configuration concerns."""
        prompt = TestConfigurationPrompt()

        assert "configuration problems" in prompt.content
        assert "pytest.ini" in prompt.content
        assert "conftest.py" in prompt.content
        assert "fixture-related issues" in prompt.content


class TestPromptRegistry:
    """Test the PromptRegistry class."""

    def test_creation(self):
        """Test creating a prompt registry."""
        registry = PromptRegistry()
        assert isinstance(registry._prompts, dict)
        assert isinstance(registry._categories, dict)
        assert len(registry._prompts) == 0

    def test_register_prompt(self):
        """Test registering a prompt."""
        registry = PromptRegistry()
        prompt = MCPPromptTemplate(
            name="test_prompt",
            title="Test",
            description="Test prompt",
            content="Test content",
            metadata={"category": "test"},
        )

        registry.register_prompt(prompt)

        assert "test_prompt" in registry._prompts
        assert registry._prompts["test_prompt"] == prompt
        assert "test" in registry._categories
        assert "test_prompt" in registry._categories["test"]

    def test_get_prompt(self):
        """Test retrieving a prompt."""
        registry = PromptRegistry()
        prompt = MCPPromptTemplate(
            name="test_prompt",
            title="Test",
            description="Test prompt",
            content="Test content",
        )

        registry.register_prompt(prompt)
        retrieved = registry.get_prompt("test_prompt")

        assert retrieved == prompt
        assert registry.get_prompt("nonexistent") is None

    def test_list_prompts(self):
        """Test listing all prompts."""
        registry = PromptRegistry()
        prompt1 = MCPPromptTemplate(
            name="prompt1", title="Test1", description="Test", content="Test"
        )
        prompt2 = MCPPromptTemplate(
            name="prompt2", title="Test2", description="Test", content="Test"
        )

        registry.register_prompt(prompt1)
        registry.register_prompt(prompt2)

        prompts = registry.list_prompts()
        assert "prompt1" in prompts
        assert "prompt2" in prompts
        assert len(prompts) == 2

    def test_list_by_category(self):
        """Test listing prompts by category."""
        registry = PromptRegistry()
        prompt1 = MCPPromptTemplate(
            name="prompt1",
            title="Test1",
            description="Test",
            content="Test",
            metadata={"category": "debug"},
        )
        prompt2 = MCPPromptTemplate(
            name="prompt2",
            title="Test2",
            description="Test",
            content="Test",
            metadata={"category": "config"},
        )

        registry.register_prompt(prompt1)
        registry.register_prompt(prompt2)

        debug_prompts = registry.list_by_category("debug")
        assert "prompt1" in debug_prompts
        assert "prompt2" not in debug_prompts

        config_prompts = registry.list_by_category("config")
        assert "prompt2" in config_prompts
        assert "prompt1" not in config_prompts

    def test_get_categories(self):
        """Test getting all categories."""
        registry = PromptRegistry()
        prompt1 = MCPPromptTemplate(
            name="prompt1",
            title="Test1",
            description="Test",
            content="Test",
            metadata={"category": "debug"},
        )
        prompt2 = MCPPromptTemplate(
            name="prompt2",
            title="Test2",
            description="Test",
            content="Test",
            metadata={"category": "config"},
        )

        registry.register_prompt(prompt1)
        registry.register_prompt(prompt2)

        categories = registry.get_categories()
        assert "debug" in categories
        assert "config" in categories

    def test_to_dict(self):
        """Test converting registry to dictionary."""
        registry = PromptRegistry()
        prompt = MCPPromptTemplate(
            name="test_prompt",
            title="Test",
            description="Test",
            content="Test",
            metadata={"category": "test"},
        )

        registry.register_prompt(prompt)
        result = registry.to_dict()

        assert "prompts" in result
        assert "categories" in result
        assert "test_prompt" in result["prompts"]
        assert "test" in result["categories"]


class TestGlobalFunctions:
    """Test global functions and registry operations."""

    def test_get_prompt_registry(self):
        """Test getting the global registry."""
        registry = get_prompt_registry()
        assert isinstance(registry, PromptRegistry)

        # Should return the same instance
        registry2 = get_prompt_registry()
        assert registry is registry2

    def test_initialize_default_prompts(self):
        """Test initializing default prompts."""
        # Clear the registry first
        registry = get_prompt_registry()
        registry._prompts.clear()
        registry._categories.clear()

        initialize_default_prompts()

        # Check that default prompts are registered
        prompts = registry.list_prompts()
        assert "pytest_debug_session" in prompts
        assert "ci_failure_investigation" in prompts
        assert "flaky_test_diagnosis" in prompts
        assert "performance_test_diagnosis" in prompts
        assert "test_configuration_debug" in prompts

    @pytest.mark.asyncio
    async def test_handle_list_prompts(self):
        """Test the handle_list_prompts function."""
        # Clear and reinitialize
        registry = get_prompt_registry()
        registry._prompts.clear()
        registry._categories.clear()
        initialize_default_prompts()

        result = await handle_list_prompts()

        assert isinstance(result, list)
        assert len(result) > 0

        # Check structure of returned prompts
        for prompt_info in result:
            assert "name" in prompt_info
            assert "description" in prompt_info
            assert "arguments" in prompt_info

    @pytest.mark.asyncio
    async def test_handle_get_prompt(self):
        """Test the handle_get_prompt function."""
        # Clear and reinitialize
        registry = get_prompt_registry()
        registry._prompts.clear()
        registry._categories.clear()
        initialize_default_prompts()

        # Test getting existing prompt
        result = await handle_get_prompt("pytest_debug_session")

        assert "name" in result
        assert "description" in result
        assert "content" in result
        assert "suggested_tools" in result
        assert "metadata" in result
        assert result["name"] == "pytest_debug_session"

    @pytest.mark.asyncio
    async def test_handle_get_prompt_not_found(self):
        """Test getting a non-existent prompt."""
        result = await handle_get_prompt("nonexistent_prompt")

        assert "error" in result
        assert "available_prompts" in result

    @pytest.mark.asyncio
    async def test_handle_get_prompt_with_arguments(self):
        """Test getting a prompt with formatting arguments."""
        registry = get_prompt_registry()
        registry._prompts.clear()

        # Register a simple prompt with formatting
        prompt = MCPPromptTemplate(
            name="format_test",
            title="Format Test",
            description="Test formatting",
            content="Hello {name}, you have {count} items!",
        )
        registry.register_prompt(prompt)

        result = await handle_get_prompt("format_test", {"name": "Alice", "count": 5})

        assert "content" in result
        assert "Hello Alice, you have 5 items!" in result["content"]

    def test_register_custom_prompt(self):
        """Test registering a custom prompt."""
        result = register_custom_prompt(
            name="custom_test",
            title="Custom Test",
            description="A custom test prompt",
            content="Custom content here",
            suggested_tools=["custom_tool"],
            metadata={"category": "custom"},
        )

        assert result is True

        registry = get_prompt_registry()
        prompt = registry.get_prompt("custom_test")
        assert prompt is not None
        assert prompt.name == "custom_test"
        assert prompt.title == "Custom Test"
        assert prompt.suggested_tools == ["custom_tool"]

    def test_register_custom_prompt_failure(self):
        """Test handling failure in custom prompt registration."""
        # Mock a failure in the registration process
        with patch(
            "pytest_analyzer.mcp.prompts.templates.get_prompt_registry"
        ) as mock_registry:
            mock_registry.side_effect = Exception("Test error")

            result = register_custom_prompt(
                name="failing_prompt",
                title="Failing",
                description="Will fail",
                content="Content",
            )

            assert result is False


class TestIntegration:
    """Integration tests for the complete prompt system."""

    def test_full_workflow(self):
        """Test a complete workflow with the prompt system."""
        # Clear registry
        registry = get_prompt_registry()
        registry._prompts.clear()
        registry._categories.clear()

        # Initialize defaults
        initialize_default_prompts()

        # Verify we have the expected prompts
        prompts = registry.list_prompts()
        assert len(prompts) >= 5

        # Test getting a specific prompt
        debug_prompt = registry.get_prompt("pytest_debug_session")
        assert debug_prompt is not None
        assert "analyze_pytest_output" in debug_prompt.suggested_tools

        # Test categories
        categories = registry.get_categories()
        assert "debugging" in categories
        assert "ci_debugging" in categories
        assert "flaky_tests" in categories

        # Test category filtering
        debug_prompts = registry.list_by_category("debugging")
        assert "pytest_debug_session" in debug_prompts

    @pytest.mark.asyncio
    async def test_async_handlers_integration(self):
        """Test the async MCP handlers integration."""
        # Clear and reinitialize
        registry = get_prompt_registry()
        registry._prompts.clear()
        registry._categories.clear()
        initialize_default_prompts()

        # Test list_prompts
        prompts_list = await handle_list_prompts()
        assert len(prompts_list) > 0

        # Test get_prompt for each listed prompt
        for prompt_info in prompts_list:
            prompt_name = prompt_info["name"]
            prompt_detail = await handle_get_prompt(prompt_name)

            assert "error" not in prompt_detail
            assert prompt_detail["name"] == prompt_name
            assert "content" in prompt_detail
            assert "suggested_tools" in prompt_detail
