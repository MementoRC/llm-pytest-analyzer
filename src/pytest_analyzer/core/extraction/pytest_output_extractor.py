"""
Extractor for raw pytest output.

This module provides an extractor for parsing raw pytest output
(console output or text file) and converting it to PytestFailure objects.
"""

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Pattern, Tuple, Union

from ...utils.path_resolver import PathResolver
from ...utils.resource_manager import ResourceMonitor, with_timeout
from ..errors import ExtractionError
from ..models.pytest_failure import PytestFailure
from ..protocols import Extractor

logger = logging.getLogger(__name__)


class PytestOutputExtractor(Extractor):
    """
    Extracts test failures from raw pytest output.

    This class parses the raw output from pytest runs (console output or text file)
    and converts it into PytestFailure objects.
    """

    def __init__(self, path_resolver: Optional[PathResolver] = None, timeout: int = 30):
        """
        Initialize the pytest output extractor.

        Args:
            path_resolver: PathResolver instance for resolving file paths
            timeout: Timeout in seconds for extraction operations
        """
        self.path_resolver = path_resolver or PathResolver()
        self.timeout = timeout

        # Patterns for extracting information from pytest output
        self.failure_pattern: Pattern = re.compile(
            r"(FAILED|ERROR)\s+(.+?)::(.+?)(?:\s|$)"
        )
        self.test_section_pattern: Pattern = re.compile(
            r"_{3,}\s+(.+?)\s+_{3,}(.*?)(?=_{3,}|\Z)", re.DOTALL
        )
        self.error_type_pattern: Pattern = re.compile(
            r"(?:^|E\s+)([A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)*(?:Error|Exception|AssertionError)):"
        )
        self.line_number_pattern: Pattern = re.compile(r"(?:.*?\.py|.*?\.pyx):(\d+)")

    def extract(self, test_results: Union[str, Path]) -> Dict[str, Any]:
        """
        Extract test failures from pytest output.

        Args:
            test_results: The pytest output to extract from (string or path)

        Returns:
            A dictionary containing extracted failures and metadata

        Raises:
            ExtractionError: If extraction fails
        """
        try:
            # Handle different input types
            if isinstance(test_results, str):
                # Check if it's a file path or direct text content
                if os.path.exists(test_results):
                    # It might be a path string, try treating it as a path first
                    try:
                        path = Path(test_results)
                        return self._extract_from_path(path)
                    except ExtractionError:
                        # If that fails, treat it as text content
                        return self._extract_from_text(test_results)
                else:
                    # Direct text input
                    return self._extract_from_text(test_results)

            # Handle Path objects
            if isinstance(test_results, Path):
                return self._extract_from_path(test_results)

            raise ExtractionError(
                f"Unsupported test_results type: {type(test_results)}"
            )
        except Exception as e:
            logger.error(f"Error extracting from pytest output: {e}")
            raise ExtractionError(f"Failed to extract from pytest output: {e}") from e

    def _extract_from_text(self, text: str) -> Dict[str, Any]:
        """
        Extract test failures from raw pytest output text.

        Args:
            text: Raw pytest output text

        Returns:
            Dictionary containing extracted failures and metadata

        Raises:
            ExtractionError: If extraction fails
        """
        try:
            failures = self.extract_failures_from_text(text)
            return {
                "failures": failures,
                "count": len(failures),
                "source": "text",
            }
        except Exception as e:
            logger.error(f"Error extracting failures from pytest text output: {e}")
            raise ExtractionError(f"Failed to extract failures from text: {e}") from e

    @with_timeout(30)
    def _extract_from_path(self, input_path: Path) -> Dict[str, Any]:
        """
        Extract test failures from a pytest output file.

        Args:
            input_path: Path to the pytest output file (text format)

        Returns:
            Dictionary containing extracted failures and metadata

        Raises:
            ExtractionError: If extraction fails
        """
        if not input_path.exists():
            logger.error(f"Pytest output file not found: {input_path}")
            raise ExtractionError(f"Pytest output file not found: {input_path}")

        try:
            with ResourceMonitor(max_time_seconds=self.timeout):
                # Use async file reading for large files
                content = self._read_file_streaming(input_path)
                failures = self.extract_failures_from_text(content)
                return {
                    "failures": failures,
                    "count": len(failures),
                    "source": str(input_path),
                }
        except Exception as e:
            logger.error(f"Error extracting failures from pytest output: {e}")
            raise ExtractionError(f"Failed to extract failures: {e}") from e

    def _read_file_streaming(self, input_path: Path, chunk_size: int = 65536) -> str:
        """
        Read a file in streaming fashion to avoid loading large files into memory at once.

        Args:
            input_path: Path to the file
            chunk_size: Size of each chunk to read

        Returns:
            The file content as a string
        """
        try:
            # Use generator to yield chunks and join for memory efficiency
            def chunk_reader():
                with open(input_path, "r", encoding="utf-8") as f:
                    while True:
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        yield chunk

            return "".join(chunk_reader())
        except Exception as e:
            logger.error(f"Error streaming file read: {e}")
            raise

    @with_timeout(30)
    def extract_failures(self, input_path: Path) -> List[PytestFailure]:
        """
        Extract test failures from a pytest output file.

        Args:
            input_path: Path to the pytest output file (text format)

        Returns:
            List of PytestFailure objects

        Note:
            This method is maintained for backward compatibility.
            New code should use the extract() method instead.
        """
        if not input_path.exists():
            logger.error(f"Pytest output file not found: {input_path}")
            return []

        try:
            with ResourceMonitor(max_time_seconds=self.timeout):
                with open(input_path, "r", encoding="utf-8") as f:
                    content = f.read()
                return self.extract_failures_from_text(content)
        except Exception as e:
            logger.error(f"Error extracting failures from pytest output: {e}")
            return []

    def extract_failures_from_text(self, text: str) -> List[PytestFailure]:
        """
        Extract test failures from pytest output text.

        Args:
            text: Raw pytest output text

        Returns:
            List of PytestFailure objects
        """
        failures = []

        # First get a list of all failed tests
        failed_tests = self._extract_failed_tests(text)

        if not failed_tests:
            logger.debug("No test failures found in the output")
            return []

        # Extract test sections with error information
        test_sections = self._extract_test_sections(text)

        # Process each failed test
        for test_file, test_name in failed_tests:
            # Look for a matching test section - handle both formats: test_file::test_name or just test_name
            test_id = f"{test_file}::{test_name}"
            test_name_only = test_name

            # Try to find the section first by full test id, then by just test name
            section = next((s for s in test_sections if test_id in s[0]), None)
            if not section:
                section = next(
                    (s for s in test_sections if test_name_only in s[0]), None
                )

            if not section:
                logger.warning(f"No detailed section found for test {test_id}")
                # Create a minimal failure record
                failures.append(
                    PytestFailure(
                        test_name=test_name,
                        test_file=str(self.path_resolver.resolve_path(test_file)),
                        error_type="Unknown",
                        error_message="No detailed error information available",
                        traceback="",
                    )
                )
                continue

            # Extract error details
            error_type, error_message, traceback, line_number = (
                self._extract_error_details(section[1])
            )

            # Extract relevant code
            relevant_code = self._extract_relevant_code(test_file, line_number)

            # Create a PytestFailure object
            failures.append(
                PytestFailure(
                    test_name=test_name,
                    test_file=str(self.path_resolver.resolve_path(test_file)),
                    error_type=error_type,
                    error_message=error_message,
                    traceback=traceback,
                    line_number=line_number,
                    relevant_code=relevant_code,
                    raw_output_section=section[1],
                )
            )

        return failures

    def _extract_failed_tests(self, text: str) -> List[Tuple[str, str]]:
        """
        Extract failed test identifiers from pytest output.

        Args:
            text: Raw pytest output text

        Returns:
            List of (test_file, test_name) tuples
        """
        failed_tests = []

        # Try the main regular expression pattern first
        for match in self.failure_pattern.finditer(text):
            _, test_file, test_name = match.groups()
            failed_tests.append((test_file, test_name))

        # If no tests were found, try a simpler approach looking at FAILED and ERROR lines
        if not failed_tests:
            # Look for lines with FAILED or ERROR
            lines = text.split("\n")
            for line in lines:
                if " FAILED " in line or " ERROR " in line:
                    # Try to parse the line
                    parts = line.strip().split("::")
                    if len(parts) >= 2:
                        test_file = parts[0].strip()
                        # The test name might have extra info after spaces
                        test_name = parts[1].split()[0].strip()
                        failed_tests.append((test_file, test_name))

        return failed_tests

    def _extract_test_sections(self, text: str) -> List[Tuple[str, str]]:
        """
        Extract test sections from pytest output.

        Args:
            text: Raw pytest output text

        Returns:
            List of (section_header, section_content) tuples
        """
        sections = []

        # Try the regular expression first
        for match in self.test_section_pattern.finditer(text):
            header, content = match.groups()
            sections.append((header.strip(), content.strip()))

        # If no sections were found, try a different approach
        if not sections:
            # Check if there's a FAILURES section
            if "=== FAILURES ===" in text:
                failures_section = text.split("=== FAILURES ===", 1)[1]

                # Split the failures section by test headers (they typically look like ___ test_name ___)
                section_splits = [s for s in failures_section.split("___") if s.strip()]

                for i in range(0, len(section_splits) - 1, 2):
                    if i + 1 < len(section_splits):
                        header = section_splits[i].strip()
                        content = section_splits[i + 1].strip()
                        # The header might have test name and info
                        if header:
                            sections.append((header, content))

        return sections

    def _extract_error_details(
        self, section_text: str
    ) -> Tuple[str, str, str, Optional[int]]:
        """
        Extract error details from a test section.

        Args:
            section_text: Text content of a test section

        Returns:
            Tuple of (error_type, error_message, traceback, line_number)
        """
        # Default values
        error_type = "Error"
        error_message = ""
        traceback = section_text
        line_number = None

        # Extract error type
        error_type_match = self.error_type_pattern.search(section_text)
        if error_type_match:
            error_type = error_type_match.group(1)

        # Extract error message
        if "E   " in section_text:
            # Extract lines starting with E and compile them
            error_lines = []
            for line in section_text.split("\n"):
                if line.strip().startswith("E   "):
                    # Remove the E prefix
                    error_lines.append(line.strip()[4:])

            if error_lines:
                # The first line often contains the error type and message
                first_line = error_lines[0]
                if ":" in first_line and error_type in first_line:
                    # Split at the first colon after the error type
                    parts = first_line.split(":", 1)
                    if len(parts) > 1:
                        error_message = parts[1].strip()
                    else:
                        error_message = first_line
                else:
                    error_message = first_line

        # If we still don't have an error message, use a fallback approach
        if not error_message and "assert" in section_text:
            # Look for assertion failures
            for line in section_text.split("\n"):
                if "assert" in line:
                    error_message = line.strip()
                    break

        # Extract line number
        line_matches = []
        for match in self.line_number_pattern.finditer(section_text):
            line_matches.append(int(match.group(1)))

        if line_matches:
            # Use the first line number
            line_number = line_matches[0]

        return error_type, error_message, traceback, line_number

    def _extract_relevant_code(
        self, test_file: str, line_number: Optional[int]
    ) -> Optional[str]:
        """
        Extract relevant code from the test file.

        Args:
            test_file: Path to the test file
            line_number: Line number in the file

        Returns:
            Relevant code snippet or None if extraction fails
        """
        if not line_number:
            return None

        # Use LRU cache for code context extraction
        return self._get_code_context_cached(test_file, line_number)

    # LRU cache for code context extraction (cache size 128)
    from functools import lru_cache

    @lru_cache(maxsize=128)
    def _get_code_context_cached(
        self, test_file: str, line_number: int
    ) -> Optional[str]:
        try:
            # Make sure we have a valid file path
            try:
                file_path = self.path_resolver.resolve_path(test_file)
            except Exception:
                # If resolution fails, try using the test_file path directly
                file_path = Path(test_file)

            if not os.path.exists(file_path):
                logger.warning(f"Test file not found: {file_path}")
                return None

            # Use generator to avoid loading all lines into memory
            context_lines = []
            start_line = max(0, line_number - 6)
            end_line = line_number + 5
            with open(file_path, "r", encoding="utf-8") as f:
                for i, line in enumerate(f):
                    if start_line <= i < end_line:
                        context_lines.append(line)
                    if i >= end_line:
                        break

            return "".join(context_lines)
        except Exception as e:
            logger.warning(f"Error extracting code from {test_file}: {e}")
            return None
