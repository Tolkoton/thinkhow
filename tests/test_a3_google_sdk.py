"""A3.2 guard: only `thinkhow.platform` imports a Google SDK — every module, imports inside functions too."""

import ast
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1] / "src" / "thinkhow"


def google_imports(source: str) -> list[str]:
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found += [alias.name for alias in node.names if alias.name.split(".")[0] == "google"]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            if node.module.split(".")[0] == "google":
                found.append(node.module)
    return found


def test_google_sdk_is_imported_only_inside_platform() -> None:
    offenders = {
        str(path.relative_to(PACKAGE)): names
        for path in PACKAGE.rglob("*.py")
        if path.relative_to(PACKAGE).parts[0] != "platform"
        and (names := google_imports(path.read_text(encoding="utf-8")))
    }
    assert offenders == {}


def test_the_guard_sees_imports_at_any_depth() -> None:
    source = "def f():\n    from google.cloud import storage\n    import google.genai as g\n"
    assert google_imports(source) == ["google.cloud", "google.genai"]


def test_the_guard_ignores_names_that_only_start_with_google() -> None:
    assert google_imports("import googlemaps\nfrom .google import x\n") == []
