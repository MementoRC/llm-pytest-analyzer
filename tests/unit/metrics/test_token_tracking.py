import logging
import os
import sqlite3
import tempfile
import unittest
from typing import List  # Added import for List
from unittest.mock import MagicMock, patch

from pytest_analyzer.core.infrastructure.llm.anthropic_service import AnthropicService
from pytest_analyzer.core.infrastructure.llm.openai_service import OpenAIService
from pytest_analyzer.core.infrastructure.llm.token_tracking_interceptor import (
    TokenTrackingInterceptor,
)
from pytest_analyzer.metrics.efficiency_tracker import (  # Added import for EfficiencyTracker
    EfficiencyTracker,
    EfficiencyTrackerError,
)
from pytest_analyzer.metrics.token_tracker import TokenTracker
from pytest_analyzer.utils.config_types import Settings

# Configure logging for tests
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class TestTokenTracking(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for the database
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "efficiency_metrics.db")

        self.settings = Settings(project_root=self.temp_dir.name)
        self.metrics_client = MagicMock()
        # Manually add the required methods for the mock
        self.metrics_client.gauge = MagicMock()
        self.metrics_client.increment = MagicMock()

        # Patch sqlite3.connect to use the temporary database, avoiding recursion
        # Store the original function before patching
        original_connect = sqlite3.connect

        def mock_sqlite_connect(path):
            # Use the original function to avoid recursion
            real_conn = original_connect(self.db_path)
            return real_conn

        self.patcher = patch("sqlite3.connect", side_effect=mock_sqlite_connect)
        self.mock_sqlite_connect = self.patcher.start()

        # Initialize EfficiencyTracker (parent class) for basic tests
        self.efficiency_tracker = EfficiencyTracker(self.settings, self.metrics_client)
        self.efficiency_tracker._init_database()  # Ensure DB is initialized for parent

        # Initialize TokenTracker
        self.token_tracker = TokenTracker(self.settings, self.metrics_client)
        self.token_tracker._init_database()  # Ensure DB is initialized for TokenTracker

    def tearDown(self):
        self.patcher.stop()
        self.temp_dir.cleanup()

    def _get_session_data_from_db(self, session_id: int) -> dict:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, start_time, end_time, total_tokens, total_fixes, successful_fixes,
                   efficiency_score, total_analysis_tokens, total_fix_suggestion_tokens,
                   total_validation_tokens, total_estimated_cost_usd
            FROM sessions WHERE id = ?
            """,
            (session_id,),
        )
        row = cursor.fetchone()
        conn.close()
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
        return dict(zip(columns, row))

    def _get_token_usage_by_type_from_db(self, session_id: int) -> List[dict]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT operation_type, provider, tokens, estimated_cost_usd, timestamp
            FROM token_usage_by_type WHERE session_id = ?
            """,
            (session_id,),
        )
        rows = cursor.fetchall()
        conn.close()
        columns = [
            "operation_type",
            "provider",
            "tokens",
            "estimated_cost_usd",
            "timestamp",
        ]
        return [dict(zip(columns, row)) for row in rows]

    # --- EfficiencyTracker (Enhanced) Tests ---
    def test_efficiency_tracker_session_fields_updated(self):
        session_id = self.efficiency_tracker.start_session()
        self.efficiency_tracker.track_token_consumption(
            100, "analysis", "openai", 0.001
        )
        self.efficiency_tracker.track_token_consumption(
            50, "fix_suggestion", "anthropic", 0.0005
        )
        self.efficiency_tracker.record_auto_fix(True)
        self.efficiency_tracker.end_session()

        session_data = self._get_session_data_from_db(session_id)
        self.assertIsNotNone(session_data)
        self.assertEqual(session_data["total_tokens"], 150)
        self.assertEqual(session_data["total_analysis_tokens"], 100)
        self.assertEqual(session_data["total_fix_suggestion_tokens"], 50)
        self.assertEqual(session_data["total_validation_tokens"], 0)
        self.assertAlmostEqual(session_data["total_estimated_cost_usd"], 0.0015)
        self.assertEqual(session_data["total_fixes"], 1)
        self.assertEqual(session_data["successful_fixes"], 1)

    def test_efficiency_tracker_get_token_usage_by_operation(self):
        session_id = self.efficiency_tracker.start_session()
        self.efficiency_tracker.track_token_consumption(
            100, "analysis", "openai", 0.001
        )
        self.efficiency_tracker.track_token_consumption(
            50, "fix_suggestion", "anthropic", 0.0005
        )
        self.efficiency_tracker.track_token_consumption(20, "analysis", "azure", 0.0002)
        self.efficiency_tracker.end_session()

        usage = self.efficiency_tracker.get_token_usage_by_operation(session_id)
        self.assertEqual(usage, {"analysis": 120, "fix_suggestion": 50})

        # Test for all sessions
        self.efficiency_tracker.start_session()
        self.efficiency_tracker.track_token_consumption(
            30, "validation", "openai", 0.0003
        )
        self.efficiency_tracker.end_session()

        all_usage = self.efficiency_tracker.get_token_usage_by_operation()
        self.assertEqual(
            all_usage, {"analysis": 120, "fix_suggestion": 50, "validation": 30}
        )

    def test_efficiency_tracker_get_token_usage_by_provider(self):
        session_id = self.efficiency_tracker.start_session()
        self.efficiency_tracker.track_token_consumption(
            100, "analysis", "openai", 0.001
        )
        self.efficiency_tracker.track_token_consumption(
            50, "fix_suggestion", "anthropic", 0.0005
        )
        self.efficiency_tracker.track_token_consumption(
            20, "analysis", "openai", 0.0002
        )
        self.efficiency_tracker.end_session()

        usage = self.efficiency_tracker.get_token_usage_by_provider(session_id)
        self.assertEqual(usage, {"openai": 120, "anthropic": 50})

    def test_efficiency_tracker_get_total_estimated_cost(self):
        session_id = self.efficiency_tracker.start_session()
        self.efficiency_tracker.track_token_consumption(
            100, "analysis", "openai", 0.001
        )
        self.efficiency_tracker.track_token_consumption(
            50, "fix_suggestion", "anthropic", 0.0005
        )
        self.efficiency_tracker.track_token_consumption(20, "analysis", "azure", 0.0002)
        self.efficiency_tracker.end_session()

        cost = self.efficiency_tracker.get_total_estimated_cost(session_id)
        self.assertAlmostEqual(cost, 0.0017)

        # Test for all sessions
        self.efficiency_tracker.start_session()
        self.efficiency_tracker.track_token_consumption(
            30, "validation", "openai", 0.0003
        )
        self.efficiency_tracker.end_session()

        all_cost = self.efficiency_tracker.get_total_estimated_cost()
        self.assertAlmostEqual(all_cost, 0.002)

    def test_efficiency_tracker_generate_recommendations_token_cost(self):
        self.efficiency_tracker.start_session()
        # Simulate high token cost
        self.efficiency_tracker.track_token_consumption(
            10000, "analysis", "openai", 0.10
        )
        self.efficiency_tracker.track_token_consumption(
            5000, "fix_suggestion", "anthropic", 0.05
        )
        self.efficiency_tracker.record_auto_fix(True)
        self.efficiency_tracker.end_session()

        recommendations = self.efficiency_tracker.generate_recommendations()
        self.assertIn("Significant LLM cost detected", recommendations)
        self.assertIn("High token usage per successful fix", recommendations)
        self.assertIn("Most tokens used for 'analysis' operations", recommendations)

    # --- TokenTracker Specific Tests ---
    @patch("tiktoken.encoding_for_model")
    def test_token_tracker_estimate_tokens_openai(self, mock_encoding_for_model):
        mock_encoder = MagicMock()
        mock_encoder.encode.return_value = [1, 2, 3, 4, 5]
        mock_encoding_for_model.return_value = mock_encoder

        tokens = self.token_tracker._estimate_tokens("Hello world", "gpt-4", "openai")
        self.assertEqual(tokens, 5)
        mock_encoding_for_model.assert_called_once_with("gpt-4")
        mock_encoder.encode.assert_called_once_with("Hello world")

    @patch("tiktoken.encoding_for_model", side_effect=KeyError)
    def test_token_tracker_estimate_tokens_openai_fallback(
        self, mock_encoding_for_model
    ):
        tokens = self.token_tracker._estimate_tokens(
            "This is a longer string for fallback", "unknown-model", "openai"
        )
        # Fallback is len(text) // 4
        self.assertEqual(tokens, len("This is a longer string for fallback") // 4)
        mock_encoding_for_model.assert_called_once_with("unknown-model")

    def test_token_tracker_estimate_tokens_anthropic(self):
        tokens = self.token_tracker._estimate_tokens(
            "Hello world from Anthropic", "claude-3-sonnet", "anthropic"
        )
        # Anthropic fallback is len(text) // 4
        self.assertEqual(tokens, len("Hello world from Anthropic") // 4)

    def test_token_tracker_estimate_tokens_generic_fallback(self):
        tokens = self.token_tracker._estimate_tokens(
            "Generic text", "some-model", "unknown-provider"
        )
        self.assertEqual(tokens, len("Generic text") // 4)

    def test_token_tracker_estimate_cost(self):
        # OpenAI GPT-4 input: 0.03/1k, output: 0.06/1k
        cost = self.token_tracker._estimate_cost(1000, 500, "openai", "gpt-4")
        self.assertAlmostEqual(
            cost, (1000 / 1000 * 0.03) + (500 / 1000 * 0.06)
        )  # 0.03 + 0.03 = 0.06

        # Anthropic Claude-3-Sonnet input: 0.003/1k, output: 0.015/1k
        cost = self.token_tracker._estimate_cost(
            2000, 1000, "anthropic", "claude-3-sonnet"
        )
        self.assertAlmostEqual(
            cost, (2000 / 1000 * 0.003) + (1000 / 1000 * 0.015)
        )  # 0.006 + 0.015 = 0.021

        # Unknown provider/model
        cost = self.token_tracker._estimate_cost(100, 100, "unknown", "unknown")
        self.assertEqual(cost, 0.0)

    def test_token_tracker_track_llm_call(self):
        session_id = self.token_tracker.start_session()
        prompt = "Analyze this failure."
        response = "Root cause is X."
        operation_type = "analysis"
        provider = "openai"
        model = "gpt-3.5-turbo"

        # Mock tiktoken for consistent token counts
        with patch("tiktoken.encoding_for_model") as mock_encoding_for_model:
            mock_encoder = MagicMock()
            mock_encoder.encode.side_effect = [
                [1] * (len(prompt) // 4),  # Input tokens
                [1] * (len(response) // 4),  # Output tokens
            ]
            mock_encoding_for_model.return_value = mock_encoder

            self.token_tracker.track_llm_call(
                prompt, response, operation_type, provider, model
            )

            # Verify real-time counters
            realtime_tokens = self.token_tracker.get_realtime_token_usage()
            realtime_cost = self.token_tracker.get_realtime_token_cost()
            self.assertGreater(realtime_tokens.get(operation_type, 0), 0)
            self.assertGreater(realtime_cost, 0.0)

            # Verify DB persistence via parent's method
            session_data = self._get_session_data_from_db(session_id)
            self.assertGreater(session_data["total_tokens"], 0)
            self.assertGreater(session_data["total_estimated_cost_usd"], 0.0)
            self.assertEqual(
                session_data["total_analysis_tokens"], realtime_tokens[operation_type]
            )

            detailed_usage = self._get_token_usage_by_type_from_db(session_id)
            self.assertEqual(len(detailed_usage), 1)
            self.assertEqual(detailed_usage[0]["operation_type"], operation_type)
            self.assertEqual(detailed_usage[0]["provider"], provider)
            self.assertGreater(detailed_usage[0]["tokens"], 0)
            self.assertGreater(detailed_usage[0]["estimated_cost_usd"], 0.0)

            # Verify metrics client calls
            self.metrics_client.gauge.assert_any_call(
                "llm_tokens_used_total", session_data["total_tokens"]
            )
            self.metrics_client.gauge.assert_any_call(
                "llm_cost_usd_total", session_data["total_estimated_cost_usd"]
            )
            self.metrics_client.gauge.assert_any_call(
                f"llm_tokens_used_by_op_{operation_type}",
                realtime_tokens[operation_type],
            )

    def test_token_tracker_budget_management(self):
        self.token_tracker.start_session()
        self.token_tracker.set_budget("analysis", 0.0001)  # Set a very low budget

        prompt = "Short prompt."
        response = "Short response."
        operation_type = "analysis"
        provider = "openai"
        model = "gpt-3.5-turbo"

        # Mock tiktoken to ensure predictable token counts for budget test
        with patch("tiktoken.encoding_for_model") as mock_encoding_for_model:
            mock_encoder = MagicMock()
            mock_encoder.encode.side_effect = [
                [1] * 10,  # Input tokens
                [1] * 10,  # Output tokens
            ]
            mock_encoding_for_model.return_value = mock_encoder

            # First call, should be within budget
            self.token_tracker.track_llm_call(
                prompt, response, operation_type, provider, model
            )
            self.metrics_client.increment.assert_not_called()  # No budget exceeded yet

            # Second call, should exceed budget
            self.token_tracker.track_llm_call(
                prompt, response, operation_type, provider, model
            )
            self.metrics_client.increment.assert_called_once_with(
                f"llm_budget_exceeded_{operation_type}"
            )

    def test_token_tracker_get_detailed_analytics(self):
        session_id = self.token_tracker.start_session()
        self.token_tracker.track_llm_call("p1", "r1", "analysis", "openai", "gpt-4")
        self.token_tracker.track_llm_call(
            "p2", "r2", "fix_suggestion", "anthropic", "claude-3-sonnet"
        )
        self.token_tracker.end_session()

        analytics = self.token_tracker.get_detailed_analytics(session_id)
        self.assertIn("total_tokens", analytics)
        self.assertIn("total_estimated_cost_usd", analytics)
        self.assertIn("tokens_by_operation", analytics)
        self.assertIn("tokens_by_provider", analytics)
        self.assertIn("realtime_tokens_by_operation", analytics)
        self.assertIn("realtime_cost_usd", analytics)

        self.assertGreater(analytics["total_tokens"], 0)
        self.assertGreater(analytics["total_estimated_cost_usd"], 0)
        self.assertIn("analysis", analytics["tokens_by_operation"])
        self.assertIn("fix_suggestion", analytics["tokens_by_operation"])
        self.assertIn("openai", analytics["tokens_by_provider"])
        self.assertIn("anthropic", analytics["tokens_by_provider"])

        # Real-time should be empty after session ends
        self.assertEqual(analytics["realtime_tokens_by_operation"], {})
        self.assertEqual(analytics["realtime_cost_usd"], 0.0)

    def test_token_tracker_generate_optimization_suggestions(self):
        self.token_tracker.start_session()
        # Simulate high token usage for analysis
        with patch("tiktoken.encoding_for_model") as mock_encoding_for_model:
            mock_encoder = MagicMock()
            mock_encoder.encode.side_effect = [
                [1] * 10000,  # Input tokens for analysis
                [1] * 5000,  # Output tokens for analysis
                [1] * 1000,  # Input tokens for fix_suggestion
                [1] * 500,  # Output tokens for fix_suggestion
            ]
            mock_encoding_for_model.return_value = mock_encoder

            self.token_tracker.track_llm_call(
                "p_analysis", "r_analysis", "analysis", "openai", "gpt-4"
            )
            self.token_tracker.track_llm_call(
                "p_fix", "r_fix", "fix_suggestion", "anthropic", "claude-3-sonnet"
            )
            self.token_tracker.record_auto_fix(True)  # One successful fix
            self.token_tracker.end_session()

        suggestions = self.token_tracker.generate_optimization_suggestions()
        self.assertIn("High overall LLM cost", suggestions)
        self.assertIn("Most tokens used for 'analysis' operations", suggestions)
        self.assertIn("Average tokens per successful fix is high", suggestions)
        self.assertIn(
            "For OpenAI models, consider using `gpt-3.5-turbo` for less complex tasks to reduce cost.",
            suggestions,
        )
        self.assertIn(
            "For Anthropic models, `claude-3-haiku` is very cost-effective for simpler tasks.",
            suggestions,
        )
        self.assertIn("Review LLM prompts for verbosity.", suggestions)

    # --- TokenTrackingInterceptor Tests ---
    def test_token_tracking_interceptor_openai_integration(self):
        mock_openai_client = MagicMock()
        mock_openai_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="Mocked OpenAI response"))],
            usage=MagicMock(prompt_tokens=10, completion_tokens=20, total_tokens=30),
        )

        interceptor = TokenTrackingInterceptor(
            wrapped_llm_client=mock_openai_client,
            token_tracker=self.token_tracker,
            operation_type="analysis",
            provider_name="openai",
            model_name="gpt-4",
        )

        self.token_tracker.start_session()

        # Call the intercepted method
        response = interceptor.chat.completions.create(
            messages=[{"role": "user", "content": "Test prompt"}]
        )

        self.assertEqual(response.choices[0].message.content, "Mocked OpenAI response")
        mock_openai_client.chat.completions.create.assert_called_once()

        # Verify token tracker was called
        realtime_tokens = self.token_tracker.get_realtime_token_usage()
        realtime_cost = self.token_tracker.get_realtime_token_cost()
        self.assertGreater(realtime_tokens.get("analysis", 0), 0)
        self.assertGreater(realtime_cost, 0.0)

        self.token_tracker.end_session()

    def test_token_tracking_interceptor_anthropic_integration(self):
        mock_anthropic_client = MagicMock()
        mock_anthropic_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="Mocked Anthropic response")],
            usage=MagicMock(input_tokens=15, output_tokens=25),
        )

        interceptor = TokenTrackingInterceptor(
            wrapped_llm_client=mock_anthropic_client,
            token_tracker=self.token_tracker,
            operation_type="fix_suggestion",
            provider_name="anthropic",
            model_name="claude-3-sonnet",
        )

        self.token_tracker.start_session()

        # Call the intercepted method
        response = interceptor.messages.create(
            messages=[{"role": "user", "content": "Test prompt"}]
        )

        self.assertEqual(response.content[0].text, "Mocked Anthropic response")
        mock_anthropic_client.messages.create.assert_called_once()

        # Verify token tracker was called
        realtime_tokens = self.token_tracker.get_realtime_token_usage()
        realtime_cost = self.token_tracker.get_realtime_token_cost()
        self.assertGreater(realtime_tokens.get("fix_suggestion", 0), 0)
        self.assertGreater(realtime_cost, 0.0)

        self.token_tracker.end_session()

    # --- End-to-End LLM Service Integration Tests ---
    def test_openai_service_with_token_tracker(self):
        session_id = self.token_tracker.start_session()

        # Initialize OpenAI Service with the TokenTracker
        openai_service = OpenAIService(
            settings=self.settings,
            token_tracker=self.token_tracker,
            operation_type="analysis",
        )
        openai_service.model = "gpt-3.5-turbo"  # Ensure a known model for estimation

        prompt = "Analyze this test failure: AssertionError in test_login."
        response = openai_service.generate(prompt)

        self.assertIn("OpenAI mock response", response)

        # Verify token tracker was called and data persisted
        session_data = self._get_session_data_from_db(session_id)
        self.assertGreater(session_data["total_tokens"], 0)
        self.assertGreater(session_data["total_estimated_cost_usd"], 0.0)
        self.assertGreater(session_data["total_analysis_tokens"], 0)

        realtime_tokens = self.token_tracker.get_realtime_token_usage()
        self.assertGreater(realtime_tokens.get("analysis", 0), 0)

        self.token_tracker.end_session()

    def test_anthropic_service_with_token_tracker(self):
        session_id = self.token_tracker.start_session()

        # Initialize Anthropic Service with the TokenTracker
        anthropic_service = AnthropicService(
            settings=self.settings,
            token_tracker=self.token_tracker,
            operation_type="fix_suggestion",
        )
        anthropic_service.model = (
            "claude-3-haiku-20240307"  # Ensure a known model for estimation
        )

        prompt = "Suggest a fix for: ImportError: No module named 'requests'."
        response = anthropic_service.generate(prompt)

        self.assertIn("Anthropic mock response", response)

        # Verify token tracker was called and data persisted
        session_data = self._get_session_data_from_db(session_id)
        self.assertGreater(session_data["total_tokens"], 0)
        self.assertGreater(session_data["total_estimated_cost_usd"], 0.0)
        self.assertGreater(session_data["total_fix_suggestion_tokens"], 0)

        realtime_tokens = self.token_tracker.get_realtime_token_usage()
        self.assertGreater(realtime_tokens.get("fix_suggestion", 0), 0)

        self.token_tracker.end_session()

    def test_llm_service_without_token_tracker(self):
        # Test that services still work without a token tracker
        openai_service = OpenAIService(settings=self.settings)
        response = openai_service.generate("Simple prompt.")
        self.assertIn("OpenAI mock response", response)

        # No session started, so no tracking should occur
        self.assertEqual(self.token_tracker.get_total_estimated_cost(), 0.0)
        self.assertEqual(self.token_tracker.get_token_usage_by_operation(), {})

    def test_token_tracker_error_handling(self):
        # Test error handling for start_session
        self.token_tracker.start_session()
        with self.assertRaises(EfficiencyTrackerError):
            self.token_tracker.start_session()  # Cannot start if already active

        # Test error handling for end_session
        self.token_tracker.end_session()  # End the active session
        with self.assertRaises(EfficiencyTrackerError):
            self.token_tracker.end_session()  # Cannot end if no active session

        # Test track_token_consumption with invalid tokens
        self.token_tracker.start_session()
        with self.assertLogs(logger, level="WARNING") as cm:
            self.token_tracker.track_token_consumption(0, "analysis", "openai", 0.0)
            self.assertIn("Attempted to track non-positive token count.", cm.output[0])

        # Test track_llm_call with no active session
        self.token_tracker.end_session()  # Ensure no active session
        with self.assertLogs(logger, level="WARNING") as cm:
            self.token_tracker.track_llm_call("p", "r", "analysis", "openai", "gpt-4")
            self.assertIn(
                "No active session - token consumption not tracked", cm.output[0]
            )

        self.token_tracker.end_session()  # Clean up
