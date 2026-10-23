"""Contract tests of voice-language: how the profile is written (workspace), from the contract."""

import json
from pathlib import Path

from vl_fakes import ALICE, profile_bytes

from thinkhow.platform.storage import Bucket, LocalStorage
from thinkhow.workspace import ensure_profile, set_language


class RecordingStorage(LocalStorage):
    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.writes: list[tuple[str, str, bytes, str]] = []

    def write(self, bucket: Bucket, path: str, data: bytes, content_type: str) -> None:
        self.writes.append((bucket, path, data, content_type))
        super().write(bucket, path, data, content_type)


def test_set_language_writes_the_whole_profile_as_utf8_application_json(tmp_path: Path) -> None:
    store = RecordingStorage(tmp_path / "data")
    set_language(store, ALICE, "uk-UA")
    assert len(store.writes) == 1
    bucket, path, data, content_type = store.writes[0]
    assert (bucket, path) == ("users", "alice-1/profile.json")
    assert content_type.split(";")[0].strip() == "application/json"
    assert json.loads(data.decode("utf-8")) == {"email": "alice@example.com", "language": "uk-UA"}


def test_ensure_profile_still_creates_an_absent_profile_with_the_email_only(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path / "data")
    ensure_profile(store, ALICE)
    raw = profile_bytes(store, ALICE)
    assert raw is not None
    assert json.loads(raw.decode("utf-8")) == {"email": "alice@example.com"}
