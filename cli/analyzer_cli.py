#!/usr/bin/env python3

"""
Command-line interface for the pytest analyzer tool.

This tool provides enhanced pytest failure analysis with robust extraction strategies
and intelligent fix suggestions, avoiding the regex-based infinite loop issues of
the original test_analyzer implementation.
"""

import sys
import os
import argparse
import logging
from pathlib import Path
from typing import List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax

from ..core.analyzer_service import TestAnalyzerService
from ..core.models.test_failure import TestFailure, FixSuggestion
from ..utils.settings import Settings, load_settings
from ..utils.path_resolver import PathResolver


# Setup rich console
console = Console()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("pytest_analyzer")


def setup_parser() -> argparse.ArgumentParser:
    """Set up the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Python Test Failure Analyzer with enhanced extraction strategies"
    )
    
    # Main arguments
    parser.add_argument(
        "test_path", 
        type=str, 
        help="Path to the test file or directory to run"
    )
    parser.add_argument(
        "-k", "--test-functions", 
        type=str, 
        help="Pytest -k expression to filter tests"
    )
    parser.add_argument(
        "--output-file", 
        type=str, 
        help="Parse failures from existing pytest output file instead of running tests"
    )
    
    # Configuration options
    parser.add_argument(
        "--project-root", 
        type=str, 
        help="Root directory of the project (auto-detected if not specified)"
    )
    parser.add_argument(
        "--config-file", 
        type=str, 
        help="Path to configuration file"
    )
    
    # Resource control
    parser.add_argument(
        "--timeout", 
        type=int, 
        default=300, 
        help="Maximum execution time in seconds (default: 300)"
    )
    parser.add_argument(
        "--max-memory", 
        type=int, 
        default=1024, 
        help="Maximum memory usage in MB (default: 1024)"
    )
    
    # Output format
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--json", 
        action="store_true", 
        help="Use JSON output format from pytest"
    )
    group.add_argument(
        "--xml", 
        action="store_true", 
        help="Use XML output format from pytest"
    )
    group.add_argument(
        "--plugin", 
        action="store_true", 
        help="Use direct pytest plugin integration"
    )
    
    # Analysis options
    parser.add_argument(
        "--max-failures", 
        type=int, 
        default=100, 
        help="Maximum number of failures to analyze (default: 100)"
    )
    parser.add_argument(
        "--max-suggestions", 
        type=int, 
        default=3, 
        help="Maximum suggestions per failure (default: 3)"
    )
    parser.add_argument(
        "--min-confidence", 
        type=float, 
        default=0.5, 
        help="Minimum confidence for fix suggestions (default: 0.5)"
    )
    
    # Pytest options
    parser.add_argument(
        "--pytest-args", 
        type=str, 
        help="Additional arguments for pytest (quoted)"
    )
    parser.add_argument(
        "--coverage", 
        action="store_true", 
        help="Enable pytest-cov"
    )
    
    # Output control
    parser.add_argument(
        "--raw-output", 
        action="store_true", 
        help="Show raw pytest output"
    )
    parser.add_argument(
        "--debug", 
        action="store_true", 
        help="Enable debug logging"
    )
    
    return parser


def configure_settings(args) -> Settings:
    """Configure settings based on command-line arguments."""
    # Load base settings from config file if provided
    settings = load_settings(args.config_file) if args.config_file else Settings()
    
    # Update settings from command-line arguments
    if args.project_root:
        settings.project_root = Path(args.project_root)
    
    # Resource limits
    settings.pytest_timeout = args.timeout
    settings.max_memory_mb = args.max_memory
    
    # Analysis settings
    settings.max_failures = args.max_failures
    settings.max_suggestions = args.max_suggestions
    settings.min_confidence = args.min_confidence
    
    # Extraction format
    if args.json:
        settings.preferred_format = "json"
    elif args.xml:
        settings.preferred_format = "xml"
    elif args.plugin:
        settings.preferred_format = "plugin"
    
    # Pytest arguments
    pytest_args = []
    if args.coverage:
        pytest_args.append("--cov")
    if args.pytest_args:
        pytest_args.extend(args.pytest_args.split())
    if args.test_functions:
        pytest_args.extend(["-k", args.test_functions])
    settings.pytest_args = pytest_args
    
    return settings


def display_suggestions(suggestions: List[FixSuggestion], args):
    """Display the fix suggestions in the console."""
    if not suggestions:
        console.print("\n[bold red]No fix suggestions found.[/bold red]")
        return
    
    console.print(f"\n[bold green]Found {len(suggestions)} fix suggestions:[/bold green]")
    
    for i, suggestion in enumerate(suggestions):
        console.rule(f"[bold]Suggestion {i+1}/{len(suggestions)}[/bold]")
        
        # Display test failure information
        failure = suggestion.failure
        console.print(f"[bold cyan]Test:[/bold cyan] {failure.test_name}")
        console.print(f"[bold cyan]File:[/bold cyan] {failure.test_file}")
        console.print(f"[bold cyan]Error:[/bold cyan] {failure.error_type}: {failure.error_message}")
        
        if failure.line_number:
            console.print(f"[bold cyan]Line number:[/bold cyan] {failure.line_number}")
        
        # Display the suggested fix
        console.print("\n[bold green]Suggested fix:[/bold green]")
        console.print(suggestion.suggestion)
        
        # Display confidence
        console.print(f"\n[bold cyan]Confidence:[/bold cyan] {suggestion.confidence:.2f}")
        
        # Display explanation if available
        if suggestion.explanation:
            console.print("\n[bold cyan]Explanation:[/bold cyan]")
            console.print(suggestion.explanation)
        
        # Display code changes if available
        if suggestion.code_changes:
            console.print("\n[bold cyan]Code changes:[/bold cyan]")
            for file_path, changes in suggestion.code_changes.items():
                console.print(f"\n[bold]File:[/bold] {file_path}")
                if isinstance(changes, str):
                    console.print(Syntax(changes, "python", theme="monokai", line_numbers=True))
                else:
                    # Display structured changes if not a simple string
                    for change in changes:
                        console.print(f"- {change}")
        
        # Display code snippet if available
        if failure.relevant_code:
            console.print("\n[bold cyan]Relevant code:[/bold cyan]")
            console.print(Syntax(failure.relevant_code, "python", theme="monokai", line_numbers=True))


def main() -> int:
    """Main entry point for the CLI application."""
    # Parse command-line arguments
    parser = setup_parser()
    args = parser.parse_args()
    
    # Configure logging
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")
    
    try:
        # Configure settings
        settings = configure_settings(args)
        
        # Print configuration if debug is enabled
        if args.debug:
            config_table = Table(title="Pytest Analyzer Configuration", show_header=False, box=None)
            config_table.add_column("Setting", style="cyan")
            config_table.add_column("Value", style="green")
            config_table.add_row("Test Path", args.test_path)
            config_table.add_row("Project Root", str(settings.project_root))
            config_table.add_row("Preferred Format", settings.preferred_format)
            config_table.add_row("Max Failures", str(settings.max_failures))
            config_table.add_row("Max Suggestions", str(settings.max_suggestions))
            config_table.add_row("Min Confidence", str(settings.min_confidence))
            config_table.add_row("Pytest Args", " ".join(settings.pytest_args))
            console.print(config_table)
        
        # Initialize the analyzer service
        analyzer_service = TestAnalyzerService(settings=settings)
        
        # Process existing output file or run tests
        if args.output_file:
            console.print(f"\n[bold]Analyzing output file: {args.output_file}[/bold]")
            suggestions = analyzer_service.analyze_pytest_output(args.output_file)
        else:
            console.print(f"\n[bold]Running tests for: {args.test_path}[/bold]")
            suggestions = analyzer_service.run_and_analyze(args.test_path, settings.pytest_args)
        
        # Display suggestions
        display_suggestions(suggestions, args)
        
        # Return success if suggestions were found
        return 0 if suggestions else 1
    
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        if args.debug:
            logger.exception("Detailed error information:")
        return 2


if __name__ == "__main__":
    sys.exit(main())