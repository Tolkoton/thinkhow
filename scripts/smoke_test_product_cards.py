"""Smoke of product-cards (task 307, S1 — the tracer): Knowledge seeded from the 25 cards of `cards/` →
the router on the real model (`gemini-4-argon`, Vertex `eu`) → its answer to turn #1 of the owner's topic
t-84d1517cb1c1.

Run on the server with ADC: `PYTHONPATH=src uv run python scripts/smoke_test_product_cards.py`. Exit 0 only
when the router offers 2–3 ways, every one a card of `cards/`; any other action, an empty list or an unknown
id → exit 1. One repeat after a non-offer answer is allowed, and the first answer stays in the artifact (slice
contract Q7). Whether a new card is offered is printed, not judged: that is S2's measure. Output:
`.engine/artifacts/spikes/product-cards-router-live-<time>.txt`.
"""

import json
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from thinkhow.facilitation import RouterAnswer, route  # noqa: E402
from thinkhow.knowledge import CurrentKnowledge, current, seed  # noqa: E402
from thinkhow.platform import llm as model  # noqa: E402
from thinkhow.platform import log  # noqa: E402
from thinkhow.platform.storage import LocalStorage  # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))
from router_eval import context_of, product_settings  # noqa: E402

NEW = ["customer-interviews", "demand-test", "positioning", "offer-design", "value-pricing",
       "traction-channels", "unit-economics"]  # fmt: skip
# Turn #1 of t-84d1517cb1c1, verbatim:
# .engine/artifacts/advice-live/2026-10-25T174143Z-t-84d1517cb1c1/conversation.md
OWNER_TURN_1 = (
    "Так, в мене є така думка зробити для керівників невеликих підприємств і фрілансерів типу "
    "персонального асистента на OpenCore. І, е-е ну, ясно, що типу шляхом курсів помогти його підняти, "
    "настроїти. Ну, таке, що типу ми ведемо тебе за ручку, ти собі то все настроюєш. Е-е і додати в "
    "пакет якийсь там, ну, наприклад, цього думального асистента, додати додати всі мої фреймворки по "
    "гормоці, по маркетингу може, інформація, щоб вони могли робити собі сайти, ну, таке всяке. Е-е як "
    "це продати?"
)
OUT = ROOT / ".engine" / "artifacts" / "spikes"


def knowledge() -> CurrentKnowledge:
    storage = LocalStorage(Path(tempfile.mkdtemp(prefix="thinkhow-product-cards-")))
    seed(storage, ROOT / "cards")
    return current(storage)


def ask(k: CurrentKnowledge, llm: model.Llm) -> RouterAnswer:
    return route(context_of({"kind": "positive", "text": OWNER_TURN_1}), k, llm)


def passed(answer: RouterAnswer, ids: set[str]) -> bool:
    found = [c.card_id for c in answer.candidates]
    return answer.action == "offer" and 2 <= len(found) <= 3 and all(cid in ids for cid in found)


def describe(answer: RouterAnswer) -> list[str]:
    lines = [f"дія: {answer.action}"]
    lines += [f"- {c.card_id}: {c.why}" for c in answer.candidates]
    lines.append(
        f"нові картки серед кандидатів: {[c.card_id for c in answer.candidates if c.card_id in NEW]}"
    )
    lines += ["текст роутера:", answer.reply or "(немає)"]
    return lines


def main() -> int:
    k = knowledge()
    settings = product_settings()
    calls: list[str] = []
    original = model.log_event

    def recording(event: str, **fields: Any) -> None:
        line = {"severity": "INFO", **fields, "event": event, "request_id": log.request_id.get()}
        calls.append(json.dumps(line, ensure_ascii=False, default=str))

    model.log_event = recording
    lines = [
        "# Smoke product-cards — роутер на першій репліці t-84d1517cb1c1",
        f"модель: {settings.model}; регіон: {settings.location}",
        f"Знання: ревізія {k.rev}, карток {len(k.cards)}; нові: {[cid for cid in NEW if cid in k.cards]}",
        "",
    ]
    try:
        llm = model.make_llm(settings, lambda *_: "")
        answer = ask(k, llm)
        lines += ["## Відповідь 1", *describe(answer), ""]
        if not passed(answer, set(k.cards)):
            answer = ask(k, llm)
            lines += ["## Відповідь 2 (повтор після не-offer, Q7)", *describe(answer), ""]
    finally:
        model.log_event = original
    ok = len(k.cards) == 25 and all(cid in k.cards for cid in NEW) and passed(answer, set(k.cards))
    lines += [
        "## llm_call",
        *[c for c in calls if '"llm_call"' in c],
        "",
        f"результат: {'PASS' if ok else 'FAIL'}",
    ]
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H%M%SZ")
    path = OUT / f"product-cards-router-live-{stamp}.txt"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nзаписано: {path.relative_to(ROOT)}")
    print("Перевірте: дія `offer`, 2–3 кандидати з `cards/`, рядок llm_call з моделлю gemini-4-argon.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
