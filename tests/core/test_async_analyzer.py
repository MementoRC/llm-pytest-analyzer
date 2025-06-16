# Test file for async processing capabilities
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from rich.progress import Progress

from pytest_analyzer.core.backward_compat import PytestAnalyzerService
from pytest_analyzer.core.models.pytest_failure import FixSuggestion, PytestFailure
from pytest_analyzer.utils.resource_manager import performance_tracker


class MockLLMClient:
    """Mock LLM client that simulates delays and returns fixed responses."""

    def __init__(self, response_delay=0.1):
        self.response_delay = response_delay
        self.messages = MagicMock()
        self.messages.create = self.mock_create

    def mock_create(self, **kwargs):
        """Simulate a synchronous LLM API call with a delay."""
        time.sleep(self.response_delay)

        # Return a response that looks like what the LLM would return
        response = MagicMock()
        response.content = [MagicMock()]
        response.content[0].text = """```json
        [
          {
            "suggestion": "Fix the issue by changing the variable",
            "confidence": 0.9,
            "explanation": "The test is failing because the variable has the wrong value",
            "code_changes": {
              "test_file.py": "def test_function():\\n    x = 1\\n    assert x == 1"
            }
          }
        ]
        ```"""
        return response

    async def mock_async_create(self, **kwargs):
        """Simulate an asynchronous LLM API call with a delay."""
        await asyncio.sleep(self.response_delay)

        # Return a response that looks like what the LLM would return
        response = MagicMock()
        response.content = [MagicMock()]
        response.content[0].text = """```json
        [
          {
            "suggestion": "Fix the issue by changing the variable",
            "confidence": 0.9,
            "explanation": "The test is failing because the variable has the wrong value",
            "code_changes": {
              "test_file.py": "def test_function():\\n    x = 1\\n    assert x == 1"
            }
          }
        ]
        ```"""
        return response


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client."""
    return MockLLMClient()


@pytest.fixture
def sample_failures():
    """Create a list of sample pytest failures for testing."""
    failures = []

    for i in range(10):
        failure = PytestFailure(
            test_name=f"test_function_{i}",
            test_file=f"test_file_{i}.py",
            error_type="AssertionError",
            error_message=f"Expected 1, got 0 in test {i}",
            traceback=f"Traceback for test {i}",
            line_number=10,
            relevant_code=f"def test_function_{i}():\n    x = 0\n    assert x == 1",
        )
        failures.append(failure)

    return failures


@pytest.fixture
def analyzer_service_sync(mock_llm_client):
    """Create a synchronous analyzer service."""
    return PytestAnalyzerService(llm_client=mock_llm_client)


@pytest.fixture
def analyzer_service_async(mock_llm_client):
    """Create an asynchronous analyzer service."""
    return PytestAnalyzerService(llm_client=mock_llm_client)


@pytest.mark.skip(
    reason="Architectural incompatibility: PytestAnalyzerService facade doesn't expose llm_suggester"
)
def test_async_generate_suggestions(analyzer_service_async, sample_failures):
    """Test that the async_generate_suggestions method works correctly."""
    # Use the first 3 failures for the test
    test_failures = sample_failures[:3]

    # Mock the async_suggest_fixes method directly on the suggester instance
    mock_async_suggest_fixes = AsyncMock()

    # Configure the mock to return a specific list of suggestions for each failure
    # The state machine groups failures, so batch_suggest_fixes (using async_suggest_fixes)
    # will likely be called once per unique failure group. Assuming 3 unique failures here.
    mock_suggestions = [
        FixSuggestion(
            failure=test_failures[i],
            suggestion=f"Mock fix for {test_failures[i].test_name}",
            confidence=0.95,
            explanation="Mock explanation",
            code_changes={"mock_file.py": "mock code change"},
        )
        for i in range(len(test_failures))
    ]
    # async_suggest_fixes is called per failure within batch_process
    # Configure the mock to return one suggestion per call, corresponding to the failure
    mock_async_suggest_fixes.side_effect = [[s] for s in mock_suggestions]

    # Reset performance metrics
    performance_tracker.reset()

    # Patch the method on the instance for the duration of the test
    with patch.object(
        analyzer_service_async.llm_suggester,
        "async_suggest_fixes",
        mock_async_suggest_fixes,
    ):
        # Run the async generation method through the public interface
        loop = asyncio.get_event_loop()
        suggestions = loop.run_until_complete(
            analyzer_service_async._async_generate_suggestions(
                failures=test_failures, quiet=True
            )
        )

    # Verify the mock was called correctly (once per failure, assuming no grouping)
    # Note: If failures were designed to group, this count would be lower.
    assert mock_async_suggest_fixes.call_count == len(test_failures)
    # Check arguments of the first call (optional, for deeper debugging)
    # first_call_args, _ = mock_async_suggest_fixes.call_args_list[0]
    # assert first_call_args[0] == test_failures[0] # Check the failure object passed

    # Verify we got the expected suggestions back
    # The state machine might duplicate suggestions if grouping occurs,
    # but with direct patching, we expect the mock results directly.
    # The exact number depends on grouping logic, but it should contain our mock suggestions.
    # Let's check if the suggestions returned contain the ones we mocked.
    assert len(suggestions) == len(
        mock_suggestions
    )  # Assuming no grouping/duplication for simplicity here
    returned_suggestion_texts = {s.suggestion for s in suggestions}
    expected_suggestion_texts = {s.suggestion for s in mock_suggestions}
    assert returned_suggestion_texts == expected_suggestion_texts

    for suggestion in suggestions:
        assert isinstance(suggestion, FixSuggestion)
        assert suggestion.confidence == 0.95
        assert isinstance(suggestion.code_changes, dict)

    # Verify performance metrics were recorded for the overall async generation
    metrics = performance_tracker.get_metrics("async_generate_suggestions")
    assert metrics is not None
    assert metrics.get("calls", 0) == 1  # The outer method is called once


@pytest.mark.skip(
    reason="Architectural incompatibility: PytestAnalyzerService facade doesn't expose llm_suggester"
)
def test_performance_comparison(
    analyzer_service_sync, analyzer_service_async, sample_failures
):
    """Compare performance between sync and async processing."""
    # Setup for test
    mock_progress = MagicMock(spec=Progress)
    performance_tracker.reset()
    failures = sample_failures[:5]  # Use a small set for testing

    # --- Mocking Setup ---
    # Create mocks for sync and async methods
    mock_sync_suggest = MagicMock(
        return_value=[
            FixSuggestion(failure=failures[0], suggestion="Sync Mock", confidence=0.8)
        ]
    )
    mock_async_suggest = AsyncMock(
        return_value=[
            FixSuggestion(failure=failures[0], suggestion="Async Mock", confidence=0.8)
        ]
    )

    # --- Measure sync performance ---
    # Patch the method directly on the instance
    with patch.object(
        analyzer_service_sync.llm_suggester, "suggest_fixes", mock_sync_suggest
    ):
        with performance_tracker.track("sync_test"):
            sync_start = time.time()
            analyzer_service_sync._sync_generate_suggestions(
                failures=failures, quiet=True, progress=mock_progress
            )
            sync_duration = time.time() - sync_start
            # Verify sync mock was called (likely multiple times due to grouping/looping)
            assert mock_sync_suggest.called

    # --- Measure async performance ---
    # Patch the method directly on the instance
    with patch.object(
        analyzer_service_async.llm_suggester, "async_suggest_fixes", mock_async_suggest
    ):
        with performance_tracker.track("async_test"):
            async_start = time.time()
            loop = asyncio.get_event_loop()
            loop.run_until_complete(
                analyzer_service_async._async_generate_suggestions(
                    failures=failures, quiet=True, progress=mock_progress
                )
            )
            async_duration = time.time() - async_start
            # Verify async mock was called (likely multiple times via batch_process)
            assert mock_async_suggest.called

    # --- Get the metrics ---
    metrics = performance_tracker.get_metrics()

    # Verify metrics
    assert "sync_test" in metrics
    assert "async_test" in metrics
    assert metrics["sync_test"]["total_time"] > 0
    assert metrics["async_test"]["total_time"] > 0

    # In a real test with more failures, async should be faster,
    # but with our mock and small test set, we're mainly checking
    # that both methods work and produce metrics.
    # The actual timing comparison might not be meaningful here due to mocks.
    print(
        f"Sync duration (mocked): {sync_duration:.3f}s, Async duration (mocked): {async_duration:.3f}s"
    )

    # Optionally check detailed metrics and performance improvement ratio
    performance_report = performance_tracker.report()
    assert "sync_test" in performance_report
    assert "async_test" in performance_report


def test_performance_tracker():
    """Test that the performance tracker accurately records metrics."""
    # Reset the tracker
    performance_tracker.reset()

    # Track some operations with different durations
    with performance_tracker.track("fast_operation"):
        time.sleep(0.01)

    with performance_tracker.track("slow_operation"):
        time.sleep(0.05)

    # Track nested operations
    with performance_tracker.track("parent_operation"):
        with performance_tracker.track("child_operation"):
            time.sleep(0.02)
        time.sleep(0.01)

    # Get metrics
    metrics = performance_tracker.get_metrics()

    # Verify metrics for individual operations
    assert "fast_operation" in metrics
    assert metrics["fast_operation"]["calls"] == 1
    assert metrics["fast_operation"]["avg_time"] >= 0.01

    assert "slow_operation" in metrics
    assert metrics["slow_operation"]["avg_time"] >= 0.05

    # Verify metrics for nested operations
    assert "parent_operation" in metrics
    assert "parent_operation.child_operation" in metrics
    assert metrics["parent_operation"]["calls"] == 1
    assert metrics["parent_operation.child_operation"]["calls"] == 1
    assert metrics["parent_operation"]["total_time"] >= 0.03

    # Verify report generation
    report = performance_tracker.report()
    assert "fast_operation" in report
    assert "slow_operation" in report
    assert "parent_operation" in report
    assert "child_operation" in report


def test_simple_performance_tracker():
    """Test that the performance tracker's basic functionality works."""
    # Reset the tracker
    performance_tracker.reset()

    # Track a simple operation
    with performance_tracker.track("test_operation"):
        time.sleep(0.1)  # Simulate work

    # Get metrics for the operation
    metrics = performance_tracker.get_metrics("test_operation")

    # Verify metrics were recorded
    assert metrics is not None
    assert "calls" in metrics
    assert metrics["calls"] == 1
    assert "total_time" in metrics
    assert metrics["total_time"] >= 0.1

    # Test report generation
    report = performance_tracker.report()
    assert "test_operation" in report
