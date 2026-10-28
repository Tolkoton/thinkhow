"""Smoke of slice voice-synthesis: real uvicorn in local mode — the page knows the voice, `/speak` gives MP3.

Run: `uv run python scripts/smoke_test_voice_synthesis.py`. Asserts by itself; prints each step.
"""

import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
NO_VOICE = "There is no voice for your language."
SILENCE = (ROOT / "src" / "thinkhow" / "platform" / "silence.mp3").read_bytes()


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def main() -> None:
    port, data = free_port(), tempfile.mkdtemp(prefix="thinkhow-tts-")
    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT / "src"),
        "THINKHOW_LOCAL": "true",
        "THINKHOW_LOCAL_DIR": data,
        "THINKHOW_OWNER_EMAIL": "owner@localhost",
    }
    command = [sys.executable, "-m", "uvicorn", "thinkhow.web.app:app", "--port", str(port)]
    server = subprocess.Popen(command, cwd=ROOT, env=env)
    base = f"http://127.0.0.1:{port}"
    try:
        wait_for(base + "/language")
        with httpx.Client(base_url=base) as client:
            check_language(client, "uk-UA", "yes")
            check_language(client, "kk-KZ", "no")
        print(f"OK: data-voice follows the language; /speak gives MP3 or 409; files under {data}")
    finally:
        server.terminate()
        server.wait(timeout=10)


def check_language(client: httpx.Client, code: str, voice: str) -> None:
    assert client.post("/language", data={"code": code}).status_code == 303
    topic = client.post("/topics", data={"title": f"Голос {code}"}, follow_redirects=True)
    assert topic.status_code == 200 and f'data-voice="{voice}"' in topic.text, topic.status_code
    print(f'{code}: topic page → 200, data-voice="{voice}"')
    spoken = client.post("/speak", data={"text": "Добрий день. Що для вас зараз найважливіше?"})
    if voice == "yes":
        assert spoken.status_code == 200, spoken.status_code
        assert spoken.headers["content-type"] == "audio/mpeg" and spoken.content == SILENCE, spoken.headers
        print(f"{code}: POST /speak → 200 audio/mpeg, {len(spoken.content)} bytes (the double's silence)")
    else:
        assert spoken.status_code == 409 and NO_VOICE in spoken.text, spoken.status_code
        print(f"{code}: POST /speak → 409 «{NO_VOICE}» (in English for every language, task 208)")


def wait_for(url: str) -> httpx.Response:
    for _ in range(100):
        try:
            return httpx.get(url)
        except httpx.ConnectError:
            time.sleep(0.1)
    raise AssertionError("uvicorn did not start")


if __name__ == "__main__":
    main()
