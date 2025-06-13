import logging
import unittest
from unittest.mock import MagicMock, patch

from pytest_analyzer.core.cross_cutting.error_handling import (
    CircuitBreaker,
    circuit_breaker,
    error_handler,
    retry,
)
from pytest_analyzer.core.errors import (
    AnalysisError,
    CircuitBreakerOpenError,
    RetryError,
)

# Disable logging for tests
logging.disable(logging.CRITICAL)


class TestEnhancedErrorHandling(unittest.TestCase):
    def setUp(self):
        self.mock_logger = MagicMock()

    # --- Test @retry decorator ---

    @patch("time.sleep")
    def test_retry_success_on_first_try(self, mock_sleep):
        @retry(attempts=3, logger=self.mock_logger)
        def success_func():
            return "success"

        self.assertEqual(success_func(), "success")
        self.mock_logger.warning.assert_not_called()
        mock_sleep.assert_not_called()

    @patch("time.sleep")
    def test_retry_success_on_third_try(self, mock_sleep):
        call_count = 0

        @retry(attempts=3, delay=0.1, logger=self.mock_logger)
        def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("temporary failure")
            return "success"

        self.assertEqual(fail_then_succeed(), "success")
        self.assertEqual(call_count, 3)
        self.assertEqual(self.mock_logger.warning.call_count, 2)
        mock_sleep.assert_called_with(0.1 * 2)  # Called with backoff

    @patch("time.sleep")
    def test_retry_fails_after_all_attempts(self, mock_sleep):
        @retry(attempts=3, logger=self.mock_logger)
        def always_fail():
            raise ValueError("permanent failure")

        with self.assertRaises(RetryError) as cm:
            always_fail()

        self.assertIsInstance(cm.exception.original_exception, ValueError)
        self.assertEqual(self.mock_logger.warning.call_count, 2)

    # --- Test CircuitBreaker and @circuit_breaker decorator ---

    def test_circuit_breaker_opens_after_threshold(self):
        breaker = CircuitBreaker(failure_threshold=2, reset_timeout=10)

        @circuit_breaker(breaker)
        def fail_func():
            raise RuntimeError("failure")

        # Fail twice to open the circuit
        with self.assertRaises(RuntimeError):
            fail_func()
        with self.assertRaises(RuntimeError):
            fail_func()

        # The third call should be blocked
        with self.assertRaises(CircuitBreakerOpenError):
            fail_func()

    @patch("time.monotonic")
    def test_circuit_breaker_half_open_and_close(self, mock_monotonic):
        breaker = CircuitBreaker(failure_threshold=1, reset_timeout=10)
        mock_monotonic.return_value = 100

        mock_func = MagicMock()

        @circuit_breaker(breaker)
        def flaky_func():
            return mock_func()

        # Open the circuit
        mock_func.side_effect = RuntimeError("failure")
        with self.assertRaises(RuntimeError):
            flaky_func()

        # Move time forward to enter HALF_OPEN state
        mock_monotonic.return_value = 120
        self.assertTrue(breaker.can_execute())

        # Succeed to close the circuit
        mock_func.side_effect = None
        mock_func.return_value = "success"
        self.assertEqual(flaky_func(), "success")
        self.assertTrue(breaker.can_execute())

    @patch("time.monotonic")
    def test_circuit_breaker_half_open_and_reopen(self, mock_monotonic):
        breaker = CircuitBreaker(failure_threshold=1, reset_timeout=10)
        mock_monotonic.return_value = 100

        @circuit_breaker(breaker)
        def flaky_func():
            raise RuntimeError("failure")

        # Open the circuit
        with self.assertRaises(RuntimeError):
            flaky_func()

        # Move time forward to enter HALF_OPEN state
        mock_monotonic.return_value = 120
        self.assertTrue(breaker.can_execute())

        # Fail again to re-open the circuit
        with self.assertRaises(RuntimeError):
            flaky_func()

        # Should be blocked again
        with self.assertRaises(CircuitBreakerOpenError):
            flaky_func()

    # --- Test @error_handler decorator ---

    def test_error_handler_success(self):
        @error_handler("test_op", AnalysisError, logger=self.mock_logger)
        def success_func():
            return "data"

        self.assertEqual(success_func(), "data")
        self.mock_logger.error.assert_not_called()

    def test_error_handler_wraps_exception(self):
        @error_handler("test_op", AnalysisError, logger=self.mock_logger)
        def fail_func():
            raise ValueError("original error")

        with self.assertRaises(AnalysisError) as cm:
            fail_func()

        self.assertIsInstance(cm.exception.original_exception, ValueError)
        self.assertEqual(cm.exception.error_code, "ANALYSIS_001")
        self.mock_logger.error.assert_called_once()

    def test_error_handler_no_reraise(self):
        @error_handler("test_op", AnalysisError, reraise=False, logger=self.mock_logger)
        def fail_func():
            raise ValueError("original error")

        result = fail_func()
        self.assertIsNone(result)
        self.mock_logger.error.assert_called_once()


if __name__ == "__main__":
    unittest.main()
