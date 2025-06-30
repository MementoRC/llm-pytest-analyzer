"""
NLQueryProcessor for pytest-analyzer: maps natural language queries to API actions.
"""

from typing import Any, Dict, List, Optional

from ..llm.llm_service import LLMService
from ..llm.llm_service_protocol import LLMServiceProtocol
from .intent_recognizer import IntentRecognizer


class NLQueryProcessor:
    """
    Processes natural language queries, recognizes intent, and maps to API actions.
    Supports multi-turn conversations and clarification.
    """

    def __init__(
        self,
        llm_service: Optional[LLMServiceProtocol] = None,
        settings: Optional[Any] = None,
    ):
        self.llm_service = llm_service or LLMService()
        self.intent_recognizer = IntentRecognizer(self.llm_service)
        self.settings = settings
        self.conversation_history: List[Dict] = []

    def process_query(self, query: str, context: Optional[Dict] = None) -> Dict:
        """
        Process a user query, recognize intent, and return a response dict.
        Handles clarification and multi-turn context.
        """
        context = context or {}
        self.conversation_history.append({"user": query})

        # Recognize intent
        intent = self.intent_recognizer.recognize(query)
        response = {"intent": intent.name, "confidence": intent.confidence}

        # Handle ambiguous/unknown intent
        if intent.name == "unknown" or intent.confidence < 0.5:
            clarification = self.suggest_clarification(query)
            response["clarification"] = clarification
            response["response"] = clarification
            self.conversation_history.append({"system": clarification})
            return response

        # Map intent to action
        handler = getattr(self, f"_handle_{intent.name}", None)
        if handler:
            result = handler(query, context)
            response.update(result)
        else:
            response["response"] = (
                f"Sorry, I don't know how to handle intent '{intent.name}'."
            )
        self.conversation_history.append({"system": response.get("response", "")})
        return response

    def suggest_clarification(self, query: str) -> str:
        """Suggest clarification for ambiguous queries using LLM."""
        prompt = (
            f"The following user query is ambiguous or unclear: '{query}'. "
            f"Suggest a clarifying question to ask the user."
        )
        clarification = self.llm_service.send_prompt(prompt)
        return clarification.strip()

    def suggest_autocomplete(self, partial_query: str) -> List[str]:
        """Suggest query autocompletions using LLM."""
        prompt = (
            f"Suggest 3 possible ways to complete this partial query for a pytest analyzer: '{partial_query}'. "
            f"Return as a comma-separated list."
        )
        completions = self.llm_service.send_prompt(prompt)
        return [c.strip() for c in completions.split(",") if c.strip()]

    # --- Intent Handlers ---

    def _handle_get_failure_reason(self, query: str, context: Dict) -> Dict:
        # Example: call failure analyzer and return summary
        return {
            "response": "To get failure reasons, use the 'analyze_failure' API or CLI."
        }

    def _handle_suggest_fix(self, query: str, context: Dict) -> Dict:
        return {
            "response": "To get fix suggestions, use the 'suggest_fixes' tool or CLI."
        }

    def _handle_get_coverage(self, query: str, context: Dict) -> Dict:
        return {
            "response": "To get test coverage, use the 'get_test_coverage' tool or CLI."
        }

    def _handle_list_tests(self, query: str, context: Dict) -> Dict:
        return {
            "response": "To list tests, use 'pytest --collect-only' or the test discovery API."
        }

    def _handle_rerun_failed(self, query: str, context: Dict) -> Dict:
        return {"response": "To rerun failed tests, use 'pytest --last-failed'."}

    def _handle_help(self, query: str, context: Dict) -> Dict:
        return {
            "response": (
                "You can ask about test failures, request fix suggestions, "
                "inquire about test coverage, list tests, rerun failed tests, or ask for help."
            )
        }
