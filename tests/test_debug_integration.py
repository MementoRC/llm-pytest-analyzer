"""
Debug script to understand why integration test is failing
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from pytest_analyzer.core.backward_compat import PytestAnalyzerService
from pytest_analyzer.core.llm.llm_service import LLMService
from pytest_analyzer.utils.settings import Settings


def test_debug_integration():
    # Create a settings object with LLM enabled
    settings = Settings()
    settings.use_llm = True

    # Create a mock LLM client
    mock_llm_client = MagicMock()

    # Create a mock LLM service
    mock_llm_service = MagicMock(spec=LLMService)
    mock_llm_service.send_prompt.return_value = """```json
    [
        {
            "suggestion": "Mock LLM suggestion",
            "confidence": 0.9,
            "explanation": "Mock explanation from integration test",
            "code_changes": {
                "fixed_code": "def test_function():\\n    assert 1 == 1  # Fixed"
            }
        }
    ]
    ```"""

    # Create the service
    service = PytestAnalyzerService(settings=settings, llm_client=mock_llm_client)

    # Replace the llm_service with our mock
    service.llm_service = mock_llm_service

    # Debug: Check what's being replaced
    print(f"service.llm_service: {service.llm_service}")
    print("Service created successfully with LLM enabled")

    # Create a sample failure
    sample_json_path = (
        Path(__file__).parent / "sample_reports" / "assertion_fail_report.json"
    )

    # Analyze the report
    suggestions = service.analyze_pytest_output(sample_json_path)

    print(f"Suggestions count: {len(suggestions) if suggestions else 0}")
    print(f"Mock service call count: {mock_llm_service.send_prompt.call_count}")
    print(f"Mock service was called: {mock_llm_service.send_prompt.called}")

    if suggestions:
        llm_suggestions = [
            s for s in suggestions if s.metadata and s.metadata.get("source") == "llm"
        ]
        print(f"LLM suggestions count: {len(llm_suggestions)}")
        if llm_suggestions:
            print(f"First LLM suggestion: {llm_suggestions[0].suggestion_text}")


if __name__ == "__main__":
    test_debug_integration()
