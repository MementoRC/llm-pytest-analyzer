import pytest

from src.pytest_analyzer.core.nlp.intent_recognizer import IntentRecognizer


@pytest.fixture
def recognizer():
    return IntentRecognizer()


@pytest.mark.parametrize(
    "query,expected_intent",
    [
        ("Why did my test fail?", "get_failure_reason"),
        ("Suggest fix for this error", "suggest_fix"),
        ("Show test coverage", "get_coverage"),
        ("List all tests", "list_tests"),
        ("Rerun failed tests", "rerun_failed"),
        ("help", "help"),
        ("What is the weather?", "unknown"),
    ],
)
def test_intent_recognition(recognizer, query, expected_intent):
    intent = recognizer.recognize(query)
    assert intent.name == expected_intent
    assert 0.0 <= intent.confidence <= 1.0
