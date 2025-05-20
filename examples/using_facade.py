#!/usr/bin/env python3
"""
Example script demonstrating how to use the PytestAnalyzerFacade.

This script shows three different ways to use the pytest analyzer:
1. Using the legacy PytestAnalyzerService class (backward compatible)
2. Using the new PytestAnalyzerFacade class directly
3. Using the DI-based DIPytestAnalyzerService with the container

All three approaches provide the same functionality but with different
levels of flexibility and integration with the new architecture.
"""

import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)


# ----- Example 1: Using the legacy PytestAnalyzerService class -----
def example_legacy_service():
    """Example using the legacy PytestAnalyzerService class."""
    print("\n--- Example 1: Using Legacy PytestAnalyzerService ---")

    from pytest_analyzer.core.analyzer_service import PytestAnalyzerService
    from pytest_analyzer.utils.settings import Settings

    # Create settings with custom configuration
    settings = Settings(
        project_root=".",
        use_llm=False,
        min_confidence=0.7,
    )

    # Create service instance
    service = PytestAnalyzerService(settings=settings)

    # Example: Analyze a test results file
    # For demonstration only - replace with actual file path
    sample_path = Path("tests/sample_reports/assertion_fail_report.xml")
    if sample_path.exists():
        suggestions = service.analyze_pytest_output(sample_path)
        print(f"Generated {len(suggestions)} fix suggestions")
    else:
        print(f"Sample file {sample_path} not found. This is a demonstration only.")

    # Example: Run tests and analyze on the fly
    # In real usage, replace with actual test path
    print("Example usage of run_and_analyze method (not actually running):")
    print("suggestions = service.run_and_analyze('tests/unit/')")


# ----- Example 2: Using the new PytestAnalyzerFacade directly -----
def example_facade_direct():
    """Example using the PytestAnalyzerFacade class directly."""
    print("\n--- Example 2: Using PytestAnalyzerFacade Directly ---")

    from pytest_analyzer.core.analyzer_facade import PytestAnalyzerFacade
    from pytest_analyzer.utils.settings import Settings

    # Create settings with custom configuration
    settings = Settings(
        project_root=".",
        use_llm=False,
        min_confidence=0.7,
    )

    # Create facade instance
    facade = PytestAnalyzerFacade(settings=settings)

    # Example: Analyze a test results file
    # For demonstration only - replace with actual file path
    sample_path = Path("tests/sample_reports/assertion_fail_report.xml")
    if sample_path.exists():
        suggestions = facade.analyze_pytest_output(sample_path)
        print(f"Generated {len(suggestions)} fix suggestions")
    else:
        print(f"Sample file {sample_path} not found. This is a demonstration only.")

    # Example: Raw input text analysis
    print("Example usage of analyze_test_results method:")
    print("result = facade.analyze_test_results('... pytest output text ...')")


# ----- Example 3: Using the DI-based DIPytestAnalyzerService -----
def example_di_service():
    """Example using DIPytestAnalyzerService with the DI container."""
    print("\n--- Example 3: Using DI-based Service ---")

    from pytest_analyzer.core.analyzer_service_di import DIPytestAnalyzerService
    from pytest_analyzer.core.di import initialize_container
    from pytest_analyzer.utils.settings import Settings

    # Create settings with custom configuration
    settings = Settings(
        project_root=".",
        use_llm=False,
        min_confidence=0.7,
    )

    # Initialize container with settings
    container = initialize_container(settings)

    try:
        # Resolve service from container and verify it works
        container.resolve(DIPytestAnalyzerService)

        print("Successfully resolved DIPytestAnalyzerService from container")

        # Example usage
        print("Example usage with DI service:")
        print("analyzer = container.resolve(DIPytestAnalyzerService)")
        print("suggestions = analyzer.run_and_analyze('tests/unit/')")
        print("results = analyzer.analyze_results(test_failures)")

    except Exception as e:
        print(f"Error resolving service: {e}")
        print("This example may not work in all environments.")


if __name__ == "__main__":
    example_legacy_service()
    example_facade_direct()
    example_di_service()
