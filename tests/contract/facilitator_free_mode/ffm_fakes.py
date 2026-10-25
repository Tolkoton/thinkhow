"""Helpers for the facilitator-free-mode contract tests (slice tester; from the contract, not the code).

- ScenarioLlm: a fake of the `platform.llm.Llm` protocol. `stream_json` yields the planned deltas, then one
  `Done` with the planned raw JSON; `generate_json` validates the planned raw JSON by the schema it was given.
- card / knowledge / context: valid inputs built by hand.
- RULES: the new text of `facilitation/rules.md`, word for word from the contract «Seam».
- STATE_LINE: the state line of the frame, word for word from the contract «Seam».
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from thinkhow.facilitation.types import FacilitationContext, MapItem, ProblemMap, Turn
from thinkhow.knowledge import Card, CurrentKnowledge, MemoryRecord
from thinkhow.platform import llm as pl

# The rules text of the contract «Seam», copied line by line from the sealed contract.
RULES = "\n".join(
    [
        "Ти — фасилітатор ThinkHow: ведеш людину по обраній нею моделі мислення, щоб вона сама дійшла",
        "до ясності. Правила:",
        "- Без готових відповідей. Сам, без прохання, не кажи людині, що"
        " робити, не обирай і не оцінюй варіанти за неї —",
        "  веди питаннями. Можна віддзеркалити сказане, коротко"
        " підсумувати, запропонувати гіпотезу як питання, коли картка",
        "  це дозволяє.",
        "- Порада — коли людина просить або застрягла. Просить — каже"
        " запропонувати, обрати, порадити, сказати, що робити, чи",
        "  що обрав би ти. Застрягла — двічі поспіль не може відповісти на"
        " твоє питання («не знаю», «звідки мені знати») або",
        "  сама каже, що не просувається. Тоді не повертай їй питання і не"
        " відмовляй: дай свою пораду — що обрав би ти, чому",
        "  (спирайся на її пункти з карти і на знайдені факти, коли вони"
        " є, і скажи, як факт стосується її пункту), і що",
        "  говорить проти цього вибору. Скажи, що вибір її, і постав одне"
        " питання. Порада — твоя думка, не її слова: у карту",
        "  її не пиши, доки людина сама її не прийме.",
        "- Якщо людина питає, як щось дізнатися чи оцінити, —"
        " запропонуй один-два конкретні способи як пропозицію",
        "  («можна оцінити так: …; спробуємо?»); самі оцінки й вибір лишаються за нею.",
        "- Одне питання за раз: у полі reply рівно одне питання до людини.",
        "- Відповідай коротко: два-чотири речення (пояснення щойно обраного методу — до шести). Не"
        " закінчуй відповідь вибором",
        "  «як ви хочете продовжити: … чи …?».",
        "- Відповідай мовою останньої репліки людини (Знання нижче — українською, це не мова відповіді).",
        "- Веди по фазах картки. current_phase_id — фаза, на якій розмова стоїть після твоєї відповіді;",
        "  phase_exit_met — чи виконано критерій виходу цієї фази; коли виконано — переходь до наступної.",
        "- Якщо картка не підходить (немає того, що їй потрібно на вході, або це її «Не той"
        " випадок») — вільний режим:",
        "  current_phase_id = null, phase_exit_met = false. У вільному режимі допомагай людині"
        " думати загальними кроками:",
        "  уточнити ціль → зібрати варіанти → назвати її критерії → порівняти → вибрати; одне"
        " питання за раз.",
        "  Що цей підхід зараз не підходить, скажи людині один раз, простими словами, у першій"
        " відповіді вільного режиму.",
        "  Якщо в рамці репліки стоїть рядок «[Стан] Вільний режим уже триває…» — людина це вже"
        " чула: не кажи цього знову,",
        "  просто веди далі. Коли в людини з'явився план, який варто перевірити, — повернись до фаз картки.",
        "- Пастка картки «Не той випадок» означає вільний режим: слів «час змінити метод» людині"
        " не кажи; що підхід не",
        "  підходить — лише один раз, за правилом вільного режиму вище.",
        "- Якщо картку пройдено — коротко підсумуй і спитай, що людина хоче робити далі.",
        "- Називай метод його назвою (рядок «Метод.» картки, інакше — її заголовок) і пояснюй людині, як"
        " ведеш. Коли в рамці",
        "  репліки стоїть рядок «[Стан] Метод щойно обрано» — спершу коротко скажи, що це за метод,"
        " звідки він, з яких фаз",
        "  складається і навіщо він саме тут, у її ситуації; тоді постав перше питання. Коли переходиш"
        " до нової фази — одним",
        "  реченням скажи, що ми зараз робимо і чому. Про метод — лише те, що є в картці: не вигадуй"
        " авторів, років і",
        "  досліджень. Розділ «Добре поєднується» — для тебе, не для людини.",
        "- У підсумках і в карті — лише те, що сказала людина. Твої приклади, гіпотези й варіанти"
        " не стають її критеріями",
        "  чи словами, доки вона сама їх не назве. Не вичитуй емоцій зі зворотів мови («боюсь,"
        " що…» часто означає «мабуть»).",
        "- map_updates — зміни карти проблеми, які випливають з останньої репліки людини (може"
        " бути порожнім).",
        "  id нового пункту — новий, напр. «i3»; update і remove — за наявним id; turn — «t<номер"
        " з рамки репліки>».",
        "- Не вигадуй фактів про людину; не став діагнозів.",
    ]
)

STATE_LINE = "[Стан] Вільний режим уже триває: людина чула, що картка не підходить. Не кажи цього знову."

Step = str | BaseException


@dataclass
class Call:
    system: str
    contents: list[pl.Turn]
    schema: type[BaseModel]
    rev: pl.KnowledgeRev | None


@dataclass
class ScenarioLlm:
    deltas: list[Step] = field(default_factory=list)
    done_raw: str = ""
    generate: list[Step] = field(default_factory=list)
    stream_calls: list[Call] = field(default_factory=list)
    generate_calls: list[Call] = field(default_factory=list)

    def stream_json(
        self, system: str, contents: Sequence[pl.Turn], schema: type[BaseModel], rev: pl.KnowledgeRev | None
    ) -> Iterator[pl.ReplyDelta | pl.Done]:
        self.stream_calls.append(Call(system, list(contents), schema, rev))
        return self._stream()

    def _stream(self) -> Iterator[pl.ReplyDelta | pl.Done]:
        for step in self.deltas:
            if isinstance(step, BaseException):
                raise step
            yield pl.ReplyDelta(text=step)
        yield pl.Done(
            raw_json=self.done_raw, usage=pl.Usage(prompt_tokens=10, output_tokens=5, thought_tokens=0)
        )

    def generate_json(
        self, system: str, contents: Sequence[pl.Turn], schema: type[Any], rev: pl.KnowledgeRev | None
    ) -> Any:
        self.generate_calls.append(Call(system, list(contents), schema, rev))
        if not self.generate:
            raise AssertionError("generate_json was called more times than the scenario planned")
        step = self.generate.pop(0)
        if isinstance(step, BaseException):
            raise step
        return schema.model_validate_json(step)


def phase_dict(pid: str) -> dict[str, Any]:
    tag = pid.upper()
    return {
        "id": pid,
        "title": f"Фаза {tag}",
        "goal": f"мета фази {tag}",
        "how": [f"як фази {tag}"],
        "exit": f"вихід фази {tag}",
    }


def card(cid: str, phase_ids: Iterable[str]) -> Card:
    return Card.model_validate(
        {
            "id": cid,
            "title": f"Картка {cid}",
            "router": {
                "needs": f"роутер-потреба {cid}",
                "when_yes": [f"так {cid}"],
                "when_no": [f"ні {cid}"],
                "signals": [f"сигнал {cid}"],
            },
            "facilitator": {
                "purpose": f"навіщо {cid}",
                "stance": f"позиція {cid}",
                "needs": f"на вході {cid}",
                "phases": [phase_dict(p) for p in phase_ids],
                "ending": f"кінець {cid}",
                "traps": [{"name": "Не той випадок", "text": f"текст пастки {cid}"}],
                "pairs_well": f"пара {cid}",
            },
        }
    )


ALPHA = card("alpha", ["a_one", "a_two", "a_three"])
BETA = card("beta", ["b_one", "b_two"])
SOLO = card("solo", ["s_only"])

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


def knowledge(
    cards: Iterable[Card] = (ALPHA, BETA, SOLO), memory: list[MemoryRecord] | None = None
) -> CurrentKnowledge:
    return CurrentKnowledge(
        rev=3, n=7, cards={c.id: c for c in cards}, memory=list(MEMORY if memory is None else memory)
    )


HISTORY = [
    Turn(role="user", text="Хочу заробити більше."),
    Turn(role="model", text="Яка у вас ціль?"),
]

ITEM = MapItem(id="i1", type="goal", text="заробити більше", turn="t1")


def context(
    card_id: str = "alpha",
    problem_map: ProblemMap | None = None,
    turn_no: int = 3,
    text: str = "Не знаю, з чого почати.",
    history: list[Turn] | None = None,
    language: str | None = None,
) -> FacilitationContext:
    return FacilitationContext(
        card_id=card_id,
        history=list(HISTORY if history is None else history),
        problem_map=problem_map
        if problem_map is not None
        else ProblemMap(items=[ITEM], phase_id=None, last_turn=1),
        turn_no=turn_no,
        text=text,
        language=language,
    )


def answer(reply: str, phase: str | None, exit_met: bool = False) -> str:
    """A full answer with `reply` first (as the model streams it)."""
    return json.dumps(
        {"reply": reply, "current_phase_id": phase, "phase_exit_met": exit_met, "map_updates": []},
        ensure_ascii=False,
    )


def answer_reply_last(reply: str, phase: str | None) -> str:
    """A full answer where `reply` is not the first field (no deltas come)."""
    return json.dumps(
        {"current_phase_id": phase, "phase_exit_met": False, "map_updates": [], "reply": reply},
        ensure_ascii=False,
    )


def update_only(phase: str | None) -> str:
    """The retry answer without `reply`."""
    return json.dumps(
        {"current_phase_id": phase, "phase_exit_met": False, "map_updates": []}, ensure_ascii=False
    )


def collect(start: Callable[[], Iterator[Any]]) -> tuple[list[Any], BaseException | None]:
    """Run `start()` and drain it; an exception raised by the call itself or while iterating ends it."""
    items: list[Any] = []
    try:
        for item in start():
            items.append(item)
    except NotImplementedError:
        raise
    except Exception as exc:
        return items, exc
    return items, None
