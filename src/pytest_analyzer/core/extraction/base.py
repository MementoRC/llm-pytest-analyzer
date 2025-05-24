"""
Base extractor module for pytest_analyzer.

This module provides the BaseExtractor abstract class that all concrete extractor
implementations should inherit from to ensure consistent behavior and interface.
"""

import abc
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ...utils.path_resolver import PathResolver
from ...utils.resource_manager import ResourceMonitor, with_timeout
from ..errors import ExtractionError
from ..models.pytest_failure import PytestFailure

logger = logging.getLogger(__name__)


class BaseExtractor(abc.ABC):
    """
    Abstract base class for all extractors.

    This class implements the Extractor protocol and provides common functionality
    for all concrete extractor implementations, including resource management,
    timeout handling, and error handling.
    """

    def __init__(self, path_resolver: Optional[PathResolver] = None, timeout: int = 30):
        """
        Initialize the extractor.

        Args:
            path_resolver: PathResolver instance for resolving file paths
            timeout: Timeout in seconds for extraction operations
        """
        self.path_resolver = path_resolver or PathResolver()
        self.timeout = timeout

    def extract(self, test_results: Union[str, Path, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Extract test failures from pytest output.

        Args:
            test_results: The pytest output to extract from (string, path, or structured data)

        Returns:
            A dictionary containing extracted failures and metadata

        Raises:
            ExtractionError: If extraction fails
        """
        try:
            # Handle different input types
            if isinstance(test_results, Dict):
                # Already parsed data
                failures = self._extract_from_dict(test_results)
                return {"failures": failures, "count": len(failures)}

            # Convert string paths to Path objects
            if isinstance(test_results, str):
                test_results = Path(test_results)

            # Handle Path objects
            if isinstance(test_results, Path):
                return self._extract_from_path(test_results)

            raise ExtractionError(f"Unsupported test_results type: {type(test_results)}")
        except Exception as e:
            logger.error(f"Error extracting data: {e}")
            raise ExtractionError(f"Failed to extract data: {e}") from e

    @with_timeout(30)
    def _extract_from_path(self, results_path: Path) -> Dict[str, Any]:
        """
        Extract test failures from a file path.

        Args:
            results_path: Path to the results file

        Returns:
            Dictionary containing extracted failures and metadata

        Raises:
            ExtractionError: If extraction fails
        """
        if not results_path.exists():
            logger.error(f"Results file not found: {results_path}")
            raise ExtractionError(f"Results file not found: {results_path}")

        try:
            with ResourceMonitor(max_time_seconds=self.timeout):
                failures = self._do_extract(results_path)
                return {
                    "failures": failures,
                    "count": len(failures),
                    "source": str(results_path),
                }
        except Exception as e:
            logger.error(f"Error extracting failures: {e}")
            raise ExtractionError(f"Failed to extract failures: {e}") from e

    def extract_failures(self, results_path: Path) -> List[PytestFailure]:
        """
        Extract test failures from a results file.

        Args:
            results_path: Path to the results file

        Returns:
            List of PytestFailure objects

        Note:
            This method is maintained for backward compatibility.
            New code should use the extract() method instead.
        """
        if not results_path.exists():
            logger.error(f"Results file not found: {results_path}")
            return []

        try:
            with ResourceMonitor(max_time_seconds=self.timeout):
                return self._do_extract(results_path)
        except Exception as e:
            logger.error(f"Error extracting failures: {e}")
            return []

    @abc.abstractmethod
    def _do_extract(self, results_path: Path) -> List[PytestFailure]:
        """
        Extract test failures from a results file.

        This is the core extraction method that concrete extractor implementations
        must implement to provide format-specific extraction logic.

        Args:
            results_path: Path to the results file

        Returns:
            List of PytestFailure objects

        Raises:
            ExtractionError: If extraction fails
        """
        pass

    @abc.abstractmethod
    def _extract_from_dict(self, data: Dict[str, Any]) -> List[PytestFailure]:
        """
        Extract test failures from a data dictionary.

        This method should be implemented by concrete extractor implementations
        to provide format-specific extraction logic for pre-parsed data.

        Args:
            data: Dictionary of pre-parsed data

        Returns:
            List of PytestFailure objects

        Raises:
            ExtractionError: If extraction fails
        """
        pass
