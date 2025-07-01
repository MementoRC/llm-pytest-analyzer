"""
Intent recognition for natural language queries in pytest-analyzer.
"""

from typing import Dict, Optional


class QueryIntent:
    """Represents a recognized intent from a user query."""

    def __init__(self, name: str, confidence: float, entities: Optional[Dict] = None):
        self.name = name
        self.confidence = confidence
        self.entities = entities or {}


# Alias for backward compatibility
Intent = QueryIntent


class IntentRecognizer:
    """
    Recognizes user intent from natural language queries.
    Uses simple rules and LLM fallback for ambiguous cases.
    """

    def __init__(self, llm_service=None):
        self.llm_service = llm_service

    def recognize(self, query: str) -> QueryIntent:
        """
        Recognize the intent of a query.
        Returns an Intent object.
        """
        # Simple rule-based mapping for common queries
        q = query.lower().strip()
        # Order matters - check more specific patterns first
        if "rerun" in q and "failed" in q:
            return QueryIntent("rerun_failed", 0.9)
        if "failed test" in q or "why did my test fail" in q:
            return QueryIntent("get_failure_reason", 0.95)
        if "suggest fix" in q or "how do i fix" in q:
            return QueryIntent("suggest_fix", 0.95)
        if "test coverage" in q or "how much is covered" in q:
            return QueryIntent("get_coverage", 0.9)
        if "list" in q and "tests" in q:
            return QueryIntent("list_tests", 0.9)
        if "help" in q or "what can i ask" in q:
            return QueryIntent("help", 0.99)

        # Fallback to LLM for ambiguous queries
        if self.llm_service:
            prompt = (
                f"Classify the following user query into one of these intents: "
                f"get_failure_reason, suggest_fix, get_coverage, list_tests, rerun_failed, help. "
                f"Return the intent name and a confidence score between 0 and 1.\n"
                f"Query: {query}"
            )
            response = self.llm_service.send_prompt(prompt)
            # Expecting response like: "suggest_fix, 0.8"
            try:
                name, conf = response.split(",")
                return QueryIntent(name.strip(), float(conf.strip()))
            except Exception:
                return QueryIntent("unknown", 0.0)
        return QueryIntent("unknown", 0.0)
