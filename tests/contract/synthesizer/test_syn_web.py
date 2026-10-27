"""Contract tests of the page /learning, the rollback over HTTP and the owner's link (slice tester)."""

import json
import re
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

from syn_fakes import (
    ALICE,
    H_ALICE,
    H_OWNER,
    NOW,
    ROLLBACKS,
    RUNS,
    H,
    SpyStorage,
    hand_apply,
    make_client,
    memory,
    note,
    one_obs,
    seeded,
)

from thinkhow.knowledge import Rollback, rollback
from thinkhow.learning.synthesize import SynthesisRun
from thinkhow.platform.storage import LocalStorage

LOCALES = Path(__file__).resolve().parents[3] / "src" / "thinkhow" / "web" / "locales"


class Page(HTMLParser):
    def __init__(self, html: str) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[tuple[str, dict[str, str | None]]] = []
        self.texts: list[str] = []
        self.feed(html)
        self.close()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append((tag, dict(attrs)))

    def handle_data(self, data: str) -> None:
        self.texts.append(data)

    @property
    def text(self) -> str:
        return " ".join(" ".join(self.texts).split())

    @property
    def hrefs(self) -> list[str]:
        return [a.get("href") or "" for t, a in self.tags if t == "a"]

    def rollback_forms(self) -> set[str]:
        return {
            a.get("action") or ""
            for t, a in self.tags
            if t == "form" and (a.get("action") or "").startswith("/learning/rollback/")
        }


def put_run(storage: LocalStorage, name: str, run: SynthesisRun) -> None:
    LocalStorage.write(
        storage, "system", f"{RUNS}{name}.json", run.model_dump_json().encode(), "application/json"
    )


def learning(tmp_path: Path, storage: SpyStorage) -> Page:
    r = make_client(tmp_path, storage).get("/learning", headers=H_OWNER)
    assert r.status_code == 200, r.text
    return Page(r.text)


# --- Seam 4 -----------------------------------------------------------------------------------------


def test_seam4_the_owner_rolls_a_change_back_over_http(tmp_path: Path) -> None:
    storage = seeded(tmp_path)
    o = one_obs(storage, "tp-1", 1, "знахідка")
    rev = hand_apply(storage, upsert=[note("n-1")], observations=[o.id], what="зміна-для-відкату")
    client = make_client(tmp_path, storage)
    before = Page(client.get("/learning", headers=H_OWNER).text)
    assert f"/learning/rollback/{rev}" in before.rollback_forms()
    r = client.post(f"/learning/rollback/{rev}", headers=H_OWNER)
    assert r.status_code == 303
    assert r.headers["location"] == "/learning"
    assert "n-1" not in memory(storage)
    files = LocalStorage.list(storage, "system", ROLLBACKS)
    assert len(files) == 1
    raw = LocalStorage.read(storage, "system", files[0])
    assert raw is not None
    assert Rollback.model_validate_json(raw).by == "owner@example.com"
    after = Page(client.get("/learning", headers=H_OWNER).text)
    assert "відкочено (відкат 1)" in after.text
    assert f"/learning/rollback/{rev}" not in after.rollback_forms()


def test_seam4_a_person_not_the_owner_gets_the_foreign_topic_404_and_writes_no_rollback(
    tmp_path: Path,
) -> None:
    storage = seeded(tmp_path)
    rev = hand_apply(storage, upsert=[note("n-1")])
    client = make_client(tmp_path, storage)
    foreign = client.get("/topics/owner-1/t-000000000000", headers=H_ALICE)
    assert foreign.status_code == 404
    got = client.get("/learning", headers=H_ALICE)
    posted = client.post(f"/learning/rollback/{rev}", headers=H_ALICE)
    assert got.status_code == 404
    assert posted.status_code == 404
    assert got.text == foreign.text
    assert posted.text == foreign.text
    assert LocalStorage.list(storage, "system", ROLLBACKS) == []
    assert "n-1" in memory(storage)


# --- the page ---------------------------------------------------------------------------------------


def test_the_feed_shows_changes_newest_first_with_their_notes_removed_ids_and_observation_links(
    tmp_path: Path,
) -> None:
    storage = seeded(tmp_path)
    o1 = one_obs(storage, "tp-1", 1, "знахідка-1")
    o2 = one_obs(storage, "tp-2", 3, "знахідка-2")
    hand_apply(storage, upsert=[note("gone-note", noticed="буде-прибрано")], what="зміна-перша")  # rev 2
    rev3 = hand_apply(
        storage,
        upsert=[note("n-1", cards=["beta"], basis="підстава-нотатки", noticed="помічено-1", do="робити-1")],
        remove=["gone-note"],
        observations=[o1.id, o2.id],
        what="зміна-друга",
    )
    page = learning(tmp_path, storage)
    text = page.text
    assert text.index("зміна-друга") < text.index("зміна-перша")
    for token in (
        str(rev3),
        "чому руками",
        "owner-test",
        "заголовок n-1",
        "помічено-1",
        "робити-1",
        "підстава-нотатки",
        "beta",
        "gone-note",
    ):
        assert token in text, token
    assert o1.link in page.hrefs
    assert o2.link in page.hrefs
    forms = page.rollback_forms()
    assert f"/learning/rollback/{rev3}" in forms
    assert "/learning/rollback/2" in forms
    assert "/learning/rollback/1" not in forms  # the seed: no upserted, no removed


def test_a_rollback_that_changed_nothing_is_marked_so_and_has_no_button(tmp_path: Path) -> None:
    storage = seeded(tmp_path)
    first = hand_apply(storage, upsert=[note("m-1", noticed="v1")], what="зміна-перша")  # rev 2
    later = hand_apply(storage, upsert=[note("m-1", noticed="v2")], what="зміна-друга")  # rev 3
    rollback(storage, first, by="owner@example.com", now=NOW - H)
    page = learning(tmp_path, storage)
    assert "відкочено — нічого не змінено" in page.text
    assert f"/learning/rollback/{first}" not in page.rollback_forms()
    assert f"/learning/rollback/{later}" in page.rollback_forms()


def test_rejected_runs_are_shown_with_their_reason(tmp_path: Path) -> None:
    storage = seeded(tmp_path)
    put_run(
        storage,
        "20261026T120000Z",
        SynthesisRun(
            at=datetime(2026, 10, 26, 12, 0, tzinfo=NOW.tzinfo),
            considered=["u-a/tp-1/t1-t2/1"],
            outcome="rejected",
            rev=None,
            rejected="подробиці людей: названо місто",
        ),
    )
    put_run(
        storage,
        "20261025T120000Z",
        SynthesisRun(
            at=datetime(2026, 10, 25, 12, 0, tzinfo=NOW.tzinfo),
            considered=["u-a/tp-2/t1-t2/1"],
            outcome="no_change",
            rev=None,
            rejected=None,
        ),
    )
    page = learning(tmp_path, storage)
    assert "відхилено перевіркою: подробиці людей: названо місто" in page.text
    assert page.text.count("відхилено перевіркою:") == 1


def test_observations_are_shown_newest_first_with_card_finding_and_link(tmp_path: Path) -> None:
    storage = seeded(tmp_path)
    old = one_obs(storage, "tp-z", 1, "знахідка-давня", card_id="beta", analyzed_at=NOW - 5 * H)
    new = one_obs(storage, "tp-a", 1, "знахідка-нова", card_id="gamma", analyzed_at=NOW - H)
    page = learning(tmp_path, storage)
    text = page.text
    assert text.index("знахідка-нова") < text.index("знахідка-давня")
    assert "beta" in text and "gamma" in text
    assert old.link in page.hrefs
    assert new.link in page.hrefs


def test_the_page_has_its_three_sections(tmp_path: Path) -> None:
    storage = seeded(tmp_path)
    one_obs(storage, "tp-1", 1, "знахідка")
    put_run(
        storage,
        "20261026T120000Z",
        SynthesisRun(at=NOW - 2 * H, considered=["x"], outcome="rejected", rev=None, rejected="причина"),
    )
    text = learning(tmp_path, storage).text
    for heading in ("Стрічка змін", "Відхилено перевіркою", "Спостереження"):
        assert heading in text, heading


def test_a_second_rollback_and_a_rollback_of_the_seed_are_409(tmp_path: Path) -> None:
    storage = seeded(tmp_path)
    rev = hand_apply(storage, upsert=[note("n-1")])
    client = make_client(tmp_path, storage)
    assert client.post(f"/learning/rollback/{rev}", headers=H_OWNER).status_code == 303
    assert client.post(f"/learning/rollback/{rev}", headers=H_OWNER).status_code == 409  # AlreadyRolledBack
    assert client.post("/learning/rollback/1", headers=H_OWNER).status_code == 409  # NotRollbackable
    assert len(LocalStorage.list(storage, "system", ROLLBACKS)) == 1


def test_a_rollback_of_an_unknown_revision_is_404(tmp_path: Path) -> None:
    storage = seeded(tmp_path)
    client = make_client(tmp_path, storage)
    r = client.post("/learning/rollback/99", headers=H_OWNER)
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("text/html"), r.text  # a fragment, not the router's JSON 404
    assert re.search("[а-яіїєґ]", r.text.lower()), r.text  # in Ukrainian, like the page
    assert LocalStorage.list(storage, "system", ROLLBACKS) == []


# --- the owner's link and the catalogs --------------------------------------------------------------


def test_the_home_page_links_to_learning_for_the_owner_only(tmp_path: Path) -> None:
    storage = seeded(tmp_path)
    client = make_client(tmp_path, storage)
    owner = client.get("/", headers=H_OWNER)
    person = client.get("/", headers=H_ALICE)
    assert owner.status_code == 200 and person.status_code == 200
    assert "/learning" in Page(owner.text).hrefs
    assert "/learning" not in Page(person.text).hrefs
    assert ALICE.is_owner is False


def test_every_catalog_has_the_learning_link_word() -> None:
    files = sorted(LOCALES.glob("*.json"))
    assert len(files) >= 76
    missing = []
    for path in files:
        words = json.loads(path.read_text(encoding="utf-8"))
        value = words.get("learning_link")
        if not (isinstance(value, str) and value.strip()):
            missing.append(path.name)
    assert missing == []
