"""Smoke of slice notes-readers: the readers of the notes on the 25 real cards (learning-loop S4).

Run: `uv run python scripts/smoke_test_notes_readers.py`. Two notes — `router` to pre-mortem, `facilitator`
to five-whys — in a CurrentKnowledge from cards/; prints the pre-mortem section of the router's instruction
and the memory section of the facilitator for five-whys and for pre-mortem, and checks: the router note stands
in the pre-mortem section and nowhere else, the facilitator note only at five-whys. Writes the same to
.engine/artifacts/notes-readers/smoke.txt; exits 1 on a failed check.
"""

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from thinkhow.facilitation.respond import system_instruction  # noqa: E402
from thinkhow.facilitation.route import router_instruction  # noqa: E402
from thinkhow.knowledge import Card, CurrentKnowledge, MemoryRecord  # noqa: E402

OUT = ROOT / ".engine" / "artifacts" / "notes-readers" / "smoke.txt"
ROUTER_NOTE = MemoryRecord(
    id="pre-mortem-router",
    title="План уже обрано",
    cards=["pre-mortem"],
    noticed="Пропонуй, коли людина вже обрала план і хоче його перевірити.",
    do="Не плутай з вибором між варіантами (wrap-decision).",
    basis="смоук",
    audience="router",
)
FACILITATOR_NOTE = MemoryRecord(
    id="five-whys-facilitator",
    title="Перше «чому» про симптом",
    cards=["five-whys"],
    noticed="Людина відповідає на перше «чому» описом симптому.",
    do="Спитай, що саме сталося перед цим.",
    basis="смоук",
)


def main() -> int:
    lines: list[str] = []
    ok = True

    def say(text: str) -> None:
        print(text)
        lines.append(text)

    def check(condition: bool, text: str) -> None:
        nonlocal ok
        ok = ok and condition
        say(f"{'OK  ' if condition else 'FAIL'} {text}")

    cards = {}
    for f in sorted((ROOT / "cards").glob("*.yaml")):
        card = Card.model_validate(yaml.safe_load(f.read_text(encoding="utf-8")))
        cards[card.id] = card
    k = CurrentKnowledge(rev=2, n=0, cards=cards, memory=[ROUTER_NOTE, FACILITATOR_NOTE])
    router = router_instruction(k, None)
    parts = router.split("\n### ")[1:]
    sections = {part.split(" — ", 1)[0]: "### " + part.split("\n\n", 1)[0] for part in parts}
    say("## Роутер, розділ pre-mortem\n" + sections["pre-mortem"])
    check(ROUTER_NOTE.title in sections["pre-mortem"], "the router note stands in the pre-mortem section")
    others = [cid for cid, text in sections.items() if ROUTER_NOTE.title in text and cid != "pre-mortem"]
    check(len(sections) == 25 and not others, "and in no other of the 25 sections")
    check(FACILITATOR_NOTE.title not in router, "the facilitator note is not in the router's instruction")
    for cid in ("five-whys", "pre-mortem"):
        memory = system_instruction(cards[cid], k.memory, None, True).split("# Пам'ять досвіду\n", 1)[1]
        say(f"## Фасилітатор {cid}, пам'ять досвіду\n{memory.strip()}")
    five = system_instruction(cards["five-whys"], k.memory, None, True)
    pre = system_instruction(cards["pre-mortem"], k.memory, None, True)
    check(FACILITATOR_NOTE.title in five, "five-whys' facilitator has its note")
    check(
        FACILITATOR_NOTE.title not in pre and ROUTER_NOTE.title not in pre,
        "pre-mortem's facilitator has none",
    )
    say("RESULT: " + ("PASS" if ok else "FAIL"))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
