"""
Extractor factory module for pytest_analyzer.

This module provides the ExtractorFactory class that creates the appropriate
extractor for a given input file type.
"""

import logging
from pathlib import Path
from typing import Dict, Optional, Type

from ...utils.path_resolver import PathResolver
from ...utils.settings import Settings
from ..protocols import Extractor
from .base import BaseExtractor
from .json_extractor import JsonResultExtractor
from .pytest_output_extractor import PytestOutputExtractor
from .xml_extractor import XmlResultExtractor

logger = logging.getLogger(__name__)


# Type alias for extractor classes
ExtractorClass = Type[BaseExtractor]


class ExtractorFactory:
    """Factory for creating extractors based on input type."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        path_resolver: Optional[PathResolver] = None,
    ):
        """
        Initialize the extractor factory.

        Args:
            settings: Settings object
            path_resolver: PathResolver instance
        """
        self.settings = settings or Settings()
        self.path_resolver = path_resolver or PathResolver(self.settings.project_root)

        # Map of file extensions to extractor classes
        self.extractor_map: Dict[str, ExtractorClass] = {
            ".json": JsonResultExtractor,
            ".xml": XmlResultExtractor,
            ".txt": PytestOutputExtractor,
            ".log": PytestOutputExtractor,
        }

    def get_extractor(self, input_path: Path) -> Extractor:
        """
        Get the appropriate extractor for the input path.

        Args:
            input_path: Path to the input file

        Returns:
            Appropriate extractor instance

        Raises:
            ValueError: If the input file type is not supported
        """
        # Check if the input path exists
        if not input_path.exists():
            raise ValueError(f"Input file not found: {input_path}")

        # Determine the file type based on extension
        file_ext = input_path.suffix.lower()

        if file_ext in self.extractor_map:
            extractor_class = self.extractor_map[file_ext]
            logger.debug(f"Using {extractor_class.__name__} for {input_path}")
            return extractor_class(
                path_resolver=self.path_resolver, timeout=self.settings.parser_timeout
            )

        # If the extension is not recognized, try to guess the file type
        if self._is_json_file(input_path):
            logger.debug(f"Detected JSON content in {input_path}")
            return JsonResultExtractor(
                path_resolver=self.path_resolver, timeout=self.settings.parser_timeout
            )

        if self._is_xml_file(input_path):
            logger.debug(f"Detected XML content in {input_path}")
            return XmlResultExtractor(
                path_resolver=self.path_resolver, timeout=self.settings.parser_timeout
            )

        # Try to see if it's a pytest output file by checking for common patterns
        if self._is_pytest_output_file(input_path):
            logger.debug(f"Detected pytest output content in {input_path}")
            return PytestOutputExtractor(
                path_resolver=self.path_resolver, timeout=self.settings.parser_timeout
            )

        # Default to JSON extractor with a warning
        logger.warning(
            f"Unsupported file type: {file_ext}, defaulting to JSON extractor"
        )
        return JsonResultExtractor(
            path_resolver=self.path_resolver, timeout=self.settings.parser_timeout
        )

    def _is_json_file(self, file_path: Path) -> bool:
        """
        Check if a file contains JSON content.

        Args:
            file_path: Path to the file

        Returns:
            True if the file contains JSON content, False otherwise
        """
        try:
            with file_path.open("r") as f:
                # Read the first 1000 characters to check for JSON content
                content = f.read(1000)
                return content.strip().startswith("{") or content.strip().startswith(
                    "["
                )
        except Exception:
            return False

    def _is_xml_file(self, file_path: Path) -> bool:
        """
        Check if a file contains XML content.

        Args:
            file_path: Path to the file

        Returns:
            True if the file contains XML content, False otherwise
        """
        try:
            with file_path.open("r") as f:
                # Read the first 1000 characters to check for XML content
                content = f.read(1000)
                return content.strip().startswith("<")
        except Exception:
            return False

    def _is_pytest_output_file(self, file_path: Path) -> bool:
        """
        Check if a file contains pytest output.

        Args:
            file_path: Path to the file

        Returns:
            True if the file contains pytest output, False otherwise
        """
        try:
            with file_path.open("r") as f:
                # Read the first 1000 characters to check for pytest patterns
                content = f.read(1000)
                # Look for common pytest output patterns
                return (
                    "=== test session starts ===" in content
                    or "collected " in content
                    and "item" in content
                    or "PASSED" in content
                    or "FAILED" in content
                    or "ERROR" in content
                    and "=== FAILURES ===" in content
                )
        except Exception:
            return False


def get_extractor(
    input_path: Path,
    settings: Optional[Settings] = None,
    path_resolver: Optional[PathResolver] = None,
) -> Extractor:
    """
    Convenience function to get an extractor for the input path.

    Args:
        input_path: Path to the input file
        settings: Settings object
        path_resolver: PathResolver instance

    Returns:
        Appropriate extractor instance
    """
    factory = ExtractorFactory(settings, path_resolver)
    return factory.get_extractor(input_path)
