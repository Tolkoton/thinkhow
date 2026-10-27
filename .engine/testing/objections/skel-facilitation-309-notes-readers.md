# Objection package — skel-facilitation, for task 309 (feature learning-loop, slice S4 notes-readers)

The sealed contract `.engine/slices/notes-readers.md` (S4, task 309) changes one thing these tests pin: the
facilitator's «# Пам'ять досвіду» now holds only the notes of **its own card** with `audience == "facilitator"`
(Seam: «розділ «# Пам'ять досвіду» містить лише записи з `audience == "facilitator"` і `card.id in record.cards`, у
тому самому вигляді `_memory_text`; жодного — «(поки порожня)», як зараз»; Q1: «Фасилітатор бачить лише нотатки
своєї картки … Rejected: усі нотатки `facilitator` без фільтра — так закріпив skel-facilitation, коли пам'ять була
порожня»). The format of a record in the section is unchanged; the router's text without router notes is
byte-equal (Seam 3).

Asked: carry each test over — expect, for a card, only its own facilitator notes (or «(поки порожня)» when it has
none); every other check unchanged.

Failing now (`uv run pytest -q <test>`):
- `tests/contract/skel_facilitation/test_skelf_respond.py::test_system_instruction_is_poc_rules_then_card_then_all_memory` — record M-2 `cards: [gamma]` expected in card alpha's instruction («no filter by card»)
- `tests/contract/skel_facilitation/test_skelf_disputed_q1_memory_cards_line.py::test_memory_cards_line_is_ids_joined_by_comma_space_with_a_period` — looks for `### M-2 — Чужий досвід` (cards: [gamma]) in alpha's instruction
