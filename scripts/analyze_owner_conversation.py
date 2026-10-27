"""Live: the old and the new analyzer on the owner's conversation t-84d1517cb1c1 «До» (task 309, AC3; slice
analysis-rules, exit criterion 2; PR-27).

Run: `uv run python scripts/analyze_owner_conversation.py [--attempt N]`. Puts the 18 turns of «До»
(`.engine/artifacts/advice-live/2026-10-25T174143Z-t-84d1517cb1c1/conversation.md`) into a temporary local
folder with the routing rebuilt from the text (offer on #1: jobs-to-be-done, opportunity-tree, goal-to-plan;
choose opportunity-tree on #3 — the contract's «Premise verified»), seeds the 25 cards and runs both analyzers
on `gemini-4-argon`/`eu`: the new one and the one of commit c14fd9b. Writes
.engine/artifacts/analysis-rules/owner-t-84d1517cb1c1.md; exits 1 when there is no `stuck` on t5, t11 or t15,
or a `stuck` on t9 or t13.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import types
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from thinkhow.facilitation import Candidate, Decision  # noqa: E402
from thinkhow.facilitation.types import Rev  # noqa: E402
from thinkhow.knowledge import seed  # noqa: E402
from thinkhow.learning import analyze as new_analyzer  # noqa: E402
from thinkhow.platform.config import load_settings  # noqa: E402
from thinkhow.platform.llm import make_llm  # noqa: E402
from thinkhow.platform.storage import LocalStorage  # noqa: E402
from thinkhow.workspace import conversation as conv_file  # noqa: E402
from thinkhow.workspace.topics import RoutingFile  # noqa: E402

SOURCE = ROOT / ".engine/artifacts/advice-live/2026-10-25T174143Z-t-84d1517cb1c1/conversation.md"
OUT = ROOT / ".engine/artifacts/analysis-rules/owner-t-84d1517cb1c1.md"
OLD_COMMIT = "c14fd9b"
UID, TOPIC = "owner", "t-84d1517cb1c1"
HEAD = re.compile(r"^### #(\d+) (Людина|ThinkHow)")
STUCK_AT, NOT_STUCK_AT = (5, 11, 15), (9, 13)


Role = Literal["user", "model"]


def before_turns() -> list[tuple[int, Role, str]]:
    """The turns of the section «До», as (no, role, text)."""
    text = SOURCE.read_text(encoding="utf-8")
    part = text.split("## До", 1)[1].split("\n## ", 1)[0]
    turns: list[tuple[int, Role, list[str]]] = []
    for line in part.splitlines():
        if m := HEAD.match(line):
            turns.append((int(m.group(1)), "user" if m.group(2) == "Людина" else "model", []))
        elif turns:
            turns[-1][2].append(line)
    return [(no, role, "\n".join(body).strip()) for no, role, body in turns]


def topic_folder(storage: LocalStorage, turns: list[tuple[int, Role, str]], start: datetime) -> None:
    session = conv_file.SessionDoc(no=1)
    for no, role, text in turns:
        session.turns.append(conv_file.Turn(no, role, start + timedelta(minutes=no), text))
    conv = conv_file.Conversation(title="Персональний асистент для керівників", sessions=[session])
    base = f"{UID}/{TOPIC}"
    storage.write("users", f"{base}/conversation.md", conv_file.render(conv).encode(), "text/markdown")
    rev = Rev(rev=1, n=0)
    offered = [
        Candidate(card_id=c, why="з тексту #2")
        for c in ("jobs-to-be-done", "opportunity-tree", "goal-to-plan")
    ]
    routing = [
        Decision(
            turn=1, rev=rev, kind="offer", profile=None, candidates=offered, card_id=None, end=None, why="#2"
        ),
        Decision(
            turn=3,
            rev=rev,
            kind="choose",
            profile=None,
            candidates=[],
            card_id="opportunity-tree",
            end=None,
            why="#3",
        ),
    ]
    storage.write(
        "users",
        f"{base}/routing.json",
        RoutingFile(decisions=routing).model_dump_json().encode(),
        "application/json",
    )


def old_analyzer() -> types.ModuleType:
    code = subprocess.run(
        ["git", "show", f"{OLD_COMMIT}:src/thinkhow/learning/analyze.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    module = types.ModuleType("old_analyze")
    exec(compile(code, f"{OLD_COMMIT}:analyze.py", "exec"), module.__dict__)  # noqa: S102 — the repository's own past code
    return module


def run(analyzer: Any, llm: Any, turns: list[tuple[int, Role, str]], now: datetime) -> list[dict[str, Any]]:
    root = Path(tempfile.mkdtemp(prefix="thinkhow-owner-"))
    storage = LocalStorage(root)
    seed(storage, ROOT / "cards")
    topic_folder(storage, turns, now - timedelta(days=3))
    report = analyzer.analyze(storage, llm, now)
    files = sorted((root / "system/learning/observations" / UID / TOPIC).glob("*.json"))
    if report.written != 1 or not files:
        raise SystemExit(f"the analyzer wrote nothing: {report}")
    data = json.loads(files[0].read_text(encoding="utf-8"))
    return list(data["observations"]) if "observations" in data else [data]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=int, default=1)
    attempt = parser.parse_args().attempt
    environ = {
        **os.environ,
        "THINKHOW_LOCAL": "false",
        "THINKHOW_USERS_BUCKET": "-",
        "THINKHOW_SYSTEM_BUCKET": "-",
    }
    settings = load_settings(environ | {"THINKHOW_OWNER_EMAIL": "-"})
    llm = make_llm(settings, script=lambda *_: "")
    turns = before_turns()
    now = datetime.now(UTC)
    new = run(new_analyzer, llm, turns, now)
    old = run(old_analyzer(), llm, turns, now)
    stuck = {o["turn"] for o in new if o["kind"] == "stuck"}
    ok = all(t in stuck for t in STUCK_AT) and not any(t in stuck for t in NOT_STUCK_AT)
    lines = [
        "# Аналізатор на розмові власника t-84d1517cb1c1 «До» (задача 309, AC3)",
        "",
        f"Дата: {now.isoformat(timespec='seconds')}; модель: {settings.model}; регіон: {settings.location}; "
        f"спроба інструкції: {attempt}; старий аналізатор — `{OLD_COMMIT}:src/thinkhow/learning/analyze.py`.",
        f"Вхід: {len(turns)} реплік розділу «До»; routing: offer на #1 (jobs-to-be-done, opportunity-tree, "
        "goal-to-plan), choose opportunity-tree на #3.",
        "",
        f"Перевірка: `stuck` на {', '.join(f't{t}' for t in STUCK_AT)} і немає `stuck` на "
        f"{', '.join(f't{t}' for t in NOT_STUCK_AT)} — **{'так' if ok else 'ні'}** (stuck: {sorted(stuck)}).",
        "",
        "## Новий аналізатор",
        "",
        "| id | kind | якір | card_id | cause | worked | finding |",
        "|---|---|---|---|---|---|---|",
        *(
            f"| {o['id'].rsplit('/', 1)[-1]} | {o['kind']} | t{o['turn']} | {o['card_id']} | {o['cause']} | "
            f"{o['worked']} | {o['finding']} |"
            for o in new
        ),
        "",
        "## Старий аналізатор (одне спостереження)",
        "",
        *(f"- t{o['turn']}, cause {o['cause']}, worked {o['worked']}: {o['finding']}" for o in old),
        "",
        "## Сирий JSON",
        "",
        "```json",
        json.dumps({"new": new, "old": old}, ensure_ascii=False, indent=1),
        "```",
        "",
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines[:8]))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
