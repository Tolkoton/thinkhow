# Supersede package — spoken-replies, by deep-research-confirm-first (task 747)

The new sealed contract `.engine/slices/deep-research-confirm-first.md` changes three prompt texts that the
spoken-replies oracle (`tests/contract/spoken_replies/sr_oracle.py`, the instruction strings captured at cefcb02)
holds byte for byte. The section «# Людина слухає» itself is unchanged; only the surrounding texts differ.

Lines of the new contract:
- «`src/thinkhow/facilitation/research.md`, речення про глибоке (між текстом S1 і останнім рядком) стає: «Коли питання
  багатогранне (ринок, кілька шляхів, порівняння) і швидкого пошуку замало, скажи одним реченням, що це можна
  дослідити глибше, якщо людина захоче; згоди не питай — що саме шукати, покаже система.»»
- «`src/thinkhow/facilitation/deep_field.md`, тіло: «Коли людина сама просить дослідити глибоко або погоджується на
  глибше дослідження, про яке щойно сказано, — постав питання дослідження в deep_question …»»
- «`src/thinkhow/facilitation/deep.md` — три наявні розділи і новий четвертий:» with «План»: «`intro` — одне речення
  людині: що саме буде досліджено, що це близько двох хвилин, і питання, чи запускати (або що змінити)…» and «Згода».

## Tests (fail now)

1. `tests/contract/spoken_replies/test_sr_instructions.py::test_system_instruction_spoken_puts_section_after_language_rule`,
   `::test_answer_fact_passes_ctx_spoken`, `::test_answer_instruction_spoken_puts_section_before_research_section`,
   `::test_deep_system_spoken_appends_section_for_each_rule` — compare with oracle strings that hold the old
   `research.md` sentence, the old `deep_field.md` body and the old «План» rule (the deep oracle keys hold the three old
   rules; now four, with «Згода»).
2. `tests/contract/spoken_replies/test_sr_invariants.py::test_I1_without_the_flag_each_instruction_is_byte_equal_to_before`
   — byte equality with the same oracle.

Asked: the oracle literals take the new texts (as the objection of task 309 and the amendment of task 729 did);
the laws about «# Людина слухає» stay as they are.
