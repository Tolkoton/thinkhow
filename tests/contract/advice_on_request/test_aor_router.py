"""Task 715 (overseer's test gap on 305): a person who asks «порадь / що б ти обрав» before any method is
chosen gets advice, not a refusal.

The router's instruction says «Не давай порад щодо самої проблеми»; the facilitator's rule (task 305) says
not to refuse advice. They do not collide while three things hold, and these tests hold them: the router's
ban never reaches the facilitator's instruction; a request about a problem that is clear is a choose with no
reply of the router, led by the facilitator on that same turn (the plumbing: test_rt_310_leads_one_method.py);
the router speaks itself (an ask) only when it does not see even roughly what the problem is — there is
nothing yet to advise on. Live, on the code as it is: `.engine/artifacts/advice-first/` (task 715 report).
"""

from pathlib import Path

from thinkhow.facilitation.respond import system_instruction
from thinkhow.facilitation.route import ROUTER_RULES
from thinkhow.knowledge import current, seed
from thinkhow.platform.storage import LocalStorage

CARDS = Path(__file__).resolve().parents[3] / "cards"
ROUTER_BAN = "Не давай порад щодо самої проблеми"


def flat(text: str) -> str:
    return " ".join(text.split())


def action_rule(name: str) -> str:
    """The text of one action item of the router's instruction, up to the next item."""
    router = flat(ROUTER_RULES)
    start = router.index(f'- "{name}" —')
    ends = [i for i in (router.find(' - "', start + 1), router.find(" - why", start)) if i != -1]
    return router[start : min(ends)]


def test_the_router_ban_is_the_routers_own_and_never_reaches_the_facilitator(tmp_path: Path) -> None:
    assert ROUTER_BAN in ROUTER_RULES
    assert "Ти не відповідаєш людині по суті" in ROUTER_RULES
    storage = LocalStorage(tmp_path)
    seed(storage, CARDS)
    for card in current(storage).cards.values():
        for routed in (True, False):
            text = flat(system_instruction(card, (), "uk-UA", routed=routed))
            assert ROUTER_BAN.lower() not in text.lower(), (card.id, routed)
            assert "Порада — коли людина просить або застрягла." in text, (card.id, routed)


def test_a_choose_hands_the_turn_to_the_facilitator_with_no_reply_of_the_router() -> None:
    rule = action_rule("choose")
    assert "одразу передай її фасилітатору" in rule
    assert "reply — null" in rule


def test_the_router_speaks_itself_only_when_the_problem_is_not_seen_even_roughly() -> None:
    rule = action_rule("ask")
    assert '"ask" — лише якщо з розмови ще не видно навіть приблизно, про що проблема' in rule
    assert 'коли вагаєшся між двома способами — не питай, а "choose" кращий' in rule
