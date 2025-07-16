import logging
import sqlite3  # Added import for sqlite3
import threading
from typing import Any, Dict, List, Optional, Union

try:
    import tiktoken
except ImportError:
    tiktoken = None  # type: ignore[assignment]
    logging.warning(
        "tiktoken not installed. OpenAI token estimation will be less accurate. "
        "Install with 'pip install tiktoken'."
    )

from pytest_analyzer.core.cross_cutting.error_handling import (
    error_handler,  # Added import for error_handler
)
from pytest_analyzer.core.cross_cutting.monitoring.metrics import ApplicationMetrics
from pytest_analyzer.core.errors import BaseError
from pytest_analyzer.metrics.efficiency_tracker import EfficiencyTracker
from pytest_analyzer.utils.config_types import Settings

logger = logging.getLogger(__name__)


class TokenTrackerError(BaseError):
    """Base exception for TokenTracker related errors."""

    pass


class TokenTracker(EfficiencyTracker):
    """
    Comprehensive TokenTracker for LLM token consumption, extending EfficiencyTracker.

    Provides:
    - Real-time token counting hooks for LLM API calls.
    - Provider-specific token estimation (OpenAI, Anthropic, Azure).
    - Token budget management and alerts.
    - Detailed token analytics and reporting.
    - Token usage optimization suggestions.
    """

    # Estimated costs per 1k tokens (as of early 2024, subject to change)
    # These are examples and should be updated with actual pricing.
    # Input / Output costs
    _TOKEN_COST_RATES_PER_1K = {
        "openai": {
            "gpt-4": {"input": 0.03, "output": 0.06},
            "gpt-4-32k": {"input": 0.06, "output": 0.12},
            "gpt-3.5-turbo": {"input": 0.0015, "output": 0.002},
            "gpt-3.5-turbo-16k": {"input": 0.003, "output": 0.004},
            "text-embedding-ada-002": {
                "input": 0.0001,
                "output": 0.0001,
            },  # Embedding models
        },
        "anthropic": {
            "claude-3-opus-20240229": {"input": 0.015, "output": 0.075},
            "claude-3-sonnet-20240229": {"input": 0.003, "output": 0.015},
            "claude-3-haiku-20240307": {"input": 0.00025, "output": 0.00125},
        },
        "azure": {  # Azure typically mirrors OpenAI pricing but can vary
            "gpt-4": {"input": 0.03, "output": 0.06},
            "gpt-35-turbo": {"input": 0.0015, "output": 0.002},
        },
        "together": {  # Example for Together.ai, pricing varies by model
            "mistralai/Mixtral-8x7B-Instruct-v0.1": {"input": 0.0006, "output": 0.0006},
        },
        "ollama": {  # Ollama is typically free (local), but can have operational costs
            "default": {"input": 0.0, "output": 0.0},
        },
        "mock": {  # For testing/mock scenarios
            "default": {"input": 0.0, "output": 0.0},
        },
    }

    # Default token budgets per operation type (in USD)
    _DEFAULT_TOKEN_BUDGETS_USD = {
        "analysis": 0.50,
        "fix_suggestion": 0.75,
        "validation": 0.25,
        "general": 1.00,  # For general LLM interactions
    }

    def __init__(self, settings: Settings, metrics_client: ApplicationMetrics):
        """
        Initialize the TokenTracker.

        Args:
            settings: Application settings.
            metrics_client: Metrics client for reporting.
        """
        super().__init__(settings, metrics_client)
        self._token_budgets_usd: Dict[str, float] = (
            self._DEFAULT_TOKEN_BUDGETS_USD.copy()
        )
        self._current_session_realtime_tokens: Dict[
            str, int
        ] = {}  # operation_type -> tokens
        self._current_session_realtime_cost: float = 0.0
        self._lock = threading.Lock()  # Inherits lock from EfficiencyTracker, but good to be explicit for new fields

    @error_handler(
        "start token tracking session", TokenTrackerError, logger=logger, reraise=True
    )
    def start_session(self) -> Optional[int]:
        """
        Starts a new tracking session and resets real-time counters.
        Overrides parent to add real-time counter reset.
        """
        session_id = super().start_session()
        with self._lock:
            self._current_session_realtime_tokens = {
                op: 0 for op in self._DEFAULT_TOKEN_BUDGETS_USD.keys()
            }
            self._current_session_realtime_cost = 0.0
        logger.info(
            f"TokenTracker session {session_id} started. Real-time counters reset."
        )
        return session_id

    @error_handler(
        "end token tracking session", TokenTrackerError, logger=logger, reraise=True
    )
    def end_session(self) -> Optional[float]:
        """
        Ends the current tracking session.
        Overrides parent to log final real-time stats.
        """
        score = super().end_session()
        with self._lock:
            logger.info(
                f"TokenTracker session ended. Final real-time tokens: {self._current_session_realtime_tokens}, cost: ${self._current_session_realtime_cost:.4f}"
            )
            self._current_session_realtime_tokens = {}
            self._current_session_realtime_cost = 0.0
        return score

    @error_handler("estimate tokens", TokenTrackerError, logger=logger, reraise=False)
    def _estimate_tokens(self, text: str, model: str, provider: str) -> int:
        """
        Estimates the number of tokens for a given text and model.
        Uses tiktoken for OpenAI models, simple char count for others.
        """
        if not text:
            return 0

        if provider == "openai" and tiktoken:
            try:
                encoding = tiktoken.encoding_for_model(model)
                return len(encoding.encode(text))
            except KeyError:
                logger.warning(
                    f"Unknown OpenAI model '{model}' for tiktoken. Falling back to character count."
                )
                return len(text) // 4  # Rough estimate
            except Exception as e:
                logger.warning(
                    f"Error with tiktoken for model '{model}': {e}. Falling back to character count."
                )
                return len(text) // 4
        elif provider == "anthropic":
            # Anthropic's tokenization is roughly character-based for English
            # A common heuristic is char_count / 4 or 5.
            return len(text) // 4
        else:
            # Generic fallback for other providers or if tiktoken is not available
            return len(text) // 4  # Rough estimate

    @error_handler(
        "estimate token cost", TokenTrackerError, logger=logger, reraise=False
    )
    def _estimate_cost(
        self, input_tokens: int, output_tokens: int, provider: str, model: str
    ) -> float:
        """
        Estimates the cost in USD for a given number of input and output tokens.
        """
        provider_costs = self._TOKEN_COST_RATES_PER_1K.get(provider.lower())
        if not provider_costs:
            logger.warning(
                f"No cost rates found for provider: {provider}. Assuming 0 cost."
            )
            return 0.0

        model_costs = provider_costs.get(model.lower())
        if not model_costs:
            # Try to find a generic model cost if specific model not found
            model_costs = provider_costs.get("default")
            if not model_costs:
                logger.warning(
                    f"No cost rates found for model: {model} under provider: {provider}. Assuming 0 cost."
                )
                return 0.0

        input_cost_per_1k = model_costs.get("input", 0.0)
        output_cost_per_1k = model_costs.get("output", 0.0)

        cost = (input_tokens / 1000 * input_cost_per_1k) + (
            output_tokens / 1000 * output_cost_per_1k
        )
        return cost

    @error_handler("track LLM call", TokenTrackerError, logger=logger, reraise=False)
    def track_llm_call(
        self,
        prompt: str,
        response: str,
        operation_type: str,
        provider: str,
        model: str,
    ) -> None:
        """
        Tracks token consumption for an LLM API call, including estimation and budget checks.

        Args:
            prompt: The input prompt sent to the LLM.
            response: The response received from the LLM.
            operation_type: The type of operation (e.g., "analysis", "fix_suggestion", "validation").
            provider: The LLM provider (e.g., "openai", "anthropic").
            model: The specific LLM model used (e.g., "gpt-4", "claude-3-sonnet").
        """
        input_tokens = self._estimate_tokens(prompt, model, provider) or 0
        output_tokens = self._estimate_tokens(response, model, provider) or 0
        total_tokens = input_tokens + output_tokens
        estimated_cost = self._estimate_cost(
            input_tokens, output_tokens, provider, model
        )

        # Use the parent's method to persist the detailed token consumption
        super().track_token_consumption(
            total_tokens, operation_type, provider, estimated_cost
        )

        with self._lock:
            self._current_session_realtime_tokens.setdefault(operation_type, 0)
            self._current_session_realtime_tokens[operation_type] += total_tokens
            self._current_session_realtime_cost += estimated_cost or 0

            self._check_budget(operation_type, self._current_session_realtime_cost)

        self.metrics_client.gauge("llm_tokens_used_total", total_tokens)  # type: ignore[attr-defined]
        self.metrics_client.gauge("llm_cost_usd_total", estimated_cost)  # type: ignore[attr-defined]
        self.metrics_client.gauge(  # type: ignore[attr-defined]
            f"llm_tokens_used_by_op_{operation_type}", total_tokens
        )
        self.metrics_client.gauge(  # type: ignore[attr-defined]
            f"llm_cost_usd_by_op_{operation_type}", estimated_cost
        )
        self.metrics_client.gauge(  # type: ignore[attr-defined]
            f"llm_tokens_used_by_provider_{provider}", total_tokens
        )
        self.metrics_client.gauge(  # type: ignore[attr-defined]
            f"llm_cost_usd_by_provider_{provider}", estimated_cost
        )

        logger.debug(
            f"LLM call tracked: {total_tokens} tokens, ${estimated_cost:.4f} "
            f"({operation_type}, {provider}/{model}). "
            f"Real-time session cost: ${self._current_session_realtime_cost:.4f}"
        )

    @error_handler("set token budget", TokenTrackerError, logger=logger, reraise=False)
    def set_budget(self, operation_type: str, budget_usd: float) -> None:
        """
        Sets a token budget for a specific operation type.

        Args:
            operation_type: The type of operation.
            budget_usd: The budget in USD.
        """
        if budget_usd < 0:
            raise ValueError("Budget must be non-negative.")
        with self._lock:
            self._token_budgets_usd[operation_type] = budget_usd
        logger.info(f"Set budget for '{operation_type}' to ${budget_usd:.2f}")

    @error_handler(
        "check token budget", TokenTrackerError, logger=logger, reraise=False
    )
    def _check_budget(self, operation_type: str, current_cost: float) -> None:
        """
        Checks if the current cost for an operation type exceeds its budget and logs an alert.
        """
        budget = self._token_budgets_usd.get(operation_type)
        if budget is None:
            logger.debug(f"No budget set for operation type '{operation_type}'.")
            return

        if current_cost > budget:
            logger.warning(
                f"🚨 Token budget alert for '{operation_type}': "
                f"Current cost ${current_cost:.4f} exceeds budget ${budget:.2f}!"
            )
            self.metrics_client.increment(f"llm_budget_exceeded_{operation_type}")  # type: ignore[attr-defined]
        elif current_cost > budget * 0.8:
            logger.info(
                f"⚠️ Token budget warning for '{operation_type}': "
                f"Current cost ${current_cost:.4f} is approaching budget ${budget:.2f} (80% threshold)."
            )

    def get_realtime_token_usage(self) -> Dict[str, int]:
        """Returns real-time token usage for the current session by operation type."""
        with self._lock:
            return self._current_session_realtime_tokens.copy()

    def get_realtime_token_cost(self) -> float:
        """Returns real-time estimated token cost for the current session."""
        with self._lock:
            return self._current_session_realtime_cost

    @error_handler(
        "get detailed token analytics", TokenTrackerError, logger=logger, reraise=True
    )
    def get_detailed_analytics(
        self, session_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Retrieves detailed token analytics, leveraging parent's methods.
        """
        return {
            "total_tokens": self.get_session_data(session_id).get("total_tokens", 0),
            "total_estimated_cost_usd": self.get_total_estimated_cost(session_id),
            "tokens_by_operation": self.get_token_usage_by_operation(session_id),
            "tokens_by_provider": self.get_token_usage_by_provider(session_id),
            "realtime_tokens_by_operation": self.get_realtime_token_usage()
            if session_id == self._current_session_id
            else {},
            "realtime_cost_usd": self.get_realtime_token_cost()
            if session_id == self._current_session_id
            else 0.0,
        }

    @error_handler("get session data", TokenTrackerError, logger=logger, reraise=True)
    def get_session_data(self, session_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Retrieves comprehensive data for a specific session or the current one.
        """
        target_session_id = (
            session_id if session_id is not None else self._current_session_id
        )
        if target_session_id is None:
            return {}  # No active or specified session

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, start_time, end_time, total_tokens, total_fixes, successful_fixes,
                       efficiency_score, total_analysis_tokens, total_fix_suggestion_tokens,
                       total_validation_tokens, total_estimated_cost_usd
                FROM sessions WHERE id = ?
                """,
                (target_session_id,),
            )
            row = cursor.fetchone()
            if not row:
                return {}

            columns = [
                "id",
                "start_time",
                "end_time",
                "total_tokens",
                "total_fixes",
                "successful_fixes",
                "efficiency_score",
                "total_analysis_tokens",
                "total_fix_suggestion_tokens",
                "total_validation_tokens",
                "total_estimated_cost_usd",
            ]
            session_data = dict(zip(columns, row))
            return session_data

    @error_handler(
        "generate token optimization suggestions",
        TokenTrackerError,
        logger=logger,
        reraise=True,
    )
    def generate_optimization_suggestions(self) -> List[str]:
        """
        Generates token usage optimization suggestions based on current and historical data.
        Overrides and enhances the parent's recommendation method.
        """
        suggestions = (
            super().generate_recommendations()
        )  # Get general recommendations first

        current_session_id = self._current_session_id
        if current_session_id is None:
            # If no active session, try to get data from the last completed session
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT total_tokens, total_estimated_cost_usd, total_analysis_tokens,
                           total_fix_suggestion_tokens, total_validation_tokens
                    FROM sessions
                    WHERE end_time IS NOT NULL
                    ORDER BY start_time DESC
                    LIMIT 1
                """)
                row = cursor.fetchone()
                if not row:
                    return suggestions  # No data, return only general suggestions

                (
                    total_tokens,
                    total_estimated_cost_usd,
                    total_analysis_tokens,
                    total_fix_suggestion_tokens,
                    total_validation_tokens,
                ) = row
        else:
            # Use current session data
            session_data = self.get_session_data(current_session_id)
            total_tokens = session_data.get("total_tokens", 0)
            total_estimated_cost_usd = session_data.get("total_estimated_cost_usd", 0.0)
            total_analysis_tokens = session_data.get("total_analysis_tokens", 0)
            total_fix_suggestion_tokens = session_data.get(
                "total_fix_suggestion_tokens", 0
            )
            total_validation_tokens = session_data.get("total_validation_tokens", 0)

        if total_tokens == 0:
            return suggestions  # No token usage to analyze

        # Analyze token distribution by operation type
        op_tokens = {
            "analysis": total_analysis_tokens,
            "fix_suggestion": total_fix_suggestion_tokens,
            "validation": total_validation_tokens,
        }
        sorted_ops = sorted(op_tokens.items(), key=lambda item: item[1], reverse=True)

        if total_estimated_cost_usd > self._DEFAULT_TOKEN_BUDGETS_USD.get(
            "general", 0.0
        ):
            suggestions.append(
                f"💰 High overall LLM cost (${total_estimated_cost_usd:.2f}). Consider optimizing prompts."
            )

        if (
            sorted_ops and sorted_ops[0][1] > total_tokens * 0.5
        ):  # If one operation dominates token usage
            suggestions.append(
                f"🔍 '{sorted_ops[0][0]}' operations consume {sorted_ops[0][1] / total_tokens:.1%} of tokens. Focus on optimizing prompts for this type of task."
            )

        # Check for high token usage per fix
        successful_fixes = self.get_session_data(current_session_id).get(
            "successful_fixes", 0
        )
        if (
            successful_fixes > 0 and total_tokens / successful_fixes > 250
        ):  # Arbitrary threshold
            suggestions.append(
                "💡 Average tokens per successful fix is high. Try to make prompts more concise or use smaller models for initial drafts."
            )

        # Provider-specific suggestions (example)
        tokens_by_provider = self.get_token_usage_by_provider(current_session_id)
        if tokens_by_provider:
            for provider, tokens in tokens_by_provider.items():
                if provider.lower() == "openai" and tokens > 0:
                    suggestions.append(
                        "⚡ For OpenAI models, consider using `gpt-3.5-turbo` for less complex tasks to reduce cost."
                    )
                elif provider.lower() == "anthropic" and tokens > 0:
                    suggestions.append(
                        "⚡ For Anthropic models, `claude-3-haiku` is very cost-effective for simpler tasks."
                    )

        # General optimization tips
        suggestions.append(
            "📝 Review LLM prompts for verbosity. Can you achieve the same result with fewer words?"
        )
        suggestions.append(
            "📏 Experiment with different LLM models. Smaller models can be more cost-effective for certain tasks."
        )
        suggestions.append(
            "🔄 Implement prompt chaining or multi-step reasoning to break down complex tasks and reduce single-call token usage."
        )

        return list(set(suggestions))  # Remove duplicates
