"""Contract tests of the synthesizer invariants I1-I3 (slice tester; inputs by hand from each Domain)."""

from collections.abc import Sequence
from datetime import timedelta
from html.parser import HTMLParser
from pathlib import Path

from syn_fakes import (
    CARDS_PREFIX,
    H_OWNER,
    NOW,
    SpyStorage,
    SynthLlm,
    all_run_records,
    answer,
    change_files,
    change_record,
    hand_apply,
    make_client,
    note,
    ok_vet,
    one_obs,
    remove_item,
    seeded,
    snapshot,
    upsert_item,
    zero_measure,
)

from thinkhow.knowledge import MemoryRecord, current
from thinkhow.learning.observations import read_all
from thinkhow.learning.synthesize import synthesize
from thinkhow.platform.llm import LlmUnavailable


class Links(HTMLParser):
    def __init__(self, html: str) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []
        self.feed(html)
        self.close()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self.hrefs += [v for k, v in attrs if k == "href" and v is not None]


def last_cards(storage: SpyStorage) -> dict[str, str]:
    return change_record(storage, current(storage).rev).cards


def test_I1_no_run_of_any_outcome_changes_the_cards(tmp_path: Path) -> None:
    storage = seeded(tmp_path)
    hand_apply(storage, upsert=[note("m-old", cards=["alpha", "beta"])])

    def refuse(records: Sequence[MemoryRecord]) -> str | None:
        return "названо людину"

    steps = [  # (new observation topic, the model's answer, vet, forced create_if_absent, outcome)
        (
            "tp-1",
            answer(upsert=[upsert_item("n-1", ["o1"], cards=["alpha", "beta", "gamma"])]),
            ok_vet,
            None,
            "applied",
        ),
        ("tp-2", answer(upsert=[upsert_item("m-old", ["o1"], cards=["gamma"])]), ok_vet, None, "applied"),
        ("tp-3", answer(remove=[remove_item("m-old", ["o1"])]), ok_vet, None, "applied"),
        ("tp-4", answer(), ok_vet, None, "no_change"),
        ("tp-5", answer(upsert=[upsert_item("n-2", ["o1"], cards=["beta"])]), refuse, None, "rejected"),
        ("tp-6", answer(remove=[remove_item("no-such", ["o1"])]), ok_vet, None, "rejected"),
        ("tp-7", answer(upsert=[upsert_item("n-3", ["o2"])]), ok_vet, None, "failed"),  # foreign alias
        ("tp-8", LlmUnavailable("down"), ok_vet, None, "failed"),
        (
            "tp-9",
            answer(upsert=[upsert_item("n-4", ["o1"])]),
            ok_vet,
            ("knowledge/changes/", False),
            "no_change",
        ),
        (None, answer(), ok_vet, None, "nothing_new"),
    ]
    at = NOW
    for topic, planned, vet, forced, outcome in steps:
        storage.forced = None
        if topic is not None:
            one_obs(storage, topic, 1, f"знахідка {topic}")
        cards_files = snapshot(storage, CARDS_PREFIX)
        cards_dict = last_cards(storage)
        storage.forced = forced
        llm = SynthLlm([planned])
        report = synthesize(storage, llm, at, vet, zero_measure)
        storage.forced = None
        assert report.outcome == outcome, (topic, report)
        assert snapshot(storage, CARDS_PREFIX) == cards_files, topic
        assert last_cards(storage) == cards_dict, topic
        at += timedelta(hours=1)


def test_I2_no_observation_is_considered_by_two_run_records(tmp_path: Path) -> None:
    storage = seeded(tmp_path)

    def refuse(records: Sequence[MemoryRecord]) -> str | None:
        return "названо людину"

    a = one_obs(storage, "tp-a", 1, "a")
    b = one_obs(storage, "tp-b", 1, "b")
    llm = SynthLlm([answer(upsert=[upsert_item("n-1", ["o1"])])])
    assert synthesize(storage, llm, NOW, ok_vet, zero_measure).outcome == "applied"  # a, b
    c = one_obs(storage, "tp-c", 1, "c")
    llm.plan.append(answer())
    assert (
        synthesize(storage, llm, NOW + timedelta(hours=1), ok_vet, zero_measure).outcome == "no_change"
    )  # c
    d = one_obs(storage, "tp-d", 1, "d")
    llm.plan.append(answer(upsert=[upsert_item("n-2", ["o1"])]))
    assert synthesize(storage, llm, NOW + timedelta(hours=2), refuse, zero_measure).outcome == "rejected"  # d
    e = one_obs(storage, "tp-e", 1, "e")
    llm.plan.append(LlmUnavailable("down"))
    assert (
        synthesize(storage, llm, NOW + timedelta(hours=3), ok_vet, zero_measure).outcome == "failed"
    )  # none
    llm.plan.append(answer(upsert=[upsert_item("n-1", ["o1"])]))
    assert synthesize(storage, llm, NOW + timedelta(hours=3), ok_vet, zero_measure).outcome == "applied"  # e
    f = one_obs(storage, "tp-f", 1, "f")
    g = one_obs(storage, "tp-g", 1, "g")
    hand_apply(storage, upsert=[note("m-hand")], observations=[f.id])  # f is consumed by a change record
    llm.plan.append(answer(remove=[remove_item("no-such", ["o1"])]))
    assert synthesize(storage, llm, NOW + timedelta(hours=3), ok_vet, zero_measure).outcome == "rejected"  # g
    assert synthesize(storage, llm, NOW + timedelta(hours=4), ok_vet, zero_measure).outcome == "nothing_new"
    considered = [set(r["considered"]) for r in all_run_records(storage)]
    for i, one in enumerate(considered):
        for other in considered[i + 1 :]:
            assert not (one & other), considered
    expected = [{a.id, b.id}, {c.id}, {d.id}, {e.id}, {g.id}]
    assert sorted(considered, key=sorted) == sorted(expected, key=sorted)


def test_I3_an_applied_change_cites_only_observations_of_its_own_input(tmp_path: Path) -> None:
    storage = seeded(tmp_path)
    hand_apply(storage, upsert=[note("m-old")])
    first = [one_obs(storage, f"tp-{i}", 2 * i + 1, f"перша-{i}") for i in range(3)]
    llm = SynthLlm([answer(upsert=[upsert_item("n-1", ["o3"])], remove=[remove_item("m-old", ["o1", "o3"])])])
    r1 = synthesize(storage, llm, NOW, ok_vet, zero_measure)
    assert r1.outcome == "applied"
    later = [one_obs(storage, f"tq-{i}", 5, f"друга-{i}") for i in range(2)]
    llm.plan.append(answer(upsert=[upsert_item("n-1", ["o1", "o2"]), upsert_item("n-2", ["o2"])]))
    r2 = synthesize(storage, llm, NOW + timedelta(days=1), ok_vet, zero_measure)
    assert r2.outcome == "applied"
    llm.plan.append(LlmUnavailable("down"))
    third = one_obs(storage, "tr-0", 9, "третя")
    llm.plan.append(answer(upsert=[upsert_item("n-3", ["o1"])]))
    synthesize(storage, llm, NOW + timedelta(days=2), ok_vet, zero_measure)  # failed
    r3 = synthesize(storage, llm, NOW + timedelta(days=3), ok_vet, zero_measure)  # applied after a failure
    assert r3.outcome == "applied"
    by_rev = {r["rev"]: set(r["considered"]) for r in all_run_records(storage) if r["outcome"] == "applied"}
    known = {o.id: o.link for o in read_all(storage)}
    expected_cited = {
        r1.rev: {first[0].id, first[2].id},
        r2.rev: {later[0].id, later[1].id},
        r3.rev: {third.id},
    }
    client = make_client(tmp_path, storage)
    page = client.get("/learning", headers=H_OWNER)
    assert page.status_code == 200
    hrefs = Links(page.text).hrefs
    for rev, cited in expected_cited.items():
        record = change_record(storage, rev)
        assert set(record.observations) == cited
        assert set(record.observations) <= by_rev[rev]
        for oid in record.observations:
            assert oid in known
            assert known[oid] in hrefs, (oid, known[oid])
    assert change_files(storage)[-1].endswith(f"{r3.rev:06d}.json")
