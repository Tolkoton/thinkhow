"""Contract tests of skel-facilitation: `respond` (slice tester; written from the contract, not the code)."""

import json

import pytest
from pydantic import ValidationError
from skelf_fakes import (
    ADD,
    ALPHA,
    HISTORY,
    MEMORY,
    PROBLEM_MAP,
    ScenarioLlm,
    answer,
    answer_reply_last,
    collect,
    context,
    knowledge,
    update_only,
)

from thinkhow.facilitation import FacilitationError, FacilitatorUpdate, ReplyDelta, respond
from thinkhow.knowledge import card_prompt
from thinkhow.platform import llm as pl

# The facilitator rules, written out by hand from the sealed contract of facilitator-free-mode
# («Seam (contract)», the fenced new text of rules.md; task 301), which replaced the PoC 101 text this slice
# started from. They keep the contract's two replacements (Q5): «i3» and «t<номер з рамки репліки>».
RULES = "\n".join(
    [
        "Ти — фасилітатор ThinkHow: ведеш людину по обраній нею моделі мислення, щоб вона сама дійшла",
        "до ясності. Правила:",
        "- Без готових відповідей. Не кажи людині, що робити, не обирай "
        "і не оцінюй варіанти за неї, не давай порад.",
        "  Можна віддзеркалити сказане, коротко підсумувати, "
        "запропонувати гіпотезу як питання, коли картка це дозволяє.",
        "  Якщо людина просить прямо сказати, що робити, — "
        "тепло поясни, що рішення її, і поверни їй питання.",
        "  Якщо людина питає, як щось дізнатися чи оцінити, — "
        "запропонуй один-два конкретні способи як пропозицію",
        "  («можна оцінити так: …; спробуємо?»); самі оцінки й вибір лишаються за нею.",
        "- Одне питання за раз: у полі reply рівно одне питання до людини.",
        "- Відповідай коротко: два-чотири речення. Не закінчуй "
        "відповідь вибором «як ви хочете продовжити: … чи …?».",
        "- Відповідай мовою останньої репліки людини (Знання нижче — українською, це не мова відповіді).",
        "- Веди по фазах картки. current_phase_id — фаза, на якій розмова стоїть після твоєї відповіді;",
        "  phase_exit_met — чи виконано критерій виходу цієї фази; коли виконано — переходь до наступної.",
        "- Якщо картка не підходить (немає того, що їй потрібно на "
        "вході, або це її «Не той випадок») — вільний режим:",
        "  current_phase_id = null, phase_exit_met = false. У вільному "
        "режимі допомагай людині думати загальними кроками:",
        "  уточнити ціль → зібрати варіанти → назвати її критерії → "
        "порівняти → вибрати; одне питання за раз.",
        "  Що цей підхід зараз не підходить, скажи людині один раз, "
        "простими словами, у першій відповіді вільного режиму.",
        "  Якщо в рамці репліки стоїть рядок «[Стан] Вільний режим уже "
        "триває…» — людина це вже чула: не кажи цього знову,",
        "  просто веди далі. Коли в людини з'явився план, який варто перевірити, — повернись до фаз картки.",
        "- Пастка картки «Не той випадок» означає вільний режим: слів "
        "«час змінити метод» людині не кажи; що підхід не",
        "  підходить — лише один раз, за правилом вільного режиму вище.",
        "- Якщо картку пройдено — коротко підсумуй і спитай, що людина хоче робити далі.",
        "- Назва картки, назви методів і розділ «Добре поєднується» — "
        "для тебе, не для людини: не називай їх у reply.",
        "- У підсумках і в карті — лише те, що сказала людина. Твої "
        "приклади, гіпотези й варіанти не стають її критеріями",
        "  чи словами, доки вона сама їх не назве. Не вичитуй емоцій зі "
        "зворотів мови («боюсь, що…» часто означає «мабуть»).",
        "- map_updates — зміни карти проблеми, які випливають з "
        "останньої репліки людини (може бути порожнім).",
        "  id нового пункту — новий, напр. «i3»; update і remove — за "
        "наявним id; turn — «t<номер з рамки репліки>».",
        "- Не вигадуй фактів про людину; не став діагнозів.",
    ]
)

RETRY_ASK = "Поверни лише оновлення до своєї відповіді вище: фаза, вихід, зміни карти."
REPLY = "Уявіть: минув рік, і кав'ярня закрилася. Що сталося?"


def test_unknown_card_raises_value_error_before_any_model_call() -> None:
    fake = ScenarioLlm(deltas=["x"], done_raw=answer("x", "a_one"))
    items, exc = collect(lambda: respond(context(card_id="nope"), knowledge(), fake))
    assert isinstance(exc, ValueError)
    assert items == []
    assert fake.stream_calls == [] and fake.generate_calls == []


def test_system_instruction_is_poc_rules_then_card_then_all_memory() -> None:
    fake = ScenarioLlm(deltas=[REPLY], done_raw=answer(REPLY, "a_one"))
    collect(lambda: respond(context(), knowledge(), fake))
    system = fake.stream_calls[0].system
    rules_at = system.find(RULES)
    assert rules_at != -1, "the PoC rules (with the two replacements) are not in the instruction verbatim"
    card_head = system.find("# Картка", rules_at + len(RULES))
    assert card_head != -1
    card_at = system.find(card_prompt(ALPHA), card_head)
    assert card_at != -1
    memory_head = system.find("# Пам'ять досвіду", card_at + len(card_prompt(ALPHA)))
    assert memory_head != -1
    memory = system[memory_head:]
    lines = memory.splitlines()
    # every record, the one whose cards do not name this card included (no filter by card)
    for rec in MEMORY:
        assert f"### {rec.id} — {rec.title}" in lines
        assert f"Що помітили: {rec.noticed}" in lines
        assert f"Що робити: {rec.do}" in lines
        assert f"Підстава: {rec.basis}" in lines
    cards_lines = [line for line in lines if line.startswith("Картки:")]
    assert len(cards_lines) == 2
    assert "alpha" in cards_lines[0] and "beta" in cards_lines[0]
    assert cards_lines[0].index("alpha") < cards_lines[0].index(",") < cards_lines[0].index("beta")
    assert "gamma" in cards_lines[1]
    assert "s2#" not in system and "«t3»" not in system


def test_empty_memory_is_written_as_still_empty() -> None:
    fake = ScenarioLlm(deltas=[REPLY], done_raw=answer(REPLY, "a_one"))
    collect(lambda: respond(context(), knowledge(memory=[]), fake))
    system = fake.stream_calls[0].system
    memory_head = system.find("# Пам'ять досвіду")
    assert memory_head != -1
    assert "(поки порожня)" in system[memory_head:]


def test_contents_are_history_as_llm_turns_plus_one_framed_current_turn() -> None:
    fake = ScenarioLlm(deltas=[REPLY], done_raw=answer(REPLY, "a_one"))
    collect(lambda: respond(context(turn_no=3, text="За пів року, біля університету."), knowledge(), fake))
    contents = fake.stream_calls[0].contents
    assert contents[:-1] == [
        pl.Turn(role="user", text="Хочу відкрити кав'ярню."),
        pl.Turn(role="model", text="Який у вас план і за який строк?"),
    ]
    assert len(contents) == len(HISTORY) + 1
    last = contents[-1]
    assert type(last) is pl.Turn and last.role == "user"
    head = "[Карта проблеми зараз]\n"
    tail = "\n\n[Репліка людини #3]\nЗа пів року, біля університету."
    assert last.text.startswith(head)
    assert last.text.endswith(tail)
    map_json = last.text[len(head) : len(last.text) - len(tail)]
    assert json.loads(map_json) == {
        "items": [{"id": "i1", "type": "plan", "text": "кав'ярня біля університету", "turn": "t1"}],
        "phase_id": "a_one",
        "last_turn": 1,
    }
    assert PROBLEM_MAP.phase_id == "a_one"


def test_stream_schema_has_reply_first_and_only_the_cards_phases() -> None:
    fake = ScenarioLlm(deltas=[REPLY], done_raw=answer(REPLY, "a_one"))
    collect(lambda: respond(context(card_id="alpha"), knowledge(), fake))
    schema = fake.stream_calls[0].schema
    assert list(schema.model_fields)[0] == "reply"
    assert set(schema.model_fields) == {"reply", "current_phase_id", "phase_exit_met", "map_updates"}
    for phase in ("a_one", "a_two", "a_three"):
        schema.model_validate_json(answer("Що сталося?", phase))
    for foreign in ("b_one", "phase_1_time_travel", ""):
        with pytest.raises(ValidationError):
            schema.model_validate_json(answer("Що сталося?", foreign))


def test_stream_call_carries_the_knowledge_rev_pair() -> None:
    fake = ScenarioLlm(deltas=[REPLY], done_raw=answer(REPLY, "a_one"))
    collect(lambda: respond(context(), knowledge(), fake))
    assert len(fake.stream_calls) == 1
    assert fake.stream_calls[0].rev == pl.KnowledgeRev(rev=3, n=7)


def test_valid_answer_with_deltas_passes_them_on_then_one_update() -> None:
    fake = ScenarioLlm(
        deltas=["Уявіть: минув рік, ", "і кав'ярня закрилася. ", "Що сталося?"],
        done_raw=answer(REPLY, "a_two", True, [ADD]),
    )
    items, exc = collect(lambda: respond(context(), knowledge(), fake))
    assert exc is None
    assert items[:3] == [
        ReplyDelta(text="Уявіть: минув рік, "),
        ReplyDelta(text="і кав'ярня закрилася. "),
        ReplyDelta(text="Що сталося?"),
    ]
    assert len(items) == 4
    update = items[3]
    assert type(update) is FacilitatorUpdate
    assert update.model_dump() == {
        "reply": REPLY,
        "current_phase_id": "a_two",
        "phase_exit_met": True,
        "map_updates": [ADD],
    }
    assert fake.generate_calls == []


def test_valid_answer_with_reply_not_first_yields_one_delta_then_update() -> None:
    fake = ScenarioLlm(deltas=[], done_raw=answer_reply_last(REPLY, "a_one"))
    items, exc = collect(lambda: respond(context(), knowledge(), fake))
    assert exc is None
    assert len(items) == 2
    assert items[0] == ReplyDelta(text=REPLY)
    assert type(items[1]) is FacilitatorUpdate
    assert items[1].reply == REPLY and items[1].current_phase_id == "a_one"
    assert fake.generate_calls == []


def test_invalid_update_after_shown_text_retries_only_the_update() -> None:
    shown = ["Уявіть провал. ", "Що сталося першим?"]
    fake = ScenarioLlm(
        deltas=list(shown),
        # the model named a phase of another card
        done_raw=answer("Уявіть провал. Що сталося першим?", "b_one"),
        generate=[update_only("a_three", False, [ADD])],
    )
    items, exc = collect(lambda: respond(context(), knowledge(), fake))
    assert exc is None
    assert items[:2] == [ReplyDelta(text="Уявіть провал. "), ReplyDelta(text="Що сталося першим?")]
    assert len(items) == 3, "the shown text is not repeated and there is exactly one update"
    assert len(fake.stream_calls) == 1
    assert len(fake.generate_calls) == 1
    retry, first = fake.generate_calls[0], fake.stream_calls[0]
    assert retry.system == first.system
    assert retry.contents == [
        *first.contents,
        pl.Turn(role="model", text="Уявіть провал. Що сталося першим?"),
        pl.Turn(role="user", text=RETRY_ASK),
    ]
    assert "reply" not in retry.schema.model_fields
    update = items[2]
    assert type(update) is FacilitatorUpdate
    assert update.model_dump() == {
        "reply": "Уявіть провал. Що сталося першим?",
        "current_phase_id": "a_three",
        "phase_exit_met": False,
        "map_updates": [ADD],
    }


def test_broken_map_updates_after_shown_text_also_retry_the_update() -> None:
    bad = dict(ADD, type="not_an_item_type")
    fake = ScenarioLlm(
        deltas=["Що сталося?"],
        done_raw=answer("Що сталося?", "a_one", False, [bad]),
        generate=[update_only("a_one")],
    )
    items, exc = collect(lambda: respond(context(), knowledge(), fake))
    assert exc is None
    assert len(fake.generate_calls) == 1
    assert "reply" not in fake.generate_calls[0].schema.model_fields
    assert items == [
        ReplyDelta(text="Що сталося?"),
        FacilitatorUpdate(
            reply="Що сталося?", current_phase_id="a_one", phase_exit_met=False, map_updates=[]
        ),
    ]


def test_retry_invalid_after_shown_text_raises_facilitation_error_after_the_same_deltas() -> None:
    fake = ScenarioLlm(
        deltas=["Уявіть провал. ", "Що сталося?"],
        done_raw=answer("Уявіть провал. Що сталося?", "b_one"),
        generate=[update_only("b_two")],
    )
    items, exc = collect(lambda: respond(context(), knowledge(), fake))
    assert isinstance(exc, FacilitationError)
    assert items == [ReplyDelta(text="Уявіть провал. "), ReplyDelta(text="Що сталося?")]
    assert len(fake.generate_calls) == 1


def test_invalid_answer_without_deltas_retries_the_full_answer() -> None:
    fake = ScenarioLlm(
        deltas=[],
        done_raw='{"current_phase_id": "a_one", "phase_exit_met": fal',  # truncated
        generate=[answer(REPLY, "a_two", True)],
    )
    items, exc = collect(lambda: respond(context(), knowledge(), fake))
    assert exc is None
    assert len(fake.generate_calls) == 1
    schema = fake.generate_calls[0].schema
    assert "reply" in schema.model_fields
    with pytest.raises(ValidationError):
        schema.model_validate_json(answer(REPLY, "b_one"))
    assert items == [
        ReplyDelta(text=REPLY),
        FacilitatorUpdate(reply=REPLY, current_phase_id="a_two", phase_exit_met=True, map_updates=[]),
    ]
    assert type(items[1]) is FacilitatorUpdate


def test_full_retry_invalid_raises_facilitation_error_with_nothing_shown() -> None:
    fake = ScenarioLlm(
        deltas=[],
        done_raw=answer_reply_last(REPLY, "b_one"),
        generate=[answer(REPLY, "b_two")],
    )
    items, exc = collect(lambda: respond(context(), knowledge(), fake))
    assert isinstance(exc, FacilitationError)
    assert items == []


def test_llm_unavailable_passes_through_unchanged() -> None:
    boom = pl.LlmUnavailable("stream broke")
    fake = ScenarioLlm(deltas=["Уявіть ", boom], done_raw=answer(REPLY, "a_one"))
    items, exc = collect(lambda: respond(context(), knowledge(), fake))
    assert exc is boom
    assert items == [ReplyDelta(text="Уявіть ")]


def test_everything_yielded_is_a_facilitation_types_instance() -> None:
    fake = ScenarioLlm(
        deltas=["Що ", "сталося?"],
        done_raw=answer("Що сталося?", "b_one"),
        generate=[update_only("a_one")],
    )
    items, exc = collect(lambda: respond(context(), knowledge(), fake))
    assert exc is None
    assert [type(i) for i in items] == [ReplyDelta, ReplyDelta, FacilitatorUpdate]
    fake2 = ScenarioLlm(deltas=["Що?"], done_raw=answer("Що?", "a_one"))
    items2, exc2 = collect(lambda: respond(context(), knowledge(), fake2))
    assert exc2 is None
    assert [type(i) for i in items2] == [ReplyDelta, FacilitatorUpdate]


def test_facilitator_update_reply_must_not_be_empty() -> None:
    with pytest.raises(ValidationError):
        FacilitatorUpdate(reply="", current_phase_id="a_one", phase_exit_met=False, map_updates=[])
