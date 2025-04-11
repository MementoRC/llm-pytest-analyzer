#!/usr/bin/env python3
"""
Example demonstrating how to use the pytest-analyzer with LLM integration.

This script shows how to:
1. Configure the analyzer to use LLM-based suggestions
2. Run analysis on failing tests
3. Display combined rule-based and LLM-based suggestions
"""

import os
import sys
import tempfile
from pathlib import Path

# Add the project root to the path to ensure imports work
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from pytest_analyzer import PytestAnalyzerService, Settings


def create_test_files():
    """Create sample test files for demonstration."""
    temp_dir = tempfile.mkdtemp(prefix="pytest_analyzer_llm_demo_")
    temp_path = Path(temp_dir)
    
    # Create a module with a bug
    module_path = temp_path / "example_module.py"
    with open(module_path, "w") as f:
        f.write("""
def calculate_average(numbers):
    \"\"\"Calculate the average of a list of numbers.\"\"\"
    total = sum(numbers)
    # Bug: doesn't handle empty list case
    return total / len(numbers)

def filter_even_numbers(numbers):
    \"\"\"Filter out odd numbers from a list.\"\"\"
    # Bug: wrong comparison operator
    return [num for num in numbers if num / 2 == 0]
""")
    
    # Create a test file
    test_path = temp_path / "test_example.py"
    with open(test_path, "w") as f:
        f.write("""
import pytest
from example_module import calculate_average, filter_even_numbers

def test_calculate_average():
    # This will fail when the list is empty (division by zero)
    result = calculate_average([])
    assert result == 0

def test_filter_even_numbers():
    # This will fail because the filtering is incorrect
    result = filter_even_numbers([1, 2, 3, 4, 5, 6])
    assert result == [2, 4, 6]
""")
    
    return temp_path


def main():
    """Run the analyzer with LLM suggestions enabled."""
    print("pytest-analyzer LLM Integration Example")
    print("-------------------------------------\n")
    
    # Create test files
    test_dir = create_test_files()
    print(f"Created test files in: {test_dir}")
    
    # Configure settings with LLM enabled
    settings = Settings(
        max_failures=5,
        max_suggestions=3,
        max_suggestions_per_failure=2,
        min_confidence=0.5,
        use_llm=True,
        llm_timeout=60,
        project_root=test_dir
    )
    
    # Check if we have API keys for LLM services
    if "ANTHROPIC_API_KEY" in os.environ:
        print("Using Anthropic API key from environment")
        settings.llm_api_key = os.environ.get("ANTHROPIC_API_KEY")
        settings.llm_model = "claude-3-haiku-20240307"
    elif "OPENAI_API_KEY" in os.environ:
        print("Using OpenAI API key from environment")
        settings.llm_api_key = os.environ.get("OPENAI_API_KEY")
        settings.llm_model = "gpt-3.5-turbo"
    else:
        print("No API keys found for LLM services. Using rule-based suggestions only.")
        settings.use_llm = False
    
    # Initialize the analyzer service
    analyzer = PytestAnalyzerService(settings=settings)
    
    try:
        # Run and analyze the tests
        print("\nRunning and analyzing tests...")
        suggestions = analyzer.run_and_analyze(str(test_dir), ["--verbose"])
        
        if not suggestions:
            print("\nNo suggestions found.")
            return
        
        # Display the results
        print(f"\nFound {len(suggestions)} suggestions:")
        
        for i, suggestion in enumerate(suggestions):
            print(f"\n--- Suggestion {i+1}/{len(suggestions)} ---")
            
            # Basic information
            failure = suggestion.failure
            print(f"Test: {failure.test_name}")
            print(f"Error: {failure.error_type}: {failure.error_message}")
            
            # Determine the source of the suggestion
            source = "LLM" if suggestion.code_changes and suggestion.code_changes.get('source') == 'llm' else "Rule-based"
            print(f"Source: {source}")
            
            # Display the suggestion and confidence
            print(f"Suggestion: {suggestion.suggestion}")
            print(f"Confidence: {suggestion.confidence:.2f}")
            
            # Display explanation if available
            if suggestion.explanation:
                print(f"Explanation: {suggestion.explanation}")
            
            # Display code changes if available
            if suggestion.code_changes and 'fixed_code' in suggestion.code_changes:
                print("\nProposed Code:")
                print(suggestion.code_changes['fixed_code'])
        
    except Exception as e:
        print(f"Error running the analyzer: {e}")


if __name__ == "__main__":
    main()