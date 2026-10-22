"""Contract tests of skel-web: the request id and the `http_request` and `stream_error` log lines."""

import re
import time
from pathlib import Path
from typing import Any

import pytest
from skelweb_fakes import (
    ALICE,
    H_ALICE,
    ArmedStorage,
    ListBroken,
    LogCapture,
    install_log_capture,
    make_app,
    seed_topic,
    update,
)


@pytest.fixture
def logs(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> LogCapture:
    return install_log_capture(monkeypatch, capsys)


def values(obj: Any) -> list[Any]:
    """Every scalar value of a log line, nested objects included (e.g. a Cloud Logging httpRequest)."""
    if isinstance(obj, dict):
        return [v for x in obj.values() for v in values(x)]
    if isinstance(obj, list):
        return [v for x in obj for v in values(x)]
    return [obj]


def find_key(obj: Any, key: str) -> list[Any]:
    if isinstance(obj, dict):
        found = [obj[key]] if key in obj else []
        return found + [v for x in obj.values() for v in find_key(x, key)]
    return []


def http_lines(logs: LogCapture, path_template: str) -> list[dict[str, Any]]:
    return [line for line in logs.events("http_request") if path_template in values(line)]


def test_request_id_from_cloud_trace_header_or_a_new_uuid4_hex(tmp_path: Path, logs: LogCapture) -> None:
    app = make_app(tmp_path)
    headers = {**H_ALICE, "x-cloud-trace-context": "abc123def456/7890;o=1"}
    assert app.client.get("/", headers=headers).status_code == 200
    assert app.client.get("/", headers=H_ALICE).status_code == 200
    lines = http_lines(logs, "/")
    assert len(lines) == 2
    assert lines[0]["request_id"] == "abc123def456"
    assert re.fullmatch(r"[0-9a-f]{32}", lines[1]["request_id"]), lines[1]


def test_http_request_line_has_method_route_template_status_latency_and_no_text_or_email(
    tmp_path: Path, logs: LogCapture
) -> None:
    app = make_app(tmp_path, [["маркер-відповіді", update("маркер-відповіді")]])
    ref = seed_topic(app.storage, ALICE, "Тема")
    r = app.client.post(
        f"/topics/{ref.uid}/{ref.topic_id}/reply", data={"text": "секретна-репліка"}, headers=H_ALICE
    )
    assert r.status_code == 200
    lines = http_lines(logs, "/topics/{uid}/{topic_id}/reply")
    assert len(lines) == 1
    vals = values(lines[0])
    assert "POST" in vals
    assert 200 in vals or "200" in vals
    latency = find_key(lines[0], "latency_ms")
    assert len(latency) == 1 and isinstance(latency[0], int | float) and latency[0] >= 0
    for line in logs.lines():
        dumped = repr(line)
        assert "секретна-репліка" not in dumped
        assert "маркер-відповіді" not in dumped
        assert "alice@example.com" not in dumped


def test_sse_latency_runs_to_the_end_of_the_stream(tmp_path: Path, logs: LogCapture) -> None:
    app = make_app(tmp_path, [["Так", lambda: time.sleep(0.4), ", так", update("Так, так")]])
    ref = seed_topic(app.storage, ALICE, "Тема")
    r = app.client.post(f"/topics/{ref.uid}/{ref.topic_id}/reply", data={"text": "Питання"}, headers=H_ALICE)
    assert r.status_code == 200
    lines = http_lines(logs, "/topics/{uid}/{topic_id}/reply")
    assert len(lines) == 1
    assert find_key(lines[0], "latency_ms")[0] >= 400


def test_unexpected_exception_is_logged_as_http_request_status_500(tmp_path: Path, logs: LogCapture) -> None:
    app = make_app(tmp_path, storage=ListBroken(tmp_path / "data"))
    assert app.client.get("/", headers=H_ALICE).status_code == 500
    lines = http_lines(logs, "/")
    assert len(lines) == 1
    vals = values(lines[0])
    assert 500 in vals or "500" in vals


def test_stream_error_line_names_the_class_and_carries_the_request_id(
    tmp_path: Path, logs: LogCapture
) -> None:
    store = ArmedStorage(tmp_path / "data")

    def arm() -> None:
        store.armed = True

    app = make_app(tmp_path, [["Відповідь", arm, update("Відповідь")]], storage=store)
    ref = seed_topic(store, ALICE, "Тема")
    headers = {**H_ALICE, "x-cloud-trace-context": "trace77/1;o=1"}
    r = app.client.post(f"/topics/{ref.uid}/{ref.topic_id}/reply", data={"text": "Питання"}, headers=headers)
    assert r.status_code == 200
    errors = logs.events("stream_error")
    assert len(errors) == 1
    assert errors[0]["request_id"] == "trace77"
    assert "StorageBroke" in values(errors[0])
    assert [line["request_id"] for line in http_lines(logs, "/topics/{uid}/{topic_id}/reply")] == ["trace77"]
