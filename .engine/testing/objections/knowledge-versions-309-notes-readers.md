# Objection package — knowledge-versions, for task 309 (feature learning-loop, slice S4 notes-readers)

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
- `tests/contract/knowledge_versions/test_kv_vet.py::test_measure_is_the_length_of_the_longest_reader_instruction` — its third case builds a 60 000-character record with `cards: [beta]` and expects alpha's facilitator instruction to carry it («every facilitator instruction carries the whole memory today»); the knowledge-versions contract itself says `measure` builds the readers' instructions and «коли S4 звузить пам'ять фасилітатора до його картки, `measure` іде за ним без зміни контракту». Asked: the long record belongs to the card whose instruction is expected longest
