"""Live tracer of slice fact-answer (`-m live`): a direct question of fact through the router, on `eu`.

A new topic whose first turn asks a price → the router's «answer» → one streamed call with search: the
answer with its sources line, research.json, a `fact` item. Recorded too, not a condition: a situation to
think through as the first turn of another topic — which action the router chose (PR-18). One run, no rerun
until green: no «answer» on the price question falsifies PR-18 (a finding). Each run writes a new file in
.engine/artifacts/spikes/.
"""

import json
import os
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

ROOT = Path(__file__).resolve().parents[2]
CARDS = ROOT / "cards"
SPIKES = ROOT / ".engine" / "artifacts" / "spikes"
PRICE = "Скільки зараз коштує новий Škoda Octavia Combi у Німеччині?"
DECIDE = "Не можу вирішити, чи переходити на нову роботу, бо там більше платять, але далеко їздити"
USER = CurrentUser(id="live-person", email="live@example.com", is_owner=False)


def _first_turn(storage: LocalStorage, facilitate: Any, title: str, text: str) -> dict[str, Any]:
    now = datetime.now(UTC)
    ref = TopicRef(USER.id, create_topic(storage, USER, title, now))
    events = list(reply(storage, facilitate, USER, ref, text, now))
    base = f"{ref.uid}/{ref.topic_id}"

    def read(name: str, empty: str) -> Any:
        return json.loads(storage.read("users", f"{base}/{name}") or empty.encode())

    problem_map = read("map.json", "{}")
    return {
        "answered": isinstance(events[-1], Answered),
        "answer": "".join(e.text for e in events if isinstance(e, Delta)),
        "decisions": [d["kind"] for d in read("routing.json", '{"decisions": []}')["decisions"]],
        "research": read("research.json", '{"entries": []}')["entries"],
        "facts": [i["text"] for i in problem_map.get("items", []) if i["type"] == "fact"],
    }


def _section(title: str, row: dict[str, Any]) -> list[str]:
    lines = [f"## {title}", "", f"answered: {row['answered']}; рішення роутера: {row['decisions']}", ""]
    lines += ["Відповідь:", "", row["answer"], ""]
    for entry in row["research"]:
        lines += [f"- запити: {entry['queries']}", f"- джерела: {[s['url'] for s in entry['sources']]}"]
    return [*lines, f"- пункти fact: {row['facts']}", ""]


@pytest.mark.live
def test_a_direct_price_question_is_answered_with_a_source(
    tmp_path: Path, capfd: pytest.CaptureFixture[str]
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
    price = _first_turn(storage, facilitate, "Машина", PRICE)
    decide = _first_turn(storage, facilitate, "Робота", DECIDE)
    out = capfd.readouterr().out
    log = [line for line in out.splitlines() if '"llm_call"' in line]
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H%M%SZ")
    lines = ["# Live tracer fact-answer (task 303, S2)", "", f"Run: {stamp}", ""]
    lines += _section(f"Пряме питання «{PRICE}»", price)
    lines += _section(f"Ситуація «{DECIDE}» — записується", decide)
    lines += ["## Рядки `llm_call`", "", "```", *log, "```", ""]
    path = SPIKES / f"fact-answer-live-{stamp}.txt"
    path.write_text("\n".join(lines), encoding="utf-8")
    print(out, end="")
    print(path)
    assert price["answered"] and price["decisions"] == ["answer"], price
    assert "\n\nДжерела: [" in price["answer"], price["answer"]
    assert price["research"] and price["research"][0]["sources"], price["research"]
    assert price["facts"], price
