# Bug 004-first-reply-after-ask

type: bugfix
status: fixed

## 1. Record
- Symptom: a topic whose first reply is the router's ask (or a fact answer) never tells the person that the system's
  opinion can be asked; the card led on turn 3 gets no first-reply line either (overseer test gap, PASS of
  `-|310-router-leads-one-method|unit 1`, request `20261028T045936Z-cd789a`; board task 728).
- Expected: the first reply of a topic says, in one sentence, that the system's opinion can be asked any time
  («що б ти обрав?») or another way asked for.
- Where the expected is written: `tasks/done/310-router-leads-one-method/task.md:24` — «**Варіант А**: у першій
  відповіді теми — що будь-коли можна спитати думку системи («що б ти обрав?»)»; the owner took variant A (same file,
  line 15: «а так варіант А, я думаю.»). `.engine/slices/one-conversation.md:78` (Q4): the line is «лише на першій
  відповіді теми».
- Actual: only the facilitator's frame can carry `FIRST_REPLY_LINE` (`src/thinkhow/facilitation/respond.py:165`), and
  only while the history has no model turn. The router's ask and the fact answer have their own frames and
  instructions with neither the line nor a rule for it; after them the history has a model turn, so no reply of the
  topic ever carries it.
- Where it was seen: code reading by the overseer; reproduced with the test doubles of `tests/contract/router/`.

## 2. Reproduction

### Attempt 1
- Command:
  ```
  PYTHONPATH=src:tests/contract/router uv run python -c '<respond() on turn 1 of an empty topic: once with the router
  answering ask(), once with router_raw("answer") and a fact stream; print whether FIRST_REPLY_LINE is in the frame
  of that reply and whether router.md / answer.md name the line>'
  ```
- Output:
  ```
  ask on turn 1 — line in its frame: False | router rules name the line: False
  fact answer on turn 1 — line in its frame: False | answer rules name the line: False
  ```
  and `grep -rn "що б ти обрав\|думку" src/thinkhow/facilitation/*.md` → only `rules.md:35` (the facilitator's rules).
- Result: reproduced

## 3. Failing test
- Test: `tests/contract/router/test_rt_gap_first_reply_of_an_ask_or_answer.py` —
  `test_a_topic_opened_by_the_routers_ask_tells_the_opinion_can_be_asked_in_that_ask`,
  `test_a_topic_opened_by_a_fact_answer_tells_the_opinion_can_be_asked_in_that_answer` (through `respond`, the public
  function the app calls; turn 1, then a choose on turn 3 of the same topic), and
  `test_a_later_ask_carries_no_first_reply_line` (green before and after: the line stays on the first reply only),
  `test_the_line_itself_tells_what_to_say_before_the_question`.
- Corrected once, before the fix was final: the first version also asserted a rule for the line inside `router.md`
  and `answer.md`. Those texts are fixed byte for byte by sealed tests
  (`tests/contract/spoken_replies/test_sr_invariants.py::test_I1_without_the_flag_each_instruction_is_byte_equal_to_before`,
  `tests/router_unknown_fact/test_ruf_rule.py::test_the_rule_stands_right_after_the_ask_rule_under_the_rules_and_before_the_language_rule`
  and 8 more went red with the rule added), so the test tested where the instruction lives, not what the person is
  told. It now asserts that the line is in the first reply's frame and itself says what to tell
  (`«що б ти обрав?»`, «інший спосіб», «перед питанням»). Not weaker: both versions are red on `base_commit` for the
  same reason (no line in the frame).
- Command that runs it: `uv run pytest -q tests/contract/router/test_rt_gap_first_reply_of_an_ask_or_answer.py`
- It fails with: `AssertionError: the ask is the topic's first reply, its frame has no line` and
  `AssertionError: the fact answer is the topic's first reply, its frame has no line` (on `base_commit`: 3 failed,
  1 passed — the fourth test fails there too, on the old line «скажи про це за правилом вище», which names a rule
  the router and the fact answer do not have).
- Tests written first to pin the present behaviour around the code: none (`respond` reaches the code).

## 4. Cause
- Where it showed: `src/thinkhow/facilitation/respond.py:164-165` — `_state` decides «first» and is the only place
  the line is written.
- Why it happened: task 310 put variant A's promise on the card-led path alone (`respond._state` + `rules.md`), but the
  topic's first reply can come from two other writers that each build their own frame and instruction — the router's
  ask (`route._contents`, `router.md`) and the fact answer (`answer.answer_fact` → `settle.frame(ctx)` with no state,
  `answer.md`). Neither was given the line nor a rule, and once they have answered, the history has a model turn.
- Same places: `grep -n "def _contents\|frame(ctx" src/thinkhow/facilitation/*.py` and the writers of a reply in
  `converse.converse`: `route` (ask — fixed here), `answer_fact` (fixed here), `deep_answer` (a deep research asked
  for on the topic's very first turn: `deep.py` builds its text from the deep cycle, no frame state — a neighbour with
  the same cause; it did not fit — see section 5), `_router_reply` of an old `offer` (no longer produced since
  task 310 — not a writer of a new topic's first reply).

## 5. Fix
- What changed:
  - `src/thinkhow/facilitation/settle.py` — `FIRST_REPLY_LINE` moves here (the module all three writers already
    import; `route` cannot import `respond` without a cycle) and now says itself what to tell, before the question:
    the router's and the fact answer's instructions are sealed byte for byte and have no rule for it. For the
    facilitator it says the same as `rules.md:34-35`.
  - `src/thinkhow/facilitation/respond.py` — re-exports `FIRST_REPLY_LINE` (its public name stays where tests import
    it); `_state` unchanged.
  - `src/thinkhow/facilitation/route.py` — `_contents` puts the line before the person's turn while the history has
    no model turn.
  - `src/thinkhow/facilitation/answer.py` — `answer_fact` passes the same line to `frame` on the same condition.
  - Neighbour not fixed here: `deep_answer` on the topic's first turn — its report call is built from the findings
    alone, with no frame of the turn; the line would have to be carried into that call. Proposal
    `tasks/proposed/747-open-item-bug-004-deep-first-reply.md`.
  - `python3 .claude/hooks/complexity_budget.py check` → «Complexity budget: within budget … production: 0 new files,
    +13 lines, 0 new public symbols, 0 new abstractions, 0 new dependencies; tests: +80 lines».
- Nothing else: no tidying on the way, no renaming, no new helper for later.

## Complexity budget
base_commit: 48a1f574a9de405800be1f586ae0fc7595d3b613
max_new_files: 0
max_net_new_lines: 40
max_new_public_symbols: 0
max_new_abstractions: 0
max_new_dependencies: 0
justification: none

## 6. Proof

```
PROVED: tests/contract/router/test_rt_gap_first_reply_of_an_ask_or_answer.py fails on 48a1f57 and passes on the working tree; the failure shows «the ask is the topic's first reply, its frame has no line»
  command: uv run pytest -q tests/contract/router/test_rt_gap_first_reply_of_an_ask_or_answer.py
  the fix: .engine/PROGRESS.md, .engine/artifacts/conversation-loop/smoke.txt, .engine/bugs/004-first-reply-after-ask.md, src/thinkhow/facilitation/answer.py, src/thinkhow/facilitation/respond.py, src/thinkhow/facilitation/route.py, src/thinkhow/facilitation/settle.py
  before the fix: exit 1
    |         assert first.kind == "answer"
    |         (stream,) = llm.stream_calls
    | >       assert FIRST_REPLY_LINE in stream.frame, (
    |             "the fact answer is the topic's first reply, its frame has no line"
    |         )
    | E       AssertionError: the fact answer is the topic's first reply, its frame has no line
    | E       assert '[Стан] Перша відповідь у темі: скажи про це за правилом вище.' in '[Карта проблеми зараз]\n{"items":[{"id":"i1","type":"goal","text":"відкрити кав\'ярню","turn":"t1"}],"phase_id":null,"last_turn":2}\n\n[Репліка людини #1]\nБоюся, що не вийде.'
    | E        +  where '[Карта проблеми зараз]\n{"items":[{"id":"i1","type":"goal","text":"відкрити кав\'ярню","turn":"t1"}],"phase_id":null,"last_turn":2}\n\n[Репліка людини #1]\nБоюся, що не вийде.' = Call(kind='stream', system="Ти — ThinkHow. Людина прямо питає факт про світ. Знайди його в інтернеті й відповідай коро...ини #1]\nБоюся, що не вийде.')], schema=<class 'thinkhow.facilitation.types.FactAnswer'>, rev=KnowledgeRev(rev=3, n=7)).frame
    | 
    | tests/contract/router/test_rt_gap_first_reply_of_an_ask_or_answer.py:69: AssertionError
    | =========================== short test summary info ============================
    | FAILED tests/contract/router/test_rt_gap_first_reply_of_an_ask_or_answer.py::test_the_line_itself_tells_what_to_say_before_the_question
    | FAILED tests/contract/router/test_rt_gap_first_reply_of_an_ask_or_answer.py::test_a_topic_opened_by_the_routers_ask_tells_the_opinion_can_be_asked_in_that_ask
    | FAILED tests/contract/router/test_rt_gap_first_reply_of_an_ask_or_answer.py::test_a_topic_opened_by_a_fact_answer_tells_the_opinion_can_be_asked_in_that_answer
    | 3 failed, 1 passed in 1.92s
  with the fix: exit 0
    | Using CPython 3.13.12
    | Creating virtual environment at: .venv
    | Installed 92 packages in 46ms
    | ....                                                                     [100%]
    | 4 passed in 1.85s
```

## 7. Gate and overseer
- Gate: fast set `uv run pytest -q -p no:cacheprovider tests/contract/router tests/contract/fact_answer
  tests/contract/one_conversation tests/contract/research_deep tests/contract/advice_on_request
  tests/contract/notes_readers tests/contract/spoken_replies tests/contract/skel_facilitation tests/router_unknown_fact
  tests/contract/conversation_loop` → `268 passed, 1 deselected`; `uv run ruff check -q src tests` clean;
  `uv run mypy src` → `Success: no issues found in 56 source files`.
- Overseer: PASS, request `20261110T145601Z-f1a80f` (it ran `bugfix.py prove` again in a temp copy: PROVED). Its
  test gap — on turn 1 with a choose the line reaches both the router's and the facilitator's frame, and no test pins
  that each carries it once — is proposal `tasks/proposed/748-open-item-test-gap-on-turn-1-when-the-router-answe.md`.
- The regression test stays in the suite: `tests/contract/router/test_rt_gap_first_reply_of_an_ask_or_answer.py`

## 8. Lesson
- Answer: a test was missing — task 310 tested the first-reply promise only on the path it changed (a choose on
  turn 1 with an empty history), not on the other writers of a topic's first reply (the router's ask, the fact
  answer).
- Queued: `#b8cc0778 added`
