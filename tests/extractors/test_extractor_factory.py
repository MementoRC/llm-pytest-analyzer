"""Tests for the extractor factory module."""

from pathlib import Path

import pytest

from src.pytest_analyzer.core.extraction.extractor_factory import (
    ExtractorFactory,
    get_extractor,
)
from src.pytest_analyzer.core.extraction.json_extractor import JsonResultExtractor
from src.pytest_analyzer.core.extraction.xml_extractor import XmlResultExtractor
from src.pytest_analyzer.utils.path_resolver import PathResolver
from src.pytest_analyzer.utils.settings import Settings


@pytest.fixture
def settings():
    """Provide a Settings instance for testing."""
    return Settings()


@pytest.fixture
def path_resolver():
    """Provide a PathResolver instance for testing."""
    return PathResolver()


@pytest.fixture
def factory(settings, path_resolver):
    """Provide an ExtractorFactory instance for testing."""
    return ExtractorFactory(settings=settings, path_resolver=path_resolver)


def test_get_extractor_json(tmp_path, factory):
    """Test getting a JSON extractor."""
    # Create a JSON file
    json_path = tmp_path / "report.json"
    json_path.touch()

    # Get an extractor
    extractor = factory.get_extractor(json_path)

    # Verify the result
    assert isinstance(extractor, JsonResultExtractor)


def test_get_extractor_xml(tmp_path, factory):
    """Test getting an XML extractor."""
    # Create an XML file
    xml_path = tmp_path / "report.xml"
    xml_path.touch()

    # Get an extractor
    extractor = factory.get_extractor(xml_path)

    # Verify the result
    assert isinstance(extractor, XmlResultExtractor)


def test_get_extractor_unknown_extension(tmp_path, factory):
    """Test getting an extractor for an unknown file extension."""
    # Create a file with an unknown extension
    unknown_path = tmp_path / "report.unknown"
    unknown_path.touch()

    # Get an extractor
    extractor = factory.get_extractor(unknown_path)

    # Verify the result (should default to JSON)
    assert isinstance(extractor, JsonResultExtractor)


def test_get_extractor_nonexistent_file(factory):
    """Test getting an extractor for a nonexistent file."""
    # Attempt to get an extractor for a nonexistent file
    with pytest.raises(ValueError, match="Input file not found"):
        factory.get_extractor(Path("/nonexistent/file.json"))


def test_is_json_file(tmp_path, factory):
    """Test detecting a JSON file."""
    # Create a JSON file
    json_path = tmp_path / "report.json"
    with open(json_path, "w") as f:
        f.write('{"key": "value"}')

    # Check if it's a JSON file
    assert factory._is_json_file(json_path) is True


def test_is_json_file_invalid(tmp_path, factory):
    """Test detecting an invalid JSON file."""
    # Create an invalid JSON file
    json_path = tmp_path / "invalid.json"
    with open(json_path, "w") as f:
        f.write("This is not valid JSON")

    # Check if it's a JSON file
    assert factory._is_json_file(json_path) is False


def test_is_xml_file(tmp_path, factory):
    """Test detecting an XML file."""
    # Create an XML file
    xml_path = tmp_path / "report.xml"
    with open(xml_path, "w") as f:
        f.write("<root><child>value</child></root>")

    # Check if it's an XML file
    assert factory._is_xml_file(xml_path) is True


def test_is_xml_file_invalid(tmp_path, factory):
    """Test detecting an invalid XML file."""
    # Create an invalid XML file
    xml_path = tmp_path / "invalid.xml"
    with open(xml_path, "w") as f:
        f.write("This is not valid XML")

    # Check if it's an XML file
    assert factory._is_xml_file(xml_path) is False


def test_factory_constructor_defaults():
    """Test factory constructor with default arguments."""
    # Create a factory with default arguments
    factory = ExtractorFactory()

    # Verify the defaults
    assert isinstance(factory.settings, Settings)
    assert isinstance(factory.path_resolver, PathResolver)


def test_get_extractor_convenience_function(tmp_path, settings, path_resolver):
    """Test the convenience function for getting an extractor."""
    # Create a JSON file
    json_path = tmp_path / "report.json"
    json_path.touch()

    # Get an extractor using the convenience function
    extractor = get_extractor(json_path, settings, path_resolver)

    # Verify the result
    assert isinstance(extractor, JsonResultExtractor)
