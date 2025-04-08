import logging
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Dict, Any, Union

from .models.test_failure import TestFailure, FixSuggestion
from .extraction.extractor_factory import get_extractor
from .extraction.pytest_plugin import collect_failures_with_plugin
from .analysis.failure_analyzer import FailureAnalyzer
from .analysis.fix_suggester import FixSuggester
from ..utils.resource_manager import with_timeout, limit_memory, ResourceMonitor
from ..utils.settings import Settings
from ..utils.path_resolver import PathResolver

logger = logging.getLogger(__name__)


class TestAnalyzerService:
    """
    Main service for analyzing pytest test failures.
    
    This class coordinates the extraction and analysis of test failures,
    using different strategies based on the input type and settings.
    """
    
    def __init__(self, settings: Optional[Settings] = None):
        """
        Initialize the test analyzer service.
        
        Args:
            settings: Settings object
        """
        self.settings = settings or Settings()
        self.path_resolver = PathResolver(self.settings.project_root)
        self.analyzer = FailureAnalyzer(max_suggestions=self.settings.max_suggestions)
        self.suggester = FixSuggester(min_confidence=self.settings.min_confidence)
        
    @with_timeout(300)
    def analyze_pytest_output(self, output_path: Union[str, Path]) -> List[FixSuggestion]:
        """
        Analyze pytest output from a file and generate fix suggestions.
        
        Args:
            output_path: Path to the pytest output file
            
        Returns:
            List of suggested fixes
        """
        # Set memory limits
        limit_memory(self.settings.max_memory_mb)
        
        # Resolve the output path
        path = Path(output_path)
        if not path.exists():
            logger.error(f"Output file does not exist: {path}")
            return []
            
        try:
            # Get the appropriate extractor for the file type
            extractor = get_extractor(path, self.settings, self.path_resolver)
            
            # Extract failures
            failures = extractor.extract_failures(path)
            
            # Limit the number of failures to analyze
            if len(failures) > self.settings.max_failures:
                logger.warning(f"Found {len(failures)} failures, limiting to {self.settings.max_failures}")
                failures = failures[:self.settings.max_failures]
                
            # Generate suggestions for each failure
            return self._generate_suggestions(failures)
            
        except Exception as e:
            logger.error(f"Error analyzing pytest output: {e}")
            return []
            
    @with_timeout(300)
    def run_and_analyze(self, test_path: str, pytest_args: Optional[List[str]] = None) -> List[FixSuggestion]:
        """
        Run pytest on the given path and analyze the output.
        
        Args:
            test_path: Path to the directory or file to test
            pytest_args: Additional pytest arguments
            
        Returns:
            List of suggested fixes
        """
        # Set memory limits
        limit_memory(self.settings.max_memory_mb)
        
        try:
            # Choose extraction strategy based on settings
            if self.settings.preferred_format == "plugin":
                # Use direct pytest plugin integration
                all_args = [test_path]
                if pytest_args:
                    all_args.extend(pytest_args)
                    
                failures = collect_failures_with_plugin(all_args)
                
            elif self.settings.preferred_format == "json":
                # Generate JSON output and parse it
                failures = self._run_and_extract_json(test_path, pytest_args)
                
            elif self.settings.preferred_format == "xml":
                # Generate XML output and parse it
                failures = self._run_and_extract_xml(test_path, pytest_args)
                
            else:
                # Default to JSON format
                failures = self._run_and_extract_json(test_path, pytest_args)
                
            # Limit the number of failures to analyze
            if len(failures) > self.settings.max_failures:
                logger.warning(f"Found {len(failures)} failures, limiting to {self.settings.max_failures}")
                failures = failures[:self.settings.max_failures]
                
            # Generate suggestions for each failure
            return self._generate_suggestions(failures)
            
        except Exception as e:
            logger.error(f"Error running and analyzing tests: {e}")
            return []
            
    def _run_and_extract_json(self, test_path: str, pytest_args: Optional[List[str]] = None) -> List[TestFailure]:
        """
        Run pytest with JSON output and extract failures.
        
        Args:
            test_path: Path to the directory or file to test
            pytest_args: Additional pytest arguments
            
        Returns:
            List of test failures
        """
        with tempfile.NamedTemporaryFile(suffix='.json') as tmp:
            args = pytest_args or []
            cmd = ['pytest', test_path, '--json-report', f'--json-report-file={tmp.name}']
            cmd.extend(args)
            
            try:
                # Run pytest with a timeout
                subprocess.run(cmd, timeout=self.settings.pytest_timeout, check=False)
                
                # Extract failures from JSON output
                extractor = get_extractor(Path(tmp.name), self.settings, self.path_resolver)
                return extractor.extract_failures(Path(tmp.name))
                
            except subprocess.TimeoutExpired:
                logger.error(f"Pytest execution timed out after {self.settings.pytest_timeout} seconds")
                return []
                
    def _run_and_extract_xml(self, test_path: str, pytest_args: Optional[List[str]] = None) -> List[TestFailure]:
        """
        Run pytest with XML output and extract failures.
        
        Args:
            test_path: Path to the directory or file to test
            pytest_args: Additional pytest arguments
            
        Returns:
            List of test failures
        """
        with tempfile.NamedTemporaryFile(suffix='.xml') as tmp:
            args = pytest_args or []
            cmd = ['pytest', test_path, '--junit-xml', tmp.name]
            cmd.extend(args)
            
            try:
                # Run pytest with a timeout
                subprocess.run(cmd, timeout=self.settings.pytest_timeout, check=False)
                
                # Extract failures from XML output
                extractor = get_extractor(Path(tmp.name), self.settings, self.path_resolver)
                return extractor.extract_failures(Path(tmp.name))
                
            except subprocess.TimeoutExpired:
                logger.error(f"Pytest execution timed out after {self.settings.pytest_timeout} seconds")
                return []
                
    def _generate_suggestions(self, failures: List[TestFailure]) -> List[FixSuggestion]:
        """
        Generate fix suggestions for the given failures.
        
        Args:
            failures: List of test failures
            
        Returns:
            List of suggested fixes
        """
        suggestions = []
        
        for failure in failures:
            try:
                # Analyze each failure and generate suggestions
                with ResourceMonitor(max_time_seconds=self.settings.analyzer_timeout):
                    failure_suggestions = self.suggester.suggest_fixes(failure)
                    suggestions.extend(failure_suggestions)
                    
            except Exception as e:
                logger.error(f"Error generating suggestions for failure: {e}")
                
        return suggestions