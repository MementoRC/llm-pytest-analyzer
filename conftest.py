"""Global conftest for proper test isolation"""

import pytest


@pytest.fixture(autouse=True)
def isolate_llm_imports(monkeypatch):
    """
    Isolate LLM imports between tests to prevent state leakage.
    This is applied automatically to all tests.
    """
    # Save original state
    import sys

    original_modules = sys.modules.copy()

    yield

    # Restore original state after test
    # Remove any modules added during the test
    added_modules = []
    for module_name in sys.modules:
        if module_name not in original_modules:
            added_modules.append(module_name)

    for module_name in added_modules:
        if "pytest_analyzer.core.llm" in module_name:
            del sys.modules[module_name]
