"""A3.2 guard (S1b): only `thinkhow.platform` imports httpx — it reaches Google's redirect links."""

import ast

from test_a3_google_sdk import PACKAGE


def httpx_imports(source: str) -> list[str]:
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found += [alias.name for alias in node.names if alias.name.split(".")[0] == "httpx"]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            if node.module.split(".")[0] == "httpx":
                found.append(node.module)
    return found


def test_httpx_is_imported_only_inside_platform() -> None:
    offenders = {
        str(path.relative_to(PACKAGE)): names
        for path in PACKAGE.rglob("*.py")
        if path.relative_to(PACKAGE).parts[0] != "platform"
        and (names := httpx_imports(path.read_text(encoding="utf-8")))
    }
    assert offenders == {}


def test_the_httpx_guard_sees_imports_inside_functions() -> None:
    assert httpx_imports("def f():\n    import httpx\n    from httpx import head\n") == ["httpx", "httpx"]
