"""MCP prompt templates for pytest-analyzer.

Provides structured prompts for MCP interactions and debugging workflows.
"""

from .templates import (
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
