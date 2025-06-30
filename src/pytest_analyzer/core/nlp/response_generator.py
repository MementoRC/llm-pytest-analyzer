"""
Response generator for NLQueryProcessor.
"""

from typing import Dict


class ResponseGenerator:
    """
    Generates user-friendly responses for NLQueryProcessor results.
    """

    def generate(self, result: Dict) -> str:
        if "clarification" in result:
            return f"🤔 {result['clarification']}"
        if "response" in result:
            return result["response"]
        return "Sorry, I could not process your query."


# Alias for backward compatibility
NLResponseGenerator = ResponseGenerator
