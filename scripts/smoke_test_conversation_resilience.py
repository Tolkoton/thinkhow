"""Smoke of slice conversation-resilience: Chromium, local mode; one /speak fails, the mode goes on.

Run: `uv run --with playwright==1.64.1 python scripts/smoke_test_conversation_resilience.py`. The stand of
`talk_harness.py`, plus: the second `/speak` of the run answers 502 (Playwright `route`), and spies record
`navigator.wakeLock.request` and the frequency of every oscillator the page starts. After one click: 3 cycles,
one `/speak` fewer answered 200 than asked, a wake lock for "screen", at least 3 listening tones (~880 Hz).
Writes its output to `.engine/artifacts/conversation-resilience/smoke.txt` itself.
"""

import importlib
import json
import tempfile
import time
from typing import Any

from talk_harness import CHROMIUM, FAKE_MIC, ROOT, clips, serve

OUT = ROOT / ".engine" / "artifacts" / "conversation-resilience"
TURNS = 3
SPIES = """
(() => {
  window.__spy = { wake: [], tones: [] };
  if (!navigator.wakeLock) {
    Object.defineProperty(navigator, "wakeLock", { value: {}, configurable: true });
  }
  navigator.wakeLock.request = (type) => {
    window.__spy.wake.push(type);
    const lock = { released: false, release() { this.released = true; return Promise.resolve(); } };
    return Promise.resolve(lock);
  };
  const create = AudioContext.prototype.createOscillator;
  AudioContext.prototype.createOscillator = function () {
    const osc = create.call(this);
    const set = osc.frequency.setValueAtTime.bind(osc.frequency);
    let hz = osc.frequency.value;
    osc.frequency.setValueAtTime = (v, t) => { hz = v; return set(v, t); };
    const start = osc.start.bind(osc);
    osc.start = (...a) => { window.__spy.tones.push(hz); return start(...a); };
    return osc;
  };
})();
"""
LINES: list[str] = []


def say(*parts: object) -> None:
    line = " ".join(str(p) for p in parts)
    LINES.append(line)
    print(line)


def main() -> None:
    data = tempfile.mkdtemp(prefix="thinkhow-resilience-")
    env = {"THINKHOW_LOCAL": "true", "THINKHOW_LOCAL_DIR": data, "THINKHOW_OWNER_EMAIL": "owner@localhost"}
    server, base = serve(env)
    try:
        result = run(base)
    finally:
        server.terminate()
        server.wait(timeout=10)
    check(result)
    OUT.mkdir(parents=True, exist_ok=True)
    say(f"OK: one /speak failed and was skipped; {TURNS} cycles without a touch; files under {data}")
    (OUT / "smoke.txt").write_text("\n".join(LINES) + "\n", encoding="utf-8")


def run(base: str) -> dict[str, Any]:
    import httpx

    sync_playwright = importlib.import_module("playwright.sync_api").sync_playwright
    httpx.post(base + "/language", data={"code": "uk-UA"})
    topic = httpx.post(base + "/topics", data={"title": "Стійкість"}).headers["location"]
    speak: list[int] = []

    def route(r: Any) -> None:
        speak.append(len(speak) + 1)
        if len(speak) == 2:
            r.fulfill(status=502, content_type="text/html", body='<p class="error">Не вдалося озвучити.</p>')
        else:
            r.continue_()

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM)
        page = browser.new_context().new_page()
        page.add_init_script(SPIES)
        page.add_init_script(FAKE_MIC % (json.dumps(clips("uk-UA", TURNS)), 600))
        statuses: list[int] = []
        page.on("response", lambda r: statuses.append(r.status) if r.url.endswith("/speak") else None)
        page.route("**/speak", route)
        page.goto(base + topic)
        page.click("#talk")
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            state = page.eval_on_selector("#talk", "b => b.dataset.state")
            spoken = page.evaluate("performance.getEntriesByName('talk:voice-start').length")
            if state == "" or (spoken >= TURNS and state == "listening"):
                break
            time.sleep(0.2)
        data = page.evaluate(
            """() => ({spy: window.__spy, log: window.__talk.log,
                       error: document.getElementById('error').textContent,
                       state: document.getElementById('talk').dataset.state})"""
        )
        browser.close()
    return {**data, "statuses": statuses}


def check(result: dict[str, Any]) -> None:
    states = [e[1] for e in result["log"] if e[0] == "state"]
    say("states:", " → ".join(s or "off" for s in states))
    statuses = result["statuses"]
    say(f"/speak statuses: {statuses}")
    tones = [round(f) for f in result["spy"]["tones"]]
    say(f"wake lock requests: {result['spy']['wake']}; tones started (Hz): {tones}")
    assert states.count("speaking") == TURNS and result["state"] == "listening", (states, result["error"])
    assert statuses.count(502) == 1 and statuses.count(200) == len(statuses) - 1, statuses
    assert result["spy"]["wake"] == ["screen"], result["spy"]["wake"]
    assert sum(1 for f in tones if 800 <= f <= 960) >= TURNS, tones


if __name__ == "__main__":
    main()
