import verbatim


def test_version_is_non_empty_string() -> None:
    assert isinstance(verbatim.__version__, str)
    assert verbatim.__version__ != ""
