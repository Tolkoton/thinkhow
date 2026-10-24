"""Hand-built cards, memory and history for the router contract tests (slice tester; from the contract).

Uses only values that existed before the slice (Card, MemoryRecord, Turn, MapItem, ProblemMap), so the golden
sample of Seam 3 can be recorded from the code of commit 5d90360 with the very same inputs.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from thinkhow.facilitation.types import MapItem, ProblemMap, Turn
from thinkhow.knowledge import Card, MemoryRecord


def phase_dict(pid: str) -> dict[str, Any]:
    return {
        "id": pid,
        "title": f"Назва фази {pid}",
        "goal": f"мета фази {pid}",
        "how": [f"як іти фазою {pid}"],
        "exit": f"вихід фази {pid}",
    }


def card(cid: str, phase_ids: Iterable[str]) -> Card:
    return Card.model_validate(
        {
            "id": cid,
            "title": f"Заголовок {cid}",
            "router": {
                "needs": f"роутер-потреба {cid}",
                "when_yes": [f"коли так {cid}"],
                "when_no": [f"коли ні {cid}"],
                "signals": [f"сигнал {cid}"],
            },
            "facilitator": {
                "purpose": f"навіщо фасилітатору {cid}",
                "stance": f"позиція фасилітатора {cid}",
                "needs": f"на вході фасилітатора {cid}",
                "phases": [phase_dict(p) for p in phase_ids],
                "ending": f"кінець картки {cid}",
                "traps": [{"name": "Не той випадок", "text": f"текст пастки {cid}"}],
                "pairs_well": f"добре поєднується {cid}",
            },
        }
    )


ALPHA = card("alpha", ["a_one", "a_two", "a_three"])
BETA = card("beta", ["b_one", "b_two"])
GAMMA = card("gamma", ["g_only"])
PREMORTEM = card("pre-mortem", ["pm_one", "pm_two"])

MEMORY = [
    MemoryRecord(
        id="M-1",
        title="Перший досвід",
        cards=["alpha", "beta"],
        noticed="людина поспішає до висновку",
        do="повернути до фази",
        basis="3 сесії.",
    ),
]

HISTORY = [
    Turn(role="user", text="Хочу відкрити кав'ярню."),
    Turn(role="model", text="Що для вас тут найважливіше?"),
]

ITEM = MapItem(id="i1", type="goal", text="відкрити кав'ярню", turn="t1")


def problem_map(phase_id: str | None = None, last_turn: int = 2) -> ProblemMap:
    return ProblemMap(items=[ITEM], phase_id=phase_id, last_turn=last_turn)
