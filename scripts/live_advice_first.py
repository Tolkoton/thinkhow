"""Live check of task 715: a person asks for advice in the topic's first turn, before any method is chosen.

Each opener is one turn through the product's `workspace.reply` (model `gemini-4-argon`, Vertex `eu`), on
the conversation stand of task 302 (`card_conversations.py`). Whether the first reply gives advice (what
the system would choose, why, what argues against, the choice hers) or pushes the request back is read by a
person from the record, not judged by code.

Run: `PYTHONPATH=src uv run python scripts/live_advice_first.py --label <text>`; the records go to
.engine/artifacts/advice-first/<time>-<label>/<id>.md.
"""

import argparse
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from live_router_leads import cc

from thinkhow.knowledge import current, seed
from thinkhow.platform import llm as model
from thinkhow.platform.storage import LocalStorage

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".engine" / "artifacts" / "advice-first"
OPENERS = {
    "jobs": "Маю дві пропозиції роботи: одна в стартапі, зарплата більша, але ризиковано; "
    "друга в банку, стабільно, але нудно. Порадь, що б ти обрав?",
    "move": "Що б ти обрав на моєму місці — переїзд до Львова чи лишитися в Києві з батьками?",
    "course": "Хочу запустити невеликий онлайн-курс з кераміки, але не знаю, з чого почати. "
    "Просто скажи, що мені робити.",
    "price": "Я продаю свічки ручної роботи по 300 гривень і думаю підняти ціну до 450. "
    "Порадь — піднімати чи ні?",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="прогін")
    args = parser.parse_args()
    llm = model.make_llm(cc._settings("gemini-4-argon"), lambda *_: "")
    storage = LocalStorage(Path(tempfile.mkdtemp(prefix="thinkhow-k-")))
    seed(storage, ROOT / "cards")
    knowledge = current(storage)
    folder = OUT / f"{datetime.now(UTC).strftime('%Y-%m-%dT%H%M%SZ')}-{args.label}"
    folder.mkdir(parents=True)

    def one(name: str) -> None:
        opener = OPENERS[name]
        conv = cc._drive(
            knowledge, llm, llm, cc._topic(name), opener, opener, cc.HOW_FOR_CARD, None, 1, False
        )
        conv.name = name
        cc.write(folder, conv, f"Перша репліка з проханням поради — `{name}` ({args.label})")
        print(name, flush=True)

    with ThreadPoolExecutor(len(OPENERS)) as pool:
        list(pool.map(one, OPENERS))
    print(folder)


if __name__ == "__main__":
    main()
