"""DISPUTED (Q3): `list(bucket, prefix)` has Cloud Storage prefix semantics in both implementations:
a plain string prefix over full paths, recursive; "" and a trailing "/" are lawful prefixes.
Not sealed until answered."""

from pathlib import Path

from skelp_fakes import FakeGcsClient

from thinkhow.platform.storage import GcsStorage, LocalStorage

FILES = ["u1/sub/b.json", "u1/cards.json", "u10/c.json", "u1/a.json"]


def test_q3_list_is_a_recursive_string_prefix_over_full_paths(tmp_path: Path) -> None:
    client = FakeGcsClient(["bu", "bs"])
    for store in (LocalStorage(tmp_path), GcsStorage(client, {"users": "bu", "system": "bs"})):
        for path in FILES:
            store.write("users", path, b"x", "application/json")
        assert store.list("users", "u1/") == ["u1/a.json", "u1/cards.json", "u1/sub/b.json"]
        assert store.list("users", "u1/ca") == ["u1/cards.json"]
        assert store.list("users", "u1") == ["u1/a.json", "u1/cards.json", "u1/sub/b.json", "u10/c.json"]
        assert store.list("users", "") == ["u1/a.json", "u1/cards.json", "u1/sub/b.json", "u10/c.json"]
        assert store.list("users", "nobody/") == []
