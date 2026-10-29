# Objection package — skel-facilitation, carried out for the owner's answer A (board task 724)

**Why this package is filed under `notes-readers`.** skel-facilitation is parked after its two rounds: a request under
it only answers «PARKED» (`.claude/hooks/testing.py`, `request_tester`, the `objection` branch). notes-readers is the
sealed contract that changes these tests (Q1) and has one round left (round 1 went to task 721). Its Exit criterion
names this package: «Objection-пакет `test_wrong` (Q1 цього контракту: фасилітатор бачить лише нотатки своєї картки)
розглянуто тестувальником: `tests/contract/skel_facilitation/test_skelf_respond.py::test_system_instruction_is_poc_rules_then_card_then_all_memory`
(запис M-2 `gamma` у картці `alpha`)». The owner answered the parked question (task 724,
`tasks/doing/724-open-item-testing-parked-skel-facilitation.md`): «Відповідь: А» — «тести застаріли: свіжий tester
переносить два тести на «лише нотатки своєї картки», формат запису той самий». Earlier list:
`.engine/testing/objections/skel-facilitation-309-notes-readers.md`.

## Item 1 — the memory filter (both tests)

`.engine/slices/notes-readers.md`, Seam: «**`facilitation/respond.py` `system_instruction(card, memory, …)`**: розділ
«# Пам'ять досвіду» містить лише записи з `audience == "facilitator"` і `card.id in record.cards`, у тому самому
вигляді `_memory_text`; жодного — «(поки порожня)», як зараз. Сигнатура та сама.» Q1: «Фасилітатор бачить лише
нотатки своєї картки … Rejected: усі нотатки `facilitator` без фільтра — так закріпив skel-facilitation, коли пам'ять
була порожня».

In `skelf_fakes.py` record M-1 has `cards=["alpha", "beta"]`, M-2 has `cards=["gamma"]`; the context's card is
`alpha`. Under Q1 card alpha's instruction holds M-1 and not M-2.

Asked: carry each test over — for a card, expect only the records that name it (and that a record naming another card
is absent); keep the format checks of a record (`### <id> — <title>`, `Що помітили:`, `Що робити:`, `Підстава:`,
`Картки: <id>, <id>.`) as strong as they are. If a test needs a second record to keep checking the «Картки:» line of
a one-card record, add one that names `alpha`.

## Item 2 — the facilitator rules text (`test_skelf_respond.py`, the constant `RULES`)

The same test also fails on its first assertion: `RULES` is not in the instruction verbatim. The comment above `RULES`
says it was written out «from the sealed contract of facilitator-free-mode (… the fenced new text of rules.md; task
301)». Task 310 (`tasks/done/310-router-leads-one-method/task.md`, «Що зробити», the owner's task: «**Варіант А**: …
кожна відповідь фасилітатора спершу дає щось своє (факт, спостереження, гіпотеза з причиною), а потім одне питання»;
the owner's words under «Рішення власника»: «… а так варіант А, я думаю.») changed `src/thinkhow/facilitation/rules.md`
in commit `4b038d6`. The difference between `RULES` and the instruction's rules (the text before `# Картка`) is
exactly:
- line 1: «по обраній нею моделі мислення» → «по обраній моделі мислення» (the router now chooses — same task);
- the first rule «- Без готових відповідей. …» (three lines) → «- Спершу своє, потім питання. Кожна відповідь спершу
  дає щось своє — факт, спостереження чи гіпотезу з причиною («схоже, що …, бо …»), — і лише тоді одне питання.
  Рішення ухвалює людина. Сам, без прохання, не кажи людині, що робити, не обирай і не оцінюй варіанти за неї.»;
- a new rule after the «Називай метод …» rule: «- Коли в рамці репліки стоїть рядок «[Стан] Перша відповідь у темі» —
  одним реченням скажи, що будь-коли можна спитати твою думку («що б ти обрав?») або попросити інший спосіб.»
  (the line `FIRST_REPLY_LINE` — `.engine/slices/one-conversation.md`, Q4).

Task 310's report says it left this sealed test untouched because skel-facilitation was parked
(`tasks/done/310-router-leads-one-method/report.md`, «Запечатаний `tests/contract/skel_facilitation/test_skelf_respond.py`
я не чіпав»). Asked: carry `RULES` over to the rules text task 310 set (the current `rules.md` up to its last rule),
keeping the two replacements of Q5 («i3», «t<номер з рамки репліки>») and every other check of the test (order rules →
`# Картка` → card → `# Пам'ять досвіду`, `s2#`/`«t3»` absent). If you judge that no contract carries task 310's text,
answer that for this item (`contract_ambiguous`) — item 1 stands on its own.

Failing now (`uv run pytest -q tests/contract/skel_facilitation`):
- `tests/contract/skel_facilitation/test_skelf_respond.py::test_system_instruction_is_poc_rules_then_card_then_all_memory` — `AssertionError: the PoC rules (with the two replacements) are not in the instruction verbatim` (item 2), and below it record M-2 `cards: [gamma]` expected in card alpha's instruction (item 1)
- `tests/contract/skel_facilitation/test_skelf_disputed_q1_memory_cards_line.py::test_memory_cards_line_is_ids_joined_by_comma_space_with_a_period` — `ValueError: '### M-2 — Чужий досвід' is not in list` (item 1)
