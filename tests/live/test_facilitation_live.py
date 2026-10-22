"""Seam 3 of skel-facilitation: one real reply by the Pre-mortem card through respond (`-m live`)."""

import os
from pathlib import Path

import pytest

from thinkhow.facilitation import FacilitationContext, FacilitatorUpdate, ProblemMap, ReplyDelta, respond
from thinkhow.knowledge import current, seed
from thinkhow.platform.config import load_settings
from thinkhow.platform.llm import make_llm
from thinkhow.platform.storage import LocalStorage

CARDS = Path(__file__).resolve().parents[2] / "cards"


@pytest.mark.live
def test_one_real_reply_streams_and_gives_a_valid_update(tmp_path: Path) -> None:
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
    llm = make_llm(load_settings(environ), script=lambda *_: "")
    ctx = FacilitationContext(
        card_id="pre-mortem",
        history=[],
        problem_map=ProblemMap(),
        turn_no=1,
        text="Хочу за три місяці відкрити кав'ярню з обсмажуванням у Львові. Перевірмо план, поки не пізно.",
    )
    items = list(respond(ctx, knowledge, llm))
    deltas = [i.text for i in items if isinstance(i, ReplyDelta)]
    update = items[-1]
    assert isinstance(update, FacilitatorUpdate)
    assert len(deltas) >= 2
    assert "".join(deltas) == update.reply
    assert update.current_phase_id in {p.id for p in knowledge.cards["pre-mortem"].facilitator.phases}
