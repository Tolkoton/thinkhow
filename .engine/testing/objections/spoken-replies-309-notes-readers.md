# Objection package — spoken-replies, for task 309 (feature learning-loop, slice S4 notes-readers)

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
- `tests/contract/spoken_replies/test_sr_invariants.py::test_I1_without_the_flag_each_instruction_is_byte_equal_to_before` — the oracle `sr_oracle.py` keys `respond|beta|one|…` hold the record M-1 `cards: [alpha]` in card beta's instruction
- `tests/contract/spoken_replies/test_sr_instructions.py::test_system_instruction_spoken_puts_section_after_language_rule` — same oracle entries (`respond|beta|one|…`)
