"""Contract test of skel-learning, Seam 4: the local chain from a topic through the S5 app to the anchor.

Slice tester; from the contract, not the code. Same shape as part 1 (`tests/smoke/test_e2e_local.py`), in a
file of its own: the app of S5 in local mode, then `job.run(["analyze"], …)` over the same folder.
"""

import re
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient
from skell_fakes import CARDS, local_environ

from thinkhow.learning.analyze import Observation
from thinkhow.learning.job import run
from thinkhow.web.app import build_deps
from thinkhow.web.server import create_app


def test_seam4_local_chain_ends_in_an_observation_whose_link_opens_an_existing_turn(tmp_path: Path) -> None:
    environ = local_environ(tmp_path)
    client = TestClient(create_app(build_deps(environ, CARDS)), follow_redirects=False)
    topic = client.post("/topics", data={"title": "Кав'ярня"}).headers["location"]
    client.post(f"{topic}/reply", data={"text": "Хочу відкрити кав'ярню за три місяці."})
    assert client.post(f"{topic}/close").status_code == 303
    topic_id = topic.rsplit("/", 1)[-1]

    assert run(["analyze"], environ, CARDS, lambda: datetime.now(UTC)) == 0

    file = tmp_path / "system" / "learning" / "observations" / "local-owner" / topic_id / "s1.json"
    assert file.is_file()
    obs = Observation.model_validate_json(file.read_bytes())
    assert obs.turn in {1, 2}
    assert obs.link == f"/topics/local-owner/{topic_id}#t{obs.turn}"
    path, anchor = obs.link.split("#", 1)
    page = client.get(path)
    assert page.status_code == 200
    assert re.search(rf"""\bid=["']{anchor}["']""", page.text), page.text
