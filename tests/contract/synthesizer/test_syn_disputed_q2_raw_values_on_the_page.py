"""Disputed (Q2): the Ukrainian page /learning read as showing `kind`, `cause` and `audience` by their stored
values (`stuck`, `router`…), not by Ukrainian words. Not sealed until the slice planner answers Q2."""

from pathlib import Path

from syn_fakes import H_OWNER, hand_apply, make_client, note, one_obs, seeded


def test_q2_the_page_shows_kind_cause_and_audience_by_their_values(tmp_path: Path) -> None:
    storage = seeded(tmp_path)
    one_obs(storage, "tp-1", 1, "знахідка", kind="method_fit", cause="circumstances")
    hand_apply(storage, upsert=[note("n-1", audience="router")])
    r = make_client(tmp_path, storage).get("/learning", headers=H_OWNER)
    assert r.status_code == 200
    for value in ("method_fit", "circumstances", "router"):
        assert value in r.text, value
