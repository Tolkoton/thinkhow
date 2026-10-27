"""Smoke of slice conversation-loop: real uvicorn in local mode + Chromium whose microphone speaks turns.

Run: `uv run --with playwright==1.64.1 python scripts/smoke_test_conversation_mode.py`. One click on «Режим
розмови», then 3 cycles «turn → text → answer → voice → listening» with no touch. Asserts by itself.
"""

import json
import tempfile

from talk_harness import ROOT, Run, latencies, serve, talk

OUT = ROOT / ".engine" / "artifacts" / "conversation-loop"
TURNS = 3
LINES: list[str] = []


def say(*parts: object) -> None:
    """Print a step and keep it for `smoke.txt`."""
    line = " ".join(str(p) for p in parts)
    LINES.append(line)
    print(line)


def main() -> None:
    data = tempfile.mkdtemp(prefix="thinkhow-talk-")
    env = {"THINKHOW_LOCAL": "true", "THINKHOW_LOCAL_DIR": data, "THINKHOW_OWNER_EMAIL": "owner@localhost"}
    server, base = serve(env)
    try:
        OUT.mkdir(parents=True, exist_ok=True)
        run = talk(base, "uk-UA", "Режим розмови", TURNS, 60, shots=OUT / "after-3-turns.png")
    finally:
        server.terminate()
        server.wait(timeout=10)
    check(run)
    (OUT / "smoke-run.json").write_text(
        json.dumps(run.__dict__, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    say(f"OK: one click, {TURNS} cycles without a touch; files under {data}")
    (OUT / "smoke.txt").write_text("\n".join(LINES) + "\n", encoding="utf-8")


def check(run: Run) -> None:
    states = [e[1] for e in run.log if e[0] == "state"]
    say("states:", " → ".join(s or "off" for s in states))
    assert not run.error, run.error
    names = [name for name, _ in run.requests]
    voice, reply = names.count("voice"), [body for name, body in run.requests if name == "reply"]
    say(f"requests: /voice ×{voice}, /reply ×{len(reply)}, /speak ×{names.count('speak')}")
    assert voice == TURNS and len(reply) == TURNS and names.count("speak") >= TURNS, names
    assert all("spoken=1" in body for body in reply), reply
    kinds = [kind for kind, _ in run.live]
    say("#live:", kinds)
    assert kinds == ["turn user", "turn model"] * TURNS, kinds
    for _ in range(TURNS):
        for state in ("listening", "hearing", "thinking", "speaking"):
            assert state in states, (state, states)
    assert states.count("speaking") == TURNS and states[-1] == "listening", states
    ends = [m["t"] for m in run.marks if m["name"] == "talk:speech-end"]
    starts = [m["t"] for m in run.marks if m["name"] == "talk:voice-start"]
    assert len(ends) == len(starts) == TURNS and all(s > e for e, s in zip(ends, starts, strict=True)), (
        run.marks
    )
    for row in latencies(run):
        say("turn", row)


if __name__ == "__main__":
    main()
