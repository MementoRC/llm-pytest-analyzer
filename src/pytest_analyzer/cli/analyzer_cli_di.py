#!/usr/bin/env python3

"""
DI-based command-line interface for the pytest analyzer tool.

This module provides a command line interface that leverages the dependency injection
container for better modularity and testability.
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import List

from rich.console import Console
from rich.syntax import Syntax

from ..core.analyzer_service_di import DIPytestAnalyzerService
from ..core.di import get_service, initialize_container
from ..core.models.pytest_failure import FixSuggestion
from ..utils.settings import Settings, load_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("pytest_analyzer")

# Configure rich console with proper terminal settings
console = Console(
    force_terminal=True if os.environ.get("FORCE_COLOR", "0") == "1" else None
)


def setup_parser() -> argparse.ArgumentParser:
    """Set up the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Python Test Failure Analyzer with enhanced extraction strategies"
    )

    # Main arguments
    parser.add_argument(
        "test_path",
        nargs="?",
        help="Path to test file or directory (optional if using --output-path)",
    )
    parser.add_argument(
        "--output-path",
        "-o",
        help="Path to pytest output file (JSON or XML)",
    )

    # Analysis settings
    parser.add_argument(
        "--max-suggestions",
        type=int,
        default=None,
        help="Maximum number of fix suggestions to generate (default: 3)",
    )
    parser.add_argument(
        "--max-failures",
        type=int,
        default=None,
        help="Maximum number of failures to analyze (default: 10)",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=None,
        help="Minimum confidence threshold for suggestions (default: 0.6)",
    )
    parser.add_argument(
        "--auto-apply",
        action="store_true",
        help="Automatically apply suggested fixes (use with caution)",
    )
    parser.add_argument(
        "--test-functions",
        help="Comma-separated list of specific test functions to run",
    )

    # LLM integration
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Use language model for enhanced suggestions",
    )
    parser.add_argument(
        "--llm-provider",
        choices=["anthropic", "openai"],
        default=None,
        help="LLM provider to use (default: auto-detect)",
    )
    parser.add_argument(
        "--llm-model",
        help="Specific LLM model to use",
    )
    parser.add_argument(
        "--llm-timeout",
        type=int,
        default=None,
        help="Timeout in seconds for LLM requests (default: 60)",
    )

    # Add new --env-manager argument here
    parser.add_argument(
        "--env-manager",
        type=str.lower,  # Ensure value is lowercase
        choices=["auto", "pixi", "poetry", "hatch", "uv", "pipenv", "pip+venv"],
        default="auto",  # Default to auto-detection
        help="Specify the environment manager to use. 'auto' will attempt to detect it. (default: auto)",
    )

    # Output format options
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--preferred-format",
        choices=["json", "xml", "plugin"],
        default=None,
        help="Preferred pytest output format (default: json)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose output"
    )
    parser.add_argument(
        "--quiet", "-q", action="store_true", help="Suppress all non-essential output"
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output",
    )
    parser.add_argument("--config", help="Path to configuration file")

    # Pytest passthrough arguments
    parser.add_argument(
        "--pytest-args",
        help="Additional arguments to pass to pytest (comma-separated)",
    )

    return parser


def configure_settings(args: argparse.Namespace) -> Settings:
    """
    Configure settings based on command-line arguments and config file.

    Args:
        args: Command-line arguments

    Returns:
        Configured Settings object
    """
    # Load settings from config file if provided
    file_settings = load_settings(args.config) if args.config else None
    settings = file_settings if file_settings else Settings()

    # Override settings with command-line arguments if provided
    if args.max_suggestions is not None:
        settings.max_suggestions = args.max_suggestions

    if args.max_failures is not None:
        settings.max_failures = args.max_failures

    if args.min_confidence is not None:
        settings.min_confidence = args.min_confidence

    if args.auto_apply:
        settings.auto_apply = True

    if args.use_llm:
        settings.use_llm = True

    if args.llm_provider:
        settings.llm_provider = args.llm_provider

    if args.llm_model:
        settings.llm_model = args.llm_model

    if args.llm_timeout is not None:
        settings.llm_timeout = args.llm_timeout

    # Environment Manager (CLI takes precedence)
    # args.env_manager is already lowercase due to type=str.lower in add_argument
    if args.env_manager == "auto":
        settings.environment_manager = None  # Force auto-detection
    else:
        settings.environment_manager = args.env_manager  # Use specified manager

    if args.preferred_format:
        settings.preferred_format = args.preferred_format

    # Configure logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger("pytest_analyzer").setLevel(logging.DEBUG)
        settings.debug = True
    elif args.quiet:
        logging.getLogger().setLevel(logging.WARNING)
        logging.getLogger("pytest_analyzer").setLevel(logging.WARNING)

    # Configure test functions if provided
    if args.test_functions:
        settings.test_functions = args.test_functions.split(",")

    # Configure pytest arguments if provided
    if args.pytest_args:
        settings.pytest_args = args.pytest_args.split(",")

    return settings


def display_suggestions(
    suggestions: List[FixSuggestion], format_: str = "text", quiet: bool = False
) -> None:
    """
    Display fix suggestions in the specified format.

    Args:
        suggestions: List of fix suggestions
        format_: Output format ('text' or 'json')
        quiet: Whether to suppress non-essential output
    """
    if not suggestions:
        if not quiet:
            console.print("[yellow]No fix suggestions found.[/yellow]")
        return

    if format_ == "json":
        # Output suggestions as JSON
        json_data = []
        for suggestion in suggestions:
            json_data.append(
                {
                    "test_name": suggestion.failure.test_name,
                    "test_file": suggestion.failure.test_file,
                    "error_type": suggestion.failure.error_type,
                    "error_message": suggestion.failure.error_message,
                    "suggestion": suggestion.suggestion,
                    "explanation": suggestion.explanation,
                    "confidence": suggestion.confidence,
                    "code_changes": suggestion.code_changes,
                }
            )
        console.print(json.dumps(json_data, indent=2))
    else:
        # Output suggestions as formatted text
        llm_suggestions = [
            s
            for s in suggestions
            if s.code_changes and s.code_changes.get("source") == "llm"
        ]
        rule_suggestions = [
            s
            for s in suggestions
            if not s.code_changes or s.code_changes.get("source") != "llm"
        ]

        if not quiet:
            console.print(
                f"[bold green]Found {len(suggestions)} fix suggestions:[/bold green]"
            )

            if rule_suggestions:
                console.print("\n[bold]Rule-based Suggestions:[/bold]")

            for i, suggestion in enumerate(rule_suggestions):
                _display_suggestion(suggestion, i + 1)

            if llm_suggestions:
                console.print("\n[bold]AI-Generated Suggestions:[/bold]")

            for i, suggestion in enumerate(llm_suggestions):
                _display_suggestion(suggestion, i + 1)


def _display_suggestion(suggestion: FixSuggestion, index: int) -> None:
    """
    Display a single fix suggestion with rich formatting.

    Args:
        suggestion: The fix suggestion to display
        index: Suggestion index for display
    """
    failure = suggestion.failure
    confidence_color = "green" if suggestion.confidence >= 0.8 else "yellow"

    # Create heading with test info
    console.print(
        f"\n[bold cyan]Suggestion {index} for {failure.test_name}[/bold cyan]"
    )
    console.print(f"[dim]{failure.test_file}:{failure.line_number}[/dim]")
    console.print(f"Error: [red]{failure.error_type}[/red]: {failure.error_message}")
    console.print(
        f"Confidence: [{confidence_color}]{suggestion.confidence:.2f}[/{confidence_color}]"
    )

    # Display suggestion and explanation
    console.print("\n[bold]Suggestion:[/bold]")
    console.print(f"{suggestion.suggestion}")

    if suggestion.explanation:
        console.print("\n[bold]Explanation:[/bold]")
        console.print(f"{suggestion.explanation}")

    # Display code changes if available
    if suggestion.code_changes:
        for file_path, changes in suggestion.code_changes.items():
            if file_path != "source":  # Skip metadata
                console.print(f"\n[bold]Code changes for {file_path}:[/bold]")

                if isinstance(changes, str):
                    # Simple string changes
                    console.print(Syntax(changes, "python", theme="monokai"))
                elif isinstance(changes, dict) and "diff" in changes:
                    # Diff-based changes
                    console.print(Syntax(changes["diff"], "diff", theme="monokai"))


def main() -> int:
    """
    Main entry point for the CLI.

    Returns:
        Exit code (0 for success, non-zero for errors)
    """
    parser = setup_parser()
    args = parser.parse_args()

    # Disable color if requested
    if args.no_color:
        console.no_color = True

    try:
        # Configure settings based on arguments
        settings = configure_settings(args)

        # Set up DI container
        initialize_container(settings)

        # Get the analyzer service
        analyzer_service = get_service(DIPytestAnalyzerService)

        # Validate essential arguments
        if not args.test_path and not args.output_path:
            parser.error("Either test_path or --output-path must be provided")
            return 1

        # Handle pytest output file if provided
        if args.output_path:
            try:
                output_path = Path(args.output_path)
                if not output_path.exists():
                    logger.error(
                        f"Error reading report file: {os.strerror(2)} '{args.output_path}'"
                    )
                    return 1

                suggestions = analyzer_service.analyze_pytest_output(output_path)
                display_suggestions(suggestions, args.format, args.quiet)

                return 0
            except Exception as e:
                logger.error(f"An error occurred: {e}")
                if args.debug:
                    logger.exception("Debug traceback:")
                return 1

        # Run and analyze pytest if test_path is provided
        if args.test_path:
            # Prepare pytest arguments
            pytest_args = []
            if args.pytest_args:
                pytest_args.extend(args.pytest_args.split(","))

            # Add test functions if specified
            if args.test_functions:
                for func in args.test_functions.split(","):
                    pytest_args.append(f"{args.test_path}::{func}")

            # Run and analyze
            suggestions = analyzer_service.run_and_analyze(
                args.test_path,
                pytest_args=pytest_args,
                quiet=args.quiet,
            )

            # Display results
            display_suggestions(suggestions, args.format, args.quiet)

            return 0

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        if args.debug:
            logger.exception("Debug traceback:")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
