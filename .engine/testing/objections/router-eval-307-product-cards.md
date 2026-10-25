# Objection package — router-eval sealed tests vs. the 25 cards of task 307

Why: `.engine/slices/product-cards.md` (feature `product-thinking-pack`, S1; task 307) adds 7 cards to `cards/` and
their cases to `tests/fixtures/routing/cases.yaml` (≥3 positive, the `-3` held out, ≥1 negative each). Its Q4 names
these tests. The subject of each stays; only the literal count 18 follows the folder, and the AC tests of feature
`thinking-models-router` (task 302) keep checking the 18 cards of task 302, while the same checks for the 7 new cards
belong to S2 `product-router-eval` (its own new test).

Asked:
1. tests/contract/router_eval/test_rev_cases.py::test_every_card_id_a_case_names_is_a_card_of_cards_dir — `len(known)
   == 18` → `len(known) == 25`. Fails now: 25 card files.
2. tests/contract/router_eval/test_rev_cases.py::test_held_out_part_is_the_third_positive_case_of_each_card —
   `len(held) == 18` → `len(held) == len(card_ids())` (the held-out part is one `-3` per card). Fails now: 25 `-3`
   cases.
3. tests/contract/thinking_models_router_block/test_tmr_block.py — `test_s1_to_s2_router_sees_router_halves_of_the_18_cards…`
   (`len(CARD_IDS) == 18` → 25), `test_s1_to_s3_the_cards_of_cases_yaml_are_exactly_the_18_cards…` (unchanged logic:
   the positive `expect`s equal the card ids — passes once the cases exist; only the name/literal if any),
   `test_ac6_job_cards_then_a_restarted_service_routes_with_revision_2` (count 18 → 25);
   `test_ac4_the_newest_router_eval_report_has_a_row_for_every_card_and_its_confusions` and
   `test_ac5_a_live_conversation_report_exists_for_every_card_with_its_index_row` — iterate over the 18 ids of task
   302 (a literal list), not over `CARD_IDS`: they are the AC4/AC5 of task 302; the 7 new cards get the same checks in
   S2. Fail now: the newest report and the conversations predate the 7 cards.
Not asked: `test_rev_conversations.py::test_person_instruction_names_no_method_for_the_situation_of_every_card` —
fails only while the new cards have no positive case; passes unchanged once the cases exist.
