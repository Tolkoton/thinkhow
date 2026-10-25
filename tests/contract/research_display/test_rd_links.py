"""Contract tests of research-display, `platform/links.py`: `resolve_link` with a fake `head` (Seam 2) and
`httpx_head` against a local HTTP server (slice tester; from the contract)."""

import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest
from rd_fakes import GOOGLE, HeadRecorder

from thinkhow.platform.links import httpx_head, resolve_link

LINK = GOOGLE + "AUZIYQHx7a1"
PAGE = "https://www.meinauto.de/skoda/octavia"


def test_seam2_resolve_link_302_gives_location_and_every_failure_keeps_the_google_link() -> None:
    cases: dict[str, tuple[object, str]] = {
        "302 with an absolute Location": ((302, PAGE), PAGE),
        "200": ((200, None), LINK),
        "302 without Location": ((302, None), LINK),
        "302 with a relative Location": ((302, "/skoda/octavia"), LINK),
        "httpx.TimeoutException": (httpx.TimeoutException("timed out"), LINK),
        "OSError": (OSError("network down"), LINK),
    }
    for name, (answer, want) in cases.items():
        head = HeadRecorder(answer)  # type: ignore[arg-type]
        assert resolve_link(LINK, head) == want, name
        assert head.calls == [(LINK, 3.0)], name


def test_seam2_resolve_link_passes_its_timeout_to_head() -> None:
    head = HeadRecorder((302, PAGE))
    assert resolve_link(LINK, head, timeout_s=1.5) == PAGE
    assert head.calls == [(LINK, 1.5)]


def test_seam2_resolve_link_does_not_call_head_for_another_address() -> None:
    head = HeadRecorder((302, PAGE))
    for url in ("https://a.example/rent", "https://vertexaisearch.cloud.google.com/other/x", ""):
        assert resolve_link(url, head) == url
    assert head.calls == []


# ------------------------------------------------------------------ httpx_head against a local server

SEEN: list[str] = []


class Handler(BaseHTTPRequestHandler):
    def _answer(self) -> None:
        SEEN.append(f"{self.command} {self.path}")
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", PAGE)
        else:
            self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    do_HEAD = _answer
    do_GET = _answer

    def log_message(self, format: str, *args: object) -> None:
        pass


@pytest.fixture
def server(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    SEEN.clear()
    try:
        yield f"http://127.0.0.1:{srv.server_address[1]}"
    finally:
        srv.shutdown()
        srv.server_close()


def test_httpx_head_is_one_head_without_following_giving_status_and_location(server: str) -> None:
    assert httpx_head(server + "/redirect", 3.0) == (302, PAGE)
    assert SEEN == ["HEAD /redirect"]
    assert httpx_head(server + "/plain", 3.0) == (200, None)
    assert SEEN == ["HEAD /redirect", "HEAD /plain"]
