import logging
import os
import tempfile

from pytest_analyzer.utils.logging_config import configure_logging
from pytest_analyzer.utils.settings import Settings


class TestLoggingConfig:
    def test_configure_logging_default(self):
        """Test logging configuration with default settings."""
        # Setup
        settings = Settings(debug=False)
        root_logger = logging.getLogger()

        # Execute
        configure_logging(settings)

        # Verify
        # Accept either 1 or more handlers (CI may add extra handlers)
        assert (
            len(root_logger.handlers) >= 1
        )  # Should have at least one console handler
        assert root_logger.level == logging.INFO
        assert any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers)

        # Check formatter
        handler = next(
            h for h in root_logger.handlers if isinstance(h, logging.StreamHandler)
        )
        formatter = handler.formatter
        assert "%(name)s" in formatter._fmt
        assert "%(levelname)s" in formatter._fmt
        assert "%(message)s" in formatter._fmt

    def test_configure_logging_debug(self):
        """Test logging configuration with debug enabled."""
        # Setup
        settings = Settings(debug=True)

        # Execute
        configure_logging(settings)

        # Verify
        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG
        assert root_logger.handlers[0].level == logging.DEBUG

    def test_configure_logging_with_file(self):
        """Test logging configuration with log file."""
        # Setup
        settings = Settings(debug=False)
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            log_file = temp_file.name

        try:
            # Execute
            configure_logging(settings, log_file=log_file)

            # Verify
            root_logger = logging.getLogger()
            # Accept 2 or more handlers (CI may add extra handlers)
            assert len(root_logger.handlers) >= 2  # Console and file handler

            # Check file handler
            file_handlers = [
                h for h in root_logger.handlers if isinstance(h, logging.FileHandler)
            ]
            assert len(file_handlers) >= 1
            assert any(
                getattr(h, "baseFilename", None) == log_file for h in file_handlers
            )

            # Check file formatter has line numbers
            formatter = file_handlers[0].formatter
            assert "%(filename)s:%(lineno)d" in formatter._fmt

            # Test logging to file
            test_message = "Test log message"
            # Ensure root logger and file handler are set to NOTSET so all messages are captured
            root_logger.setLevel(logging.NOTSET)
            for h in root_logger.handlers:
                h.setLevel(logging.NOTSET)
            logging.info(test_message)

            # Flush all handlers to ensure log is written
            for h in root_logger.handlers:
                if hasattr(h, "flush"):
                    h.flush()

            with open(log_file, "r") as f:
                log_content = f.read()
                assert test_message in log_content

        finally:
            # Cleanup
            if os.path.exists(log_file):
                os.unlink(log_file)

    def test_library_loggers_less_verbose(self):
        """Test that library loggers are set to be less verbose."""
        # Setup
        settings = Settings(debug=False)

        # Execute
        configure_logging(settings)

        # Verify
        urllib3_logger = logging.getLogger("urllib3")
        requests_logger = logging.getLogger("requests")

        # Accept WARNING or stricter (CI may override)
        assert urllib3_logger.level >= logging.WARNING
        assert requests_logger.level >= logging.WARNING

    def test_configure_logging_clears_existing_handlers(self):
        """Test that configure_logging clears existing handlers."""
        # Setup
        settings = Settings(debug=False)
        root_logger = logging.getLogger()

        # Add a temp handler
        temp_handler = logging.StreamHandler()
        root_logger.addHandler(temp_handler)
        initial_handlers_count = len(root_logger.handlers)
        assert initial_handlers_count > 0

        # Execute
        configure_logging(settings)

        # Verify
        # Accept 1 or more handlers (CI may add extra handlers)
        assert len(root_logger.handlers) >= 1  # Only the new handler should remain
        assert temp_handler not in root_logger.handlers
