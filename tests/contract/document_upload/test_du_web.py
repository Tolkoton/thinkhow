"""Contract tests of document-upload: `POST .../document`, the topic page, the words, the logs.

Slice tester; from the contract `.engine/slices/document-upload.md`, not the code. The page's script (32 MiB,
Cloud Run's 413) is the smoke's, by the contract's Seam 4 (Playwright, real input[type=file]).
"""

import html
from pathlib import Path
from typing import Any

import pytest
from du_fakes import (
    ALICE,
    H_ALICE,
    H_BOB,
    MAX,
    RESUME_PDF_TEXT,
    T0,
    Facil,
    M,
    Tags,
    document_url,
    file_bytes,
    make_client,
    new_topic,
    page_url,
    say,
    sse_events,
    topic_files,
    turns,
    txt,
    uk,
    upload,
)
from fastapi.testclient import TestClient

from thinkhow.platform.storage import LocalStorage
from thinkhow.workspace import TopicRef


def _post(
    client: TestClient, ref: TopicRef, name: str, data: bytes, headers: dict[str, str] = H_ALICE
) -> Any:
    return client.post(
        document_url(ref),
        files={"file": (name, data, "application/octet-stream")},
        headers=headers,
    )


def _shows(body: str, key: str) -> bool:
    return uk(key) in html.unescape(body)


def test_post_document_streams_saved_delta_answered_and_stores_the_turn(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path / "data")
    ref = new_topic(storage)
    client = make_client(tmp_path, storage, Facil(["Бачу fintech."]), T0)
    r = client.post(
        document_url(ref),
        files={"file": ("resume.pdf", file_bytes("resume.pdf"), "application/pdf")},
        headers=H_ALICE,
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/event-stream")
    names = [name for name, _ in sse_events(r.text)]
    assert names[0] == "saved" and "delta" in names and names[-1] == "answered", names
    assert [t.text for t in turns(storage, ref, T0 + M)] == ["📎 resume.pdf", "Бачу fintech."]


def test_an_unreadable_file_is_422_err_document_unreadable_and_nothing_is_stored(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path / "data")
    ref = new_topic(storage)
    client = make_client(tmp_path, storage, Facil(), T0)
    before = topic_files(tmp_path / "data", ref)
    r = _post(client, ref, "scan.pdf", file_bytes("scan.pdf"))
    assert r.status_code == 422
    assert _shows(r.text, "err_document_unreadable"), r.text
    assert topic_files(tmp_path / "data", ref) == before


def test_documents_over_the_limit_are_413_err_document_too_large(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path / "data")
    ref = new_topic(storage)
    upload(storage, Facil(), ref, "full.txt", txt("а" * MAX), T0 - M)
    client = make_client(tmp_path, storage, Facil(), T0)
    before = topic_files(tmp_path / "data", ref)
    r = _post(client, ref, "one.txt", txt("б"))
    assert r.status_code == 413
    assert _shows(r.text, "err_document_too_large"), r.text
    assert topic_files(tmp_path / "data", ref) == before


def test_a_foreign_topic_is_404(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path / "data")
    ref = new_topic(storage)
    client = make_client(tmp_path, storage, Facil(), T0)
    r = _post(client, ref, "cv.txt", txt("Резюме"), headers=H_BOB)
    assert r.status_code == 404
    assert turns(storage, ref, T0) == []
    # the same request by the topic's own person is taken: the 404 above is the refusal, not a missing route
    assert _post(client, ref, "cv.txt", txt("Резюме")).status_code == 200


def test_a_pending_answer_is_409(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path / "data")
    ref = new_topic(storage)
    say(storage, Facil([None]), ref, "Без відповіді.", T0 - M)
    client = make_client(tmp_path, storage, Facil(), T0)
    r = _post(client, ref, "cv.txt", txt("Резюме"))
    assert r.status_code == 409
    assert [t.text for t in turns(storage, ref, T0)] == ["Без відповіді."]


def test_no_file_field_is_400_err_not_accepted(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path / "data")
    ref = new_topic(storage)
    client = make_client(tmp_path, storage, Facil(), T0)
    r = client.post(document_url(ref), data={"text": "без файла"}, headers=H_ALICE)
    assert r.status_code == 400
    assert _shows(r.text, "err_not_accepted"), r.text
    assert turns(storage, ref, T0) == []


def test_the_page_has_the_attach_icon_button_between_mic_and_send_and_the_file_input(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path / "data")
    ref = new_topic(storage)
    client = make_client(tmp_path, storage, Facil(), T0)
    r = client.get(page_url(ref), headers=H_ALICE)
    assert r.status_code == 200
    page = Tags(r.text)
    tag, attrs = page.by_id("attach")
    assert tag == "button"
    assert "icon" in (attrs.get("class") or "").split()
    assert attrs.get("aria-label") == uk("upload_document")
    assert page.texts.get("attach", "").strip() == ""  # an icon, no words
    assert page.index_of("mic") < page.index_of("attach") < page.index_of("send")
    tag, attrs = page.by_id("document")
    assert tag == "input" and attrs.get("type") == "file"
    assert attrs.get("accept") == ".pdf,.docx,.txt,.md,.markdown"


def _logs(out: str) -> list[dict[str, object]]:
    import json

    found = []
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if isinstance(obj, dict):
                found.append(obj)
    return found


def test_document_added_is_logged_with_its_fields_and_never_the_name_or_the_text(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    storage = LocalStorage(tmp_path / "data")
    ref = new_topic(storage)
    client = make_client(tmp_path, storage, Facil(), T0)
    data = file_bytes("resume.pdf")
    capsys.readouterr()
    r = _post(client, ref, "zqx-secret-name.pdf", data)
    assert r.status_code == 200
    out = capsys.readouterr()
    lines = _logs(out.out + "\n" + out.err)
    added = [line for line in lines if line.get("event") == "document_added"]
    assert len(added) == 1, lines
    (one,) = added
    assert (one.get("uid"), one.get("topic_id"), one.get("turn")) == (ALICE.id, ref.topic_id, 1)
    assert "format" in one
    assert (one.get("bytes"), one.get("chars")) == (len(data), len(RESUME_PDF_TEXT))
    raw = out.out + out.err
    assert "zqx-secret-name" not in raw
    assert "Monobank" not in raw


def test_document_unreadable_is_a_warning_with_format_reason_bytes_and_never_the_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    storage = LocalStorage(tmp_path / "data")
    ref = new_topic(storage)
    client = make_client(tmp_path, storage, Facil(), T0)
    data = file_bytes("scan.pdf")
    capsys.readouterr()
    r = _post(client, ref, "zqx-secret-scan.pdf", data)
    assert r.status_code == 422
    out = capsys.readouterr()
    lines = _logs(out.out + "\n" + out.err)
    found = [line for line in lines if line.get("event") == "document_unreadable"]
    assert len(found) == 1, lines
    (one,) = found
    assert one.get("severity") == "WARNING"
    assert "format" in one
    assert (one.get("reason"), one.get("bytes")) == ("empty", len(data))
    assert "zqx-secret-scan" not in out.out + out.err
