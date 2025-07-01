import pytest

from src.pytest_analyzer.core.nlp.query_processor import NLQueryProcessor


class DummyLLM:
    def send_prompt(self, prompt):
        return "help, 0.99"


@pytest.fixture
def processor():
    return NLQueryProcessor(llm_service=DummyLLM())


def test_process_known_query(processor):
    result = processor.process_query("help")
    assert result["intent"] == "help"
    assert "response" in result


def test_process_unknown_query(processor):
    result = processor.process_query("What is the weather?")
    assert result["intent"] == "help" or result["intent"] == "unknown"


def test_autocomplete(processor):
    completions = processor.suggest_autocomplete("show")
    assert isinstance(completions, list)
