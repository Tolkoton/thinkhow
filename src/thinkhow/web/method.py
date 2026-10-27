"""What the topic page says of the thinking model that leads (task 203): a caption and marks in the history.

Reads only what the router and the facilitator already write: routing.json and the map's phase. The caption
and the marks are apart from the replies, which since task 205 name the method themselves too. Their words
and the card's title come in the person's language (task 208).
"""

from collections.abc import Mapping, Sequence

from thinkhow.facilitation import Decision, current_card
from thinkhow.knowledge import Card
from thinkhow.web.ui_text import card_title

ENDED = {"done": "method_done", "not_fit": "method_not_fit"}


def caption(
    routing: Sequence[Decision],
    phase_id: str | None,
    cards: Mapping[str, Card],
    words: Mapping[str, str],
) -> str:
    """«Title · k з n» of the card that leads, its title alone without a known phase, else «free»."""
    card = cards.get(current_card(routing) or "")
    if card is None:
        return words["free_conversation"]
    ids = [phase.id for phase in card.facilitator.phases]
    title = card_title(card, words)
    if phase_id not in ids:
        return title
    return words["phase_of"].format(title=title, k=ids.index(phase_id) + 1, n=len(ids))


def marks(
    routing: Sequence[Decision], cards: Mapping[str, Card], words: Mapping[str, str]
) -> dict[int, list[str]]:
    """Turn number → the marks before it: a choice before the card's first reply, an end after its last."""
    found: dict[int, list[str]] = {}
    for decision in routing:
        if decision.card_id is None:
            continue
        title = _title(decision.card_id, cards, words)
        if decision.kind == "choose":
            found.setdefault(decision.turn + 1, []).append(words["method_leads"].format(title=title))
        elif decision.kind == "end" and decision.end is not None:
            text = words[ENDED[decision.end]].format(title=title)
            found.setdefault(decision.turn + 2, []).append(text)
    return found


def _title(card_id: str, cards: Mapping[str, Card], words: Mapping[str, str]) -> str:
    card = cards.get(card_id)
    return card_id if card is None else card_title(card, words)
