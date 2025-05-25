"""Tests for the pytest plugin module."""

from unittest.mock import MagicMock, patch

import pytest

from pytest_analyzer.core.extraction.pytest_plugin import (
    FailureCollectorPlugin,
    collect_failures_with_plugin,
)
from pytest_analyzer.core.models.pytest_failure import PytestFailure


@pytest.fixture
def plugin():
    """Provide a FailureCollectorPlugin instance for testing."""
    return FailureCollectorPlugin()


def test_plugin_initialization(plugin):
    """Test initialization of the plugin."""
    assert isinstance(plugin, FailureCollectorPlugin)
    assert plugin.results == []
    assert plugin.test_items == {}


def test_plugin_collection_modifyitems(plugin):
    """Test the pytest_collection_modifyitems hook."""
    # Create mock pytest items with full attributes
    item1 = MagicMock()
    item1.nodeid = "test_file.py::test_function1"
    item1.path = "test_file.py"
    item1.module = MagicMock(__name__="test_module1")
    item1.function = MagicMock(__name__="test_function1")

    item2 = MagicMock()
    item2.nodeid = "test_file.py::test_function2"
    item2.path = "test_file.py"
    item2.module = MagicMock(__name__="test_module2")
    item2.function = MagicMock(__name__="test_function2")

    # Create the items list
    items = [item1, item2]

    # Get the generator from the hook
    gen = plugin.pytest_collection_modifyitems(items)

    # Run code up to the yield
    gen.send(None)  # Equivalent to next(gen)

    # Complete the generator
    try:
        next(gen)
    except StopIteration:
        # This is expected - the generator should finish
        pass

    # Verify the results
    assert len(plugin.test_items) == 2
    assert plugin.test_items[item1.nodeid]["path"] == "test_file.py"
    assert plugin.test_items[item2.nodeid]["path"] == "test_file.py"


@patch("pytest_analyzer.core.extraction.pytest_plugin.logger.error")
def test_plugin_collection_modifyitems_error(mock_logger_error, plugin):
    """Test error handling in the pytest_collection_modifyitems hook."""
    # Create a mock item that raises an exception when accessed
    item = MagicMock()
    item.nodeid = "test_file.py::test_function"

    # Define a function that raises an exception when called
    def raise_error(*args, **kwargs):
        raise Exception("Test error")

    # Set the path property to use our function
    type(item).path = property(fget=raise_error)

    # Create the items list
    items = [item]

    # Get the generator from the hook
    gen = plugin.pytest_collection_modifyitems(items)

    # Run code up to the yield
    gen.send(None)  # Equivalent to next(gen)

    # Complete the generator
    try:
        next(gen)
    except StopIteration:
        # This is expected - the generator should finish
        pass

    # Verify the error was logged
    mock_logger_error.assert_called_once()


def test_plugin_runtest_makereport_failed(plugin):
    """Test the pytest_runtest_makereport hook for a failed test."""
    # Create mock pytest objects
    item = MagicMock()
    item.nodeid = "test_file.py::test_function"
    item.path = "test_file.py"

    call = MagicMock()
    call.when = "call"  # Set the phase to 'call'

    report = MagicMock()
    report.outcome = "failed"  # Updated to use outcome
    report.when = "call"  # Match the phase from call
    report.longrepr = "Assert failed"

    # Mock the _process_result method
    plugin._process_result = MagicMock()

    # Create the outcome object to be sent back into the generator
    outcome = MagicMock()
    outcome.get_result.return_value = report

    # Get the generator from the hook
    gen = plugin.pytest_runtest_makereport(item, call)

    # Run code up to the yield
    gen.send(None)  # Equivalent to next(gen)

    # Send the outcome back to resume after the yield
    try:
        gen.send(outcome)
    except StopIteration:
        # This is expected - the generator should finish
        pass

    # Verify that _process_result was called
    plugin._process_result.assert_called_once_with(item, report)


def test_plugin_runtest_makereport_passed(plugin):
    """Test the pytest_runtest_makereport hook for a passed test."""
    # Create mock pytest objects
    item = MagicMock()
    item.nodeid = "test_file.py::test_function_passed"
    item.path = "test_file.py"

    call = MagicMock()
    call.when = "call"  # Ensure 'call' phase for processing

    report = MagicMock()
    report.outcome = "passed"  # Test for passed outcome
    report.when = "call"  # Ensure 'call' phase for processing
    report.longrepr = None  # Passed tests might not have longrepr

    # Mock the _process_result method
    plugin._process_result = MagicMock()

    # Create the outcome object
    outcome = MagicMock()
    outcome.get_result.return_value = report

    # Get the generator from the hook
    gen = plugin.pytest_runtest_makereport(item, call)
    gen.send(None)  # Prime the generator
    try:
        gen.send(outcome)  # Send outcome
    except StopIteration:
        pass

    # Verify that _process_result was called for passed tests too
    plugin._process_result.assert_called_once_with(item, report)


def test_plugin_runtest_makereport_skipped(plugin):
    """Test the pytest_runtest_makereport hook for a skipped test."""
    item = MagicMock()
    item.nodeid = "test_file.py::test_function_skipped"
    item.path = "test_file.py"

    call = MagicMock()
    call.when = "call"

    report = MagicMock()
    report.outcome = "skipped"
    report.when = "call"
    report.longrepr = ("test_file.py", 10, "Skipped: reason")

    plugin._process_result = MagicMock()

    outcome = MagicMock()
    outcome.get_result.return_value = report

    gen = plugin.pytest_runtest_makereport(item, call)
    gen.send(None)
    try:
        gen.send(outcome)
    except StopIteration:
        pass

    plugin._process_result.assert_called_once_with(item, report)


@patch("pytest_analyzer.core.extraction.pytest_plugin.logger.error")
def test_plugin_runtest_makereport_error(mock_logger_error, plugin):
    """Test error handling in the pytest_runtest_makereport hook."""
    # Create mock pytest objects
    item = MagicMock()
    item.nodeid = "test_file.py::test_function"
    item.path = "test_file.py"

    call = MagicMock()
    call.when = "call"  # Set the phase to 'call'

    report = MagicMock()
    report.outcome = "failed"  # Use outcome
    report.when = "call"  # Match the phase from call
    report.longrepr = "Assert failed"

    # Mock the _process_result method to raise an exception
    plugin._process_result = MagicMock(side_effect=Exception("Test error"))

    # Create the outcome object to be sent back into the generator
    outcome = MagicMock()
    outcome.get_result.return_value = report

    # Get the generator from the hook
    gen = plugin.pytest_runtest_makereport(item, call)

    # Run code up to the yield
    gen.send(None)  # Equivalent to next(gen)

    # Send the outcome back to resume after the yield
    try:
        gen.send(outcome)
    except StopIteration:
        # This is expected - the generator should finish
        pass

    # Verify that the error was logged
    mock_logger_error.assert_called_once()


def test_process_result_failed_outcome(plugin):
    """Test the _process_result method for a failed test outcome."""
    # Create mock pytest objects
    item = MagicMock()
    item.nodeid = "test_file.py::test_function_failed"
    item.path = "test_file.py"

    report = MagicMock()
    report.outcome = "failed"

    # Mock the longrepr object for a failed test
    longrepr = MagicMock()
    longrepr.reprcrash.message = "AssertionError: Expected 1, got 2"
    longrepr.reprtraceback.entries = [MagicMock()]
    longrepr.reprtraceback.entries[-1].lineno = 42
    longrepr.reprtraceback.entries[-1].reprfuncargs = "test_function_failed(param=1)"
    # Ensure longrepr itself can be stringified for traceback and raw_output_section
    longrepr.__str__ = MagicMock(return_value="Detailed traceback for failure")

    report.longrepr = longrepr

    # Call the _process_result method
    plugin._process_result(item, report)

    # Verify that a result was added
    assert len(plugin.results) == 1
    result = plugin.results[0]
    assert result.outcome == "failed"
    assert result.test_name == "test_file.py::test_function_failed"
    assert result.test_file == "test_file.py"
    assert result.line_number == 42
    assert result.error_type == "AssertionError"
    assert result.error_message == "AssertionError: Expected 1, got 2"
    assert result.relevant_code == "test_function_failed(param=1)"
    assert result.traceback == "Detailed traceback for failure"
    assert result.raw_output_section == "Detailed traceback for failure"


def test_process_result_passed_outcome(plugin):
    """Test the _process_result method for a passed test outcome."""
    item = MagicMock()
    item.nodeid = "test_file.py::test_function_passed"
    item.path = "test_file.py"

    report = MagicMock()
    report.outcome = "passed"
    report.longrepr = None  # Passed tests usually have no longrepr or it's minimal

    plugin._process_result(item, report)

    assert len(plugin.results) == 1
    result = plugin.results[0]
    assert result.outcome == "passed"
    assert result.test_name == "test_file.py::test_function_passed"
    assert result.test_file == "test_file.py"
    assert result.line_number is None
    assert result.error_type is None
    assert result.error_message is None
    assert result.traceback is None
    assert result.relevant_code == ""
    assert result.raw_output_section == "None"  # str(None)


def test_process_result_skipped_outcome(plugin):
    """Test the _process_result method for a skipped test outcome."""
    item = MagicMock()
    item.nodeid = "test_file.py::test_function_skipped"
    item.path = "test_file.py"

    report = MagicMock()
    report.outcome = "skipped"
    # Simulate longrepr for skipped tests (filepath, lineno, message)
    report.longrepr = ("/path/to/skip_location.py", 123, "Skipped: Test needs environment setup")

    plugin._process_result(item, report)

    assert len(plugin.results) == 1
    result = plugin.results[0]
    assert result.outcome == "skipped"
    assert result.test_name == "test_file.py::test_function_skipped"
    assert result.test_file == "test_file.py"
    assert (
        result.line_number is None
    )  # Skipped tests don't have failure line numbers from traceback
    assert result.error_type is None
    assert result.error_message == "Skipped: Test needs environment setup"
    assert result.traceback is None
    assert result.relevant_code == ""
    assert (
        result.raw_output_section
        == "('/path/to/skip_location.py', 123, 'Skipped: Test needs environment setup')"
    )


@patch("pytest.main")
def test_collect_failures_with_plugin(mock_pytest_main):
    """Test the collect_failures_with_plugin function (now collects all results)."""
    # Create a mock plugin instance to be returned by pytest.main's plugins arg
    # This instance will have its get_results method called.
    mock_plugin_instance = FailureCollectorPlugin()
    mock_plugin_instance.results = [
        PytestFailure(
            outcome="failed",
            test_name="test_file.py::test_function",
            test_file="test_file.py",
            error_type="AssertionError",
            error_message="Expected 1, got 2",
            traceback="Traceback",
        ),
        PytestFailure(
            outcome="passed",
            test_name="test_file.py::test_another_function",
            test_file="test_file.py",
        ),
    ]

    # Mock pytest.main to simulate its behavior with plugins
    def mock_main_side_effect(args, plugins):
        # The first plugin in the list is our FailureCollectorPlugin instance
        # We assign the predefined results to it, as if pytest ran and populated them.
        plugins[0].results = mock_plugin_instance.results
        return 0  # Pytest exit code 0 for success

    mock_pytest_main.side_effect = mock_main_side_effect

    # Call the function
    pytest_args = ["test_file.py", "-v"]
    collected_results = collect_failures_with_plugin(pytest_args)

    # Verify pytest.main was called correctly
    # The plugins argument to pytest.main will contain an instance of FailureCollectorPlugin
    # created by collect_failures_with_plugin. We need to check its type.
    mock_pytest_main.assert_called_once()
    call_args, call_kwargs = mock_pytest_main.call_args
    assert call_args[0] == pytest_args
    assert isinstance(call_kwargs["plugins"][0], FailureCollectorPlugin)

    # Verify the results returned by collect_failures_with_plugin
    assert len(collected_results) == 2
    assert collected_results[0].test_name == "test_file.py::test_function"
    assert collected_results[0].outcome == "failed"
    assert collected_results[1].test_name == "test_file.py::test_another_function"
    assert collected_results[1].outcome == "passed"


def test_clear_results():
    """Test that clear_results properly resets plugin state."""
    plugin = FailureCollectorPlugin()

    # Add some dummy data
    plugin.results.append(
        PytestFailure(test_name="test_dummy", test_file="dummy.py", outcome="failed")
    )
    plugin.test_items["dummy"] = "test_item"

    # Verify data is present
    assert len(plugin.results) == 1
    assert len(plugin.test_items) == 1

    # Clear and verify state is reset
    plugin.clear_results()
    assert len(plugin.results) == 0
    assert len(plugin.test_items) == 0
