"""Live run of task 305 (`-m live`): the owner's conversations again from turn #1, through the product.

Each topic is read at run time from the users bucket (ADC). A fresh local topic gets the owner's turns
#1…#last verbatim, one by one, through `workspace.reply` with the router and `VertexLlm(search=True)`, as
`web.app` runs them. `t-84d1517cb1c1` to #17 — the turn where the owner asked the system to propose a solution
itself; the control `t-d824f508a729` to #11 — no request for advice and no repeated «не знаю». Whether the
answers advise only when asked is read by a person from the record (`.engine/artifacts/advice-live/<time>/`),
not judged by code.
"""

import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from thinkhow.access import CurrentUser
from thinkhow.facilitation import respond
from thinkhow.knowledge import current, seed
from thinkhow.platform.config import load_settings
from thinkhow.platform.llm import make_llm
from thinkhow.platform.storage import LocalStorage
from thinkhow.workspace import Answered, Delta, TopicRef, create_topic, reply, set_language
from thinkhow.workspace import conversation as conv_file

ROOT = Path(__file__).resolve().parents[2]
CARDS = ROOT / "cards"
OUT = ROOT / ".engine" / "artifacts" / "advice-live"
BUCKET = "gs://pocket-lawyer-431614-thinkhow-users/104839836105981044615"
USER = CurrentUser(id="live-person", email="live@example.com", is_owner=False)
IN_USD, OUT_USD, QUERY_USD = 2.2 / 1e6, 11 / 1e6, 14 / 1000  # PR-19, as in test_research_owner_live.py


def _cat(topic: str) -> str:
    return subprocess.run(
        ["gcloud", "storage", "cat", f"{BUCKET}/{topic}/conversation.md"],
        capture_output=True,
        check=True,
        text=True,
    ).stdout


def _price(calls: list[dict[str, Any]]) -> str:
    model = sum(
        c["prompt_tokens"] * IN_USD + (c["output_tokens"] + c["thought_tokens"]) * OUT_USD for c in calls
    )
    queries = sum(c["queries"] for c in calls)
    seconds = sum(c["latency_ms"] for c in calls) / 1000
    return f"{len(calls)} викликів, {seconds:.1f} с моделі, {queries} пошукових запитів; ${model:.3f} модель"


def _decisions(new: list[dict[str, Any]]) -> str:
    if not new:
        return "без нового рішення роутера"
    return "; ".join(
        f"{d['kind']} {d.get('card_id') or ', '.join(c['card_id'] for c in d['candidates'])}" for d in new
    )


@pytest.mark.live
@pytest.mark.parametrize(("topic", "last"), [("t-84d1517cb1c1", 17), ("t-d824f508a729", 11)])
def test_the_owners_turns_again_from_the_first(
    topic: str, last: int, tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    storage = LocalStorage(tmp_path)
    seed(storage, CARDS)
    knowledge = current(storage)
    environ = {
        **os.environ,
        "THINKHOW_LOCAL": "false",
        "THINKHOW_USERS_BUCKET": "-",
        "THINKHOW_SYSTEM_BUCKET": "-",
        "THINKHOW_OWNER_EMAIL": "-",
    }
    llm = make_llm(load_settings(environ), lambda *_: "", search=True)

    def facilitate(ctx: Any) -> Any:
        return respond(ctx, knowledge, llm)

    set_language(storage, USER, "uk-UA")
    owner = conv_file.parse(_cat(topic))
    turns = [t for s in owner.sessions for t in s.turns if t.no <= last]
    ref = TopicRef(USER.id, create_topic(storage, USER, owner.title, turns[0].at))
    base = f"{ref.uid}/{ref.topic_id}"

    def read(name: str, empty: str) -> Any:
        return json.loads(storage.read("users", f"{base}/{name}") or empty.encode())

    capfd.readouterr()
    after: list[str] = []
    failed: str | None = None
    for turn in (t for t in turns if t.role == "user"):
        before = read("routing.json", '{"decisions": []}')["decisions"]
        events = list(reply(storage, facilitate, USER, ref, turn.text, turn.at))
        calls = [json.loads(line) for line in capfd.readouterr().out.splitlines() if '"llm_call"' in line]
        after += [f"### #{turn.no} Людина", "", turn.text, ""]
        if not isinstance(events[-1], Answered):
            failed = f"#{turn.no}: {events[-1]}"
            after += [f"**Відповіді немає: {events[-1]}**", ""]
            break
        no = events[-1].turn_no
        searched = [e for e in read("research.json", '{"entries": []}')["entries"] if e["turn"] == no]
        answer = "".join(e.text for e in events if isinstance(e, Delta))
        new = read("routing.json", '{"decisions": []}')["decisions"][len(before) :]
        after += [f"### #{no} ThinkHow", "", answer, "", f"- роутер: {_decisions(new)}"]
        after += [f"- дослідження {e['depth']}: запити {e['queries']}" for e in searched]
        after += [f"- {_price(calls)}", ""]
    then: list[str] = []
    for t in (t for s in owner.sessions for t in s.turns if t.no <= last + 1):
        then += [f"### #{t.no} {'Людина' if t.role == 'user' else 'ThinkHow (тоді)'}", "", t.text, ""]
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H%M%SZ")
    folder = OUT / f"{stamp}-{topic}"
    folder.mkdir(parents=True, exist_ok=True)
    lines = [f"# Розмова власника `{topic}` #1–#{last} заново (задача 305)", "", f"Прогін: {stamp}.", ""]
    lines += ["## До (як у bucket)", "", *then, "## Після (продукт з правилом поради)", "", *after]
    (folder / "conversation.md").write_text("\n".join(lines), encoding="utf-8")
    print(folder / "conversation.md")
    assert failed is None, failed
