"""The builder's tests of skel-workspace: the test gap the overseer named at its PASS of unit 4 (2026-10-22).

They reuse the sealed slice-tester helpers (`skelw_fakes`) without changing them.
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parents[1] / "contract" / "skel_workspace"
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from skelw_fakes import ALICE, H24, S1, T0, ScenarioFacilitate, conv_lines, drain, ok  # noqa: E402

from thinkhow.platform.storage import LocalStorage  # noqa: E402
from thinkhow.workspace import TopicRef, create_topic, open_topic, reply  # noqa: E402

KYIV = timezone(timedelta(hours=2))


def test_a_reply_at_plus_two_is_stamped_and_silenced_from_its_utc_second(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    ref = TopicRef("alice-1", create_topic(store, ALICE, "Тема", T0))
    now = datetime(2026, 10, 22, 18, 0, 0, 500_000, tzinfo=KYIV)
    drain(reply(store, ScenarioFacilitate(store, [ok("Що може піти не так?")]), ALICE, ref, "Кав'ярня.", now))
    turns = [line for line in conv_lines(store, ref) if line.startswith("<!-- thinkhow:turn")]
    assert turns == [
        "<!-- thinkhow:turn 1 user 2026-10-22T16:00:00Z -->",
        "<!-- thinkhow:turn 2 model 2026-10-22T16:00:00Z -->",
    ]
    assert open_topic(store, ALICE, ref, (T0 + H24 - S1).astimezone(KYIV)).sessions[-1].closed_at is None
    assert open_topic(store, ALICE, ref, (T0 + H24).astimezone(KYIV)).sessions[-1].closed_at == T0 + H24
