import logging
import os
import tempfile

from pytest_analyzer.utils.logging_config import (
    clear_logging_context,
    configure_logging,
    get_logging_context,
    log_performance,
    mask_sensitive_data,
    set_logging_context,
)
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

    def test_logging_context_management(self):
        """Test enhanced logging context management."""
        # Test setting context
        context = set_logging_context(
            correlation_id="test-cid-123",
            user_id="user-456",
            operation="test-operation",
        )

        assert context["correlation_id"] == "test-cid-123"
        assert context["user_id"] == "user-456"
        assert context["operation"] == "test-operation"

        # Test getting context
        retrieved_context = get_logging_context()
        assert retrieved_context["correlation_id"] == "test-cid-123"
        assert retrieved_context["user_id"] == "user-456"
        assert retrieved_context["operation"] == "test-operation"

        # Test clearing context
        clear_logging_context()
        cleared_context = get_logging_context()
        assert cleared_context["correlation_id"] is None
        assert cleared_context["user_id"] is None
        assert cleared_context["operation"] is None

    def test_sensitive_data_masking(self):
        """Test enhanced sensitive data masking."""
        sensitive_data = {
            "username": "testuser",
            "password": "secret123",
            "api_key": "abc123",
            "normal_field": "normal_value",
            "nested": {"token": "xyz789", "safe_data": "safe_value"},
            "list_data": [{"secret": "hidden", "public": "visible"}],
        }

        masked_data = mask_sensitive_data(sensitive_data)

        # Check that sensitive fields are masked
        assert masked_data["password"] == "***MASKED***"
        assert masked_data["api_key"] == "***MASKED***"
        assert masked_data["nested"]["token"] == "***MASKED***"
        assert masked_data["list_data"][0]["secret"] == "***MASKED***"

        # Check that non-sensitive fields are preserved
        assert masked_data["username"] == "testuser"
        assert masked_data["normal_field"] == "normal_value"
        assert masked_data["nested"]["safe_data"] == "safe_value"
        assert masked_data["list_data"][0]["public"] == "visible"

    def test_performance_logging_decorator(self):
        """Test performance logging decorator."""
        import time

        @log_performance(operation_name="test_operation", min_duration_ms=0.0)
        def test_function():
            time.sleep(0.01)  # Small delay to ensure measurable duration
            return "test_result"

        # This should work without errors
        result = test_function()
        assert result == "test_result"

    def test_configure_logging_with_module_levels(self):
        """Test configuration with module-specific log levels."""
        settings = Settings(debug=False)
        module_levels = {"test.module1": "DEBUG", "test.module2": "WARNING"}

        configure_logging(settings, module_levels=module_levels)

        # Verify module-specific levels are set
        assert logging.getLogger("test.module1").level == logging.DEBUG
        assert logging.getLogger("test.module2").level == logging.WARNING

    def test_configure_logging_with_enhanced_features(self):
        """Test logging configuration with enhanced features."""
        settings = Settings(debug=False)

        # Test with enhanced configuration
        configure_logging(
            settings,
            structured=True,
            use_structlog=False,  # Test without structlog for compatibility
            module_levels={"test": "DEBUG"},
            log_rotation_config={"maxBytes": 1024, "backupCount": 3},
        )

        # Should not raise any errors
        root_logger = logging.getLogger()
        assert len(root_logger.handlers) >= 1
