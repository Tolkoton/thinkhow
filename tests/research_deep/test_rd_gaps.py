"""The builder's tests of research-deep: the three test gaps the overseer named at its PASS (2026-10-25).

They reuse the sealed slice-tester helpers (`rdp_fakes`) without changing them.
"""

import importlib
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parents[1] / "contract" / "research_deep"
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

f: Any = importlib.import_module("rdp_fakes")  # the sealed research-deep helpers

from thinkhow.facilitation.deep import DeepDone, run_deep, with_deep  # noqa: E402
from thinkhow.facilitation.route import RouterAnswer  # noqa: E402
from thinkhow.facilitation.types import FacilitatorUpdate, PendingDeep, ReplyDelta  # noqa: E402
from thinkhow.platform import llm as pl  # noqa: E402

REV = pl.KnowledgeRev(rev=3, n=7)


def test_a_blank_deep_question_beside_an_offer_or_an_ask_is_none_and_valid() -> None:
    offer = f.fa.router_raw("offer", ("alpha", "beta"), None, f.fa.OFFER_REPLY, "пропоную")
    ask = f.fa.router_raw("ask", (), None, "Що для вас важливо?")
    for raw in (offer, ask):
        for blank in ("", "   ", "\n"):
            answer = RouterAnswer.model_validate_json(f.with_deep_question(raw, blank))
            assert answer.deep_question is None


def test_with_deep_cannot_meet_an_empty_reply_so_its_separator_always_follows_text() -> None:
    """The overseer's case «no text before the deep part» cannot arise: an update never has an empty reply;
    the proposal (deep-research-confirm-first) follows the answer after its separator."""
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        FacilitatorUpdate(reply="", current_phase_id="a_one", phase_exit_met=False, map_updates=[])
    llm = f.full_deep()
    update = FacilitatorUpdate(reply="Почну.", current_phase_id="a_one", phase_exit_met=False, map_updates=[])
    items = list(with_deep(iter([update]), lambda: f.DQ, f.ctx(), llm, REV))
    shown = "".join(i.text for i in items if isinstance(i, ReplyDelta))
    (last,) = [i for i in items if isinstance(i, FacilitatorUpdate)]
    assert shown.startswith("\n\n") and last.reply == "Почну." + shown


def test_a_query_two_searches_return_is_recorded_once_in_sub_question_order() -> None:
    same = "Mittelstand Beratung"
    searches = {
        f.QA: (f.TEXT_A, pl.Found((same, "erste"), (f.PA,), None)),
        f.QB: (f.TEXT_B, pl.Found(("zweite", same), (f.PB,), None)),
    }
    llm = f.deep_llm([], [f.report_raw()], searches)
    pending = PendingDeep(question=f.DQ, intro="Дослідю.", questions=[f.QA, f.QB])
    (done,) = [i for i in run_deep(pending, f.ctx(), llm, REV) if isinstance(i, DeepDone)]
    assert done.event.queries == (same, "erste", "zweite")
