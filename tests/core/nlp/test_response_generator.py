from src.pytest_analyzer.core.nlp.response_generator import NLResponseGenerator


def test_generate_response_clarification():
    gen = NLResponseGenerator()
    result = {"clarification": "Can you clarify your question?"}
    assert "clarify" in gen.generate(result)


def test_generate_response_normal():
    gen = NLResponseGenerator()
    result = {"response": "Here is your answer."}
    assert "answer" in gen.generate(result)
