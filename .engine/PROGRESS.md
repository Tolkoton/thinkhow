# PROGRESS


## Slice 1 — skel-platform (DONE 2026-10-22)

- Module: `src/thinkhow/platform/` — config, log, storage, identity, llm, `_reply_stream` (~650 LOC)
- Tests: 50 contract tests of the slice-tester (`tests/contract/skel_platform/`), A3 guards
  `tests/test_a3_imports.py`, `tests/test_a3_google_sdk.py`; live `tests/live/test_llm_live.py` green on
  `gemini-4-argon`/`eu`
- Smoke: passed — `scripts/smoke_test_skel_platform.py`, output `.engine/artifacts/spikes/skel-platform-smoke-2026-10-22.txt`
- Surprises: `log_event`'s default stream is bound at import, so `redirect_stdout` does not capture it (tests pass `stream`)
- Open for next slice: real GCS and IAP only on the owner's deployment (PR-04, PR-07)

## Slice 2 — skel-knowledge (DONE 2026-10-22)

- Module: `src/thinkhow/knowledge/` — schema, prompt, store (~230 LOC); `cards/pre-mortem.yaml`
- Tests: 35 contract tests of the slice-tester (`tests/contract/skel_knowledge/`), all green
- Smoke: passed — `scripts/smoke_test_skel_knowledge.py`, output `.engine/artifacts/spikes/skel-knowledge-smoke-2026-10-22.txt`
- Surprises: the tester's hand-in needs the module skeleton in the tree first (import), else the script refuses it
- Open for next slice: none; the real bucket is the owner's (Job `seed`, PR-07)

## Slice 3 — skel-facilitation (DONE 2026-10-22)

- Module: `src/thinkhow/facilitation/` — types, respond, rules.md (PoC 101 instruction, two lines changed) (~250 LOC)
- Tests: 21 contract tests of the slice-tester (`tests/contract/skel_facilitation/`); live `tests/live/test_facilitation_live.py` green
- Smoke: passed — `scripts/smoke_test_skel_facilitation.py`, output `.engine/artifacts/spikes/skel-facilitation-smoke-2026-10-22.txt`
- Surprises: in 1 of 3 smoke runs the reply's first sentence was Russian to a Ukrainian message (C4) — reported to the owner;
  import-linter counts indirect chains, so `workspace` imports only `facilitation.types` (Q6)
- Open for next slice: S4 imports `thinkhow.facilitation.types` only; `turn_no` is the topic-wide number of the person's message

## Slice 4 — skel-workspace (DONE 2026-10-22)

- Module: `src/thinkhow/access/` (CurrentUser, owner rule) and `src/thinkhow/workspace/` — model, conversation (format, ADR-0004), topics (~420 LOC)
- Tests: 46 contract tests of the slice-tester (`tests/contract/skel_workspace/`), all green
- Smoke: passed — `scripts/smoke_test_skel_workspace.py`, output `.engine/artifacts/spikes/skel-workspace-smoke-2026-10-22.txt`
- Surprises: none in the code; planning found that an unanswered turn crossing a session close needed a rule (Q7, I5)
- Open for next slice: S5 must call `all_topics_for_learning` only for `is_owner`; `reply`/`retry` raise before the stream

## Slice 5 — skel-web (DONE 2026-10-22) — tracer bullet, part 1

- Module: `src/thinkhow/web/` — server (routes, SSE, login layer, one error handler, ASGI request log), app (composition root), local (scripted model), templates, `static/conversation.js` (~470 LOC with JS)
- Tests: 50 contract tests of the slice-tester (`tests/contract/skel_web/`, 13 run under `node --test`); `tests/smoke/test_e2e_local.py`; `tests/web/test_conversation_js.py`
- Smoke: passed — `scripts/smoke_test_skel_web.py` (real uvicorn, local mode), output `.engine/artifacts/spikes/skel-web-smoke-2026-10-22.txt`
- Surprises: FastAPI 0.159.1 treats an empty form field as missing (422) — fields are `Form("")`; `fetch` does not reject on HTTP errors — the controller handles `!ok`
- Open for next slice: S6 extends `tests/smoke/test_e2e_local.py` to `analyze`; S7: Dockerfile must copy `cards/`; PR-04 in a real browser through IAP is the owner's check

## Slice 6 — skel-learning (DONE 2026-10-22) — tracer bullet, part 2

- Module: `src/thinkhow/learning/` — analyze (one call per closed session, anchor `enum` of the session's turns), local, job (`python -m thinkhow.learning.job seed|analyze`) (~200 LOC)
- Tests: 24 contract tests of the slice-tester (`tests/contract/skel_learning/`, one live: a 40-turn session on `gemini-4-argon`/`eu`, green); `tests/smoke/test_e2e_local.py` extended to `analyze` — PR-09 `verified`
- Smoke: passed — `scripts/smoke_test_skel_learning.py` (Job as processes, local mode), output `.engine/artifacts/spikes/skel-learning-smoke-2026-10-22.txt`
- Surprises: pydantic writes `const` for a one-value `Literal` — the anchor schema forces `enum`; the same holds for a one-phase card in S3 (not reachable now: one card, 4 phases)
- Open for next slice: S7 — Job rights (read `users`, write `system`), Scheduler, Dockerfile with `cards/`

## Slice 7 — skel-guards-deploy (DONE 2026-10-22)

- Files: `tests/test_a3_guards.py` (A3.3, A3.4, strict bucket rule, planted breaches), `tests/test_ac4.py` (the four AC4 guards), `tests/test_dockerfile.py`, `tests/test_deploy_doc.py`, `Dockerfile`, `.dockerignore`, `docs/deploy.md` (owner's steps and checklist)
- Tests: 36 contract tests of the slice-tester (`tests/contract/skel_guards_deploy/`), all green
- Smoke: none in this slice by contract — the agent has no Docker daemon and may not deploy; the image is built by the owner's `gcloud builds submit`
- Surprises: the deploy order matters (seed before the service: the service reads the Knowledge at start); the Job needs the same `THINKHOW_*` as the service
- Open: AC1–AC3 (PR-04, PR-07) — the owner's checklist in `docs/deploy.md`

## Slice 8 — voice-language (DONE 2026-10-23) — F13, tracer bullet part 1

- Module: `src/thinkhow/workspace/languages.py` (85 languages, CLDR endonyms, no Russian), `workspace/profile.py`
  (`language`, `set_language`, `NoLanguage`), `web` — `/language` page and form, the `NoLanguage` handler (GET → 303
  `/language`, other methods → 409), «Мова» on every page (~200 LOC with the list)
- Tests: 20 contract tests of the slice-tester (`tests/contract/voice_language/`); 18 sealed tests of skel-web and
  skel-learning corrected by a fresh tester on two objection packages (`.engine/testing/objections/`), only the
  language choice added; walking-skeleton block tests, `tests/smoke/test_e2e_local.py` and both skeleton smokes
  choose a language first
- Smoke: passed — `scripts/smoke_test_voice_language.py`, output `.engine/artifacts/spikes/voice-language-smoke-2026-10-23.txt`
- Surprises: FastAPI answers `HEAD` on a GET route with 405 before the login layer (critic probe) — the handler
  splits GET vs. the rest only; a list in the profile's `language` field broke a dict lookup (caught by I1)
- Open for next slice: S2 (`voice-dictation`) and S3 (`voice-reply-language`) call `workspace.language(...)` and get
  409 on POST from the handler; the owner chooses a language once after the deployment

## Slice 9 — voice-dictation (DONE 2026-10-23) — F13, tracer bullet part 2

- Module: `src/thinkhow/platform/speech.py` (`GeminiSpeech` — `gemini-3.5-transcribe` on Vertex `eu`, pinned
  language, retries, `speech_call` log; `ScriptedSpeech`; `make_speech`), `platform/_retry.py` (the retry rule moved
  out of `llm`), `workspace/voice.py` (`transcribe`), `web` — `POST …/voice`, 400/502 fragments, `Deps.speech`;
  `static/conversation.js` — `createRecorder` and the page's microphone (~330 LOC with JS)
- Tests: 52 contract tests of the slice-tester (`tests/contract/voice_dictation/`, 18 under `node --test`); live
  `tests/live/test_speech_live.py` (`-m live`: webm 1.38 s, AAC 1.16 s, verbatim; `-m live_codes`: `xx-XX` refused,
  all 85 codes accepted)
- Smoke: passed — `uv run --with playwright==1.64.1 python scripts/smoke_test_voice_dictation.py` (real Chromium,
  fake microphone), output `.engine/artifacts/spikes/voice-dictation-smoke-2026-10-23.txt`
- Docs: ADR-0005; M2 S8, M3 A2/A6 and the diagram, INDEX F13; `docs/deploy.md` checklist items 10–14
- Surprises: Chromium records 128 kbit/s by default (pinned 64 kbit/s); Playwright does not expose Blob bodies; a
  mismatched pinned language is a hint, not a filter; the 1.64 Playwright needs the cached chromium-1208 by path
- Open for next slice: S3 (`voice-reply-language`) — the facilitator answers in the profile's language

## Slice 10 — voice-reply-language (DONE 2026-10-23) — F13, the last slice

- Module: `facilitation/respond.py` (`language_rule`; «# Мова відповіді» between the rules and the card),
  `facilitation/types.py` (`FacilitationContext.language: str | None = None`), `workspace/topics.py` (`reply`/`retry`
  read the person's language eagerly, `None` before the first choice), `workspace/_paths.py` (`JSON`, `UID`, `_uid`
  moved out of `topics` to break the `profile` ↔ `topics` cycle) (~60 LOC)
- Tests: 19 contract tests of the slice-tester (`tests/contract/voice_reply_language/`); no sealed test of an earlier
  slice changed (`testing.py check` — match for skel-facilitation, skel-workspace, skel-web)
- Smoke: live — `tests/live/test_facilitation_language_live.py` 7/7 (pl → pl; ru from a uk person → uk, 5 of 5;
  uk from an en person → en), output `.engine/artifacts/spikes/voice-reply-language-live-2026-10-23.txt`; after S3
  the browser smoke and the speech live test are green again (`voice-dictation-smoke-2026-10-23-after-s3.txt`)
- Surprises: none in the code; the departures from the feature artifact (default field, rules.md untouched, no 409)
  are logged AUTONOMOUS (escalations 2026-10-23T18:40Z)
- Open: deployment by the owner (checklist 10–14 in `docs/deploy.md`)

## Slice 11 — minimal-design (DONE 2026-10-23) — task 201

- Module: `web/static/style.css` (new, one palette for the light and the dark theme), `web/templates/*.html` (link,
  `<header class="site">`, `<main>`, classes, `#pending`, `autocomplete="off"` on `#send`/`#retry`); `conversation.js`
  unchanged; `scripts/screenshots_minimal_design.py` (new)
- Tests: 13 contract tests of the slice-tester (`tests/contract/minimal_design/`); `testing.py check` — match for
  skel-web, voice-dictation, voice-language, voice-reply-language
- Smoke: `scripts/screenshots_minimal_design.py` — OK (dark theme, pending while `/reply` is held, error and network
  ends, hidden buttons, line breaks, no horizontal scroll at 390/360 px), output
  `.engine/artifacts/spikes/minimal-design-screens-2026-10-23.txt`, screenshots `tasks/done/201-minimal-design/screens/`;
  `smoke_test_voice_dictation.py`, `smoke_test_skel_web.py`, `smoke_test_voice_language.py` — OK
- Surprises: `.turn.model { pre-wrap }` (old) put blank lines into saved answers — fixed (behaviors file, self-added)
- Open: I2 contrast threshold 4.5:1 PROVISIONAL (owner); `autocomplete="off"` not checked in a real Firefox

## Slice 12 — continuous-analysis (BUILT, waiting for the owner 2026-10-23) — task 202

- Module: `learning/analyze.py` (one call per topic about the turns after the last analyzed one; cursor from the names
  `t<a>-t<b>.json`, an old `s<n>.json` moves it to the end of session n; context = analyzed turns of the same session),
  `workspace.topic_sessions` (new reader for learning); removed `close_session`, `closed_sessions`, `ClosedSession`,
  `POST …/close`, the «Завершити сесію» form and its CSS; the old `closed` marker is only read
- Tests: 24 contract tests of the slice-tester (`tests/contract/continuous_analysis/`); objection rounds (all
  `test_wrong`, resealed) for skel-learning, skel-workspace, skel-guards-deploy (walking_skeleton_block);
  `tests/smoke/test_e2e_local.py` rewritten to the exit criterion
- Smoke: `scripts/smoke_test_skel_learning.py`, `scripts/smoke_test_skel_workspace.py` — OK,
  `.engine/artifacts/spikes/continuous-analysis-smoke-{learning,workspace}-2026-10-23.txt`
- Open: skel-web is PARKED (two dispute rounds used before; a third is refused) — 3 sealed tests there still expect
  the button and the close route; owner's answer in `tasks/blocked/202-no-end-session-button.md`. No overseer audit yet.

## SKELETON_VERIFIED — 2026-10-24 — task 105

- The walking skeleton works end to end on the owner's deployment (`pocket-lawyer-431614`, `europe-west3`): IAP login
  with Gmail → topic `t-113f78de92a5` → two replies streamed by `gemini-4-argon` on `eu` (owner, 2026-10-23) →
  `conversation.md`, `map.json`, `profile.json` in bucket `users` → redeploy `thinkhow-00002-nrf` (image of `7095cb0`),
  files in place → Job `analyze` wrote `learning/observations/<uid>/t-113f78de92a5/t1-t4.json`, `link` `#t3`; second run
  `written=0` → logs in `thinkhow-eu` without conversation text.
- Evidence: `.engine/artifacts/spikes/skeleton-deploy-verify-2026-10-24.txt`; Сонько's run
  `~/sonko/done/2026-10-24-thinkhow-checklist-5-9.md`. PR-04, PR-07 → `verified` (`.engine/premises/premise-log.md`).
- Not checked on the deployment, by the owner's word (task 105, question 6): item 2 (IAP open to
  `allAuthenticatedUsers`), item 4 (draft after the IAP session ends — covered by tests). Items 10–14 (F13 voice) belong
  to task 106.

## Slice 13 — facilitator-free-mode (BUILT 2026-10-24) — task 301

- Module: `facilitation/rules.md` (new rules: free mode when the card does not fit, said once in plain words, no method
  names, ways to evaluate on «як це дізнатися?», summaries only from the person's words, short answers);
  `facilitation/types.py` (`current_phase_id: str | None`); `facilitation/respond.py` (schemas `Literal[phases] | None`,
  the frame line `[Стан] Вільний режим уже триває…` when `phase_id` is null and `last_turn > 0`); `web/local.py`
  (`_first_phase` reads `anyOf`)
- Tests: 6 contract tests of the slice-tester (`tests/contract/facilitator_free_mode/`, one objection round on I3);
  objection rounds (`test_wrong`, resealed) for skel-facilitation and voice-reply-language — the `RULES` constant;
  `tests/live/test_facilitation_free_mode_live.py` (A, B live; detector tests in the ordinary run)
- Live: A `.engine/artifacts/spikes/facilitator-free-mode-live-A-2026-10-24T085834Z.md` (one announcement, at #1; no
  method names; two ways to evaluate at #13), B `…-live-B-2026-10-24T085925Z.md` (phases 1→2→3→4→4)
- Smoke: `scripts/smoke_test_skel_facilitation.py`, `tests/live/test_facilitation_live.py` — OK,
  `.engine/artifacts/spikes/facilitator-free-mode-smoke-2026-10-24.txt`
- Open: the new rules reach the owner's prototype only after a new image and redeploy (`docs/deploy.md` 5, 8)

## Slice 14 — cards-library (DONE 2026-10-24) — task 302, feature thinking-models-router S1

- Module: `knowledge/store.py` (`publish`: a new revision from `cards/` — new version files only for changed and new
  cards, the change record last, `None` when nothing changed), `learning/job.py` (command `cards`, `cards_published`);
  17 new cards in `cards/` (18 with Pre-mortem, unchanged); `docs/deploy.md` §7 (Job `cards`, then the service);
  `scripts/smoke_test_skel_knowledge.py` (ids = the files of `cards/`) (~70 LOC of code, ~1 900 lines of cards)
- Tests: 34 contract tests of the slice-tester (`tests/contract/cards_library/`, one question answered: bans are
  case-insensitive); one objection round for skel-knowledge (`test_skelk_real_card.py`, `test_wrong`, resealed with
  the 18 ids)
- Smoke: passed — `scripts/smoke_test_cards_library.py` (rev 1 with Pre-mortem → Job `cards` as a process → rev 2,
  18 cards, Pre-mortem `v1.json`; repeat `rev: null`), output `.engine/artifacts/spikes/cards-library-smoke-2026-10-24.txt`
- Surprises: the testing hook records a hand-in only when the agent stops — a hand record is refused while wired
- Open for next slice: S2 (router) reads `card.router`; local folders seeded before S1 keep one card (`build_deps`
  calls only `seed`)

## Slice 15 — router (DONE 2026-10-24) — task 302, feature thinking-models-router S2, tracer bullet

- Module: `facilitation/route.py` (one `generate_json`: profile of 8 dimensions + offer 2–3 / ask / choose; schema
  narrowed to the revision's card ids; one retry), `facilitation/router.md` (the router's rules), `facilitation/converse.py`
  (router before the facilitator; `end` done / not_fit before the closing update), `facilitation/routed.md` (the
  facilitator under the router), `facilitation/language.py` (the language rule moved out of `respond`), `types.py`
  (`Profile`, `Candidate`, `Rev`, `Decision`, `RoutingEvent`, `current_card`, `routing` outside equality),
  `respond.py` (`respond` dispatches: no routing → `lead` as before), `workspace/topics.py` (`routing.json`),
  `web/local.py` (the local twin chooses pre-mortem) (~330 LOC)
- Tests: 46 contract tests of the slice-tester (`tests/contract/router/`, two questions answered); no sealed test of an
  earlier slice changed; `tests/smoke/test_e2e_local.py` checks `routing.json`; offline detector tests in
  `tests/live/test_router_live.py`
- Live: tracer `tests/live/test_router_live.py` — class iii on the first run,
  `.engine/artifacts/spikes/router-live-2026-10-24T142943Z.md` (PR-14 verified). Calls of that run (`llm_call` lines, printed by the run;
  the artifact of that run predates their capture): router `offer` — 13 098 ms, 9 834 prompt + 721 output tokens;
  router `choose` — 6 306 ms, 10 094 + 175; facilitator (issue-tree) — 5 731 ms, 3 383 + 207; all `attempts: 1`,
  `outcome: ok`, `rev 1`. Every later live run writes its `llm_call` lines into its own artifact; the second run (after the capture was added) — class iii too,
  `.engine/artifacts/spikes/router-live-2026-10-24T143627Z.md`, with its three `llm_call` lines inside
- Surprises: a sealed block test pins `deps.facilitate.func is respond` and its slice has no objection rounds left —
  `respond` dispatches instead of a new `converse` in the app; `routing` outside equality (`compare=False`)
- Open for next slice: S3 measures the router on `cases.yaml`, live conversations per card; the 301 live tests A/B
  now go through the router (A's free-mode expectations no longer apply)

## Slice 16 — router-eval (DONE 2026-10-24) — task 302, feature thinking-models-router S3

- Files: `tests/fixtures/routing/cases.yaml` (85 situations, held-out `*-3`), `scripts/router_eval.py`,
  `scripts/card_conversations.py` (synthetic person `gemini-3.5-flash`); card edits (router halves of `issue-tree`,
  `jobs-to-be-done`, `complexity-sensemaking`)
- Tests: 49 contract tests of the slice-tester (`tests/contract/router_eval/`, two questions answered)
- Live: router eval run 1 `.engine/artifacts/router-eval/2026-10-24T181411Z.md` — first 83/85, held-out 18/18; run 2
  after the card edits `…181915Z.md` — first 85/85, held-out 18/18; conversations
  `.engine/artifacts/card-conversations/2026-10-24T181933Z/` (18 cards: offered, led, last phase, `end: done`; switch)
  and `…183048Z/` (the owner's topic: issue-tree → pre-mortem → jobs-to-be-done)
- Surprises: the owner topic driver stopped at the first `end` — fixed (no target card → runs to N turns); task-301
  live A now fails only its free-mode phase check, superseded by the router
- Open: AC6 — deployment through Сонько (Job `cards`, then the service)

## Slice 17 — research-quick (DONE 2026-10-25) — task 303, feature research-in-conversation S1, tracer bullet

- Module: `platform/llm.py` (`Source`, `Found`, `Done.found`, `VertexLlm(search=True)` — `enterprise_web_search` only in
  `stream_json`, metadata united over the chunks; `ScriptedLlm(found_script)`; `make_llm(search, found_script)`;
  `llm_call` + `search`, `queries`), `facilitation/research.md` (the rule «Факти про світ», under the router only),
  `facilitation/respond.py` (`sources_line`, `with_research`), `facilitation/types.py` (`Source`, `ResearchEvent`,
  `fact`), `facilitation/converse.py`, `workspace/topics.py` (`research.json`), `web/local.py` (`local_found`),
  `web/app.py` (~190 LOC)
- Tests: 28 contract tests of the slice-tester (`tests/contract/research_quick/`, seven questions answered); no sealed
  test of an earlier slice changed (742 passed); new smoke `tests/smoke/test_e2e_local.py` part 3
- Live: `tests/live/test_research_live.py` — `.engine/artifacts/spikes/research-quick-live-2026-10-25T084129Z.txt`:
  the owner's #17 → searched (2 queries, 2 sources), market timelines + one question, two `fact` items; #25 → no search;
  the Škoda price → 32 840 € with 4 sources. `llm_call`: #17 180.9 s, 5 668 + 579 tokens; #25 65.5 s; price 189.4 s,
  `attempts: 3`
- Surprises: search answers took 3 min (the spike of 25.10: 25–44 s) — recorded, no threshold (P4); on #25 the model
  put a fact about the person (not found) into the map as `fact` — the rule's text is sealed in this slice; the next
  slice that touches the rules (S2) words it: «fact» only for what was found
- Open for next slice: S1b — unwrap Google's redirect links (the line and `research.json` keep them for now), show
  Search suggestions; S1 is not deployed before S1b

## Slice 18 — research-display (DONE 2026-10-25) — task 303, feature research-in-conversation S1b

- Module: `platform/links.py` (`resolve_link`, `httpx_head`), `platform/llm.py` (`resolve_sources`, `VertexLlm(resolve)`,
  `make_llm` wires it with search), `workspace` (`ResearchView`, `TopicView.research`), `web/text.py` (`turn_html`),
  `topic.html` (links, `iframe srcdoc` with `<base target="_blank">` + Google's HTML), `style.css`; `httpx` declared
  (~110 LOC)
- Tests: 24 contract tests of the slice-tester (`tests/contract/research_display/`, two questions answered); new guard
  `tests/test_a3_httpx.py`; 768 passed, no sealed test changed
- Probe: `.engine/artifacts/spikes/research-display-probe-2026-10-25/probe.out` — Google's chips have no `target`
- Live: `.engine/artifacts/spikes/research-display-live-2026-10-25T091556Z.txt` — #17: 4 sources, all real pages
  (jobbers.io, kudiso.de…), 0 Google links left; the page: 4 `<a href>`, the frame after #18; `llm_call` 46.5 s
  (#17), 9.0 s (#25, no search), 30.4 s (price, 3 queries)
- Surprises: the same calls took 3 min an hour earlier — Vertex's own latency varies; recorded only (P4)
- Open for next slice: S2 — «answer»; the rule's line «fact — only what was found» (S1 finding)

## Slice 19 — fact-answer (DONE 2026-10-25) — task 303, feature research-in-conversation S2

- Module: `facilitation/answer.py` + `answer.md` (one streamed call with search, no card), `facilitation/settle.py`
  (settle, sources line, research event, frame — moved out of `respond.py`, no change of behaviour), router action
  `answer` (`route.py`, `router.md`: the item and «В "ask" не питай… фактів про світ»), `converse.py` branch,
  `types.py` (`FactAnswer`, `FactUpdate`, `Decision.kind` + `answer`), `research.md` + «fact — лише для знайденого»,
  `scripts/card_conversations.py` (`answer` = роутер) (~140 LOC)
- Tests: 18 contract tests of a fresh slice-tester (`tests/contract/fact_answer/`; the first hand-in was not recorded and its tests were written with the code present — replaced; three questions answered); 786 passed
- Live: `.engine/artifacts/spikes/fact-answer-live-2026-10-25T095155Z.txt` — the Škoda price as a first turn →
  `answer`: 32 840 € with 3 real sources and a `fact`; router 14.3 s + answer 16.9 s; a job dilemma → `offer` (PR-18
  verified)
- Surprises: none
- Open for next slice: S3 — `deep_question` (also in `FactAnswer`), the cycle in `settle`'s neighbourhood

## Slice 20 — research-deep (DONE 2026-10-25) — task 303, feature research-in-conversation S3

- Module: `facilitation/deep.py` + `deep.md` (plan → parallel searches in the caller's context → report; facts made
  map items by code), `deep_field.md` (the `deep_question` rule, facilitator under the router only), `research.md`
  (+ the offer sentence), `router.md` (+ agreement → `answer` with `deep_question`), `respond.py` (routed schemas with
  `deep_question`, `_Asked`), `converse.py` (`deep_answer`), `route.py` (`deep_question`, trimmed), `types.py`
  (`DeepPlan`, `DeepReport`, `clean_question`), `platform/llm.py` (`search_text`, `search_script`), `web/local.py`
  (`local_search`) (~260 LOC)
- Tests: 34 contract tests of the slice-tester (`tests/contract/research_deep/`, seven questions answered in the
  ledger reply below); 820 passed, no sealed test changed
- Live (AC3): `.engine/artifacts/spikes/research-deep-live-2026-10-25T110340Z.txt` — «Так, досліди.» under the card →
  4 sub-questions, 12 queries, a report with local sources ending in one question, `fact` items; 104.6 s;
  ≈ $0.31 ($0.145 model + $0.168 search beyond the free 5 000/month); shown = recorded
- Surprises: the facilitator said «Починаю дослідження…» and the plan's intro said it again — two lines of the same
  meaning; the planning took 4+4+3 critic rounds (each a new defect)
- Open for next slice: S4 — the owner's conversation #16–#30 again, before and after; deploy through Сонько; the
  deep run through the deployed service (SSE silence ~100 s)
- Answers to the tester's questions (no test waited on them): plan/search/report systems carry
  `language_rule` under «# Мова відповіді»; suggestions — the last non-empty in sub-question order; findings headed
  by their sub-question; queries collapsed; a blank `deep_question` is None with any action; locally `search_script`
  is passed always; the separator goes into both stream and reply only after text
