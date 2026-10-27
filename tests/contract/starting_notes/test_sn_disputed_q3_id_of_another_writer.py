"""DISPUTED (Q3) — not sealed until the slice planner answers.

Q3: a folder id that is in the current memory, put there by another writer (the synthesizer), and that no
`notes` change ever upserted. The filter line («ті, чиїх `id` не upsert-ила жодна попередня зміна з
`by="notes"` … → apply_memory») upserts it and overwrites the synthesizer's record; I1 («кожен запис пам'яті,
що був до `notes`, після нього той самий») forbids that. Reading taken: I1 — the record stays as it was.
"""

from pathlib import Path

import pytest
from sn_fakes import Job, as_record, facilitator, hand_change, memory, newest_record, router


def test_q3_a_folder_id_the_synthesizer_already_holds_is_left_as_it_is(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    jb = Job(tmp_path, monkeypatch)
    jb.seed()
    theirs = as_record(facilitator("alpha", noticed="запис синтезатора"))
    hand_change(jb.storage, upsert=[theirs])
    path = newest_record(jb.storage).memory["alpha-facilitator"]
    jb.put("alpha.yaml", [router("alpha"), facilitator("alpha", noticed="з репозиторію")])
    assert jb("notes") == 0
    assert memory(jb.storage)["alpha-facilitator"] == theirs
    assert newest_record(jb.storage).memory["alpha-facilitator"] == path
    assert "alpha-router" in memory(jb.storage)
