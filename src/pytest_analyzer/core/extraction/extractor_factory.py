import logging
from pathlib import Path
from typing import Optional, Type, Union

from ...utils.path_resolver import PathResolver
from ...utils.settings import Settings
from ..infrastructure.base_factory import BaseFactory
from .json_extractor import JsonResultExtractor
from .xml_extractor import XmlResultExtractor

logger = logging.getLogger(__name__)


class BaseExtractor:
    """Base class for all extractors with a common interface."""

    def extract_failures(self, input_path: Path):
        """Extract failures from the input path."""
        raise NotImplementedError("Subclasses must implement extract_failures")


# Type alias for extractor classes
ExtractorClass = Type[Union[JsonResultExtractor, XmlResultExtractor]]


class ExtractorFactory(BaseFactory):
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
        super().__init__(settings)
        self.path_resolver = path_resolver or PathResolver(self.settings.project_root)

        # Register default extractors
        self.register("json", JsonResultExtractor)
        self.register("xml", XmlResultExtractor)

    def create(
        self, input_path: Path
    ) -> Union[JsonResultExtractor, XmlResultExtractor]:
        """
        Create an extractor instance for the given input file.

        Args:
            input_path: Path to the input file

        Returns:
            An appropriate extractor instance.
        """
        file_ext_key = self._detect_file_type(str(input_path))  # e.g., "json", "xml"
        extractor_class: Optional[ExtractorClass] = None

        if file_ext_key:
            try:
                extractor_class = self.get_implementation(file_ext_key)
                logger.debug(
                    f"Using {extractor_class.__name__} for {input_path} based on extension '.{file_ext_key}'"
                )
            except KeyError:
                logger.debug(
                    f"Extension '.{file_ext_key}' not directly registered. Attempting content detection for {input_path}."
                )
                # Fall through to content detection

        if not extractor_class:
            if self._is_json_file(input_path):
                logger.debug(f"Detected JSON content in {input_path}")
                extractor_class = self.get_implementation("json")
            elif self._is_xml_file(input_path):
                logger.debug(f"Detected XML content in {input_path}")
                extractor_class = self.get_implementation("xml")
            else:
                # Default to JSON extractor with a warning
                warning_msg = f"Unsupported or ambiguous file type for {input_path}"
                if file_ext_key:  # if an extension was detected but not matched
                    warning_msg += f" (extension: '.{file_ext_key}')"
                warning_msg += ", defaulting to JSON extractor"
                logger.warning(warning_msg)
                extractor_class = self.get_implementation("json")

        return extractor_class(
            path_resolver=self.path_resolver, timeout=self.settings.parser_timeout
        )

    def get_extractor(
        self, input_path: Path
    ) -> Union[JsonResultExtractor, XmlResultExtractor]:
        """
        Get the appropriate extractor for the input path.
        Maintains backward compatibility.

        Args:
            input_path: Path to the input file

        Returns:
            Appropriate extractor instance

        Raises:
            ValueError: If the input file type is not supported or file not found
        """
        # Check if the input path exists
        if not input_path.exists():
            raise ValueError(f"Input file not found: {input_path}")

        return self.create(input_path)

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


def get_extractor(
    input_path: Path,
    settings: Optional[Settings] = None,
    path_resolver: Optional[PathResolver] = None,
) -> Union[JsonResultExtractor, XmlResultExtractor]:
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
