"""Bug 001 (task 210, 738): every /static URL on the pages carries ?v= — the hash of the files in static/.

Without a browser, so these run where Playwright is absent. The second test changes a file in a copy of the
package: a version written down once (a constant, the commit's time) keeps the old URL and fails it.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from thinkhow.web.app import CARDS_DIR, build_deps
from thinkhow.web.server import create_app

SRC = Path(__file__).resolve().parents[2] / "src"
STATIC_URLS = {"/static/style.css", "/static/rename.js", "/static/conversation.js"}
# Renders the start page and a topic page of the `thinkhow` it imports; writes its file and the pages to
# argv[3] (stdout carries the request log).
RENDER = r"""
import sys
from pathlib import Path
from fastapi.testclient import TestClient
import thinkhow
from thinkhow.web.app import build_deps
from thinkhow.web.server import create_app
env = {"THINKHOW_LOCAL": "true", "THINKHOW_LOCAL_DIR": sys.argv[1]}
client = TestClient(create_app(build_deps(env, Path(sys.argv[2]))))
client.post("/language", data={"code": "uk-UA"})
topic = client.post("/topics", data={"title": "Тест версії"})
Path(sys.argv[3]).write_text(thinkhow.__file__ + "\n" + client.get("/").text + topic.text, encoding="utf-8")
"""


def _version(static: Path) -> str:
    files = sorted(f for f in static.iterdir() if f.is_file())
    return hashlib.sha256(b"".join(f.read_bytes() for f in files)).hexdigest()[:12]


def _static_urls(html: str) -> list[str]:
    return re.findall(r'"(/static/[^"]*)"', html)


def _render_copy(src: Path, data: Path) -> tuple[str, str]:
    out = data.parent / "rendered.txt"
    subprocess.run(
        [sys.executable, "-c", RENDER, str(data), str(CARDS_DIR), str(out)],
        env={"PYTHONPATH": str(src), "PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        check=True,
    )
    module, _, html = out.read_text(encoding="utf-8").partition("\n")
    return module, html


def test_every_static_url_on_the_pages_carries_the_content_version(tmp_path: Path) -> None:
    env = {"THINKHOW_LOCAL": "true", "THINKHOW_LOCAL_DIR": str(tmp_path / "data")}
    version = _version(SRC / "thinkhow/web/static")
    client = TestClient(create_app(build_deps(env, CARDS_DIR)))
    client.post("/language", data={"code": "uk-UA"})
    topic = client.post("/topics", data={"title": "Тест версії"})
    urls = _static_urls(client.get("/").text + topic.text)
    assert {u.split("?")[0] for u in urls} == STATIC_URLS, urls
    assert all(u.endswith(f"?v={version}") for u in urls), urls


def test_a_changed_static_file_changes_the_version_of_every_url(tmp_path: Path) -> None:
    copy = tmp_path / "src"
    shutil.copytree(SRC / "thinkhow", copy / "thinkhow", ignore=shutil.ignore_patterns("__pycache__"))
    static = copy / "thinkhow/web/static"
    before = _version(static)
    with (static / "rename.js").open("a", encoding="utf-8") as f:
        f.write("\n/* a deploy changed rename.js */\n")
    after = _version(static)
    module, html = _render_copy(copy, tmp_path / "data")
    assert Path(module).is_relative_to(copy), module
    urls = _static_urls(html)
    assert {u.split("?")[0] for u in urls} == STATIC_URLS, urls
    assert after != before
    assert all(u.endswith(f"?v={after}") for u in urls), (before, urls)
