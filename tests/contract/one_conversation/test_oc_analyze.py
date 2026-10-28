"""Contract tests of one-conversation: the analyzer's context is every analyzed turn of the topic
(Seam 4, I2). Slice tester; from the contract `.engine/slices/one-conversation.md`, not the code."""

from datetime import datetime
from pathlib import Path
from typing import cast

from oc_fakes import ca

from thinkhow.learning.analyze import AnalyzeReport
from thinkhow.learning.analyze import analyze as _analyze
from thinkhow.platform.llm import Llm, LlmUnavailable
from thinkhow.platform.storage import LocalStorage

ALICE = ca.ALICE
CTX, NEW = ca.CTX, ca.NEW
DAY, H, M = ca.DAY, ca.H, ca.M


def analyze(storage: LocalStorage, llm: ca.FakeLlm, now: datetime) -> AnalyzeReport:
    """The nightly `analyze` with the model double."""
    return _analyze(storage, cast(Llm, llm), now)


# --- Seam 4: new turns start in a new session ------------------------------------------------------


def test_seam4_new_turns_in_a_third_session_get_every_analyzed_turn_of_the_topic_as_context(
    tmp_path: Path,
) -> None:
    storage = LocalStorage(tmp_path)
    t0 = ca.NOW - 5 * DAY
    ref = ca.new_topic(storage, ALICE, t0 - M)
    ca.say(storage, ALICE, ref, "Один.", "Два?", t0)
    analyze(storage, ca.FakeLlm(), t0 + H)
    ca.say(storage, ALICE, ref, "Три.", "Чотири?", t0 + DAY)  # session 2
    analyze(storage, ca.FakeLlm(), t0 + DAY + H)
    assert ca.obs_names(storage, ref) == {"t1-t2.json", "t3-t4.json"}
    ca.say(storage, ALICE, ref, "П'ять.", "Шість?", t0 + 2 * DAY)  # session 3
    llm = ca.FakeLlm()
    assert analyze(storage, llm, t0 + 2 * DAY + H) == AnalyzeReport(written=1, skipped=0, failed=0)
    assert len(llm.calls) == 1
    assert llm.calls[0].lines() == [
        CTX,
        "#1 людина: Один.",
        "#2 фасилітатор: Два?",
        "#3 людина: Три.",
        "#4 фасилітатор: Чотири?",
        NEW,
        "#5 людина: П'ять.",
        "#6 фасилітатор: Шість?",
    ]
    assert llm.calls[0].anchors() == ["t5", "t6"]
    assert ca.obs_names(storage, ref) == {"t1-t2.json", "t3-t4.json", "t5-t6.json"}


# --- I2 --------------------------------------------------------------------------------------------


def test_I2_the_context_is_every_turn_below_the_first_new_and_the_anchor_is_among_the_new_only(
    tmp_path: Path,
) -> None:
    t0 = ca.NOW - 10 * DAY

    # nothing analyzed yet, turns in two sessions: no context, every turn is new
    s = LocalStorage(tmp_path / "a")
    a = ca.new_topic(s, ALICE, t0 - M)
    ca.say(s, ALICE, a, "Один.", "Два?", t0)
    ca.say(s, ALICE, a, "Три.", "Чотири?", t0 + DAY)
    llm = ca.FakeLlm(pick="first")
    analyze(s, llm, t0 + DAY + H)
    assert len(llm.calls) == 1
    assert llm.calls[0].lines() == [
        "#1 людина: Один.",
        "#2 фасилітатор: Два?",
        "#3 людина: Три.",
        "#4 фасилітатор: Чотири?",
    ]
    assert llm.calls[0].anchors() == ["t1", "t2", "t3", "t4"]
    assert ca.obs_names(s, a) == {"t1-t4.json"}

    # the cursor in the middle of session 2; new turns go on in session 2 and into session 3
    s = LocalStorage(tmp_path / "b")
    b = ca.new_topic(s, ALICE, t0 - M)
    ca.say(s, ALICE, b, "Один.", "Два?", t0)
    ca.say(s, ALICE, b, "Три.", "Чотири?", t0 + DAY)
    analyze(s, ca.FakeLlm(), t0 + DAY + H)
    ca.say(s, ALICE, b, "П'ять.", "Шість?", t0 + DAY + 2 * H)  # still session 2
    ca.say(s, ALICE, b, "Сім.", "Вісім?", t0 + 2 * DAY + 2 * H)  # session 3
    llm = ca.FakeLlm(pick="first")
    analyze(s, llm, t0 + 2 * DAY + 3 * H)
    assert len(llm.calls) == 1
    assert llm.calls[0].lines() == [
        CTX,
        "#1 людина: Один.",
        "#2 фасилітатор: Два?",
        "#3 людина: Три.",
        "#4 фасилітатор: Чотири?",
        NEW,
        "#5 людина: П'ять.",
        "#6 фасилітатор: Шість?",
        "#7 людина: Сім.",
        "#8 фасилітатор: Вісім?",
    ]
    assert llm.calls[0].anchors() == ["t5", "t6", "t7", "t8"]
    assert ca.obs_names(s, b) == {"t1-t4.json", "t5-t8.json"}
    assert [o["turn"] for o in ca.items(s, b, "t5-t8.json")] == [5]

    # a legacy cursor s1.json (session 1 closed by the old marker): new turns are session 2's
    old = ca.NOW - 8 * DAY
    s = LocalStorage(tmp_path / "c")
    c = ca.legacy_topic(
        s,
        ALICE,
        [
            ca.LS(1, ca.pair(1, "в-перша", old), closed=old + H),
            ca.LS(2, ca.pair(3, "в-друга", ca.NOW - 2 * H)),
        ],
    )
    ca.put_obs(s, c, "s1.json")
    llm = ca.FakeLlm(pick="first")
    analyze(s, llm, ca.NOW)
    assert len(llm.calls) == 1
    assert llm.calls[0].lines() == [
        CTX,
        "#1 людина: в-перша людина 1",
        "#2 фасилітатор: в-перша фасилітатор 2",
        NEW,
        "#3 людина: в-друга людина 3",
        "#4 фасилітатор: в-друга фасилітатор 4",
    ]
    assert llm.calls[0].anchors() == ["t3", "t4"]
    assert ca.obs_names(s, c) == {"s1.json", "t3-t4.json"}

    # a legacy cursor s2.json over three sessions: two sessions of context
    s = LocalStorage(tmp_path / "d")
    d = ca.legacy_topic(
        s,
        ALICE,
        [
            ca.LS(1, ca.pair(1, "г-перша", old)),
            ca.LS(2, ca.pair(3, "г-друга", old + 2 * DAY)),
            ca.LS(3, ca.pair(5, "г-третя", ca.NOW - 3 * H)),
        ],
    )
    ca.put_obs(s, d, "s2.json")
    llm = ca.FakeLlm()
    analyze(s, llm, ca.NOW)
    assert len(llm.calls) == 1
    assert llm.calls[0].lines() == [
        CTX,
        "#1 людина: г-перша людина 1",
        "#2 фасилітатор: г-перша фасилітатор 2",
        "#3 людина: г-друга людина 3",
        "#4 фасилітатор: г-друга фасилітатор 4",
        NEW,
        "#5 людина: г-третя людина 5",
        "#6 фасилітатор: г-третя фасилітатор 6",
    ]
    assert llm.calls[0].anchors() == ["t5", "t6"]

    # a failed run, then the next one: the same context and the same new turns
    s = LocalStorage(tmp_path / "e")
    e = ca.new_topic(s, ALICE, t0 - M)
    ca.say(s, ALICE, e, "Один.", "Два?", t0)
    analyze(s, ca.FakeLlm(), t0 + H)
    ca.say(s, ALICE, e, "Три.", "Чотири?", t0 + DAY)  # session 2
    down = ca.FakeLlm(fail_all=LlmUnavailable("down"))
    assert analyze(s, down, t0 + DAY + H) == AnalyzeReport(written=0, skipped=0, failed=1)
    llm = ca.FakeLlm(pick="first")
    analyze(s, llm, t0 + DAY + 2 * H)
    expected = [
        CTX,
        "#1 людина: Один.",
        "#2 фасилітатор: Два?",
        NEW,
        "#3 людина: Три.",
        "#4 фасилітатор: Чотири?",
    ]
    assert down.calls[0].lines() == expected
    assert llm.calls[0].lines() == expected
    assert llm.calls[0].anchors() == ["t3", "t4"]
    assert ca.obs_names(s, e) == {"t1-t2.json", "t3-t4.json"}
    assert [o["turn"] for o in ca.items(s, e, "t3-t4.json")] == [3]
