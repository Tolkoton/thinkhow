"""Contract tests of skel-guards-deploy: `storage_calls` of `tests/test_a3_guards.py` (slice tester).

Seam 1: a guard whose finder finds nothing would pass every scan of the tree — these feed it
hand-written source.
"""

from skelgd_files import guards_module


def pairs(source: str) -> list[tuple[str, str]]:
    return sorted((call.method, call.bucket) for call in guards_module().storage_calls(source))


def test_storage_calls_finds_a_write_to_users_inside_a_function() -> None:
    source = 'def f(storage):\n    storage.write("users", "u1/t1/conversation.md", b"x", "text/markdown")\n'
    assert pairs(source) == [("write", "users")]


def test_storage_calls_finds_create_if_absent_on_self_storage_with_system() -> None:
    source = (
        "class K:\n"
        "    def seed(self):\n"
        '        self.storage.create_if_absent("system", "knowledge/x", b"{}", "application/json")\n'
    )
    assert pairs(source) == [("create_if_absent", "system")]


def test_storage_calls_finds_read_and_list_too() -> None:
    source = (
        "def g(storage):\n"
        '    data = storage.read("system", "knowledge/cards/a.json")\n'
        '    return storage.list("users", "u1/")\n'
    )
    assert pairs(source) == [("list", "users"), ("read", "system")]


def test_storage_calls_ignores_other_methods_other_buckets_and_users_not_first() -> None:
    source = (
        "def h(storage, path):\n"
        '    storage.delete("users", "x")\n'
        '    storage.write("other", "x", b"", "t")\n'
        '    storage.write(path, "users", b"", "t")\n'
        '    print("users")\n'
    )
    assert pairs(source) == []
