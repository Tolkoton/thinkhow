"""Contract tests of analysis-rules (learning-loop S2): `learning.observations.read_all` over three shapes.

Seam 3: the bytes of the old files are literal JSON by the `Observation` model of `669a07e` (`s<n>.json`)
and of `c14fd9b` (`t<a>-t<b>.json`), not made by the new code. Slice tester; from the contract, not the code.
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from ar_fakes import install_log_capture, put_raw

from thinkhow.learning.observations import Observation, read_all
from thinkhow.platform.storage import LocalStorage

T_OLD = datetime(2026, 10, 22, 4, 0, 0, tzinfo=UTC)
T_MID = datetime(2026, 10, 24, 4, 0, 0, tzinfo=UTC)
T_NEW = datetime(2026, 10, 27, 4, 0, 0, tzinfo=UTC)

# an old range file of continuous-analysis (c14fd9b): one observation
OLD_RANGE_WORKED = """{"uid":"alice-1","topic_id":"aaa111","first_turn":3,"last_turn":4,"turn":4,\
"link":"/topics/alice-1/aaa111#t4","worked":true,"finding":"людина назвала крок","cause":"facilitation",\
"analyzed_at":"2026-10-24T04:00:00Z"}"""
OLD_RANGE_NOT_WORKED = """{"uid":"alice-1","topic_id":"aaa111","first_turn":11,"last_turn":12,"turn":11,\
"link":"/topics/alice-1/aaa111#t11","worked":false,"finding":"питання повторилось","cause":"method",\
"analyzed_at":"2026-10-24T04:00:00Z"}"""

# an old s<n>.json of skel-learning (669a07e)
OLD_S2 = """{"uid":"alice-1","topic_id":"aaa111","session_no":2,"turn":2,"link":"/topics/alice-1/aaa111#t2",\
"worked":false,"finding":"сесія друга","cause":"circumstances","closed_at":"2026-10-22T03:00:00Z",\
"analyzed_at":"2026-10-22T04:00:00Z"}"""
OLD_S10 = """{"uid":"alice-1","topic_id":"aaa111","session_no":10,"turn":1,\
"link":"/topics/alice-1/aaa111#t1",\
"worked":true,"finding":"сесія десята","cause":"method","closed_at":"2026-10-22T03:00:00Z",\
"analyzed_at":"2026-10-22T04:00:00Z"}"""

# a new set (this slice)
NEW_SET = """{"uid":"alice-1","topic_id":"aaa111","first_turn":13,"last_turn":16,\
"analyzed_at":"2026-10-27T04:00:00Z","observations":[\
{"id":"alice-1/aaa111/t13-t16/1","turn":15,"link":"/topics/alice-1/aaa111#t15","kind":"stuck","worked":false,\
"finding":"не знає відповіді","cause":"facilitation","card_id":"alpha","analyzed_at":"2026-10-27T04:00:00Z"},\
{"id":"alice-1/aaa111/t13-t16/2","turn":13,"link":"/topics/alice-1/aaa111#t13","kind":"step","worked":true,\
"finding":"зробила крок","cause":"circumstances","card_id":null,"analyzed_at":"2026-10-27T04:00:00Z"}]}"""


def _o(
    oid: str,
    turn: int,
    topic: str,
    kind: str,
    worked: bool,
    finding: str,
    cause: str,
    card_id: str | None,
    at: datetime,
    uid: str = "alice-1",
) -> Observation:
    return Observation.model_validate(
        {
            "id": oid,
            "turn": turn,
            "link": f"/topics/{uid}/{topic}#t{turn}",
            "kind": kind,
            "worked": worked,
            "finding": finding,
            "cause": cause,
            "card_id": card_id,
            "analyzed_at": at,
        }
    )


def test_seam3_an_old_range_file_reads_as_a_set_of_one_with_kind_from_worked(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    put_raw(storage, "alice-1", "aaa111", "t3-t4.json", OLD_RANGE_WORKED)
    put_raw(storage, "alice-1", "aaa111", "t11-t12.json", OLD_RANGE_NOT_WORKED)
    assert read_all(storage) == [
        _o(
            "alice-1/aaa111/t3-t4/1",
            4,
            "aaa111",
            "progress",
            True,
            "людина назвала крок",
            "facilitation",
            None,
            T_MID,
        ),
        _o(
            "alice-1/aaa111/t11-t12/1",
            11,
            "aaa111",
            "stuck",
            False,
            "питання повторилось",
            "method",
            None,
            T_MID,
        ),
    ]


def test_seam3_an_old_s_file_reads_as_a_set_of_one_with_its_session_id(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    put_raw(storage, "alice-1", "aaa111", "s2.json", OLD_S2)
    put_raw(storage, "alice-1", "aaa111", "s10.json", OLD_S10)
    assert read_all(storage) == [
        _o("alice-1/aaa111/s2/1", 2, "aaa111", "stuck", False, "сесія друга", "circumstances", None, T_OLD),
        _o("alice-1/aaa111/s10/1", 1, "aaa111", "progress", True, "сесія десята", "method", None, T_OLD),
    ]


def test_a_new_set_reads_as_it_is_and_kind_step_is_accepted(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    put_raw(storage, "alice-1", "aaa111", "t13-t16.json", NEW_SET)
    assert read_all(storage) == [
        _o(
            "alice-1/aaa111/t13-t16/1",
            15,
            "aaa111",
            "stuck",
            False,
            "не знає відповіді",
            "facilitation",
            "alpha",
            T_NEW,
        ),
        _o(
            "alice-1/aaa111/t13-t16/2",
            13,
            "aaa111",
            "step",
            True,
            "зробила крок",
            "circumstances",
            None,
            T_NEW,
        ),
    ]


def test_read_all_order_is_uid_topic_then_s_files_by_n_then_range_files_by_a_then_k(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    # written in a shuffled order; the second user and a second topic come after
    put_raw(
        storage, "bob_2", "ccc333", "s1.json", OLD_S2.replace("alice-1", "bob_2").replace("aaa111", "ccc333")
    )
    put_raw(storage, "alice-1", "bbb222", "t1-t2.json", OLD_RANGE_WORKED.replace("aaa111", "bbb222"))
    put_raw(storage, "alice-1", "aaa111", "t13-t16.json", NEW_SET)
    put_raw(storage, "alice-1", "aaa111", "t11-t12.json", OLD_RANGE_NOT_WORKED)
    put_raw(storage, "alice-1", "aaa111", "s10.json", OLD_S10)
    put_raw(storage, "alice-1", "aaa111", "t3-t4.json", OLD_RANGE_WORKED)
    put_raw(storage, "alice-1", "aaa111", "s2.json", OLD_S2)
    assert [o.id for o in read_all(storage)] == [
        "alice-1/aaa111/s2/1",
        "alice-1/aaa111/s10/1",
        "alice-1/aaa111/t3-t4/1",
        "alice-1/aaa111/t11-t12/1",
        "alice-1/aaa111/t13-t16/1",
        "alice-1/aaa111/t13-t16/2",
        "alice-1/bbb222/t1-t2/1",
        "bob_2/ccc333/s1/1",
    ]


def test_an_unreadable_file_is_skipped_with_a_log_line_that_has_the_path_and_no_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    logs = install_log_capture(monkeypatch)
    storage = LocalStorage(tmp_path)
    put_raw(storage, "alice-1", "aaa111", "t3-t4.json", OLD_RANGE_WORKED)
    put_raw(storage, "alice-1", "aaa111", "t5-t6.json", b"\xff not json SECRET-TEXT-ONE")
    put_raw(storage, "alice-1", "aaa111", "s3.json", '{"legacy": true, "note": "SECRET-TEXT-TWO"}')
    put_raw(storage, "alice-1", "aaa111", "t7-t8.json", '{"observations": "SECRET-TEXT-THREE"}')
    got = read_all(storage)
    assert [o.id for o in got] == ["alice-1/aaa111/t3-t4/1"]
    lines = logs.events("observation_unreadable")
    assert len(lines) == 3
    for name in ("t5-t6.json", "s3.json", "t7-t8.json"):
        tail = f"alice-1/aaa111/{name}"
        assert [
            line for line in lines if any(isinstance(v, str) and v.endswith(tail) for v in line.values())
        ], name
    assert "SECRET-TEXT" not in logs.text()
