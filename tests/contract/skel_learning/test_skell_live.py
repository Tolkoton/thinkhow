"""Contract test of skel-learning, Seam 3: one real analyzer call to gemini-4-argon on `eu` (`-m live`).

Slice tester; from the contract, not the code. A topic of 40 Ukrainian turns → one call through
`analyze` → one `Observation` whose turn is one of the topic's turns.

Corrected by objection (round 2, slice continuous-analysis, task 202): no closing is needed; the file is
`t1-t40.json`.
"""

import os
from datetime import timedelta
from pathlib import Path

import pytest
from skell_fakes import ALICE, NOW, S1, S, T, range_path, write_topic

from thinkhow.learning.analyze import AnalyzeReport, Observation, analyze
from thinkhow.platform.config import load_settings
from thinkhow.platform.llm import make_llm
from thinkhow.platform.storage import LocalStorage

PERSON = [
    "Хочу за три місяці відкрити кав'ярню з власним обсмажуванням у Львові.",
    "Гроші є: заощадження і невеликий кредит від родини.",
    "Приміщення вже дивився, біля університету, оренда помірна.",
    "Найбільше боюся, що студенти влітку роз'їдуться.",
    "Мабуть, треба мати запас грошей на літо.",
]
FACILITATOR = [
    "Уявіть, що минув рік і кав'ярня закрилася. Що найімовірніше сталося?",
    "Що з цього ви можете перевірити ще до підписання оренди?",
    "Які з цих ризиків найважче помітити заздалегідь?",
    "Який знак скаже вам, що план іде не так?",
    "Що ви зробите першого ж тижня, якщо цей знак з'явиться?",
]


@pytest.mark.live
def test_seam3_real_model_anchors_the_observation_to_a_turn_of_a_40_turn_topic(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    start = NOW - timedelta(hours=5)
    turns = [
        T(n, "user", PERSON[(n // 2) % 5], start + n * 60 * S1)
        if n % 2
        else T(n, "model", FACILITATOR[(n // 2 - 1) % 5], start + n * 60 * S1)
        for n in range(1, 41)
    ]
    write_topic(storage, ALICE, "t-a00000000001", [S(1, turns)], "Кав'ярня")
    settings = load_settings(
        {
            **os.environ,
            "THINKHOW_LOCAL": "false",
            "THINKHOW_USERS_BUCKET": "-",
            "THINKHOW_SYSTEM_BUCKET": "-",
            "THINKHOW_OWNER_EMAIL": "-",
        }
    )
    assert settings.model == "gemini-4-argon" and settings.location == "eu"
    llm = make_llm(settings, script=lambda *_: "")
    report = analyze(storage, llm, NOW)
    assert report == AnalyzeReport(written=1, skipped=0, failed=0)
    raw = storage.read("system", range_path(ALICE, "t-a00000000001", 1, 40))
    assert raw is not None
    obs = Observation.model_validate_json(raw)
    assert (obs.first_turn, obs.last_turn) == (1, 40)
    assert obs.turn in set(range(1, 41))
    assert obs.link == f"/topics/{ALICE}/t-a00000000001#t{obs.turn}"
    assert obs.finding.strip() != ""
