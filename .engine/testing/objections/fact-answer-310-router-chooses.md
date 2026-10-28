# Objection package — fact-answer, round 1 (task 310: the router chooses one method itself)

The owner's decision of 2026-10-27 (task `tasks/doing/310-router-leads-one-method.md`, «Рішення власника» and
«Що зробити»): the router no longer offers the person 2–3 ways to choose from; it chooses one card itself and the
facilitator leads by it at once. «Це замінює рішення задачі 302 «вибір способу — у розмові»: тепер вибирає система.»
So `router.md` no longer describes an `"offer"` action at all (the schema still reads an offer, for the routing state
written before; `tests/contract/router/test_rt_310_leads_one_method.py` holds that the rules never mention `"offer"`).

The contract of fact-answer quotes the router rules' `answer` item verbatim, and its last sentence names that old action:

> Якщо за питанням стоїть рішення, яке треба продумати, — не "answer", а "offer" чи "ask".

(`.engine/slices/fact-answer.md` line 52.) After task 310 this sentence names an action the router no longer has. The
item's meaning — a question behind which stands a decision to think through is not `answer` but leading by a way of
thinking — stays; only the name of the action changes: the router's way to start leading is now `"choose"`. The new
`router.md` text of the item (`src/thinkhow/facilitation/router.md`):

```
  - "answer" — коли людина прямо питає факт про світ, який можна знайти (ціна, строк, правило, як це зазвичай
    роблять), а способу думати ще не обрано, і сама відповідь фактом — те, чого вона хоче. reply — null; card_id —
    null. Якщо за питанням стоїть рішення, яке треба продумати, — не "answer", а "choose". Так само "answer" —
    …
```

## Disputed test

1. `tests/contract/fact_answer/test_fa_route.py::test_seam5_router_rules_have_the_answer_item_after_ask_and_before_why`
   — expects `fa_fakes.ROUTER_ANSWER_ITEM`, whose last sentence ends `— не "answer", а "offer" чи "ask".`
   Contract line: `.engine/slices/fact-answer.md` 49–53 (the item), superseded in its last sentence by the owner's
   decision of task 310. Asked: the expected item ends `— не "answer", а "choose".`; the position check (after
   `- "ask" — `, before `- why відповіді`) stays as it is — the new text keeps that order.

The same constant is read by research-deep's sealed
`tests/contract/research_deep/test_rdp_route.py::test_router_md_answer_item_ends_with_the_sentence_about_agreeing_to_deep_research`
(`fa.ROUTER_ANSWER_ITEM + " " + ROUTER_DEEP_SENTENCE`); with the constant corrected it passes unchanged — no
change asked in research-deep's files.

Not disputed: `test_seam5_router_rules_say_ask_does_not_ask_facts_of_the_world_among_the_rules` — the line
`- В "ask" не питай людину фактів про світ, які можна знайти: для них є "answer".` stands in «Правила» verbatim.

Reproduce: `uv run pytest -q tests/contract/fact_answer/test_fa_route.py tests/contract/research_deep/test_rdp_route.py`
— 2 failed now (both on that sentence), the rest passes.
