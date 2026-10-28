"""Contract tests of step-results (learning-loop S6): the topic page — the question, the block «Кроки»,
and the catalogs (Seam 4).

Slice tester; from the contract `.engine/slices/step-results.md`, not the code. The texts are PROVISIONAL:
the tests take them from the uk catalog and check the keys and the `{step}`, not the words.
"""

import html
import re
from datetime import datetime
from pathlib import Path

from stp_fakes import (
    DAY,
    H_ALICE,
    H_OWNER,
    LOCALES,
    NEW_KEYS,
    STEP,
    T0,
    M,
    Rec,
    catalog,
    make_client,
    outcome,
    page_url,
    say,
    uk,
    with_chosen_step,
)

from thinkhow.platform.storage import LocalStorage
from thinkhow.workspace import TopicRef


def _page(
    tmp_path: Path, storage: LocalStorage, now: datetime, ref: TopicRef, headers: dict[str, str]
) -> str:
    r = make_client(tmp_path, storage, now).get(page_url(ref), headers=headers)
    assert r.status_code == 200, r.text[:300]
    return html.unescape(r.text)


def test_the_page_shows_the_question_as_a_line_before_the_input_field_to_the_topics_owner_only(
    tmp_path: Path,
) -> None:
    storage = LocalStorage(tmp_path / "data")
    ref = with_chosen_step(storage, T0)
    question = uk("step_question").replace("{step}", STEP)
    own = _page(tmp_path, storage, T0 + DAY, ref, H_ALICE)
    assert question in own
    assert own.index(question) < own.index("<textarea")
    others = _page(tmp_path, storage, T0 + DAY, ref, H_OWNER)
    assert question not in others


def test_the_block_steps_shows_step_result_clearer_and_said_also_to_the_owner_in_someone_elses_topic(
    tmp_path: Path,
) -> None:
    storage = LocalStorage(tmp_path / "data")
    back = T0 + DAY
    done = with_chosen_step(storage, T0, step="Поговорити з трьома клієнтами")
    say(
        storage,
        done,
        "Несподівано: хочуть доставку.",
        back,
        recognize=Rec(outcome("unexpected", "partly", "хочуть доставку")),
    )
    silent = with_chosen_step(storage, T0, step_id="s2", step="Порахувати оренду")
    say(storage, silent, "Сьогодні про меню.", back)  # no recognize: outcome None
    for headers in (H_ALICE, H_OWNER):
        page = _page(tmp_path, storage, back + M, done, headers)
        for part in (
            uk("steps_title"),
            "Поговорити з трьома клієнтами",
            uk("step_unexpected"),
            uk("clearer_partly"),
            "хочуть доставку",
        ):
            assert part in page, (headers, part)
        page = _page(tmp_path, storage, back + M, silent, headers)
        for part in (uk("steps_title"), "Порахувати оренду", uk("step_no_answer")):
            assert part in page, (headers, part)


def test_seam4_every_new_key_is_in_every_catalog_with_the_same_placeholders() -> None:
    names = sorted(p.stem for p in LOCALES.glob("*.json"))
    assert len(names) == 76
    source = catalog("uk")
    missing = [k for k in NEW_KEYS if k not in source]
    assert not missing, f"uk lacks {missing}"
    assert re.findall(r"\{\w+\}", source["step_question"]) == ["{step}"]
    for name in names:
        words = catalog(name)
        for key in NEW_KEYS:
            assert key in words, (name, key)
            assert sorted(re.findall(r"\{\w+\}", words[key])) == sorted(
                re.findall(r"\{\w+\}", source[key])
            ), (
                name,
                key,
            )
