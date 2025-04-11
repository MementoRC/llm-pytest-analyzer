"""Tests for the resource manager utilities."""
import pytest
import time
import signal
import resource
from unittest.mock import patch, MagicMock

from src.pytest_analyzer.utils.resource_manager import (
    timeout_context, with_timeout, limit_memory,
    ResourceMonitor, TimeoutError, MemoryLimitError
)


def test_timeout_context_success():
    """Test successful execution within timeout."""
    # Should complete within the timeout
    with timeout_context(1):
        pass


def test_timeout_context_timeout():
    """Test timeout exception when execution exceeds timeout."""
    # Should raise a TimeoutError
    with pytest.raises(TimeoutError):
        with timeout_context(0.1):
            time.sleep(0.2)


def test_timeout_context_exception():
    """Test that the context manager restores the signal handler on exception."""
    # Store the original signal handler
    original_handler = signal.getsignal(signal.SIGALRM)
    
    # Raise an exception within the context
    try:
        with timeout_context(1):
            raise ValueError("Test error")
    except ValueError:
        pass
    
    # Verify that the signal handler was restored
    assert signal.getsignal(signal.SIGALRM) == original_handler


def test_with_timeout_decorator_success():
    """Test successful execution of a decorated function."""
    # Define a decorated function
    @with_timeout(1)
    def test_function():
        return "Success"
    
    # Call the function
    result = test_function()
    
    # Verify the result
    assert result == "Success"


def test_with_timeout_decorator_timeout():
    """Test timeout exception when a decorated function exceeds timeout."""
    # Define a decorated function that sleeps
    @with_timeout(0.1)
    def slow_function():
        time.sleep(0.2)
        return "Success"
    
    # Call the function
    with pytest.raises(TimeoutError):
        slow_function()


def test_limit_memory():
    """Test setting memory limits."""
    # Test with a reasonable limit
    limit_memory(1024)  # 1024 MB
    
    # Get the current limit
    soft, hard = resource.getrlimit(resource.RLIMIT_AS)
    
    # Verify the limit (with some tolerance for platform differences)
    assert soft > 0


@patch('resource.getrlimit')
@patch('resource.setrlimit')
def test_limit_memory_none(mock_setrlimit, mock_getrlimit):
    """Test that limit_memory does nothing when max_mb is None."""
    # Call limit_memory with None
    limit_memory(None)
    
    # Verify that setrlimit was not called
    mock_setrlimit.assert_not_called()


@patch('resource.getrlimit')
@patch('resource.setrlimit')
@patch('logging.Logger.warning')
def test_limit_memory_error(mock_logger_warning, mock_setrlimit, mock_getrlimit):
    """Test error handling when setting memory limits."""
    # Make setrlimit raise an exception
    mock_getrlimit.return_value = (1024, 1024)
    mock_setrlimit.side_effect = resource.error("Test error")
    
    # Call limit_memory
    limit_memory(1024)
    
    # Verify that the error was logged
    mock_logger_warning.assert_called_once()


def test_resource_monitor_initialization():
    """Test initialization of ResourceMonitor."""
    # Create a monitor with limits
    monitor = ResourceMonitor(max_memory_mb=1024, max_time_seconds=60)
    
    # Verify the limits
    assert monitor.max_memory_bytes == 1024 * 1024 * 1024
    assert monitor.max_time_seconds == 60
    assert monitor.start_time is None
    assert monitor.peak_memory == 0


def test_resource_monitor_context_manager():
    """Test the ResourceMonitor context manager."""
    # Create a monitor with limits
    monitor = ResourceMonitor(max_memory_mb=1024, max_time_seconds=60)
    
    # Use the monitor as a context manager
    with monitor:
        assert monitor.start_time is not None
    
    # Verify that the elapsed time is reasonable
    elapsed = time.time() - monitor.start_time
    assert elapsed >= 0


def test_resource_monitor_context_manager_with_exception():
    """Test the ResourceMonitor context manager with an exception."""
    # Create a monitor with limits
    monitor = ResourceMonitor(max_memory_mb=1024, max_time_seconds=60)
    
    # Use the monitor as a context manager with an exception
    try:
        with monitor:
            raise ValueError("Test error")
    except ValueError:
        pass
    
    # Verify that the elapsed time is reasonable
    elapsed = time.time() - monitor.start_time
    assert elapsed >= 0


@patch('time.time')
@patch('resource.getrusage')
def test_resource_monitor_check_time_limit(mock_getrusage, mock_time):
    """Test checking the time limit."""
    # Use a callable for more flexibility
    time_values = {"calls": 0}
    
    def mock_time_func():
        time_values["calls"] += 1
        if time_values["calls"] == 1:  # First call in __enter__
            return 0
        else:  # Subsequent calls in check() and __exit__
            return 61
            
    mock_time.side_effect = mock_time_func
    
    # Create a monitor with a time limit
    monitor = ResourceMonitor(max_time_seconds=60)
    
    # Start the monitor
    with pytest.raises(TimeoutError):
        with monitor:
            monitor.check()


@patch('time.time')
@patch('resource.getrusage')
def test_resource_monitor_check_memory_limit(mock_getrusage, mock_time):
    """Test checking the memory limit."""
    # Mock time.time to return consistent values
    mock_time.return_value = 0
    
    # Mock getrusage to return memory usage
    mock_usage = MagicMock()
    mock_usage.ru_maxrss = 2 * 1024 * 1024  # 2 GB in KB
    mock_getrusage.return_value = mock_usage
    
    # Create a monitor with a memory limit
    monitor = ResourceMonitor(max_memory_mb=1024)  # 1 GB
    
    # Start the monitor
    with pytest.raises(MemoryLimitError):
        with monitor:
            monitor.check()


@patch('time.time')
@patch('resource.getrusage')
def test_resource_monitor_check_within_limits(mock_getrusage, mock_time):
    """Test checking resource usage within limits."""
    # Use a callable for more flexibility
    time_values = {"calls": 0}
    
    def mock_time_func():
        time_values["calls"] += 1
        if time_values["calls"] == 1:  # First call in __enter__
            return 0
        else:  # Subsequent calls in check() and __exit__
            return 30
            
    mock_time.side_effect = mock_time_func
    
    # Mock getrusage to return memory usage
    mock_usage = MagicMock()
    mock_usage.ru_maxrss = 512 * 1024  # 512 MB in KB
    mock_getrusage.return_value = mock_usage
    
    # Create a monitor with limits
    monitor = ResourceMonitor(max_memory_mb=1024, max_time_seconds=60)
    
    # Start the monitor
    with monitor:
        monitor.check()
    
    # Verify the peak memory usage
    assert monitor.peak_memory == 512 * 1024 * 1024  # 512 MB in bytes