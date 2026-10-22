"""Contract tests of skel-platform: storage.py (slice tester; written from the contract, not the code)."""

from pathlib import Path

import pytest
from skelp_fakes import FakeGcsClient

from thinkhow.platform.config import Settings
from thinkhow.platform.storage import Bucket, GcsStorage, LocalStorage, make_storage

NAMES: dict[Bucket, str] = {"users": "th-users-bkt", "system": "th-system-bkt"}

BAD_PATHS = ["../x", "a/../b", "..", ".", "./a", "a/./b", "a//b", "/abs", "/", "", "a/", "a/b/.."]
BAD_PREFIXES = ["../x", "a/../b", "..", "./a", "a/./b", "a//b", "/abs"]


def gcs() -> tuple[GcsStorage, FakeGcsClient]:
    client = FakeGcsClient(list(NAMES.values()))
    return GcsStorage(client, NAMES), client


def all_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*") if p.is_file())


# ------------------------------------------------------------------ LocalStorage


def test_local_write_lands_at_root_bucket_path_and_reads_back(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    store.write("users", "u1/cards/c1.json", b'{"a": 1}', "application/json")
    assert (tmp_path / "users" / "u1" / "cards" / "c1.json").read_bytes() == b'{"a": 1}'
    assert store.read("users", "u1/cards/c1.json") == b'{"a": 1}'
    (tmp_path / "system" / "seed").mkdir(parents=True)
    (tmp_path / "system" / "seed" / "k.md").write_bytes("знання".encode())
    assert store.read("system", "seed/k.md") == "знання".encode()


def test_local_read_of_a_missing_file_is_none(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    assert store.read("users", "u1/nothing.json") is None
    store.write("users", "u1/a.json", b"x", "application/json")
    assert store.read("system", "u1/a.json") is None


def test_local_list_gives_full_paths_inside_the_bucket_sorted(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    for path in ("u1/b.json", "u1/a.json", "u2/c.json"):
        store.write("users", path, b"x", "application/json")
    store.write("system", "u1/z.json", b"x", "application/json")
    assert store.list("users", "u1") == ["u1/a.json", "u1/b.json"]


def test_local_create_if_absent_creates_and_reports_true(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    assert store.create_if_absent("users", "u1/changes/1.json", b"first", "application/json") is True
    assert store.read("users", "u1/changes/1.json") == b"first"


# ------------------------------------------------------------------ GcsStorage (fake client)


def test_gcs_write_read_go_to_the_named_bucket() -> None:
    store, client = gcs()
    store.write("users", "u1/a.json", b'{"x": 1}', "application/json")
    assert client.buckets["th-users-bkt"].objects == {"u1/a.json": b'{"x": 1}'}
    assert client.buckets["th-system-bkt"].objects == {}
    assert store.read("users", "u1/a.json") == b'{"x": 1}'
    uploads = [op for op in client.io if op[0] == "upload"]
    assert uploads and uploads[-1][3]["content_type"] == "application/json"


def test_gcs_read_of_a_missing_object_is_none() -> None:
    store, client = gcs()
    assert store.read("system", "seed/none.md") is None


def test_gcs_list_gives_full_paths_sorted() -> None:
    store, client = gcs()
    bucket = client.buckets["th-users-bkt"]
    bucket.objects.update({"u1/b.json": b"x", "u1/a.json": b"x", "u2/c.json": b"x"})
    client.buckets["th-system-bkt"].objects["u1/z.json"] = b"x"
    assert store.list("users", "u1") == ["u1/a.json", "u1/b.json"]


def test_gcs_create_if_absent_sends_generation_match_zero_and_maps_precondition_to_false() -> None:
    # absent: created, with the precondition, True
    store, client = gcs()
    assert store.create_if_absent("users", "u1/changes/1.json", b"first", "application/json") is True
    uploads = [op for op in client.io if op[0] == "upload"]
    assert uploads and all(op[3].get("if_generation_match") == 0 for op in uploads)
    assert client.buckets["th-users-bkt"].objects["u1/changes/1.json"] == b"first"
    # a race: every read says absent, but the object appears before the upload -> PreconditionFailed -> False
    store, client = gcs()
    client.buckets["th-users-bkt"].racing.add("u1/changes/2.json")
    assert store.create_if_absent("users", "u1/changes/2.json", b"mine", "application/json") is False
    uploads = [op for op in client.io if op[0] == "upload"]
    assert uploads and uploads[-1][3].get("if_generation_match") == 0
    assert "u1/changes/2.json" not in client.buckets["th-users-bkt"].objects


# ------------------------------------------------------------------ make_storage


def test_make_storage_local_keeps_files_under_local_dir(tmp_path: Path) -> None:
    store = make_storage(Settings(local=True, local_dir=tmp_path))
    assert isinstance(store, LocalStorage)
    store.write("users", "u1/a.json", b"hello", "application/json")
    assert store.read("users", "u1/a.json") == b"hello"
    assert b"hello" in [p.read_bytes() for p in all_files(tmp_path)]


# ------------------------------------------------------------------ invariants


def test_I2_create_if_absent_never_changes_an_existing_file(tmp_path: Path) -> None:
    local = LocalStorage(tmp_path)
    gstore, client = gcs()
    for store in (local, gstore):
        # created, then refused
        assert store.create_if_absent("users", "u1/seed.json", b"one", "application/json") is True
        assert store.create_if_absent("users", "u1/seed.json", b"two", "application/json") is False
        assert store.read("users", "u1/seed.json") == b"one"
        # written by write, then refused
        store.write("system", "k/changes/7.json", "кирилиця".encode(), "application/json")
        assert store.create_if_absent("system", "k/changes/7.json", b"other", "application/json") is False
        assert store.read("system", "k/changes/7.json") == "кирилиця".encode()
        # an existing EMPTY file is still existing
        store.write("users", "u1/empty", b"", "text/plain")
        assert store.create_if_absent("users", "u1/empty", b"not empty", "text/plain") is False
        assert store.read("users", "u1/empty") == b""
        # the same path in the other bucket is a different file
        assert store.create_if_absent("system", "u1/seed.json", b"sys", "application/json") is True
        assert store.read("users", "u1/seed.json") == b"one"
    assert client.buckets["th-users-bkt"].objects["u1/seed.json"] == b"one"


def test_I3_bad_path_never_reaches_disk_or_cloud_storage(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (tmp_path / "secret.txt").write_bytes(b"outside")
    local = LocalStorage(root)
    gstore, client = gcs()
    client.buckets["th-users-bkt"].objects["secret.txt"] = b"outside"
    for store in (local, gstore):
        for path in BAD_PATHS:
            with pytest.raises(ValueError):
                store.read("users", path)
            with pytest.raises(ValueError):
                store.write("users", path, b"evil", "text/plain")
            with pytest.raises(ValueError):
                store.create_if_absent("users", path, b"evil", "text/plain")
        for prefix in BAD_PREFIXES:
            with pytest.raises(ValueError):
                store.list("users", prefix)
        # a refused path does not stop a lawful one afterwards
        store.write("users", "u1/ok.json", b"ok", "application/json")
        assert store.read("users", "u1/ok.json") == b"ok"
    assert (root / "users" / "u1" / "ok.json").read_bytes() == b"ok"
    assert b"evil" not in [p.read_bytes() for p in all_files(tmp_path)]
    assert (tmp_path / "secret.txt").read_bytes() == b"outside"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["root", "secret.txt"]
    io_before_lawful = [op for op in client.io if op[2] != "u1/ok.json"]
    assert io_before_lawful == []
    assert client.buckets["th-users-bkt"].objects == {"secret.txt": b"outside", "u1/ok.json": b"ok"}
