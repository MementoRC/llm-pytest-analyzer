Getting Started with pytest-analyzer
====================================

pytest-analyzer is a tool for analyzing pytest test failures and generating intelligent fix suggestions.

Installation
------------

Install from source:

.. code-block:: bash

    pip install -e /path/to/pytest_analyzer

Or, once published:

.. code-block:: bash

    pip install pytest-analyzer

Basic Usage
-----------

**Command Line:**

.. code-block:: bash

    pytest-analyzer path/to/tests

**Python API:**

.. code-block:: python

    from pytest_analyzer import PytestAnalyzerService, Settings

    # Configure settings
    settings = Settings(
        max_failures=10,
        max_suggestions=3,
        min_confidence=0.7,
        preferred_format="json"
    )

    # Initialize the analyzer service
    analyzer = PytestAnalyzerService(settings=settings)

    # Run tests and analyze failures
    suggestions = analyzer.run_and_analyze("tests/", ["--verbose"])

    # Analyze existing output file
    suggestions = analyzer.analyze_pytest_output("pytest_output.json")

    # Process suggestions
    for suggestion in suggestions:
        print(f"Test: {suggestion.failure.test_name}")
        print(f"Error: {suggestion.failure.error_type}: {suggestion.failure.error_message}")
        print(f"Suggestion: {suggestion.suggestion}")
        print(f"Confidence: {suggestion.confidence}")

For more advanced usage, see the :doc:`api_reference`.
