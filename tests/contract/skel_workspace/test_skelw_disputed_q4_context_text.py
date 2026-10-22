"""Disputed (Q4): `FacilitationContext.text` given by `reply` is the normalized text, not the raw argument.

Reading taken: «нормалізують `text`» happens before step (2), so `facilitate` sees what was saved.
Not sealed until the slice planner answers Q4.
"""

from pathlib import Path

from skelw_fakes import ALICE, T0, ScenarioFacilitate, drain, ok

from thinkhow.platform.storage import LocalStorage
from thinkhow.workspace import TopicRef, create_topic, reply


def test_facilitate_gets_the_normalized_text(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    ref = TopicRef("alice-1", create_topic(store, ALICE, "Тема", T0))
    fac = ScenarioFacilitate(store, [ok("Так?")])
    drain(reply(store, fac, ALICE, ref, "  питання\r\nдруге\r ", T0))
    assert fac.calls[0].context.text == "питання\nдруге"
