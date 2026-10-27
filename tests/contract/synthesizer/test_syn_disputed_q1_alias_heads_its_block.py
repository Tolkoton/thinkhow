"""Disputed (Q1): «кожне під коротким псевдонімом `o<k>`» read as — the alias comes first and the fields of
observation k stand between `o<k>` and `o<k+1>`. Not sealed until the slice planner answers Q1."""

import re
from pathlib import Path

from syn_fakes import NOW, Ob, SynthLlm, answer, ok_vet, put_set, seeded, zero_measure

from thinkhow.learning.synthesize import synthesize


def test_q1_each_observation_stands_under_its_own_alias(tmp_path: Path) -> None:
    storage = seeded(tmp_path)
    obs = put_set(
        storage,
        [
            Ob("u-a", "tp-1", 1, 6, 1, 1, "знахідка-один", card_id="alpha"),
            Ob("u-a", "tp-1", 1, 6, 2, 3, "знахідка-два", card_id="beta"),
            Ob("u-a", "tp-1", 1, 6, 3, 5, "знахідка-три", card_id="gamma"),
        ],
    )
    llm = SynthLlm([answer()])
    synthesize(storage, llm, NOW, ok_vet, zero_measure)
    text = llm.calls[0].text
    starts = []
    for k in range(1, len(obs) + 1):
        found = re.search(rf"(?<![A-Za-z0-9])o{k}(?![0-9])", text)
        assert found, f"o{k}"
        starts.append(found.start())
    assert starts == sorted(starts)
    bounds = [*starts, len(text)]
    for k, o in enumerate(obs):
        block = text[bounds[k] : bounds[k + 1]]
        assert o.finding in block, (k + 1, block)
        for other in obs:
            if other is not o:
                assert other.finding not in block, (k + 1, block)
