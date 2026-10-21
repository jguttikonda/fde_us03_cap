from importlib import import_module
from importlib.metadata import version


def test_required_runtime_dependencies_are_available() -> None:
    for module in ("google.adk", "pydantic", "pydantic_settings"):
        import_module(module)

    assert version("google-adk")
    assert version("pydantic").split(".", maxsplit=1)[0] == "2"
    assert version("pydantic-settings")
