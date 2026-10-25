# Objection package — cards-library sealed tests vs. the 25 cards of task 307

Why: a later contract, `.engine/slices/product-cards.md` (feature `product-thinking-pack`, S1; the owner's words in task
307: «нам треба додати продуктову лінійку логіки… ширше»), puts 7 more card files into `cards/` («Goal» 1: the 18 ids
of task 302 and `customer-interviews`, `demand-test`, `positioning`, `offer-design`, `value-pricing`,
`traction-channels`, `unit-economics`). Its Q4 names these tests. Each test's subject stays; only the set of ids
follows the repository folder, and the bans that held for «the 17 new cards» of task 302 hold for every card except
`pre-mortem` (24), as product-cards I4 says.

Asked:
1. tests/contract/cards_library/test_cl_content.py — `GOAL_IDS` = the 18 ids + the 7 ids of task 307 (25);
   `test_seam5_cards_holds_exactly_the_18_ids_of_the_goal` checks those 25; `NEW_IDS` (every id but `pre-mortem`, now
   24) keeps feeding the trademark ban and the «час змінити метод» / crisis bans; the pre-mortem blob test unchanged.
   Fails now: `cards/` holds 25 files, `sorted(...) == sorted(GOAL_IDS)` with 18 fails although the library is as
   specified.
2. tests/contract/cards_library/test_cl_job.py::test_goal2_revision_1_with_pre_mortem_becomes_revision_2_with_18_cards_and_the_same_pre_mortem_file
   — `GOAL_IDS` = the same 25; revision 2 holds all 25 cards; every other check (rev 2, the same pre-mortem file, a
   repeat writes nothing) unchanged. Fails now for the same reason.
Not asked: `test_cl_catchup_*` — they fail only through `scripts/smoke_test_cards_library.py:60` (`== 18`), a script
the builder sets to the literal 25 (product-cards Seam); with that they pass unchanged.
`test_cl_disputed_q1_case_insensitive.py` — does not fail with 25 cards and is not changed (product-cards Q4).
