"""Disputed (Q1): the map item of local_script carries exactly the person's text after the frame line.

Not sealed until the slice planner answers Q1.
"""

import json
from pathlib import Path

from skelweb_fakes import CARDS

from thinkhow.facilitation.respond import answer_schema
from thinkhow.knowledge import current, seed
from thinkhow.platform.llm import Turn
from thinkhow.platform.storage import LocalStorage
from thinkhow.web.local import local_script


def test_local_script_item_text_is_exactly_the_persons_text(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path / "k")
    seed(store, CARDS)
    schema = answer_schema(current(store).cards["pre-mortem"])
    frame = (
        '[Карта проблеми зараз]\n{"items":[],"phase_id":null,"last_turn":0}\n\n[Репліка людини #1]\nКав\'ярня'
    )
    obj = json.loads(local_script("system", [Turn("user", frame)], schema))
    assert obj["map_updates"][0]["text"] == "Кав'ярня"
