"""Live of slice spoken-replies (`-m live`, PR-26): the model writes for the ear when the person listens.

On `eu`, through `workspace.reply(..., spoken=True)` and `respond` with search, as the product does:
(а) a situation to think through → the router's offer without markup or list symbols;
(б) a direct price question → the answer names a source in words before the sources line;
(в) «Давай перший.» → the chosen card's first reply names its method.
One recorded run; a red item falsifies PR-26 for it (contract spoken-replies, Exit criterion).
Each run writes a file in .engine/artifacts/spikes/.
"""

import json
import os
import re
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
USER = CurrentUser(id="live-listener", email="live@example.com", is_owner=False)
DECIDE = "Не можу вирішити, чи переходити на нову роботу, бо там більше платять, але далеко їздити"
PRICE = "Скільки зараз коштує новий Škoda Octavia Combi у Німеччині?"
CHOOSE = "Давай перший."
SOURCES = "\n\nДжерела: "
MARKUP = re.compile(r"\*\*|^\s*#|^\s*[-*•]\s|^\s*\d+[.)]\s", re.M)


def _turn(storage: LocalStorage, facilitate: Any, ref: TopicRef, text: str) -> dict[str, Any]:
    events = list(reply(storage, facilitate, USER, ref, text, datetime.now(UTC), spoken=True))
    base = f"{ref.uid}/{ref.topic_id}"

    def read(name: str, empty: str) -> Any:
        return json.loads(storage.read("users", f"{base}/{name}") or empty.encode())

    routing = read("routing.json", '{"decisions": []}')["decisions"]
    return {
        "answered": isinstance(events[-1], Answered),
        "answer": "".join(e.text for e in events if isinstance(e, Delta)),
        "decision": routing[-1] if routing else None,
        "research": read("research.json", '{"entries": []}')["entries"],
    }


def _names(entry: dict[str, Any]) -> list[str]:
    """A source said in words: the site's name without its zone (adac.de → adac), or a word of its title."""
    out = []
    for source in entry["sources"]:
        title = source["title"].lower()
        out.append(title.split(".")[0] if "." in title else title)
    return [n for n in out if len(n) >= 3]


@pytest.mark.live
def test_the_model_writes_for_the_ear_when_the_person_listens(
    tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    storage = LocalStorage(tmp_path)
    seed(storage, CARDS)
    knowledge = current(storage)
    environ = {**os.environ, "THINKHOW_LOCAL": "false", "THINKHOW_USERS_BUCKET": "-"}
    environ |= {"THINKHOW_SYSTEM_BUCKET": "-", "THINKHOW_OWNER_EMAIL": "-"}
    llm = make_llm(load_settings(environ), lambda *_: "", search=True)

    def facilitate(ctx: Any) -> Any:
        assert ctx.spoken is True
        return respond(ctx, knowledge, llm)

    set_language(storage, USER, "uk-UA")
    now = datetime.now(UTC)
    work = TopicRef(USER.id, create_topic(storage, USER, "Робота", now))
    car = TopicRef(USER.id, create_topic(storage, USER, "Машина", now))
    a = _turn(storage, facilitate, work, DECIDE)
    b = _turn(storage, facilitate, car, PRICE)
    c = _turn(storage, facilitate, work, CHOOSE)
    card = knowledge.cards.get((c["decision"] or {}).get("card_id") or "")
    method = [n for n in ((card.method, card.title) if card else ()) if n]
    spoken_b = b["answer"].split(SOURCES)[0].lower()
    names = [n for e in b["research"] for n in _names(e)]
    checks = {
        "а offer без розмітки": bool(a["decision"] and a["decision"]["kind"] == "offer")
        and not MARKUP.search(a["answer"]),
        "б джерело словами": any(n in spoken_b for n in names),
        "в метод названо": bool(c["decision"] and c["decision"]["kind"] == "choose")
        and any(m.lower() in c["answer"].lower() for m in method),
    }
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H%M%SZ")
    lines = ["# Live spoken-replies (task 308, S3, PR-26)", "", f"Run: {stamp}", ""]
    for title, row in (("а — ситуація", a), ("б — ціна", b), ("в — «Давай перший.»", c)):
        kind = (row["decision"] or {}).get("kind")
        lines += [f"## {title}", "", f"рішення роутера: {kind}", "", row["answer"], ""]
    lines += [f"джерела (назви): {names}", f"метод: {method}", "", "## Перевірки", ""]
    lines += [f"- {k}: {'так' if v else 'НІ'}" for k, v in checks.items()]
    path = SPIKES / f"spoken-replies-live-{stamp}.txt"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(capfd.readouterr().out, end="")
    print(path)
    assert all(row["answered"] for row in (a, b, c))
    assert all(checks.values()), checks
