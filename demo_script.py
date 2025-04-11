#!/usr/bin/env python3
"""
Demo script showcasing pytest-analyzer functionality.

This script demonstrates the different ways to use the pytest-analyzer tool:
1. As a Python API for programmatic usage
2. As a CLI tool (by simulating command-line arguments)
3. With different extraction strategies (JSON, XML, and plugin)

It includes example test files that will fail in different ways to
demonstrate the analyzer's ability to suggest fixes for various error types.
"""

import os
import sys
import tempfile
from pathlib import Path
import argparse

# Add the project root to the Python path to ensure imports work
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

# Now we can import from the package
from pytest_analyzer.core.analyzer_service import PytestAnalyzerService
from pytest_analyzer.utils.settings import Settings
from pytest_analyzer.cli.analyzer_cli import main as cli_main


def create_test_files():
    """Create example test files with different types of failures."""
    # Create a temp directory for our test files
    temp_dir = Path(tempfile.mkdtemp(prefix="pytest_analyzer_demo_"))
    print(f"Created test directory: {temp_dir}")
    
    # Create a simple module to test
    module_path = temp_dir / "sample_module.py"
    with open(module_path, "w") as f:
        f.write("""
def add(a, b):
    return a + b

def divide(a, b):
    return a / b
    
def get_item(items, index):
    return items[index]

def process_data(data):
    return data['value'] * 2
""")

    # Create test file with assertion error
    test_assertion_path = temp_dir / "test_assertion.py"
    with open(test_assertion_path, "w") as f:
        f.write("""
from sample_module import add

def test_add():
    # This will fail - expecting 5 but getting 3
    assert add(1, 2) == 5
""")

    # Create test file with type error
    test_type_path = temp_dir / "test_type.py"
    with open(test_type_path, "w") as f:
        f.write("""
from sample_module import add

def test_add_with_wrong_types():
    # This will fail - can't add string and int
    result = add("hello", 5)
    assert isinstance(result, str)
""")

    # Create test file with zero division error
    test_zerodiv_path = temp_dir / "test_zerodiv.py"
    with open(test_zerodiv_path, "w") as f:
        f.write("""
from sample_module import divide

def test_divide_by_zero():
    # This will fail - division by zero
    result = divide(10, 0)
    assert result > 0
""")

    # Create test file with index error
    test_index_path = temp_dir / "test_index.py"
    with open(test_index_path, "w") as f:
        f.write("""
from sample_module import get_item

def test_index_error():
    # This will fail - index out of range
    items = [1, 2, 3]
    result = get_item(items, 5)
    assert result == 3
""")

    # Create test file with key error
    test_key_path = temp_dir / "test_key.py"
    with open(test_key_path, "w") as f:
        f.write("""
from sample_module import process_data

def test_key_error():
    # This will fail - missing key
    data = {"wrong_key": 10}
    result = process_data(data)
    assert result == 20
""")

    # Create test file with import error
    test_import_path = temp_dir / "test_import.py"
    with open(test_import_path, "w") as f:
        f.write("""
# This will fail - module doesn't exist
from nonexistent_module import some_function

def test_import_error():
    assert some_function() == True
""")

    # Create test file with syntax error
    test_syntax_path = temp_dir / "test_syntax.py"
    with open(test_syntax_path, "w") as f:
        f.write("""
def test_syntax_error()
    # Missing colon above
    x = 1
    assert x == 1
""")

    return temp_dir


def demo_api_usage(test_dir):
    """Demonstrate using the pytest-analyzer as a Python API."""
    print("\n" + "="*80)
    print("DEMO 1: Using pytest-analyzer as a Python API")
    print("="*80)
    
    # Configure settings
    settings = Settings(
        max_failures=10,
        max_suggestions=2,
        min_confidence=0.5,
        preferred_format="json",
        project_root=test_dir
    )
    
    # Initialize the analyzer service
    analyzer = PytestAnalyzerService(settings=settings)
    
    # Run tests and analyze failures
    print(f"Running tests in {test_dir}")
    suggestions = analyzer.run_and_analyze(str(test_dir), ["--verbose"])
    
    # Display suggestions
    print(f"\nFound {len(suggestions)} suggestions:")
    for i, suggestion in enumerate(suggestions):
        print(f"\nSuggestion {i+1}:")
        print(f"Test: {suggestion.failure.test_name}")
        print(f"Error: {suggestion.failure.error_type}: {suggestion.failure.error_message}")
        print(f"Suggestion: {suggestion.suggestion}")
        print(f"Confidence: {suggestion.confidence}")
        if suggestion.explanation:
            print(f"Explanation: {suggestion.explanation}")


def demo_cli_usage(test_dir):
    """Demonstrate using the pytest-analyzer as a CLI tool."""
    print("\n" + "="*80)
    print("DEMO 2: Using pytest-analyzer as a CLI tool")
    print("="*80)
    
    # Simulate command-line arguments
    sys.argv = [
        "pytest-analyzer",
        str(test_dir),
        "--json",
        "--max-failures", "5",
        "--max-suggestions", "2",
        "--min-confidence", "0.5"
    ]
    
    # Call the CLI entry point
    print("Calling the CLI with arguments:", " ".join(sys.argv[1:]))
    cli_main()


def demo_different_extractors(test_dir):
    """Demonstrate using different extraction strategies."""
    print("\n" + "="*80)
    print("DEMO 3: Using different extraction strategies")
    print("="*80)
    
    strategies = ["json", "xml", "plugin"]
    
    for strategy in strategies:
        print(f"\nUsing {strategy.upper()} extraction strategy:")
        
        # Configure settings
        settings = Settings(
            max_failures=3,
            max_suggestions=1,
            preferred_format=strategy,
            project_root=test_dir
        )
        
        # Initialize the analyzer service
        analyzer = PytestAnalyzerService(settings=settings)
        
        # Run a specific test file to keep output focused
        test_file = test_dir / "test_assertion.py"
        
        try:
            suggestions = analyzer.run_and_analyze(str(test_file), ["--verbose"])
            
            # Display suggestions
            print(f"Found {len(suggestions)} suggestions for {test_file.name}")
            if suggestions:
                suggestion = suggestions[0]  # Just show the first one
                print(f"Error: {suggestion.failure.error_type}: {suggestion.failure.error_message}")
                print(f"Suggestion: {suggestion.suggestion}")
                print(f"Confidence: {suggestion.confidence}")
        except Exception as e:
            print(f"Error using {strategy} extractor: {e}")


def main():
    """Main function to run the demo."""
    print("pytest-analyzer Demo Script")
    print("--------------------------\n")
    
    # Create test files
    test_dir = create_test_files()
    print(f"Created test files in {test_dir}")
    
    try:
        # Run the different demos
        demo_api_usage(test_dir)
        demo_cli_usage(test_dir)
        demo_different_extractors(test_dir)
        
    except KeyboardInterrupt:
        print("\nDemo interrupted by user.")
    except Exception as e:
        print(f"\nError running demo: {e}")
    finally:
        print("\nDemo completed.")


if __name__ == "__main__":
    main()