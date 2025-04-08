"""Tests for the pytest plugin module."""
import pytest
import sys
from unittest.mock import MagicMock, patch

from ...core.extraction.pytest_plugin import FailureCollectorPlugin, collect_failures_with_plugin
from ...core.models.test_failure import TestFailure


class MockPytestPlugin:
    """Mock class for testing pytest plugin functionality."""
    
    @staticmethod
    def pytest_collection_modifyitems(items):
        """Mock implementation of pytest_collection_modifyitems."""
        pass
    
    @staticmethod
    def pytest_runtest_makereport(item, call):
        """Mock implementation of pytest_runtest_makereport."""
        pass


@pytest.fixture
def plugin():
    """Provide a FailureCollectorPlugin instance for testing."""
    return FailureCollectorPlugin()


def test_plugin_initialization(plugin):
    """Test initialization of the plugin."""
    assert isinstance(plugin, FailureCollectorPlugin)
    assert plugin.failures == []
    assert plugin.test_items == {}


def test_plugin_collection_modifyitems(plugin):
    """Test the pytest_collection_modifyitems hook."""
    # Create mock pytest items
    item1 = MagicMock()
    item1.nodeid = "test_file.py::test_function1"
    item1.path = "test_file.py"
    
    item2 = MagicMock()
    item2.nodeid = "test_file.py::test_function2"
    item2.path = "test_file.py"
    
    # Call the hook
    items = [item1, item2]
    plugin.pytest_collection_modifyitems(items)
    
    # Verify the results
    assert len(plugin.test_items) == 2
    assert plugin.test_items[item1.nodeid]['path'] == "test_file.py"
    assert plugin.test_items[item2.nodeid]['path'] == "test_file.py"


@patch('logging.Logger.error')
def test_plugin_collection_modifyitems_error(mock_logger_error, plugin):
    """Test error handling in the pytest_collection_modifyitems hook."""
    # Create a mock item that raises an exception when accessed
    item = MagicMock()
    item.nodeid = "test_file.py::test_function"
    type(item).path = property(side_effect=Exception("Test error"))
    
    # Call the hook
    items = [item]
    # The hook should catch the exception and continue
    plugin.pytest_collection_modifyitems(items)
    
    # Verify the error was logged
    assert mock_logger_error.called


def test_plugin_runtest_makereport_failed(plugin):
    """Test the pytest_runtest_makereport hook for a failed test."""
    # Create mock pytest objects
    item = MagicMock()
    item.nodeid = "test_file.py::test_function"
    item.path = "test_file.py"
    
    call = MagicMock()
    
    report = MagicMock()
    report.failed = True
    report.longrepr = "Assert failed"
    
    # Mock the _process_failure method
    plugin._process_failure = MagicMock()
    
    # Call the hook
    outcome = MagicMock()
    outcome.get_result.return_value = report
    
    # The hook uses the yield statement, so we need to set up a generator
    # that yields the outcome
    def mock_generator():
        yield outcome
    
    # Call the hook through its wrapper
    next(plugin.pytest_runtest_makereport(item, call))
    
    # Verify that _process_failure was called
    plugin._process_failure.assert_called_once_with(item, report)


def test_plugin_runtest_makereport_passed(plugin):
    """Test the pytest_runtest_makereport hook for a passed test."""
    # Create mock pytest objects
    item = MagicMock()
    item.nodeid = "test_file.py::test_function"
    item.path = "test_file.py"
    
    call = MagicMock()
    
    report = MagicMock()
    report.failed = False
    
    # Mock the _process_failure method
    plugin._process_failure = MagicMock()
    
    # Call the hook
    outcome = MagicMock()
    outcome.get_result.return_value = report
    
    # The hook uses the yield statement, so we need to set up a generator
    # that yields the outcome
    def mock_generator():
        yield outcome
    
    # Call the hook through its wrapper
    next(plugin.pytest_runtest_makereport(item, call))
    
    # Verify that _process_failure was not called
    plugin._process_failure.assert_not_called()


@patch('logging.Logger.error')
def test_plugin_runtest_makereport_error(mock_logger_error, plugin):
    """Test error handling in the pytest_runtest_makereport hook."""
    # Create mock pytest objects
    item = MagicMock()
    item.nodeid = "test_file.py::test_function"
    item.path = "test_file.py"
    
    call = MagicMock()
    
    report = MagicMock()
    report.failed = True
    report.longrepr = "Assert failed"
    
    # Mock the _process_failure method to raise an exception
    plugin._process_failure = MagicMock(side_effect=Exception("Test error"))
    
    # Call the hook
    outcome = MagicMock()
    outcome.get_result.return_value = report
    
    # The hook uses the yield statement, so we need to set up a generator
    # that yields the outcome
    def mock_generator():
        yield outcome
    
    # Call the hook through its wrapper
    next(plugin.pytest_runtest_makereport(item, call))
    
    # Verify that the error was logged
    mock_logger_error.assert_called_once()


def test_process_failure(plugin):
    """Test the _process_failure method."""
    # Create mock pytest objects
    item = MagicMock()
    item.nodeid = "test_file.py::test_function"
    item.path = "test_file.py"
    
    report = MagicMock()
    
    # Mock the longrepr object
    longrepr = MagicMock()
    longrepr.reprcrash.message = "AssertionError: Expected 1, got 2"
    longrepr.reprtraceback.entries = [MagicMock()]
    longrepr.reprtraceback.entries[-1].lineno = 42
    longrepr.reprtraceback.entries[-1].reprfuncargs = "test_function(param=1)"
    
    report.longrepr = longrepr
    
    # Call the _process_failure method
    plugin._process_failure(item, report)
    
    # Verify that a failure was added
    assert len(plugin.failures) == 1
    assert plugin.failures[0].test_name == "test_file.py::test_function"
    assert plugin.failures[0].test_file == "test_file.py"
    assert plugin.failures[0].line_number == 42
    assert plugin.failures[0].error_type == "AssertionError"
    assert plugin.failures[0].error_message == "AssertionError: Expected 1, got 2"


@patch('pytest.main')
def test_collect_failures_with_plugin(mock_pytest_main):
    """Test the collect_failures_with_plugin function."""
    # Create a mock plugin
    mock_plugin = MagicMock()
    mock_plugin.get_failures.return_value = [
        TestFailure(
            test_name="test_file.py::test_function",
            test_file="test_file.py",
            error_type="AssertionError",
            error_message="Expected 1, got 2",
            traceback="Traceback"
        )
    ]
    
    # Mock pytest.main to capture the passed arguments
    def mock_main(args, plugins):
        # Store the plugin for later retrieval
        mock_main.captured_plugin = plugins[0]
        return 0
    
    mock_pytest_main.side_effect = mock_main
    mock_main.captured_plugin = None
    
    # Call the function
    pytest_args = ["test_file.py", "-v"]
    failures = collect_failures_with_plugin(pytest_args)
    
    # Verify the results
    mock_pytest_main.assert_called_once_with(pytest_args, plugins=[mock_main.captured_plugin])
    assert isinstance(mock_main.captured_plugin, FailureCollectorPlugin)