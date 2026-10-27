"""spoken-replies: the form field `spoken` of `/reply` and `/retry` reaches `FacilitationContext.spoken` as
`spoken == "1"` (slice tester; Seam 3 of «Hardest seams», web half)."""

from pathlib import Path
from typing import Any

from sr_fakes import ALICE, H_ALICE, T0, ScenarioFacilitate, fail, make_client, ok

from thinkhow.workspace import TopicRef, create_topic

# What the form sends → what the context must hold; None = the field is not sent at all.
CASES: tuple[tuple[str | None, bool], ...] = (("1", True), (None, False), ("0", False), ("", False))


def url(ref: TopicRef, action: str) -> str:
    return f"/topics/{ref.uid}/{ref.topic_id}/{action}"


def form(spoken: str | None, **rest: str) -> dict[str, Any]:
    return rest if spoken is None else {**rest, "spoken": spoken}


def test_reply_form_spoken_reaches_the_context(tmp_path: Path) -> None:
    fac = ScenarioFacilitate()
    client, store = make_client(tmp_path, fac)
    ref = TopicRef(ALICE.id, create_topic(store, ALICE, "Тема", T0))
    for value, expected in CASES:
        fac.scripts.append(ok())
        r = client.post(url(ref, "reply"), data=form(value, text="Репліка."), headers=H_ALICE)
        assert r.status_code == 200, (value, r.status_code)
        assert "answered" in r.text, value
        assert fac.contexts[-1].spoken is expected, value


def test_retry_form_spoken_reaches_the_context(tmp_path: Path) -> None:
    fac = ScenarioFacilitate()
    client, store = make_client(tmp_path, fac)
    ref = TopicRef(ALICE.id, create_topic(store, ALICE, "Тема", T0))
    for value, expected in CASES:
        fac.scripts += [fail(), ok()]
        r = client.post(url(ref, "reply"), data={"text": "Репліка."}, headers=H_ALICE)
        assert r.status_code == 200, (value, r.status_code)
        r = client.post(url(ref, "retry"), data=form(value), headers=H_ALICE)
        assert r.status_code == 200, (value, r.status_code)
        assert "answered" in r.text, value
        assert fac.contexts[-1].spoken is expected, value
