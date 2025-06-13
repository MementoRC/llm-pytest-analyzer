import logging

logger = logging.getLogger("test_logger")


def test_caplog_structure(caplog):
    # Set up logger and log a message
    logger.error("Test error message")

    # Debug caplog structure
    print(f"caplog.text = {repr(caplog.text)}")
    print(f"caplog.messages = {caplog.messages}")
    print(f"caplog.records = {caplog.records}")
    assert caplog.records, "No log records captured"
    print(f"Type of first record: {type(caplog.records[0])}")
    print(f"First record: {caplog.records[0]}")
    print(f"First record message: {caplog.records[0].message}")

    # Test assertions
    assert "Test error message" in caplog.text
    assert any("Test error message" in message for message in caplog.messages)
    assert any("Test error message" in record.message for record in caplog.records)
