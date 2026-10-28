"""Smoke of slice finish-answer (task 712): the window is closed mid-answer, the server still writes it.

Run: `uv run python scripts/smoke_test_finish_answer.py`. Real uvicorn in local mode on a free port with a
slow scripted facilitator (pauses between deltas, ≥ 2 s in all); httpx sends a turn, reads `saved` and closes
the connection. Right after the close the answer must not be in conversation.md yet (else the smoke proves
nothing), then within 10 s it must be. Exits 1 on a failed check. `serve <port>` is the server half, run by
the script itself.
"""

import functools
import os
import socket
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
ANSWER = "Що саме в плані вас найбільше непокоїть?"


def slow_facilitate(ctx: Any, types: Any) -> Iterator[Any]:
    for word in ANSWER.split(" "):
        time.sleep(0.5)
        yield types.ReplyDelta(word + " ")
    yield types.FacilitatorUpdate(reply=ANSWER, current_phase_id=None, phase_exit_met=False, map_updates=[])


def serve(port: int) -> None:
    import uvicorn

    sys.path.insert(0, str(ROOT / "src"))
    from thinkhow.facilitation import types
    from thinkhow.platform.config import load_settings
    from thinkhow.platform.identity import make_identity
    from thinkhow.platform.speech import make_speech
    from thinkhow.platform.storage import make_storage
    from thinkhow.web.server import Deps, create_app

    settings = load_settings(os.environ)
    facilitate = functools.partial(slow_facilitate, types=types)
    deps = Deps(
        make_storage(settings),
        make_identity(settings),
        settings,
        facilitate,
        lambda: datetime.now(UTC),
        make_speech(settings),
    )
    uvicorn.run(create_app(deps), port=port, log_level="warning")


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def answered(data: Path) -> bool:
    return any(ANSWER in path.read_text("utf-8") for path in data.rglob("conversation.md"))


def main() -> int:
    port, data = free_port(), Path(tempfile.mkdtemp(prefix="thinkhow-smoke-"))
    env = {
        **os.environ,
        "THINKHOW_LOCAL": "true",
        "THINKHOW_LOCAL_DIR": str(data),
        "THINKHOW_OWNER_EMAIL": "owner@localhost",
    }
    server = subprocess.Popen([sys.executable, __file__, "serve", str(port)], cwd=ROOT, env=env)
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            try:
                httpx.get(base + "/language")
                break
            except httpx.ConnectError:
                time.sleep(0.1)
        else:
            print("FAIL: uvicorn did not start")
            return 1
        httpx.post(base + "/language", data={"code": "uk-UA"})
        topic = httpx.post(base + "/topics", data={"title": "Smoke"}).headers["location"]
        with httpx.stream("POST", base + topic + "/reply", data={"text": "Хочу перевірити план."}) as r:
            first = next(line for line in r.iter_lines() if line.startswith("event:"))
        print("first event, then the connection is closed:", first)
        if first != "event: saved":
            print("FAIL: the first event is not saved")
            return 1
        if answered(data):
            print("FAIL: the answer is in conversation.md right after the close — the smoke proves nothing")
            return 1
        print("right after the close: no answer in conversation.md yet")
        for waited in range(100):
            if answered(data):
                print(f"the answer is in conversation.md {waited / 10:.1f} s after the close")
                print(f"OK: the server finished the answer with no one reading; the files stay under {data}")
                return 0
            time.sleep(0.1)
        print("FAIL: no answer in conversation.md 10 s after the close")
        return 1
    finally:
        server.terminate()
        server.wait(timeout=20)


if __name__ == "__main__":
    if sys.argv[1:2] == ["serve"]:
        serve(int(sys.argv[2]))
    else:
        sys.exit(main())
