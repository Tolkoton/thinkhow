"""Live acceptance of the conversation mode (task 308, AC5): the browser stand on the real models.

Run: `uv run --with playwright==1.64.1 python scripts/live_conversation_mode.py [uk-UA pl-PL]`. For each
language: one click on «Режим розмови», then the person's recorded turns
(`tests/fixtures/voice/conversation/<lang>-<n>.mp3`, 6 each) with no touch; the server is
`scripts/live_app.py` (Gemini `eu` with search, `gemini-3.5-transcribe`, Cloud TTS `eu`). Writes
`.engine/artifacts/conversation-mode/live-<UTC>.md`: per turn — what was recognised, what was said back (the
texts sent to /speak), the latency from the end of the person's speech to the first voice.
"""

import json
import subprocess
import sys
import tempfile
import urllib.parse
from datetime import UTC, datetime

from talk_harness import CLIPS, ROOT, Run, latencies, serve, talk

OUT = ROOT / ".engine" / "artifacts" / "conversation-mode"
TURNS = 6
TURN_TIMEOUT_S = 420  # deep research takes ~2 min; the wait restarts after every spoken answer


def main(languages: list[str]) -> None:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    OUT.mkdir(parents=True, exist_ok=True)
    lines = [f"# Live conversation mode (task 308) — {stamp}", ""]
    for language in languages:
        data = tempfile.mkdtemp(prefix=f"thinkhow-live-{language}-")
        env = {
            "THINKHOW_LOCAL": "true",
            "THINKHOW_LOCAL_DIR": data,
            "THINKHOW_OWNER_EMAIL": "owner@localhost",
        }
        server, base = serve(env, app="scripts.live_app:app")
        try:
            shot = OUT / f"live-{stamp}-{language}.png"
            run = talk(base, language, "Режим розмови (live)", TURNS, TURN_TIMEOUT_S, shot)
            (OUT / f"live-{stamp}-{language}.json").write_text(
                json.dumps(run.__dict__, ensure_ascii=False, indent=1)
            )
        finally:
            stop(server)
        lines += section(language, run)
    path = OUT / f"live-{stamp}.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(path)


def stop(server: subprocess.Popen[bytes]) -> None:
    """A stream the browser left open can keep uvicorn from stopping: then it is killed."""
    server.terminate()
    try:
        server.wait(timeout=10)
    except subprocess.TimeoutExpired:
        server.kill()
        server.wait(timeout=10)


def section(language: str, run: Run) -> list[str]:
    said = json.loads((CLIPS / "lines.json").read_text(encoding="utf-8"))[language]
    users = [text for kind, text in run.live if kind == "turn user"]
    answers = [text for kind, text in run.live if kind == "turn model"]
    spoken = [
        urllib.parse.parse_qs(body).get("text", [""])[0] for name, body in run.requests if name == "speak"
    ]
    rows = latencies(run)
    out = [f"## {language}", "", f"Помилка на сторінці: {run.error or '—'}", ""]
    out += ["| # | затримка, с (кінець мови → голос) | від кінця запису, с |", "|---|---|---|"]
    out += [
        f"| {r['turn']} | {r['speech_end_to_voice_s']} | {r.get('clip_end_to_voice_s', '—')} |" for r in rows
    ]
    out.append("")
    for i, text in enumerate(said):
        out += [f"### Репліка {i + 1}", "", f"Людина сказала: {text}", ""]
        out += [f"Розпізнано: {users[i] if i < len(users) else '—'}", ""]
        out += [f"Відповідь (текст): {answers[i] if i < len(answers) else '—'}", ""]
    out += ["### Усе, що сказано голосом (запити /speak по черзі)", ""]
    out += [f"{n + 1}. {text}" for n, text in enumerate(spoken)]
    return [*out, ""]


if __name__ == "__main__":
    main(sys.argv[1:] or ["uk-UA", "pl-PL"])
