import pytest

from src.pytest_analyzer.core.documentation.docstring_parser import (
    DocstringParseError,
    DocstringParser,
)


def test_empty_docstring():
    def func():
        pass

    parser = DocstringParser()
    result = parser.parse(func)
    assert result == {}


def test_enhance_docstring():
    def func():
        """Short summary."""
        pass

    parser = DocstringParser()
    doc_info = parser.parse(func)
    enhanced = parser.enhance(doc_info, {"custom": "meta"})
    assert "custom" in enhanced
    assert enhanced["custom"] == "meta"


def test_invalid_docstring(monkeypatch):
    parser = DocstringParser()

    def broken_parse_google(doc):
        raise Exception("parse error")

    monkeypatch.setattr(parser, "_parse_google", broken_parse_google)

    def func():
        """Args: x (int): foo"""
        pass

    with pytest.raises(DocstringParseError):
        parser.parse(func)
