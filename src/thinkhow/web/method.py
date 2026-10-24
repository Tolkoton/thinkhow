"""What the topic page says of the thinking model that leads (task 203): a caption and marks in the history.

Reads only what the router and the facilitator already write: routing.json and the map's phase. The replies
themselves still never name a method (task 301): the caption and the marks are apart from them.
"""

from collections.abc import Mapping, Sequence

from thinkhow.facilitation import Decision, current_card
from thinkhow.knowledge import Card

FREE = "вільна розмова"
ENDED = {"done": "пройдено", "not_fit": "не підійшла"}


def caption(routing: Sequence[Decision], phase_id: str | None, cards: Mapping[str, Card]) -> str:
    """«Title · k з n» of the card that leads, its title alone without a known phase, else FREE."""
    card = cards.get(current_card(routing) or "")
    if card is None:
        return FREE
    ids = [phase.id for phase in card.facilitator.phases]
    if phase_id not in ids:
        return card.title
    return f"{card.title} · {ids.index(phase_id) + 1} з {len(ids)}"


def marks(routing: Sequence[Decision], cards: Mapping[str, Card]) -> dict[int, list[str]]:
    """Turn number → the marks before it: a choice before the card's first reply, an end after its last."""
    found: dict[int, list[str]] = {}
    for decision in routing:
        if decision.card_id is None:
            continue
        title = _title(decision.card_id, cards)
        if decision.kind == "choose":
            found.setdefault(decision.turn + 1, []).append(f"Далі веде модель мислення «{title}»")
        elif decision.kind == "end" and decision.end is not None:
            text = f"«{title}» {ENDED[decision.end]} · далі вільна розмова"
            found.setdefault(decision.turn + 2, []).append(text)
    return found


def _title(card_id: str, cards: Mapping[str, Card]) -> str:
    card = cards.get(card_id)
    return card_id if card is None else card.title
