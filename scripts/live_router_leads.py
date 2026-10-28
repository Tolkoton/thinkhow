"""Live check of task 310: the router chooses one method itself and the facilitator leads by it at once.

Two conversations through the product's `workspace.reply` (model `gemini-4-argon`, Vertex `eu`), a synthetic
person (`gemini-3.5-flash`) answering after the first turn:
- the owner's `t-84d1517cb1c1`, turn #1 verbatim (taken from the record of task 305, where the answer of that
  time — the list of three ways — stands too);
- a new one: a situation of the routing set, and after two led replies the person says «Давай інакше…».

Run: `PYTHONPATH=src uv run python scripts/live_router_leads.py [--turns N]`. Each conversation goes to
.engine/artifacts/router-leads/<time>/<name>.md with index.md; whether every reply gives something of its own
before its question is read by a person from the record, not judged by code.
"""

import argparse
import importlib.util
import re
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

import yaml

from thinkhow.knowledge import current, seed
from thinkhow.platform import llm as model
from thinkhow.platform.storage import LocalStorage

ROOT = Path(__file__).resolve().parents[1]
BEFORE = ROOT / ".engine/artifacts/advice-live/2026-10-25T174143Z-t-84d1517cb1c1/conversation.md"
OUT = ROOT / ".engine" / "artifacts" / "router-leads"
NEW_CASE = "wr-1"


def _stand() -> ModuleType:
    """The conversation stand of task 302 (`card_conversations.py`), loaded by path, without a copy."""
    spec = importlib.util.spec_from_file_location(
        "card_conversations", ROOT / "scripts" / "card_conversations.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def owner_turn_1(text: str) -> str:
    """The owner's turn #1 as the record of task 305 holds it: the paragraph under «### #1 Людина»."""
    found = re.search(r"### #1 Людина\n\n(.+?)\n\n###", text, re.S)
    assert found is not None, "no turn #1 in the record"
    return found.group(1).strip()


def first_reply(conv: Any) -> dict[str, Any]:
    """What the first answer was: who gave it, the first decision of the router, whether it names a method."""
    answer = conv.rows[1]
    kinds = [d["kind"] for d in answer.decisions]
    return {
        "who": answer.who,
        "kinds": kinds,
        "named": cc.names_a_method(answer.text),
        "offer": "offer" in kinds,
    }


def index(convs: list[Any], stamp: str) -> str:
    lines = [f"# Задача 310 — жива перевірка, {stamp}", ""]
    for c in convs:
        first = first_reply(c)
        kinds = [d["kind"] for d in c.routing]
        lines += [
            f"## `{c.name}`",
            "",
            f"- Перша відповідь: {first['who']}; рішення роутера: {', '.join(first['kinds']) or '—'}; "
            f"називає метод: {'так' if first['named'] else 'ні'}.",
            f"- Усі рішення роутера: {', '.join(kinds)};",
            f"  пропозицій зі списку (offer): {kinds.count('offer')}.",
            f"- Вели картками: {', '.join(d['card_id'] for d in c.routing if d['kind'] == 'choose') or '—'}.",
            f"- {c.broken and 'обірвано: ' + c.broken or 'не обірвано'}.",
            "",
        ]
    return "\n".join(lines)


cc = _stand()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--turns", type=int, default=5)
    args = parser.parse_args()
    llm = model.make_llm(cc._settings("gemini-4-argon"), lambda *_: "")
    person = model.make_llm(cc._settings(cc.PERSON_MODEL), lambda *_: "")
    storage = LocalStorage(Path(tempfile.mkdtemp(prefix="thinkhow-k-")))
    seed(storage, ROOT / "cards")
    knowledge = current(storage)
    opener = owner_turn_1(BEFORE.read_text(encoding="utf-8"))
    owner = cc._drive(
        knowledge,
        llm,
        person,
        cc._topic("Продати асистента"),
        opener,
        opener,
        cc.HOW_FOR_CARD,
        None,
        args.turns,
        False,
    )
    owner.name = "owner-t-84d1517cb1c1"
    case = next(c for c in yaml.safe_load(cc.CASES.read_text("utf-8"))["cases"] if c["id"] == NEW_CASE)
    new = cc.converse_card(knowledge, llm, person, case["expect"], case["text"].strip(), args.turns + 2, True)
    new.name = f"new-{NEW_CASE}-switch"
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H%M%SZ")
    folder = OUT / stamp
    folder.mkdir(parents=True)
    for c in (owner, new):
        cc.write(folder, c, f"Жива розмова — `{c.name}`")
    (folder / "index.md").write_text(index([owner, new], stamp), encoding="utf-8")
    print(folder / "index.md")


if __name__ == "__main__":
    main()
