# Supersede package — research-live (research-in-conversation block tests), by deep-research-confirm-first (task 747)

The new sealed contract `.engine/slices/deep-research-confirm-first.md`: the reply that decides on deep research shows
a proposal and asks; the cycle runs on the person's next turn when it agrees («yes»).

Lines of the new contract that change what these tests hold:
- «`with_deep(items, deep_question, ctx, llm, rev)` — та сама сигнатура; при `deep_question` і не `ctx.deep_off` —
  пропозиція замість циклу»
- «`def deep_offer(question, ctx, llm, rev) -> Iterator[ReplyDelta | FacilitatorUpdate | DeepProposed]` — шлях
  роутера (`answer` з `deep_question`)»
- «`converse`: перш за все, коли `ctx.pending_deep` є: `consent(...)`; `yes` → `deep_agreed`»

## Tests (fail now)

1. `tests/contract/research_in_conversation_block/test_ric_block.py::test_one_topic_quick_then_no_search_then_deep_entries_keep_the_model_turns_and_the_file_is_left_alone`
   — its deep turn expects the deep entry in the same reply; now the proposal, the entry after «yes».
2. `tests/contract/research_in_conversation_block/test_ric_block.py::test_the_sources_line_shown_live_is_the_one_recorded_on_the_card_answer_and_deep_paths`
   — its deep path expects the report's sources line in the reply that decided; now after «yes».
3. `tests/contract/research_in_conversation_block/test_ric_disputed_q1_deep_question.py::test_deep_question_only_under_the_router_and_the_one_cycle_runs_from_the_card_and_from_answer`
   — expects the cycle to run from the card and from `answer` in that reply; now a proposal on both paths, the cycle
   after consent.
