"""A3.3 and A3.4 guards (M3): who may name a bucket of people's folders, and who may write the Knowledge.

The rule is about a value — the bucket argument of a Storage call — so import-linter cannot see it
(skel-guards-deploy Q1). Strict: outside `platform/` every Storage call names its bucket with
a string constant as its first argument.
"""

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import TypeGuard

PACKAGE = Path(__file__).resolve().parents[1] / "src" / "thinkhow"
METHODS = {"read", "write", "create_if_absent", "list"}
WRITES = {"write", "create_if_absent"}
BUCKETS = {"users", "system"}


@dataclass(frozen=True)
class StorageCall:
    method: str
    bucket: str
    line: int


def storage_calls(source: str) -> list[StorageCall]:
    """Every `x.read|write|create_if_absent|list("users"|"system", …)` of the module (1-based start line)."""
    calls = []
    for node in ast.walk(ast.parse(source)):
        if _is_method_call(node) and isinstance(bucket := _constant_bucket(node), str) and bucket in BUCKETS:
            calls.append(StorageCall(_method(node), bucket, node.lineno))
    return calls


def unnamed_buckets(source: str) -> list[int]:
    """Lines of Storage-method calls whose bucket is not a constant first argument (the strict rule)."""
    lines = []
    for node in ast.walk(ast.parse(source)):
        if not _is_method_call(node) or _constant_bucket(node) in BUCKETS:
            continue
        if any(k.arg == "bucket" for k in node.keywords) or (node.args and _looks_like_bucket(node.args[0])):
            lines.append(node.lineno)
    return lines


def system_writes_outside(source: str, prefix: str) -> list[int]:
    """Lines of writes into `system` whose path is not known to start with `prefix`."""
    tree = ast.parse(source)
    bad = []
    for func in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)]:
        local = _string_assignments(func)
        for node in ast.walk(func):
            if _is_method_call(node) and _method(node) in WRITES and _constant_bucket(node) == "system":
                path = node.args[1] if len(node.args) > 1 else None
                if not _starts_with(path, prefix, local):
                    bad.append(node.lineno)
    return bad


def modules() -> list[tuple[str, str]]:
    return [
        (str(p.relative_to(PACKAGE)), p.read_text(encoding="utf-8")) for p in sorted(PACKAGE.rglob("*.py"))
    ]


def part(name: str) -> str:
    return name.split("/")[0]


def test_users_paths_are_built_only_by_workspace() -> None:
    offenders = [
        f"{name}:{call.line}"
        for name, source in modules()
        if part(name) not in ("workspace", "platform")
        for call in storage_calls(source)
        if call.bucket == "users"
    ]
    unnamed = [
        f"{name}:{line}"
        for name, source in modules()
        if part(name) != "platform"
        for line in unnamed_buckets(source)
    ]
    assert offenders == [] and unnamed == []


def test_knowledge_files_are_written_only_by_knowledge() -> None:
    offenders = [
        f"{name}:{call.line}"
        for name, source in modules()
        if part(name) not in ("knowledge", "learning", "platform")
        for call in storage_calls(source)
        if call.bucket == "system" and call.method in WRITES
    ]
    learning = [
        f"{n}:{line}"
        for n, src in modules()
        if part(n) == "learning"
        for line in system_writes_outside(src, "learning/")
    ]
    assert offenders == [] and learning == []


def test_the_guards_see_a_planted_breach() -> None:
    planted = "def f(storage):\n    storage.write('users', 'u/x', b'', 't')\n"
    assert [(c.method, c.bucket, c.line) for c in storage_calls(planted)] == [("write", "users", 2)]
    nested = "class K:\n  def g(self):\n    self.storage.create_if_absent('system', 'knowledge/x', b'', '')\n"
    assert [(c.method, c.bucket) for c in storage_calls(nested)] == [("create_if_absent", "system")]
    assert unnamed_buckets("def h(storage):\n    b = 'users'\n    storage.write(b, 'u/x', b'', 't')\n") == [3]
    assert unnamed_buckets(
        "def h(storage):\n    storage.write(bucket='users', path='u/x', data=b'', content_type='t')\n"
    ) == [2]
    assert system_writes_outside(
        "def j(s):\n    s.write('system', 'knowledge/x', b'', 't')\n", "learning/"
    ) == [2]
    ok = "def j(s, k):\n    path = f'learning/observations/{k}.json'\n    s.write('system', path, b'', 't')\n"
    assert system_writes_outside(ok, "learning/") == []


def _is_method_call(node: ast.AST) -> TypeGuard[ast.Call]:
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in METHODS


def _method(node: ast.Call) -> str:
    return node.func.attr if isinstance(node.func, ast.Attribute) else ""


def _constant_bucket(node: ast.Call) -> object:
    first = node.args[0] if node.args else None
    return first.value if isinstance(first, ast.Constant) else None


def _looks_like_bucket(arg: ast.expr) -> bool:
    """A name or an attribute as the first argument of a Storage method (a variable bucket)."""
    return isinstance(arg, ast.Name | ast.Attribute)


def _string_assignments(func: ast.AST) -> dict[str, ast.expr]:
    found: dict[str, ast.expr] = {}
    for node in ast.walk(func):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            found[node.targets[0].id] = node.value
    return found


def _starts_with(path: ast.expr | None, prefix: str, local: dict[str, ast.expr]) -> bool:
    if isinstance(path, ast.Name) and path.id in local:
        path = local[path.id]
    if isinstance(path, ast.Constant) and isinstance(path.value, str):
        return path.value.startswith(prefix)
    if isinstance(path, ast.JoinedStr) and path.values and isinstance(path.values[0], ast.Constant):
        return str(path.values[0].value).startswith(prefix)
    return False
