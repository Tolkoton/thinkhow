"""Task 204: a person deletes a topic of their own — every file of its folder in `users`, nobody else's."""

from __future__ import annotations

import ast
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from google.api_core.exceptions import NotFound

from thinkhow.access import CurrentUser
from thinkhow.platform.config import load_settings
from thinkhow.platform.identity import IapIdentity
from thinkhow.platform.speech import ScriptedSpeech
from thinkhow.platform.storage import Bucket, GcsStorage, LocalStorage
from thinkhow.web.server import Deps, create_app
from thinkhow.workspace import (
    TopicNotFound,
    TopicRef,
    all_topics_for_learning,
    create_topic,
    delete_topic,
    ensure_profile,
    list_topics,
    open_topic,
    set_language,
)

T0 = datetime(2026, 10, 25, 12, 0, 0, tzinfo=UTC)
ALICE = CurrentUser(id="alice-1", email="alice@example.com", is_owner=False)
OWNER = CurrentUser(id="owner-0", email="owner@example.com", is_owner=True)
TOKENS = {
    "tok-alice": {"sub": "accounts.google.com:alice-1", "email": "alice@example.com"},
    "tok-owner": {"sub": "accounts.google.com:owner-0", "email": "owner@example.com"},
}
H_ALICE = {"x-goog-iap-jwt-assertion": "tok-alice"}
H_OWNER = {"x-goog-iap-jwt-assertion": "tok-owner"}
EXTRA = {
    "routing.json": b'{"decisions": []}',
    "research.json": b'{"entries": []}',
    "notes/voice.webm": b"x",
}


def _topic(store: LocalStorage, user: CurrentUser, title: str) -> TopicRef:
    ref = TopicRef(user.id, create_topic(store, user, title, T0))
    for name, data in EXTRA.items():
        store.write("users", f"{ref.uid}/{ref.topic_id}/{name}", data, "application/octet-stream")
    return ref


def _files(store: LocalStorage, ref: TopicRef) -> list[str]:
    return store.list("users", f"{ref.uid}/{ref.topic_id}/")


# --- storage -------------------------------------------------------------------------------------


def test_local_delete_removes_the_file_and_a_missing_file_is_no_error(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    store.write("users", "u/t/a.json", b"1", "application/json")
    store.delete("users", "u/t/a.json")
    store.delete("users", "u/t/a.json")
    assert store.read("users", "u/t/a.json") is None


def test_local_delete_refuses_an_unsafe_path(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        LocalStorage(tmp_path).delete("users", "../system/x")


def _not_found() -> Exception:
    """google.api_core's exception constructors are untyped: one typed door, as in skelp_fakes."""
    kind: Any = NotFound
    exc: Exception = kind("gone")
    return exc


class _Blob:
    def __init__(self, found: bool, deleted: list[str], name: str) -> None:
        self.found, self.deleted, self.name = found, deleted, name

    def delete(self) -> None:
        if not self.found:
            raise _not_found()
        self.deleted.append(self.name)


class _Client:
    def __init__(self, found: bool) -> None:
        self.found = found
        self.deleted: list[str] = []
        self.bucket_name = ""

    def bucket(self, name: str) -> Any:
        self.bucket_name = name
        client = self

        class _Bucket:
            def blob(self, path: str) -> _Blob:
                return _Blob(client.found, client.deleted, path)

        return _Bucket()


def test_gcs_delete_deletes_the_blob_of_the_named_bucket_and_a_missing_one_is_no_error() -> None:
    names: dict[Bucket, str] = {"users": "real-users", "system": "real-system"}
    client = _Client(found=True)
    GcsStorage(client, names).delete("users", "u/t/a.json")
    assert (client.bucket_name, client.deleted) == ("real-users", ["u/t/a.json"])
    GcsStorage(_Client(found=False), names).delete("users", "u/t/a.json")


def test_only_workspace_topics_deletes_and_only_in_users() -> None:
    package = Path(__file__).resolve().parents[2] / "src" / "thinkhow"
    calls = []
    for file in sorted(package.rglob("*.py")):
        for node in ast.walk(ast.parse(file.read_text(encoding="utf-8"))):
            func = node.func if isinstance(node, ast.Call) else None
            if isinstance(node, ast.Call) and isinstance(func, ast.Attribute) and func.attr == "delete":
                first = node.args[0] if node.args else None
                bucket = first.value if isinstance(first, ast.Constant) else None
                calls.append((file.relative_to(package).as_posix(), bucket))
    assert {c for c in calls if not c[0].startswith("platform/")} == {("workspace/topics.py", "users")}


# --- workspace -----------------------------------------------------------------------------------


def test_delete_topic_removes_every_file_of_its_folder_and_nothing_else(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    ensure_profile(store, ALICE)
    gone, kept = _topic(store, ALICE, "Непотрібна"), _topic(store, ALICE, "Потрібна")
    assert len(_files(store, gone)) == 5
    delete_topic(store, ALICE, gone)
    assert _files(store, gone) == []
    assert len(_files(store, kept)) == 5
    assert store.read("users", "alice-1/profile.json") is not None


def test_a_deleted_topic_is_gone_from_every_list_and_cannot_be_opened(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    gone, kept = _topic(store, ALICE, "Непотрібна"), _topic(store, ALICE, "Потрібна")
    delete_topic(store, ALICE, gone)
    assert [t.title for t in list_topics(store, ALICE)] == ["Потрібна"]
    assert list(all_topics_for_learning(store)) == [kept]
    with pytest.raises(TopicNotFound):
        open_topic(store, ALICE, gone, T0)


def test_conversation_md_is_deleted_last_so_a_broken_delete_leaves_the_topic_listed(tmp_path: Path) -> None:
    order: list[str] = []

    class Spy(LocalStorage):
        def delete(self, bucket: Bucket, path: str) -> None:
            order.append(path.rsplit("/", 1)[-1])
            if path.endswith("research.json"):
                raise OSError("storage broke")
            super().delete(bucket, path)

    store = Spy(tmp_path)
    ref = _topic(store, ALICE, "Тема")
    with pytest.raises(OSError):
        delete_topic(store, ALICE, ref)
    assert "conversation.md" not in order
    assert [t.ref for t in list_topics(store, ALICE)] == [ref]
    store_ok = LocalStorage(tmp_path)
    delete_topic(store_ok, ALICE, ref)
    assert _files(store_ok, ref) == []


def test_conversation_md_comes_last_in_the_delete_order(tmp_path: Path) -> None:
    order: list[str] = []

    class Spy(LocalStorage):
        def delete(self, bucket: Bucket, path: str) -> None:
            order.append(path.rsplit("/", 1)[-1])
            super().delete(bucket, path)

    store = Spy(tmp_path)
    delete_topic(store, ALICE, _topic(store, ALICE, "Тема"))
    assert order[-1] == "conversation.md" and len(order) == 5


def test_nobody_deletes_a_topic_of_another_person_not_even_the_owner(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    ref = _topic(store, ALICE, "Тема Аліси")
    with pytest.raises(TopicNotFound):
        delete_topic(store, OWNER, ref)
    assert len(_files(store, ref)) == 5


def test_an_unknown_or_malformed_topic_is_not_found_and_touches_nothing(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    ref = _topic(store, ALICE, "Тема")
    with pytest.raises(TopicNotFound):
        delete_topic(store, ALICE, TopicRef(ALICE.id, "t-000000000000"))
    with pytest.raises(TopicNotFound):
        delete_topic(store, ALICE, TopicRef(ALICE.id, "../" + ref.topic_id))
    assert len(_files(store, ref)) == 5


# --- web -----------------------------------------------------------------------------------------


def _client(tmp_path: Path, store: LocalStorage) -> TestClient:
    settings = load_settings(
        {"THINKHOW_LOCAL": "true", "THINKHOW_LOCAL_DIR": str(tmp_path), "THINKHOW_OWNER_EMAIL": OWNER.email}
    )
    identity = IapIdentity("aud", lambda token, audience: TOKENS[token])
    deps = Deps(store, identity, settings, lambda ctx: iter(()), lambda: T0, ScriptedSpeech(""))
    for user in (ALICE, OWNER):
        set_language(store, user, "uk-UA")
    return TestClient(create_app(deps), raise_server_exceptions=False)


def _url(ref: TopicRef) -> str:
    return f"/topics/{ref.uid}/{ref.topic_id}"


def _delete_forms(html: str) -> list[str]:
    return re.findall(r'<form[^>]*action="(/topics/[^"]+/delete)"', html)


def test_post_delete_removes_the_topic_and_goes_home(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    client = _client(tmp_path, store)
    ref = _topic(store, ALICE, "Непотрібна розмова")
    r = client.post(_url(ref) + "/delete", headers=H_ALICE, follow_redirects=False)
    assert (r.status_code, r.headers["location"]) == (303, "/")
    assert _files(store, ref) == []
    assert "Непотрібна розмова" not in client.get("/", headers=H_ALICE).text
    assert client.get(_url(ref), headers=H_ALICE).status_code == 404


def test_post_delete_of_a_foreign_topic_is_404_and_deletes_nothing(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    client = _client(tmp_path, store)
    ref = _topic(store, ALICE, "Тема Аліси")
    r = client.post(_url(ref) + "/delete", headers=H_OWNER, follow_redirects=False)
    assert r.status_code == 404 and "Тему не знайдено." in r.text
    assert len(_files(store, ref)) == 5


def test_home_has_a_delete_form_with_one_confirmation_for_each_own_topic_only(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    client = _client(tmp_path, store)
    mine = _topic(store, OWNER, "Моя тема")
    _topic(store, ALICE, "Тема Аліси")
    page = client.get("/", headers=H_OWNER).text
    assert _delete_forms(page) == [_url(mine) + "/delete"]
    assert "Видалити" in page and "Так, видалити" in page
    form = page[page.index("<details") : page.index("</details>")]
    assert "<summary" in form and "Моя тема" in form and 'type="submit"' in form


def test_the_own_topic_page_has_the_delete_form_and_a_foreign_one_has_none(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    client = _client(tmp_path, store)
    ref = _topic(store, ALICE, "Тема Аліси")
    own = client.get(_url(ref), headers=H_ALICE).text
    foreign = client.get(_url(ref), headers=H_OWNER).text
    assert _delete_forms(own) == [_url(ref) + "/delete"] and "Так, видалити" in own
    assert _delete_forms(foreign) == [] and "Так, видалити" not in foreign
