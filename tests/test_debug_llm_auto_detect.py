from pytest_analyzer.core.llm.backward_compat import LLMService


def test_check_global_vars(monkeypatch):
    """Test to check the actual values of imports during test"""
    with monkeypatch.context() as m:
        # Force Anthropic to None to see if that's affecting other tests
        m.setattr("pytest_analyzer.core.llm.llm_service.Anthropic", None)

        import pytest_analyzer.core.llm.llm_service

        print(f"Anthropic = {pytest_analyzer.core.llm.llm_service.Anthropic}")
        print(f"openai = {pytest_analyzer.core.llm.llm_service.openai}")

        # Now create service to see what happens
        service = LLMService()
        print(f"service._llm_request_func = {service._llm_request_func}")

    # Check again after exiting context
    from pytest_analyzer.core.llm import llm_service as fresh_module

    print(f"After: Anthropic = {fresh_module.Anthropic}")
    print(f"After: openai = {fresh_module.openai}")
