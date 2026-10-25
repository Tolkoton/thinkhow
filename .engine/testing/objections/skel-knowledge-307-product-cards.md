# Objection package — skel-knowledge sealed test vs. the 25 cards of task 307

Why: `.engine/slices/product-cards.md` (feature `product-thinking-pack`, S1; task 307) adds 7 card files to `cards/`.
Its Q4 names this test. Its subject — seeding the repository's `cards/` gives revision 1, `n` 0, empty memory, the real
Pre-mortem, and a repeat seed is refused — stays; only the expected set of ids follows the repository folder (as the
objection of task 302, `skel-knowledge-302-cards.md`, did for 18).

Asked: tests/contract/skel_knowledge/test_skelk_real_card.py::test_seeding_the_repository_cards_gives_revision_1_with_pre_mortem —
`REPOSITORY_CARD_IDS` = the 18 ids + `customer-interviews`, `demand-test`, `positioning`, `offer-design`,
`value-pricing`, `traction-channels`, `unit-economics` (sorted, 25); every other check as written. Fails now: 25 files.
