from unittest.mock import patch

import pytest

from src.pytest_analyzer.mcp.security import (
    CircuitBreakerState,
    SecurityError,
    SecurityManager,
)
from src.pytest_analyzer.utils.config_types import SecuritySettings

# Fixtures


@pytest.fixture
def rate_limit_settings():
    return SecuritySettings(
        max_requests_per_window=5,
        rate_limit_window_seconds=10,
        per_tool_rate_limits={"strict_tool": 2},
        llm_rate_limit=3,
        abuse_ban_count=2,
        enable_circuit_breaker=True,
        circuit_breaker_failures=3,
        circuit_breaker_timeout_seconds=20,
        circuit_breaker_successes_to_close=2,
    )


@pytest.fixture
def security_manager(rate_limit_settings):
    return SecurityManager(rate_limit_settings)


# Tests


def test_config_validation():
    # Test pydantic validation for new fields
    with pytest.raises(ValueError):
        SecuritySettings(llm_rate_limit=0)
    with pytest.raises(ValueError):
        SecuritySettings(circuit_breaker_failures=0)
    with pytest.raises(ValueError):
        SecuritySettings(circuit_breaker_timeout_seconds=0)
    with pytest.raises(ValueError):
        SecuritySettings(circuit_breaker_successes_to_close=0)

    # Test valid config
    s = SecuritySettings(
        per_tool_rate_limits={"tool1": 10},
        llm_rate_limit=5,
        circuit_breaker_failures=1,
        circuit_breaker_timeout_seconds=1,
        circuit_breaker_successes_to_close=1,
    )
    assert s.per_tool_rate_limits == {"tool1": 10}


# Rate Limiting Tests


@patch("time.time")
def test_default_rate_limiting(mock_time, security_manager):
    mock_time.return_value = 1000
    for i in range(5):
        security_manager.check_rate_limit("client1", "some_tool")

    with pytest.raises(SecurityError, match="Rate limit of 5 req/window exceeded"):
        security_manager.check_rate_limit("client1", "some_tool")

    # After window expires
    mock_time.return_value = 1011
    security_manager.check_rate_limit("client1", "some_tool")  # Should succeed


@patch("time.time")
def test_per_tool_rate_limiting(mock_time, security_manager):
    mock_time.return_value = 1000
    # Strict tool
    for i in range(2):
        security_manager.check_rate_limit("client1", "strict_tool")
    with pytest.raises(SecurityError, match="Rate limit of 2 req/window exceeded"):
        security_manager.check_rate_limit("client1", "strict_tool")

    # Default tool should still be allowed
    security_manager.check_rate_limit("client1", "default_tool")


@patch("time.time")
def test_llm_rate_limiting(mock_time, security_manager):
    mock_time.return_value = 1000
    for i in range(3):
        security_manager.check_rate_limit("client1", "llm_tool_abc")
    with pytest.raises(SecurityError, match="Rate limit of 3 req/window exceeded"):
        security_manager.check_rate_limit("client1", "llm_tool_abc")


@patch("time.time")
def test_abuse_detection_and_ban(mock_time, security_manager):
    mock_time.return_value = 1000
    client_id = "abuser"

    # Exceed limit, abuse_count becomes 1
    for _ in range(5):
        security_manager.check_rate_limit(client_id, "tool")
    with pytest.raises(SecurityError, match="Rate limit"):
        security_manager.check_rate_limit(client_id, "tool")  # 6th call

    # Exceed again, abuse_count becomes 2
    with pytest.raises(SecurityError, match="Rate limit"):
        security_manager.check_rate_limit(client_id, "tool")  # 7th call

    # Now abuse_count is 2. Client should be banned.
    with pytest.raises(SecurityError, match="temporarily banned"):
        security_manager.check_rate_limit(client_id, "tool")  # 8th call

    # Ban should persist across windows until the client behaves
    mock_time.return_value = 1022
    with pytest.raises(SecurityError, match="temporarily banned"):
        security_manager.check_rate_limit(client_id, "tool")


# Circuit Breaker Tests


@patch("time.time")
def test_circuit_breaker_opens_on_failures(mock_time, security_manager):
    mock_time.return_value = 1000
    tool_name = "failing_tool"

    # Initial state is CLOSED
    breaker = security_manager._get_breaker(tool_name)
    assert breaker["state"] == CircuitBreakerState.CLOSED

    # Record failures
    security_manager.record_failure(tool_name)
    security_manager.record_failure(tool_name)
    assert breaker["failures"] == 2

    # Third failure opens the circuit
    security_manager.record_failure(tool_name)
    assert breaker["state"] == CircuitBreakerState.OPEN
    assert breaker["opened_at"] == 1000

    # Check should now raise an error
    with pytest.raises(
        SecurityError, match="Circuit breaker for tool 'failing_tool' is open"
    ):
        security_manager.check_circuit_breaker(tool_name)


@patch("time.time")
def test_circuit_breaker_half_open_and_close(mock_time, security_manager):
    mock_time.return_value = 1000
    tool_name = "flaky_tool"

    # Open the circuit
    for _ in range(3):
        security_manager.record_failure(tool_name)

    mock_time.return_value = 1021  # After timeout

    # Should move to HALF_OPEN on next check
    security_manager.check_circuit_breaker(tool_name)
    breaker = security_manager._get_breaker(tool_name)
    assert breaker["state"] == CircuitBreakerState.HALF_OPEN

    # Record successes to close it
    security_manager.record_success(tool_name)
    assert breaker["successes"] == 1
    security_manager.record_success(tool_name)
    assert breaker["state"] == CircuitBreakerState.CLOSED
    assert breaker["failures"] == 0
    assert breaker["successes"] == 0


@patch("time.time")
def test_circuit_breaker_reopens_from_half_open(mock_time, security_manager):
    mock_time.return_value = 1000
    tool_name = "still_failing_tool"

    # Open the circuit
    for _ in range(3):
        security_manager.record_failure(tool_name)

    mock_time.return_value = 1021  # After timeout, moves to HALF_OPEN on check
    security_manager.check_circuit_breaker(tool_name)

    # Record one success
    security_manager.record_success(tool_name)

    # Then a failure
    mock_time.return_value = 1022
    security_manager.record_failure(tool_name)

    # Should be OPEN again
    breaker = security_manager._get_breaker(tool_name)
    assert breaker["state"] == CircuitBreakerState.OPEN
    assert breaker["opened_at"] == 1022


def test_circuit_breaker_disabled(rate_limit_settings):
    rate_limit_settings.enable_circuit_breaker = False
    sm = SecurityManager(rate_limit_settings)
    tool_name = "any_tool"

    # Should not open
    for _ in range(10):
        sm.record_failure(tool_name)

    breaker = sm._get_breaker(tool_name)
    assert breaker["state"] == CircuitBreakerState.CLOSED

    # Check should not raise
    sm.check_circuit_breaker(tool_name)


def test_success_resets_failure_count_in_closed_state(security_manager):
    tool_name = "recovering_tool"

    security_manager.record_failure(tool_name)
    security_manager.record_failure(tool_name)
    breaker = security_manager._get_breaker(tool_name)
    assert breaker["failures"] == 2

    security_manager.record_success(tool_name)
    assert breaker["failures"] == 0
