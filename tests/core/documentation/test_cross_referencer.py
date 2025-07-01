from pytest_analyzer.core.documentation.cross_referencer import CrossReferencer


class DummyModule:
    def foo(self):
        pass

    bar = 42


def test_resolve_with_root_module():
    dummy = DummyModule()
    ref = CrossReferencer(root_module=dummy)
    assert ref.resolve("foo") == f"{dummy.foo.__module__}.{dummy.foo.__name__}"


def test_resolve_with_context():
    dummy = DummyModule()
    ref = CrossReferencer()
    assert (
        ref.resolve("foo", context=dummy)
        == f"{dummy.foo.__module__}.{dummy.foo.__name__}"
    )


def test_resolve_unresolved_returns_none():
    ref = CrossReferencer()
    assert ref.resolve("nonexistent") is None


def test_format_link_with_template():
    ref = CrossReferencer()
    url = ref.format_link(
        "os.path.join", url_template="https://docs.python.org/3/library/{ref}.html"
    )
    assert url == "https://docs.python.org/3/library/os/path/join.html"


def test_format_link_without_template():
    ref = CrossReferencer()
    assert ref.format_link("os.path.join") == "os.path.join"
