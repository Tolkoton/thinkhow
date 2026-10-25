"""Disputed (Q1): I3 — the AC5 rule of Seam 2 — on index.md fixtures. Slice tester; from the contract.

The rule lives in the AC test (`test_pre_ac.py`), not in the skeleton, so this test checks the rule that
test applies (`pre_helpers.card_passes`). Fixtures are built by `card_conversations.index()` (Seam 2) and
from a real `index.md` row.
"""

from typing import Any

from pre_helpers import card_passes, script

CARD = "demand-test"
OTHER = "customer-interviews"


def conv(
    name: str,
    target: str | None,
    led: str | None,
    *,
    offered: bool = True,
    done: bool = True,
    last_phase: bool = True,
    seeded: bool = False,
    note: str = "",
) -> Any:
    cc = script("card_conversations")
    return cc.Conversation(
        name=name,
        target=target,
        led=led,
        offered=offered,
        seeded=seeded,
        phases=["phase_1_pretotype", "phase_2_xyz"],
        last_phase=last_phase,
        done=done,
        note=note,
    )


def index(*convs: Any) -> str:
    text: str = script("card_conversations").index(list(convs), "2026-10-26T010203Z")
    return text


REAL_HEADER = (
    "| розмова | цільова | вели | запропоновано | фази | остання фаза | end: done | реплік людини "
    "| позначки |\n"
    "|---|---|---|---|---|---|---|---|---|\n"
)


def test_I3_a_new_card_passes_iff_one_of_its_target_rows_is_chosen_led_and_done() -> None:
    first_failed = conv(CARD, CARD, CARD, done=False, last_phase=True)  # «остання фаза» так, «end: done» ні
    second_ok = conv(f"{CARD}-спроба-2", CARD, CARD, done=True, last_phase=False)

    # A failed first row and a successful «-спроба-2»: PASS, in either order.
    assert card_passes(index(first_failed, second_ok), CARD) is True
    assert card_passes(index(second_ok, first_failed), CARD) is True

    # Only failed rows, the seeded one with «end: done» = так included: FAIL.
    other_led = conv(f"{CARD}-спроба-2", CARD, OTHER, note=f"обрано іншу картку ({OTHER})")
    not_offered = conv(f"{CARD}-спроба-3", CARD, CARD, offered=False)
    seeded = conv(f"{CARD}-засіяно", CARD, CARD, offered=True, seeded=True)
    assert card_passes(index(first_failed, other_led, not_offered, seeded), CARD) is False
    assert card_passes(index(seeded, not_offered, other_led, first_failed), CARD) is False

    # A row of another target where «вели» = this card does not count; nor does the owner's conversation.
    foreign = conv(OTHER, OTHER, CARD, done=True)
    owner = conv("owner-t-d824f508a729", None, CARD, offered=False, done=True)
    assert card_passes(index(foreign, owner, first_failed), CARD) is False

    # Rows of other targets around a successful one change nothing.
    assert card_passes(index(foreign, second_ok, owner), CARD) is True

    # A real row of index.md, backticks and all; the seeding mark is matched as a substring.
    real_ok = (
        f"| [{CARD}]({CARD}.md) | `{CARD}` | `{CARD}` | так | phase_1_pretotype → phase_2_xyz | ні "
        f"| так | 7 |  |\n"
    )
    real_seeded = (
        f"| [{CARD}-засіяно]({CARD}-засіяно.md) | `{CARD}` | `{CARD}` | так | phase_1_pretotype | так "
        f"| так | 5 | вели без вибору роутером (не запропоновано) |\n"
    )
    assert card_passes("# Живі розмови по картках\n\n" + REAL_HEADER + real_ok, CARD) is True
    assert card_passes("# Живі розмови по картках\n\n" + REAL_HEADER + real_seeded, CARD) is False
