"""synthesizer exit criterion 3 (PR-29): the synthesizer on the real model (`pytest -m live`).

1. The observations of the live analyzer run on the owner's conversation (analysis-rules artifact, attempt 2):
   the change is applied, it cites only observations of its input, the person-details check lets it through.
2. ≈200 synthetic observations: Vertex takes the schema with the enum o1…o200 (the first deployed run takes
   the whole history). Writes .engine/artifacts/synthesizer/live.txt.
"""

import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path

import pytest

from thinkhow import knowledge
from thinkhow.learning.observations import Observation, ObservationSet
from thinkhow.learning.synthesize import runs, synthesize
from thinkhow.learning.vet import measure, vet_with
from thinkhow.platform.config import load_settings
from thinkhow.platform.llm import make_llm
from thinkhow.platform.storage import LocalStorage

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / ".engine/artifacts/analysis-rules/owner-t-84d1517cb1c1.md"
OUT = ROOT / ".engine/artifacts/synthesizer/live.txt"
NOW = datetime(2026, 10, 27, 20, 0, tzinfo=UTC)
STUCK = "застрягла на питанні про метрику"


def owner_observations() -> list[Observation]:
    text = SOURCE.read_text(encoding="utf-8").split("## Спроба 2", 1)[1]
    raw = re.search(r"```json\n(.*?)\n```", text, re.S)
    assert raw is not None
    return [Observation.model_validate(o) for o in json.loads(raw.group(1))["new"]]


def store(tmp: Path, observations: list[Observation]) -> LocalStorage:
    storage = LocalStorage(tmp)
    knowledge.seed(storage, ROOT / "cards")
    found = ObservationSet(
        uid="owner",
        topic_id="t-84d1517cb1c1",
        first_turn=1,
        last_turn=max(o.turn for o in observations),
        analyzed_at=NOW,
        observations=observations,
    )
    storage.write(
        "system",
        f"learning/observations/owner/t-84d1517cb1c1/t1-t{found.last_turn}.json",
        found.model_dump_json().encode(),
        "application/json",
    )
    return storage


def synthetic(n: int) -> list[Observation]:
    kinds = ("stuck", "progress", "method_fit")
    return [
        Observation(
            id=f"owner/t-84d1517cb1c1/t1-t400/{k}",
            turn=k,
            link=f"/topics/owner/t-84d1517cb1c1#t{k}",
            kind=kinds[k % 3],
            worked=k % 3 == 1,
            finding=f"Спостереження {k}: людина {STUCK if k % 3 == 0 else 'просунулась'}.",
            cause="facilitation",
            card_id="opportunity-tree",
            analyzed_at=NOW,
        )
        for k in range(1, n + 1)
    ]


@pytest.mark.live
def test_the_synthesizer_applies_a_change_citing_its_input_and_takes_two_hundred(tmp_path: Path) -> None:
    environ = {**os.environ, "THINKHOW_LOCAL": "false", "THINKHOW_USERS_BUCKET": "-"}
    settings = load_settings(environ | {"THINKHOW_SYSTEM_BUCKET": "-", "THINKHOW_OWNER_EMAIL": "-"})
    llm = make_llm(settings, script=lambda *_: "")
    owner = store(tmp_path / "owner", owner_observations())
    report = synthesize(owner, llm, NOW, vet_with(llm), measure)
    feed = knowledge.changes(owner)
    lines = [f"model: {settings.model}; region: {settings.location}", f"owner: {report}"]
    if report.outcome == "applied":
        change = feed[0]
        lines += [f"what: {change.what}", f"why: {change.why}", f"observations: {change.observations}"]
        lines += [
            f"- {r.id} [{r.audience}; {', '.join(r.cards)}] {r.title}: {r.noticed} → {r.do}"
            for r in change.upserted
        ]
    many = store(tmp_path / "many", synthetic(200))
    big = synthesize(many, llm, NOW, vet_with(llm), measure)
    lines.append(f"200 synthetic: {big}; rejected: {runs(many)[-1].rejected if runs(many) else None}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert report.outcome == "applied"
    assert set(feed[0].observations) <= set(runs(owner)[-1].considered)
    assert big.outcome != "failed"
