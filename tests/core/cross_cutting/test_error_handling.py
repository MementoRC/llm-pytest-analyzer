import pytest
import logging
from typing import Any, List, Optional, Type, Tuple

from pytest_analyzer.core.interfaces.errors import BaseError
from pytest_analyzer.core.cross_cutting.error_handling import (
    error_context,
    error_handler,
    batch_operation,
    module_logger as error_handling_module_logger, # For testing default logger
)

# --- Test Fixtures and Helper Classes ---

test_logger = logging.getLogger("test_error_handling")
# To capture logs from the module_logger in error_handling.py when testing default logger usage
# Ensure its propagation or add a handler if needed, though caplog should capture it.

class MyCustomError(BaseError):
    """Custom error for testing, derived from BaseError."""
    pass

class AnotherError(Exception):
    """Custom error for testing, not derived from BaseError."""
    pass

# --- Tests for BaseError ---

def test_base_error_instantiation_and_attributes():
    original_exc = ValueError("Original issue")
    err = BaseError("Test message", original_exception=original_exc)
    assert err.message == "Test message"
    assert err.original_exception == original_exc
    assert str(err) == "Test message: Original issue"

def test_base_error_without_original_exception():
    err = BaseError("Test message only")
    assert err.message == "Test message only"
    assert err.original_exception is None
    assert str(err) == "Test message only"

# --- Tests for error_context (sync) ---

def test_error_context_success(caplog):
    op_name = "SuccessfulOp"
    with error_context(op_name, test_logger, MyCustomError):
        pass # Simulate work
    assert f"Starting operation: {op_name}" in caplog.text
    assert f"Successfully completed operation: {op_name}" in caplog.text
    assert not any(record.levelno == logging.ERROR for record in caplog.records)

def test_error_context_catches_and_reraises_base_error_subclass(caplog):
    original_exc = ValueError("Sync failure details")
    op_name = "CTX_BASE_ERROR"
    with pytest.raises(MyCustomError) as exc_info:
        with error_context(op_name, test_logger, MyCustomError):
            raise original_exc
    
    assert str(exc_info.value) == f"{op_name} failed: {original_exc}"
    assert exc_info.value.__cause__ is original_exc
    assert isinstance(exc_info.value, MyCustomError)
    # For BaseError subclasses, original_exception should now be set
    assert exc_info.value.original_exception is original_exc
    assert f"Error during operation '{op_name}': {original_exc}" in caplog.text

def test_error_context_wraps_with_standard_error(caplog):
    original_exc = ValueError("Sync failure details")
    op_name = "CTX_STD_WRAP"
    # Use a standard error like RuntimeError as the error_type
    with pytest.raises(RuntimeError) as exc_info:
        with error_context(op_name, test_logger, RuntimeError):
            raise original_exc
    
    assert str(exc_info.value) == f"{op_name} failed: {original_exc}"
    assert exc_info.value.__cause__ is original_exc
    # Standard errors won't have 'original_exception' attribute unless they define it
    assert not hasattr(exc_info.value, "original_exception")
    assert f"Error during operation '{op_name}': {original_exc}" in caplog.text

def test_error_context_does_not_double_wrap(caplog):
    original_custom_exc = MyCustomError("Original custom message")
    op_name = "CTX_NO_DOUBLE_WRAP"
    with pytest.raises(MyCustomError) as exc_info:
        with error_context(op_name, test_logger, MyCustomError):
            raise original_custom_exc
    
    assert exc_info.value is original_custom_exc # Should be the exact same exception instance
    assert str(exc_info.value) == "Original custom message"
    assert f"Error during operation '{op_name}': {original_custom_exc}" in caplog.text
    # Check that it didn't try to log "Successfully completed"
    assert f"Successfully completed operation: {op_name}" not in caplog.text

def test_error_context_suppresses_error_if_reraise_false(caplog):
    original_exc = ValueError("Suppressed failure")
    op_name = "CTX_SUPPRESS"
    try:
        with error_context(op_name, test_logger, MyCustomError, reraise=False):
            raise original_exc
    except MyCustomError:
        pytest.fail("Exception should have been suppressed by reraise=False")
    
    assert f"Starting operation: {op_name}" in caplog.text
    assert f"Error during operation '{op_name}': {original_exc}" in caplog.text
    # Ensure success message is not logged
    assert f"Successfully completed operation: {op_name}" not in caplog.text

# --- Tests for error_handler ---

def test_error_handler_success(caplog):
    op_name = "HandlerSuccessOp"
    @error_handler(op_name, MyCustomError, logger=test_logger)
    def my_sync_func(a: int, b: int) -> int:
        return a + b
    
    assert my_sync_func(1, 2) == 3
    assert f"Calling function 'my_sync_func' for operation: {op_name}" in caplog.text
    assert f"Function 'my_sync_func' for operation '{op_name}' completed successfully." in caplog.text

def test_error_handler_catches_and_reraises_wrapped(caplog):
    original_exc = ValueError("Sync func failure")
    op_name = "HandlerWrap"
    
    @error_handler(op_name, MyCustomError, logger=test_logger)
    def my_sync_func_raises():
        raise original_exc
    
    with pytest.raises(MyCustomError) as exc_info:
        my_sync_func_raises()
    
    expected_message = f"Operation '{op_name}' (function: my_sync_func_raises) failed: {original_exc}"
    assert str(exc_info.value) == expected_message
    assert exc_info.value.__cause__ is original_exc
    assert isinstance(exc_info.value, MyCustomError)
    assert exc_info.value.original_exception is original_exc # For BaseError subclass
    assert f"Error in function 'my_sync_func_raises' during operation '{op_name}': {original_exc}" in caplog.text

def test_error_handler_does_not_double_wrap(caplog):
    original_custom_exc = MyCustomError("Original custom message for sync")
    op_name = "HandlerNoDoubleWrap"

    @error_handler(op_name, MyCustomError, logger=test_logger)
    def my_sync_func_raises_custom():
        raise original_custom_exc

    with pytest.raises(MyCustomError) as exc_info:
        my_sync_func_raises_custom()
    
    assert exc_info.value is original_custom_exc
    assert str(exc_info.value) == "Original custom message for sync"
    assert f"Error in function 'my_sync_func_raises_custom' during operation '{op_name}': {original_custom_exc}" in caplog.text

def test_error_handler_suppresses_error_and_returns_none_if_reraise_false(caplog):
    original_exc = ValueError("Suppressed handler failure")
    op_name = "HandlerSuppress"

    @error_handler(op_name, MyCustomError, reraise=False, logger=test_logger)
    def my_sync_func_error_suppressed(fail: bool):
        if fail:
            raise original_exc
        return "success"

    result = my_sync_func_error_suppressed(fail=True)
    assert result is None
    assert f"Error in function 'my_sync_func_error_suppressed' during operation '{op_name}': {original_exc}" in caplog.text
    
    caplog.clear()
    result_success = my_sync_func_error_suppressed(fail=False)
    assert result_success == "success"
    assert f"Function 'my_sync_func_error_suppressed' for operation '{op_name}' completed successfully." in caplog.text

def test_error_handler_uses_default_logger_if_none_provided(caplog):
    op_name = "HandlerDefaultLogger"
    # Note: No logger passed to decorator
    @error_handler(op_name, MyCustomError) 
    def my_func_default_logger():
        return "data"

    my_func_default_logger()
    # Check that the module_logger (from error_handling.py) was used
    assert f"Calling function 'my_func_default_logger' for operation: {op_name}" in caplog.text
    # Verify the logger name by checking record.name
    assert any(
        record.name == error_handling_module_logger.name and 
        op_name in record.message 
        for record in caplog.records
    )

# --- Tests for batch_operation ---

def sample_op_success(item: Any) -> str:
    return f"Processed {item}"

def sample_op_failure(item: Any, fail_on: Optional[Any] = None, error_to_raise: Exception = ValueError("Simulated failure")) -> str:
    if fail_on is not None and item == fail_on:
        raise error_to_raise
    if isinstance(item, str) and item.startswith("fail"):
        raise error_to_raise
    return f"Processed {item}"

def test_batch_operation_all_success(caplog):
    items = [1, 2, 3]
    op_name = "BatchSuccess"
    results, errors = batch_operation(
        items,
        sample_op_success,
        op_name,
        logger=test_logger
    )
    assert results == ["Processed 1", "Processed 2", "Processed 3"]
    assert not errors
    assert f"Starting batch operation: {op_name} for {len(items)} items." in caplog.text
    assert f"Batch operation '{op_name}' completed. Successful: 3, Failed: 0." in caplog.text
    assert caplog.records[-1].levelname == "INFO" # Last message is completion

def test_batch_operation_some_failures_continue_on_error_true(caplog):
    items = [1, "fail_item", 3, "another_fail"]
    op_name = "BatchSomeFail"
    
    def op_func(item: Any) -> str:
        return sample_op_failure(item, error_to_raise=ValueError(f"Failure on {item}"))

    results, errors = batch_operation(
        items,
        op_func,
        op_name,
        continue_on_error=True, # Explicitly True
        logger=test_logger
    )
    
    assert results == ["Processed 1", "Processed 3"]
    assert len(errors) == 2
    
    # Error format is (item, exception_instance)
    item1, error1 = errors[0]
    assert item1 == "fail_item"
    assert isinstance(error1, ValueError)
    assert str(error1) == "Failure on fail_item"

    item2, error2 = errors[1]
    assert item2 == "another_fail"
    assert isinstance(error2, ValueError)
    assert str(error2) == "Failure on another_fail"

    assert f"Error processing item 'fail_item'" in caplog.text
    assert f"Error processing item 'another_fail'" in caplog.text
    assert f"Batch operation '{op_name}' completed. Successful: 2, Failed: 2." in caplog.text

def test_batch_operation_stops_on_first_error_if_continue_on_error_false(caplog):
    items = [1, "fail_item", 3, "another_fail"]
    op_name = "BatchStopOnError"
    
    def op_func(item: Any) -> str:
        return sample_op_failure(item, error_to_raise=ValueError(f"Failure on {item}"))

    results, errors = batch_operation(
        items,
        op_func,
        op_name,
        continue_on_error=False, # Key change
        logger=test_logger
    )
    
    assert results == ["Processed 1"] # Only item before failure
    assert len(errors) == 1
    
    item1, error1 = errors[0]
    assert item1 == "fail_item"
    assert isinstance(error1, ValueError)
    assert str(error1) == "Failure on fail_item"

    assert f"Error processing item 'fail_item'" in caplog.text
    assert f"Batch operation '{op_name}' stopped early due to error on item 'fail_item'" in caplog.text
    # Item 3 and 'another_fail' should not have been processed
    assert "Processing item '3'" not in caplog.text 
    assert "Error processing item 'another_fail'" not in caplog.text
    assert f"Batch operation '{op_name}' completed. Successful: 1, Failed: 1." in caplog.text

def test_batch_operation_all_failures(caplog):
    items = ["fail1", "fail2"]
    op_name = "BatchAllFail"
    def op_func_all_fail(item: Any) -> str:
        raise ValueError(f"Always fails for {item}")

    results, errors = batch_operation(
        items,
        op_func_all_fail,
        op_name,
        logger=test_logger
    )
    
    assert not results
    assert len(errors) == 2
    assert errors[0][0] == "fail1"
    assert isinstance(errors[0][1], ValueError)
    assert str(errors[0][1]) == "Always fails for fail1"
    assert errors[1][0] == "fail2"
    assert isinstance(errors[1][1], ValueError)
    assert str(errors[1][1]) == "Always fails for fail2"
    assert f"Batch operation '{op_name}' completed. Successful: 0, Failed: 2." in caplog.text

def test_batch_operation_empty_list(caplog):
    items: List[Any] = []
    op_name = "BatchEmpty"
    results, errors = batch_operation(
        items,
        sample_op_success, # Operation function doesn't matter much here
        op_name,
        logger=test_logger
    )
    assert not results
    assert not errors
    assert f"Starting batch operation: {op_name} for 0 items." in caplog.text
    assert f"Batch operation '{op_name}' completed. Successful: 0, Failed: 0." in caplog.text

def test_batch_operation_preserves_original_error_details_in_tuple(caplog):
    items = ["specific_error_item"]
    specific_error = TypeError("Specific type error for item")
    op_name = "BatchSpecificError"
    
    def op_func_specific_error(item: Any) -> str:
        if item == "specific_error_item":
            raise specific_error
        return f"Processed {item}" # Should not be reached

    results, errors = batch_operation(
        items,
        op_func_specific_error,
        op_name,
        logger=test_logger
    )

    assert not results
    assert len(errors) == 1
    
    failed_item, error_instance = errors[0]
    
    assert failed_item == "specific_error_item"
    assert error_instance is specific_error # Check exact instance
    assert isinstance(error_instance, TypeError)
    assert str(error_instance) == "Specific type error for item"
    assert f"Error processing item 'specific_error_item'" in caplog.text
    assert str(specific_error) in caplog.text

def test_batch_operation_uses_default_logger_if_none_provided(caplog):
    items = [1]
    op_name = "BatchDefaultLogger"
    # Note: No logger passed
    batch_operation(items, sample_op_success, op_name)
    
    assert f"Starting batch operation: {op_name} for {len(items)} items." in caplog.text
    # Verify the logger name
    assert any(
        record.name == error_handling_module_logger.name and
        op_name in record.message
        for record in caplog.records
    )
