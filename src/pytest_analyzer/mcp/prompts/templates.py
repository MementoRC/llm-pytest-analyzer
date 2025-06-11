"""MCP prompt templates for structured pytest debugging workflows.

Provides comprehensive prompt templates that guide users through systematic
debugging processes while leveraging available MCP tools.
"""

import logging
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class MCPPromptTemplate:
    """Base class for MCP prompt templates."""

    name: str
    title: str
    description: str
    content: str
    suggested_tools: List[str] = field(default_factory=list)
    arguments: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert prompt template to dictionary."""
        return asdict(self)

    def format(self, **kwargs) -> str:
        """Format prompt content with parameters."""
        try:
            return self.content.format(**kwargs)
        except KeyError as e:
            logger.warning(f"Missing template parameter: {e}")
            return self.content


# Core Debugging Workflow Prompts
class PytestDebugSessionPrompt(MCPPromptTemplate):
    """Primary debugging workflow for test failures."""

    def __init__(self):
        super().__init__(
            name="pytest_debug_session",
            title="Debug Pytest Failure",
            description="Analyze and fix pytest test failures systematically",
            content="",  # Will be set below
            suggested_tools=[
                "analyze_pytest_output",
                "suggest_fixes",
                "validate_suggestion",
                "get_failure_summary",
            ],
            metadata={
                "category": "debugging",
                "complexity": "basic",
                "estimated_time": "10-15 minutes",
            },
        )
        self.content = """I need help debugging a pytest failure. I'll provide the test output, and I'd like you to:

1. **Analyze the test output** to identify the root cause
2. **Suggest specific fixes** for the failing tests
3. **Help me understand** why the test is failing
4. **Provide guidance** on how to prevent similar issues

Here's my test output:
```
[Paste your pytest output here]
```

**Additional context (optional):**
- Test environment: [local/CI/specific environment]
- Recent changes: [describe any recent code changes]
- Expected behavior: [what should happen]

**Please start by using the `analyze_pytest_output` tool to examine the failure details.**"""


class CIFailureInvestigationPrompt(MCPPromptTemplate):
    """Systematic CI-specific debugging workflow."""

    def __init__(self):
        super().__init__(
            name="ci_failure_investigation",
            title="Investigate CI Pipeline Failure",
            description="Systematically debug test failures occurring in CI pipelines",
            content="",  # Will be set below
            suggested_tools=[
                "analyze_pytest_output",
                "get_failure_summary",
                "suggest_fixes",
                "run_and_analyze",
            ],
            metadata={
                "category": "ci_debugging",
                "complexity": "intermediate",
                "estimated_time": "20-30 minutes",
            },
        )
        self.content = """I'm investigating a test failure that occurs in our CI pipeline but not locally. I need help with:

1. **Analyzing the CI test output** to identify environment-specific issues
2. **Understanding potential race conditions** or timing issues
3. **Identifying configuration differences** between CI and local environments
4. **Creating a reliable fix** that works across all environments

Here's the CI failure output:
```
[Paste your CI failure output here]
```

**CI Environment Details:**
- CI Platform: [GitHub Actions/Jenkins/other]
- OS/Container: [ubuntu-latest/specific container]
- Python version: [3.x]
- Dependencies: [specific versions if relevant]
- Parallel execution: [yes/no, how many workers]

**Local Environment:**
- OS: [your operating system]
- Python version: [3.x]
- Same dependencies: [yes/no/differences]

**Differences noted:**
- [List any known differences between environments]

**Please start by using the `analyze_pytest_output` tool followed by `get_failure_summary` to identify patterns.**"""


class FlakyTestDiagnosisPrompt(MCPPromptTemplate):
    """Intermittent test failure analysis workflow."""

    def __init__(self):
        super().__init__(
            name="flaky_test_diagnosis",
            title="Diagnose Flaky Test",
            description="Analyze and fix intermittently failing tests",
            content="",  # Will be set below
            suggested_tools=[
                "get_failure_summary",
                "analyze_pytest_output",
                "suggest_fixes",
                "validate_suggestion",
            ],
            metadata={
                "category": "flaky_tests",
                "complexity": "advanced",
                "estimated_time": "30-45 minutes",
            },
        )
        self.content = """I'm dealing with flaky tests that fail intermittently. I need help:

1. **Analyzing patterns** in the test failures
2. **Identifying potential race conditions**, timing issues, or resource conflicts
3. **Developing a strategy** to make the tests more deterministic
4. **Creating fixes** that ensure test stability

**Flaky Test Information:**
- Test name(s): [specific test names]
- Failure frequency: [X% failure rate, pattern if any]
- Environment(s): [where it fails - local/CI/both]

Here are examples of the test failures from multiple runs:

**Failure Example 1:**
```
[Paste first failure example here]
```

**Failure Example 2:**
```
[Paste second failure example here]
```

**Failure Example 3 (if different):**
```
[Paste third failure example if pattern differs]
```

**Test Environment Details:**
- Testing framework: [pytest + specific plugins]
- Async code: [yes/no - describe if yes]
- External dependencies: [databases, APIs, file system, etc.]
- Parallelization: [yes/no, configuration]
- Fixtures: [describe shared fixtures or state]

**Suspected causes:**
- [List any theories about why it's flaky]

**Please start with `get_failure_summary` to analyze patterns, then use `analyze_pytest_output` for detailed analysis.**"""


class PerformanceTestingPrompt(MCPPromptTemplate):
    """Performance-related test failure analysis."""

    def __init__(self):
        super().__init__(
            name="performance_test_diagnosis",
            title="Diagnose Performance Test Issues",
            description="Analyze performance-related test failures and timeouts",
            content="",  # Will be set below
            suggested_tools=[
                "analyze_pytest_output",
                "suggest_fixes",
                "get_test_coverage",
                "run_and_analyze",
            ],
            metadata={
                "category": "performance",
                "complexity": "intermediate",
                "estimated_time": "25-35 minutes",
            },
        )
        self.content = """I'm experiencing performance-related test issues. I need help with:

1. **Analyzing timeout failures** and slow test execution
2. **Identifying performance bottlenecks** in test code
3. **Optimizing test performance** without losing coverage
4. **Setting appropriate timeouts** and performance expectations

**Performance Issue Details:**
- Issue type: [timeouts/slow execution/memory issues]
- Affected tests: [specific test names or patterns]
- Expected duration: [normal vs current timing]
- Resource usage: [CPU/memory observations]

Here's the test output showing performance issues:
```
[Paste your test output with timing/timeout information]
```

**Environment Context:**
- Test environment: [local/CI/specific setup]
- System resources: [available CPU/memory]
- Test data size: [amount of test data involved]
- External services: [any network calls or external dependencies]

**Recent changes:**
- [Describe any recent changes that might affect performance]

**Please use `analyze_pytest_output` to examine the failures and `suggest_fixes` for optimization strategies.**"""


class TestConfigurationPrompt(MCPPromptTemplate):
    """Test configuration and setup debugging."""

    def __init__(self):
        super().__init__(
            name="test_configuration_debug",
            title="Debug Test Configuration Issues",
            description="Resolve test configuration, fixtures, and setup problems",
            content="",  # Will be set below
            suggested_tools=[
                "get_config",
                "analyze_pytest_output",
                "suggest_fixes",
                "update_config",
            ],
            metadata={
                "category": "configuration",
                "complexity": "intermediate",
                "estimated_time": "15-25 minutes",
            },
        )
        self.content = """I'm having issues with test configuration, fixtures, or test setup. I need help with:

1. **Diagnosing configuration problems** (pytest.ini, conftest.py, etc.)
2. **Fixing fixture-related issues** (scope, dependencies, cleanup)
3. **Resolving import and discovery problems**
4. **Optimizing test setup and teardown**

**Configuration Issue Type:**
- [fixtures/imports/discovery/plugins/environment]

**Current test output with configuration errors:**
```
[Paste your test output showing configuration issues]
```

**Current configuration files:**

**pytest.ini / pyproject.toml [pytest] section:**
```
[Paste your pytest configuration]
```

**conftest.py (relevant parts):**
```
[Paste relevant conftest.py sections]
```

**Project structure:**
- [Describe your test directory structure]

**What's not working:**
- [Describe the specific configuration issue]

**Expected behavior:**
- [What should happen instead]

**Please start with `get_config` to examine current configuration, then use `analyze_pytest_output` for detailed diagnosis.**"""


# Prompt Registry
class PromptRegistry:
    """Registry for managing MCP prompt templates."""

    def __init__(self):
        self._prompts: Dict[str, MCPPromptTemplate] = {}
        self._categories: Dict[str, List[str]] = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def register_prompt(self, prompt: MCPPromptTemplate) -> None:
        """Register a prompt template."""
        if prompt.name in self._prompts:
            self.logger.warning(f"Overwriting existing prompt: {prompt.name}")

        self._prompts[prompt.name] = prompt

        # Organize by category
        category = prompt.metadata.get("category", "general")
        if category not in self._categories:
            self._categories[category] = []
        self._categories[category].append(prompt.name)

        self.logger.info(f"Registered prompt: {prompt.name} (category: {category})")

    def get_prompt(self, name: str) -> Optional[MCPPromptTemplate]:
        """Get a prompt template by name."""
        return self._prompts.get(name)

    def list_prompts(self) -> List[str]:
        """List all registered prompt names."""
        return list(self._prompts.keys())

    def list_by_category(self, category: str) -> List[str]:
        """List prompts in a specific category."""
        return self._categories.get(category, [])

    def get_categories(self) -> List[str]:
        """Get all available categories."""
        return list(self._categories.keys())

    def to_dict(self) -> Dict[str, Any]:
        """Convert registry to dictionary for serialization."""
        return {
            "prompts": {
                name: prompt.to_dict() for name, prompt in self._prompts.items()
            },
            "categories": self._categories,
        }


# Global registry instance
_prompt_registry = PromptRegistry()


def get_prompt_registry() -> PromptRegistry:
    """Get the global prompt registry instance."""
    return _prompt_registry


def initialize_default_prompts() -> None:
    """Initialize default prompt templates."""
    registry = get_prompt_registry()

    # Register all default prompts
    default_prompts = [
        PytestDebugSessionPrompt(),
        CIFailureInvestigationPrompt(),
        FlakyTestDiagnosisPrompt(),
        PerformanceTestingPrompt(),
        TestConfigurationPrompt(),
    ]

    for prompt in default_prompts:
        registry.register_prompt(prompt)

    logger.info(f"Initialized {len(default_prompts)} default prompt templates")


# MCP Protocol Integration Functions
async def handle_list_prompts() -> List[Dict[str, Any]]:
    """Handle MCP list_prompts request."""
    try:
        registry = get_prompt_registry()
        prompts = []

        for name in registry.list_prompts():
            prompt = registry.get_prompt(name)
            if prompt:
                prompts.append(
                    {
                        "name": prompt.name,
                        "description": prompt.description,
                        "arguments": prompt.arguments or {},
                    }
                )

        logger.debug(f"Listed {len(prompts)} prompts")
        return prompts

    except Exception as e:
        logger.error(f"Error listing prompts: {e}")
        return []


async def handle_get_prompt(
    name: str, arguments: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Handle MCP get_prompt request."""
    try:
        registry = get_prompt_registry()
        prompt = registry.get_prompt(name)

        if not prompt:
            return {
                "error": f"Prompt '{name}' not found",
                "available_prompts": registry.list_prompts(),
            }

        # Format content if arguments provided
        content = prompt.content
        if arguments:
            try:
                content = prompt.format(**arguments)
            except Exception as e:
                logger.warning(f"Failed to format prompt {name} with arguments: {e}")

        result = {
            "name": prompt.name,
            "description": prompt.description,
            "content": content,
            "suggested_tools": prompt.suggested_tools,
            "metadata": prompt.metadata,
        }

        logger.info(f"Retrieved prompt: {name}")
        return result

    except Exception as e:
        logger.error(f"Error getting prompt {name}: {e}")
        return {"error": f"Failed to retrieve prompt: {str(e)}"}


def register_custom_prompt(
    name: str,
    title: str,
    description: str,
    content: str,
    suggested_tools: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    """Register a custom prompt template."""
    try:
        prompt = MCPPromptTemplate(
            name=name,
            title=title,
            description=description,
            content=content,
            suggested_tools=suggested_tools or [],
            metadata=metadata or {},
        )

        registry = get_prompt_registry()
        registry.register_prompt(prompt)
        return True

    except Exception as e:
        logger.error(f"Failed to register custom prompt {name}: {e}")
        return False


__all__ = [
    "MCPPromptTemplate",
    "PytestDebugSessionPrompt",
    "CIFailureInvestigationPrompt",
    "FlakyTestDiagnosisPrompt",
    "PerformanceTestingPrompt",
    "TestConfigurationPrompt",
    "PromptRegistry",
    "get_prompt_registry",
    "initialize_default_prompts",
    "handle_list_prompts",
    "handle_get_prompt",
    "register_custom_prompt",
]
