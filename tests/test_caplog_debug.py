import logging

logger = logging.getLogger("test_logger")


def test_caplog_structure(caplog):
    # Ensure logger is set to NOTSET so caplog can capture all levels
    logger.setLevel(logging.NOTSET)
    caplog.set_level(logging.NOTSET)

    # Set up logger and log a message
    logger.error("Test error message")

    # Assert that records are captured (debug print statements removed)
    assert getattr(caplog, "records", []), "No log records captured"

    # Test assertions (robust for CI)
    assert "Test error message" in getattr(caplog, "text", "")
    assert any(
        "Test error message" in str(message)
        for message in getattr(caplog, "messages", [])
    )
    assert any(
        "Test error message" in getattr(record, "message", "")
        for record in getattr(caplog, "records", [])
    )
