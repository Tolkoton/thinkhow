# Objection package — skel-knowledge sealed test vs. the 18 cards of task 302

Why: a later sealed contract, `.engine/slices/cards-library.md` (feature `thinking-models-router`, S1; owner's words
in task 302: «Ні, додай всі моделі… Треба додати, широкий спектр моделей»), puts 18 card files into `cards/`
(«Goal» 1 names the 18 ids). Its Q4 names this test: «чекає в `cards/` лише Pre-mortem — його передумову скасовує
задача власника 302… заміна: ревізія 1, рівно 18 id з «Goal» 1, Pre-mortem дорівнює справжній картці». The test's own
subject — seeding the repository's `cards/` gives revision 1, `n` 0, empty memory, the real Pre-mortem, and a repeat
seed is refused — stays; only the expected set of ids follows the repository folder.

Asked: replace `["pre-mortem"]` by the 18 ids of `cards-library` «Goal» 1 (sorted), keep every other check as written
(`seed` True then False, `rev` 1, `n` 0, memory `[]`, `cards["pre-mortem"] == load_real_card()`).

Items:
1. tests/contract/skel_knowledge/test_skelk_real_card.py::test_seeding_the_repository_cards_gives_revision_1_with_pre_mortem —
   skel-knowledge exit criterion («seeding the repository's `cards/`»); with the 18 files of cards-library the set of
   ids is 18, so `sorted(knowledge.cards) == ["pre-mortem"]` fails although seeding works as specified.
