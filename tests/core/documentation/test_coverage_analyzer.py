import types

import pytest

from pytest_analyzer.core.documentation.coverage_analyzer import (
    CoverageAnalyzer,
    CoverageAnalyzerError,
)


def documented_func():
    """This is documented."""
    pass


def undocumented_func():
    pass


class DocumentedClass:
    """Docstring here."""

    def method(self):
        pass


class UndocumentedClass:
    pass


def test_analyze_module_coverage():
    mod = types.ModuleType("testmod")
    mod.documented_func = documented_func
    mod.undocumented_func = undocumented_func
    mod.DocumentedClass = DocumentedClass
    mod.UndocumentedClass = UndocumentedClass

    analyzer = CoverageAnalyzer()
    result = analyzer.analyze(mod)
    assert result["total"] == 4
    assert result["documented"] == 2
    assert result["undocumented"] == 2
    assert "undocumented_func" in result["undocumented_items"]
    assert "UndocumentedClass" in result["undocumented_items"]
    assert result["coverage"] == 50.0


def test_analyze_empty_module():
    mod = types.ModuleType("empty")
    analyzer = CoverageAnalyzer()
    result = analyzer.analyze(mod)
    assert result["total"] == 0
    assert result["coverage"] == 100.0


def test_analyze_raises_on_error(monkeypatch):
    analyzer = CoverageAnalyzer()

    class Broken:
        pass

    # Patch inspect.getmembers to raise
    monkeypatch.setattr(
        "inspect.getmembers", lambda m: (_ for _ in ()).throw(Exception("fail"))
    )
    with pytest.raises(CoverageAnalyzerError):
        analyzer.analyze(Broken)
