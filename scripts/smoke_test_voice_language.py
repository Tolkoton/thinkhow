"""Smoke of slice voice-language: real uvicorn in local mode, first visit → the language page → a choice.

Run: `uv run python scripts/smoke_test_voice_language.py`. Asserts by itself; prints each step.
"""

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
PL = json.loads((ROOT / "src" / "thinkhow" / "web" / "locales" / "pl.json").read_text(encoding="utf-8"))


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def main() -> None:
    port, data = free_port(), tempfile.mkdtemp(prefix="thinkhow-language-")
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
    profile = Path(data) / "users" / "local-owner" / "profile.json"
    try:
        first = wait_for(base + "/")
        assert first.status_code == 303 and first.headers["location"] == "/language", first
        print("first visit: GET / → 303 /language")
        page = httpx.get(base + "/language")
        assert page.status_code == 200 and '<select name="code"' in page.text, page.status_code
        print('GET /language → 200 with <select name="code">')
        chosen = httpx.post(base + "/language", data={"code": "pl-PL"})
        assert chosen.status_code == 303 and chosen.headers["location"] == "/", chosen
        print("POST /language pl-PL → 303 /")
        home = httpx.get(base + "/")
        chosen = f"{PL['language']}: Polski"  # the page speaks the chosen language (task 208)
        assert home.status_code == 200 and chosen in home.text, home.status_code
        print(f"GET / → 200, «{chosen}»")
        stored = json.loads(profile.read_text(encoding="utf-8"))
        assert stored == {"email": "owner@localhost", "language": "pl-PL"}, stored
        print("profile.json:", stored)
        before = profile.read_bytes()
        refused = httpx.post(base + "/language", data={"code": "ru-RU"})
        assert refused.status_code == 400 and PL["err_unknown_language"] in refused.text, refused.status_code
        assert profile.read_bytes() == before
        print("POST /language ru-RU → 400, profile.json unchanged")
        profile.write_text(json.dumps({"email": "owner@localhost"}), encoding="utf-8")
        again = httpx.get(base + "/")
        assert again.status_code == 303 and again.headers["location"] == "/language", again
        print("a profile with the email only (as after task 105): GET / → 303 /language")
        print(f"OK: the language is chosen, stored and refused for Russian; the files stay under {data}")
    finally:
        server.terminate()
        server.wait(timeout=10)


def wait_for(url: str) -> httpx.Response:
    for _ in range(100):
        try:
            return httpx.get(url)
        except httpx.ConnectError:
            time.sleep(0.1)
    raise AssertionError("uvicorn did not start")


if __name__ == "__main__":
    main()
