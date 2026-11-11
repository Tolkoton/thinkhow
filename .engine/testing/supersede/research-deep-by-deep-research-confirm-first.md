# Supersede package — research-deep, by deep-research-confirm-first (task 747)

The new sealed contract `.engine/slices/deep-research-confirm-first.md` changes the order of the deep cycle: the
reply that decides on deep research no longer runs it — it shows a proposal (the research question and the
sub-questions that go to the search word for word) and asks; the person's next turn agrees (`run_deep` searches
exactly the shown sub-questions, no plan call), changes it (a new proposal) or declines. `deep_research` and
`deep_answer` are removed. The prompt texts change too (contract «Тексти промптів», Q11).

Lines of the new contract that change what these tests hold:
- «`deep_research` (план + цикл в одній відповіді) і `deep_answer` прибираються: у продукті їх більше ніхто не кличе.»
- «`with_deep(items, deep_question, ctx, llm, rev)` — та сама сигнатура; при `deep_question` і не `ctx.deep_off` —
  пропозиція замість циклу»
- «`def deep_offer(question, ctx, llm, rev) -> Iterator[ReplyDelta | FacilitatorUpdate | DeepProposed]` — шлях
  роутера (`answer` з `deep_question`)»
- «`src/thinkhow/facilitation/research.md`, речення про глибоке (між текстом S1 і останнім рядком) стає: …»
- «`src/thinkhow/facilitation/deep_field.md`, тіло: …»

## Tests (all fail now)

1. `tests/contract/research_deep/test_rdp_deep.py` — the whole file fails at import (`deep_research` gone). Tests of
   `deep_research` (plan → steps → searches → report; retries; parallel searches; request_id; failed searches) —
   the plan part is now `propose`, the cycle part `run_deep(pending, …)`; `with_deep` now appends a proposal. Asked:
   rewrite to `propose`/`run_deep`/the new `with_deep`, or delete what the new contract's tests already hold
   (`tests/contract/deep_confirm/`).
2. `tests/contract/research_deep/test_rdp_invariants.py` — fails at import (`deep_research`). I1 (shown = recorded
   with deep research), I2 (sources union), I3 (no deep call without deep_question), I4 (fact ids unique) — the same
   laws over `run_deep`/the new paths.
3. `tests/contract/research_deep/test_rdp_respond.py::test_seam1_respond_under_the_router_gives_the_deep_events_and_the_card_end_before_the_held_update`,
   `::test_under_the_router_the_retry_of_the_update_carries_deep_question_and_the_cycle_follows`,
   `::test_seam2_converse_on_answer_with_deep_question_runs_the_cycle_at_once_without_answer_fact` — expect the cycle
   in the same reply; now a proposal (`with_deep`, `deep_offer`).
4. `tests/contract/research_deep/test_rdp_route.py::test_deep_field_section_only_under_the_router_after_the_facts_and_before_the_card`
   (expects the old `DEEP_FIELD_BODY`), `::test_research_md_has_the_offer_sentence_between_the_s1_text_and_the_last_line`
   (expects the old `RESEARCH_SENTENCE`), `::test_deep_question_is_trimmed_and_a_blank_one_is_none_on_the_router_and_the_facilitator_path`
   (its non-blank case expects a `ResearchEvent` with the question in the same reply; now a `DeepProposed`).
5. `tests/contract/research_deep/test_rdp_workspace.py` — all three tests (`test_seam1_…`, `test_seam2_…`,
   `test_seam3_every_search_failed_…`) drive one reply that decides on deep research and expect the cycle's writes in
   it; now the proposal is written (`deep_pending.json`) and the cycle comes on the next turn's «yes».

`rdp_fakes.py` (not in the seal) carries `RESEARCH_SENTENCE`, `DEEP_FIELD_BODY` — update with the texts. Note:
`tests/research_deep/test_rd_gaps.py` (builder's, unsealed) imports `rdp_fakes` (`fa`, `with_deep_question`, `full_deep`,
`deep_llm`, `ctx`, `DQ`, `QA`, `QB`, `TEXT_A`, `TEXT_B`, `PA`, `PB`, `plan_raw`, `report_raw`); keep those names or say so.
