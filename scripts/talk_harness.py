"""The browser stand of the conversation mode (task 308): Chromium whose microphone speaks a person's turns.

The page's own code is untouched: `getUserMedia` returns a stream from an AudioContext of the stand, and each
time the mode's button (`#talk[data-state]`) becomes `listening`, the stand plays the next recorded turn into
that stream after `DELAY_MS`. Nobody touches the page after the one click on `#talk`. Used by
`smoke_test_conversation_mode.py` (local mode) and `live_conversation_mode.py` (real models). Playwright is no
project dependency (`uv run --with …`).
"""

import base64
import importlib
import json
import os
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
CLIPS = ROOT / "tests" / "fixtures" / "voice" / "conversation"
CACHED = Path.home() / ".cache/ms-playwright/chromium-1208/chrome-linux64/chrome"
CHROMIUM = os.environ.get("THINKHOW_CHROMIUM", str(CACHED))
DELAY_MS = 600

FAKE_MIC = """
(() => {
  const clips = %s;
  const delay = %d;
  let ctx = null, dest = null, current = null, next = 0;
  window.__talk = { log: [], played: 0 };
  const log = (...e) => window.__talk.log.push([...e, performance.now()]);
  navigator.mediaDevices.getUserMedia = async () => {
    ctx = ctx || new AudioContext();
    await ctx.resume();
    dest = dest || ctx.createMediaStreamDestination();
    return dest.stream;
  };
  async function play() {
    const button = document.getElementById("talk");
    if (next >= clips.length || button.dataset.state !== "listening") return;
    if (current) { try { current.stop(); } catch (e) {} }
    const bytes = Uint8Array.from(atob(clips[next]), (c) => c.charCodeAt(0));
    const n = next++;
    const buffer = await ctx.decodeAudioData(bytes.buffer);
    const source = ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(dest);
    source.onended = () => log("clip-end", n);
    current = source;
    log("clip-start", n, buffer.duration);
    window.__talk.played = next;
    source.start();
  }
  function watch() {
    const button = document.getElementById("talk");
    if (!button) return setTimeout(watch, 50);
    new MutationObserver(() => {
      log("state", button.dataset.state);
      if (button.dataset.state === "listening") setTimeout(play, delay);
    }).observe(button, { attributes: true, attributeFilter: ["data-state"] });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", watch);
  else watch();
})();
"""


@dataclass
class Run:
    log: list[list[Any]]
    marks: list[dict[str, Any]]
    requests: list[tuple[str, str]] = field(default_factory=list)
    live: list[tuple[str, str]] = field(default_factory=list)
    error: str = ""


def clips(language: str, count: int) -> list[str]:
    return [
        base64.b64encode((CLIPS / f"{language}-{n}.mp3").read_bytes()).decode() for n in range(1, count + 1)
    ]


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def serve(env: dict[str, str], app: str = "thinkhow.web.app:app") -> tuple[subprocess.Popen[bytes], str]:
    port = free_port()
    command = [sys.executable, "-m", "uvicorn", app, "--port", str(port)]
    server = subprocess.Popen(command, cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT / "src"), **env})
    base = f"http://127.0.0.1:{port}"
    for _ in range(300):
        try:
            httpx.get(base + "/language")
            return server, base
        except httpx.ConnectError:
            time.sleep(0.1)
    server.terminate()
    raise AssertionError("uvicorn did not start")


def talk(
    base: str, language: str, title: str, turns: int, turn_timeout_s: float, shots: Path | None = None
) -> Run:
    """Flow: a language and a topic → the page → one click on #talk → wait for `turns` spoken answers."""
    sync_playwright = importlib.import_module("playwright.sync_api").sync_playwright
    httpx.post(base + "/language", data={"code": language})
    topic = httpx.post(base + "/topics", data={"title": title}).headers["location"]
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM)
        page = browser.new_context().new_page()
        page.add_init_script(FAKE_MIC % (json.dumps(clips(language, turns)), DELAY_MS))
        requests: list[tuple[str, str]] = []
        page.on("request", lambda r: requests.append((r.url.split("/")[-1], r.post_data or "")))
        page.goto(base + topic)
        assert page.locator("#talk").is_visible(), "the mode's button is hidden"
        page.click("#talk")
        run = wait(page, turns, turn_timeout_s)
        run.requests = requests
        if shots:
            page.screenshot(path=str(shots), full_page=True)
        browser.close()
    return run


def wait(page: Any, turns: int, turn_timeout_s: float) -> Run:
    """Until `turns` answers were spoken and the mode listens again (or it stopped on an error)."""
    deadline = time.monotonic() + turn_timeout_s
    seen = 0
    while time.monotonic() < deadline:
        state = page.eval_on_selector("#talk", "b => b.dataset.state")
        spoken = page.evaluate("performance.getEntriesByName('talk:voice-start').length")
        if spoken > seen:
            seen, deadline = spoken, time.monotonic() + turn_timeout_s
        if state == "" or (spoken >= turns and state == "listening"):
            break
        time.sleep(0.2)
    data = page.evaluate(
        """() => ({
          log: window.__talk.log,
          marks: performance.getEntriesByType('mark').map(m => ({name: m.name, t: m.startTime})),
          live: [...document.querySelectorAll('#live p')].map(p => [p.className, p.textContent]),
          error: document.getElementById('error').textContent,
        })"""
    )
    return Run(data["log"], data["marks"], live=[tuple(x) for x in data["live"]], error=data["error"])


def latencies(run: Run) -> list[dict[str, float]]:
    """Per turn: the end of the person's speech (last voiced frame) → the first voice of the answer; also
    the clip's own end → the first voice (the clip ends with a little silence, so this one is shorter)."""
    ends = [m["t"] for m in run.marks if m["name"] == "talk:speech-end"]
    starts = [m["t"] for m in run.marks if m["name"] == "talk:voice-start"]
    clip_ends = [e[-1] for e in run.log if e[0] == "clip-end"]
    out = []
    for i, (end, start) in enumerate(zip(ends, starts, strict=False)):
        row = {"turn": i + 1, "speech_end_to_voice_s": round((start - end) / 1000, 2)}
        if i < len(clip_ends):
            row["clip_end_to_voice_s"] = round((start - clip_ends[i]) / 1000, 2)
        out.append(row)
    return out
