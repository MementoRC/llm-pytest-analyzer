import pytest
import logging
from typing import List, Optional, Dict, Any
from pathlib import Path

from ..models.test_failure import TestFailure

logger = logging.getLogger(__name__)


class FailureCollectorPlugin:
    """
    Pytest plugin that collects test failures during test execution.
    
    This plugin hooks into pytest's reporting mechanism to capture
    detailed information about test failures directly from the test run.
    
    Usage:
        plugin = FailureCollectorPlugin()
        pytest.main(['tests/'], plugins=[plugin])
        failures = plugin.get_failures()
    """
    
    def __init__(self):
        self.failures: List[TestFailure] = []
        self.test_items: Dict[str, Any] = {}
        
    @pytest.hookimpl(hookwrapper=True)
    def pytest_collection_modifyitems(self, items):
        """Store test items for later reference."""
        for item in items:
            self.test_items[item.nodeid] = {
                'path': str(item.path) if hasattr(item, 'path') else None,
                'module': item.module.__name__ if hasattr(item, 'module') else None,
                'function': item.function.__name__ if hasattr(item, 'function') else None,
            }
        yield
        
    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(self, item, call):
        """Capture test failures during test execution."""
        outcome = yield
        report = outcome.get_result()
        
        if report.failed:
            try:
                self._process_failure(item, report)
            except Exception as e:
                logger.error(f"Error processing test failure: {e}")
                
    def _process_failure(self, item, report):
        """Process a test failure and add it to the failure list."""
        # Extract traceback information
        traceback_text = ""
        relevant_code = ""
        error_type = "Unknown"
        error_message = ""
        line_number = None
        
        if hasattr(report, 'longrepr'):
            longrepr = report.longrepr
            
            # Extract traceback text
            if hasattr(longrepr, 'reprtraceback'):
                traceback_text = str(longrepr)
                
                # Extract line number from traceback entry
                entries = longrepr.reprtraceback.entries
                if entries:
                    last_entry = entries[-1]
                    if hasattr(last_entry, 'lineno'):
                        line_number = last_entry.lineno
                    
                    # Extract relevant code
                    if hasattr(last_entry, 'reprfuncargs'):
                        relevant_code = str(last_entry.reprfuncargs)
            
            # Extract error type and message
            if hasattr(longrepr, 'reprcrash'):
                crash = longrepr.reprcrash
                error_type = crash.message.split(':', 1)[0] if ':' in crash.message else "AssertionError"
                error_message = crash.message
        
        # Create TestFailure object
        failure = TestFailure(
            test_name=item.nodeid,
            test_file=str(item.path) if hasattr(item, 'path') else "",
            line_number=line_number,
            error_type=error_type,
            error_message=error_message,
            traceback=traceback_text,
            relevant_code=relevant_code,
            raw_output_section=str(report.longrepr) if hasattr(report, 'longrepr') else ""
        )
        
        self.failures.append(failure)
        
    def get_failures(self) -> List[TestFailure]:
        """Get the collected failures."""
        return self.failures


def collect_failures_with_plugin(pytest_args: List[str]) -> List[TestFailure]:
    """
    Run pytest with the FailureCollectorPlugin to collect failures.
    
    Args:
        pytest_args: Arguments to pass to pytest
        
    Returns:
        List of TestFailure objects
    """
    plugin = FailureCollectorPlugin()
    pytest.main(pytest_args, plugins=[plugin])
    return plugin.get_failures()