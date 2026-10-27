# Objection package — product-thinking-pack block test (slice product-router-eval), for task 309

One sealed block test pins files that a later, planned feature changes. The test is right about task 307 and wrong
as a rule for every later commit.

1. `tests/contract/product_thinking_pack_block/test_ptp_block.py::test_s1_to_s2_the_seven_ids_and_their_cases_stand_as_s1_left_them_and_s2_edited_only_texts`
   - Lines 124 and 133: `git diff S1_CLOSED -- src/thinkhow/knowledge` and
     `git diff S1_CLOSED -- scripts/router_eval.py scripts/card_conversations.py` must be empty. They compare the
     working tree with `82e6213`, so they fail on any later change to those paths, by any task.
   - The behaviour the test guards: between S1 (product-cards) and S2 (product-router-eval) of feature
     product-thinking-pack, S2 changed only texts, not the Knowledge code or the eval scripts. That holds: at the
     close of task 307 (`15134a2`) both diffs were empty.
   - Why it is wrong now: task 309 (feature learning-loop, sealed contracts `.engine/slices/knowledge-versions.md`
     and `.engine/slices/starting-notes.md`) changes `src/thinkhow/knowledge` (memory revisions, rollbacks) and
     `scripts/router_eval.py` (`--notes`). Fails today with `+ diff --git a/src/thinkhow/knowledge/__init__.py …`.
   - Asked: bound both checks to feature 307's window (`git diff 82e6213 15134a2 -- …`, the commit where task 307
     closed), so the test keeps saying what S2 did and stops failing on later work. Every other assertion unchanged.

Reproduce: `uv run pytest -q "tests/contract/product_thinking_pack_block/test_ptp_block.py::test_s1_to_s2_the_seven_ids_and_their_cases_stand_as_s1_left_them_and_s2_edited_only_texts"`.
