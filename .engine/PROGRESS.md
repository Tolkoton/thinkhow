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

## Slice 21 — research-live (DONE 2026-10-25) — task 303, feature research-in-conversation S4

- Files: `tests/live/test_research_owner_live.py` (helpers `owner_turns`, `start_map`, `evidence` + the live run); no
  product code
- Tests: 9 contract tests of the slice-tester (`tests/contract/research_live/`, five questions)
- Live: `.engine/artifacts/research-live/2026-10-25T112606Z/conversation.md` — the owner's #17–#29 verbatim after his
  #1–#16 (map cut to turns ≤ 16, no `routing.json`): all 7 answered; #17, #19, #23, #25, #27 — the router offered ways
  to think (no fact asked of the person, no search), #21 «якби я знав… чи треба мені фасилітатор?» — `answer` with 3
  queries and sources (freelance 1–4 weeks, micro-SaaS 14–90 days, Mittelstand months), #29 — `ask`
- Surprises: replayed verbatim, the owner's turns never choose an offered way, so the router offers again on every
  turn; the router answers by search only when the turn is a question of fact (#21), not on «Як це можна взнати?»
  (#17) — a finding for the owner, not changed here
- Open: deployment through Сонько; the deployed deep run (SSE silence)
- S4 rerun after the overseer's PASS (its two test gaps closed in the live test: I1 asserted, every check after the
  artifact): `.engine/artifacts/research-live/2026-10-25T113539Z/conversation.md` — all 7 answered, I1 held; this time
  #21 also `offer`, no search on any turn → the router path does not meet AC1; probe and slice S2b `router-unknown-fact`

## Slice 22 — router-unknown-fact (DONE 2026-10-25) — task 303, feature research-in-conversation S2b (added after S4)

- Module: `facilitation/router.md` — one rule under «Правила»: the person does not know a fact about the world or asks
  how to find it → `answer` (the system searches); facts about the person — not `answer`
- Tests: builder's `tests/router_unknown_fact/test_ruf_rule.py` (RED before the line, GREEN after); 845 passed
- Probe: `.engine/artifacts/spikes/router-unknown-fact-2026-10-25/` — without the rule `offer` 12/12 on #17, #19, #21,
  #25; with it `answer` 8/9 on #17–#21, #25 `offer` 3/3
- Router set: before `.engine/artifacts/router-eval/2026-10-25T114855Z.md` 83/85 first (held-out 18/18), after
  `…120636Z.md` 84/85 (18/18); no situation fell, no `answer` in the set; the one confusion after
  (`wrap-decision → reversible-doors`) was there before
- Live S4 again: `.engine/artifacts/research-live/2026-10-25T120515Z/conversation.md` — #17 → `answer` with search
  (2 queries, sources); #19, #21 → `offer` (n = 1; the probe gave #19 2/3); #25 → the person chose a way, the card led
- Open: the owner judges #19/#21; no further change without his word

## Slice 23 — delete-topic (DONE 2026-10-25) — task 204, one slice without /plan-slice (as task 203)

- Modules: `platform/storage.py` — `Storage.delete(bucket, path)` (Local: unlink, Gcs: blob.delete; a missing file is
  no error); `workspace/topics.py` — `delete_topic(storage, user, ref)`: own topics only (the owner too), every file
  under `<uid>/<topic_id>/`, `conversation.md` last; `web/server.py` — `POST /topics/{uid}/{topic_id}/delete` → 303
  to `/`; `web/templates/delete.html` — `<details>` «Видалити» → one confirmation «Так, видалити», included in the
  home list (own topics) and on the own topic page
- Tests: `tests/web/test_delete_topic.py` (14: storage, workspace, web, the guard «only workspace/topics.py deletes,
  only in users»)
- Screens: `scripts/screenshots_delete_topic.py` → `.engine/artifacts/delete-topic/` (4 PNGs + `run.txt`: files before
  and after)
- Not done (decided): observations of the nightly learning stay in `system/learning/observations/` (the web account
  cannot write `system`); no «restore» — the bucket's versioning keeps the deleted files as old versions

## Slice 24 — send-stops-recording (DONE 2026-10-25) — task 206, one slice without /plan-slice (as tasks 203, 204)

- Module: `web/static/conversation.js` — `createRecorder` exposes `busy()` (from `start` until the text came or the
  recognition failed, the gap between `stop()` and the recorder's `stop` event included); `attach` routes «Надіслати»
  to `recorder.stop()` while the microphone is busy (a no-op while recognizing), so nothing is sent and the
  «Порожню репліку не надіслано.» refusal never comes; the next press sends the field
- Tests: `tests/web/send_stops_recording.test.mjs` (4, `node --test`) via `tests/web/test_send_stops_recording.py`
- Browser: `scripts/smoke_test_send_stops_recording.py` (fake microphone) → `.engine/artifacts/send-stops-recording/`
  (`browser.txt`, 2 PNGs, `red.txt`)

## Slice 25 — product-cards (DONE 2026-10-25) — task 307, feature product-thinking-pack S1 (tracer)

- Content: 7 cards `cards/{customer-interviews,demand-test,positioning,offer-design,value-pricing,traction-channels,
  unit-economics}.yaml` from `docs/research/04-product-pack.md` §3; boundaries added to `when_no` / `pairs_well` of
  `jobs-to-be-done` and `opportunity-tree`; 34 router cases of the new cards in `tests/fixtures/routing/cases.yaml`
  (commit 6ed9740, before the cards), old `ot-2` gets `demand-test` in `also_ok` (`# 307`)
- Tests: 21 contract tests by the independent slice-tester (`tests/contract/product_cards/`, sealed); sealed tests of
  cards-library, router-eval, skel-knowledge changed only by objection (`test_wrong`); `test_ntm_methods.py`, the
  detector of `tests/live/test_router_live.py`, `scripts/smoke_test_cards_library.py` (25), `router_eval.py` and the
  live test's card count follow `cards/`
- Smoke: `scripts/smoke_test_product_cards.py` PASS on the first answer —
  `.engine/artifacts/spikes/product-cards-router-live-2026-10-25T221243Z.txt`: 25 cards, `offer` with
  `offer-design`, `jobs-to-be-done`, `demand-test` on the owner's t-84d1517cb1c1 #1 (`gemini-4-argon`, `eu`)
- Surprises: two YAML list items with «: » parsed as mappings — quoted
- Open for next slice: S2 product-router-eval (runs 1–2, live conversations, AC4/AC5 test of the 7 new cards)

## Slice 26 — product-router-eval (DONE 2026-10-25) — task 307, feature product-thinking-pack S2

- Module: `scripts/router_eval_compare.py` — `compare` (old cases per case against the base: regressions, fixed,
  missing, unavailable outside the denominators, `ot-2` changed expectation; new cases by card, held-out apart, hard
  negatives), `render` → `<X>.compare.md`, `shares` / `summary_table` → `repeats/summary.md` (side = folder)
- Runs: run 1 `.engine/artifacts/router-eval/2026-10-25T224739Z` (25 cards, 119 cases): 116 of 119 first; new 23 of
  23 first, held-out 7 of 7, no hard negative broken; old 82 of 85 (base 83): `fw-3` changed, `fw-2`, `wr-1` as in
  the base. No confusion on a new card → no card edit, no run 2
- Repeats ×5 (`repeats/18/` on 6091f88, `repeats/25/`): `fw-3` 2/5 → 4/5, `wr-1` 4/5 → 2/5 (the same three old cards
  offered on both sides, only WRAP/doors order changes), `fw-2` 5/5 → 5/5, `ot-2` 5/5 → 5/5
- Conversations: `.engine/artifacts/card-conversations/2026-10-25T224310Z/` — 7 of 7 offered, chosen, all phases,
  `end: done` in 6–7 turns of the person
- Tests: 24 tests by the slice-tester in `tests/contract/product_router_eval/` (two hand-ins refused on RED: I3 has
  no code and two AC tests read artifacts measured before the tests — escalation AUTONOMOUS 2026-10-25T23:20Z; the
  files stay unsealed, all green); 11 block tests `tests/contract/product_thinking_pack_block/` (sealed, all green)
- Surprises: the contract put I3 into a test helper; measurement before tests made RED impossible — next time a
  measuring slice runs its live steps after the tester's hand-in

## Slice voice-synthesis — S1 of voice-conversation-mode, tracer part 1 (DONE 2026-10-27)

- Module: `src/thinkhow/platform/tts.py` (port `Tts`, `CloudTts` — Cloud TTS `eu`, Chirp 3 HD / Gemini-TTS by
  language, `ScriptedTts` with 1 s silence MP3), `src/thinkhow/workspace/speak.py` (`speak`, `has_voice`), route
  `POST /speak`, `data-voice` on the reply form; `_retry.retryable` knows `httpx.HTTPStatusError` 429/5xx
- Tests: 48 by the slice-tester in `tests/contract/voice_synthesis/` (sealed; Q1, Q2 answered `taken`), all green;
  full suite 1010 passed; ruff, mypy, import-linter clean
- Live: `tests/live/test_tts_live.py` — uk-UA 16 224 B in 1.21 s (Chirp 3 HD), ka-GE 23 616 B in 5.15 s (Gemini-TTS)
  (`.engine/artifacts/voice-synthesis/live-*.txt`)
- Smoke: `scripts/smoke_test_voice_synthesis.py` — `data-voice` yes/no by language, `/speak` 200 `audio/mpeg` / 409
  (`.engine/artifacts/voice-synthesis/smoke.txt`)
- Surprises: Gemini-TTS takes at most 4000 bytes and gives 502 already at ~3900 (`gemini_limit.out`) — the limit is
  4000, the client sends ≤ 1000 bytes; `tests/web/test_current_model.py` passed `cards` by position — now by name
- Open for next slice: S2a — the loop in the browser

## Slice conversation-loop — S2a of voice-conversation-mode, tracer part 2 (DONE 2026-10-27)

- Module: `src/thinkhow/web/static/conversation.js` — `createSilenceDetector` (RMS, calibration on the minimum of
  300 ms, threshold max(0.02, 3×noise), 1.6 s of silence, 14.5 min cap), `splitSentences` (≤ 1000 bytes UTF-8),
  `createTalk` (listening → hearing → thinking → speaking, half duplex, one AudioContext and one mic stream per mode),
  `attachTalk`; `createController.send(text, fields)`; button `#talk` (icon, CSS states)
- Tests: 42 by the slice-tester in `tests/contract/conversation_loop/` (sealed; Q1, Q2, Q4 `taken`; one objection
  ruled `test_wrong`: helper and wrapper names collided with cards_library); full suite 1060 passed
- Smoke: `scripts/smoke_test_conversation_mode.py` (stand `scripts/talk_harness.py`) — one click, 3 cycles with no
  touch; local doubles: end of speech → voice 1.62–1.67 s (of it 1.6 s is the silence window)
  (`.engine/artifacts/conversation-loop/smoke.txt`); PR-25 verified
- Surprises: the old page test runs conversation.js in a vm without TextEncoder — bytes are counted by code points;
  `tests/web/test_icon_buttons.py` lists the topic page's buttons — «Режим розмови» added
- Open for next slice: S2b (resilience), S3 (spoken replies), then the live check

## Slice spoken-replies — S3 of voice-conversation-mode (DONE 2026-10-27)

- Module: `src/thinkhow/facilitation/listening.md` + `language.listening_rule`; the section «# Людина слухає» right
  after «# Мова відповіді» in the facilitator, router, fact answer and deep cycle instructions, only with
  `FacilitationContext.spoken`; `workspace.reply/retry(..., spoken)`; `/reply`, `/retry` take the form field `spoken`
- Tests: 16 by the slice-tester in `tests/contract/spoken_replies/` (sealed; Seam 1 oracle — the 42 strings of
  commit cefcb02); full suite 1090 passed
- Live (PR-26 verified): `.engine/artifacts/spikes/spoken-replies-live-2026-10-27T113010Z.txt` — offer in words
  «перший… другий… третій», sources «за даними AutoScout24… ADAC», «Ми обрали метод WRAP, і перший крок…»
- Smoke: `scripts/smoke_test_spoken_replies.py` — with `spoken=1` every system instruction has the section, without
  it none (`.engine/artifacts/spikes/spoken-replies-smoke-2026-10-27.txt`)
- Surprises: none
- Open for next slice: S2b (resilience), then the live check of the whole mode

## Slice conversation-resilience — S2b of voice-conversation-mode (CODE COMPLETE — BLOCKED 2026-10-27)

- Module: `conversation.js` — `voiceText`, `stableText` (I4 prefix property), `createEarcons`; recognition miss → tone
  and listen (3 in a row stop), one automatic `/retry` (not on 409), skip a sentence that cannot be voiced, Wake Lock,
  microphone reopen, sound resume + `#talk-resume` (icon button, task 207's rule)
- Tests: 48 by the slice-tester in `tests/contract/conversation_resilience/` (sealed), all green; smoke
  `scripts/smoke_test_conversation_resilience.py` green (`.engine/artifacts/conversation-resilience/smoke.txt`)
- Blocked: 3 sealed conversation-loop tests encode the old «any error stops» rule; the objection would be that slice's
  third round, so it is parked — board 718 and question 1 of task 308 (the owner's answer)
- Live acceptance of the whole mode (AC5): `.engine/artifacts/conversation-mode/live-2026-10-27.md` — 6 turns uk-UA
  and 6 pl-PL with no touch; latency 15–24 s (uk) and 30–87 s (pl), almost all of it the model

## Slice knowledge-versions — S1 of learning-loop, tracer part 1 (DONE 2026-10-27)

- Module: `src/thinkhow/knowledge/versions.py` (`apply_memory` with the version check — ids, cards, budget,
  `vet`; `rollback`; `changes`), `store.py` (`current_paths`/`read_history`/`apply_rollbacks` — the rollback rule by
  provenance, `n` in the revision; `publish` builds memory from the current state), `schema.py` (`audience`,
  `ChangeRecord.observations/by/replaced`, `Rollback`), `src/thinkhow/learning/vet.py` (`vet_with`, `measure`)
- Tests: 47 by the slice-tester in `tests/contract/knowledge_versions/` (sealed; Q1–Q6 answered `taken`; objection
  round 1 `test_wrong`: a typed helper instead of two type-ignores); sealed skel-knowledge and cards-library green
- Live: `tests/live/test_vet_live.py` — the person-details check refuses «Олена з Львова… 3000 €», passes the
  general note (`.engine/artifacts/knowledge-versions/vet-live.txt`, PR-32 verified)
- Smoke: `scripts/smoke_test_knowledge_versions.py` — 25 cards, a note, a rollback, cards byte-for-byte
  (`.engine/artifacts/knowledge-versions/smoke.txt`, PASS)
- Surprises: the 307 block test pinned `src/thinkhow/knowledge` against `82e6213` for ever — objection on
  product-router-eval, bounded to 307's window (`test_wrong`); Vertex gives no `input_token_limit` (PR-31)
- Open for next slice: S2 analysis-rules

## Slice analysis-rules — S2 of learning-loop (CODE COMPLETE — BLOCKED: 21 old sealed tests wait for the owner, 2026-10-27)

- Module: `src/thinkhow/learning/analyze.py` (rules of analysis in `ANALYZER`, several observations a run, state lines
  of the method from `routing.json`, `card_at` by the decision numbers), `src/thinkhow/learning/observations.py`
  (`ObservationSet`, `Observation`, `read_all` of the new and two old shapes), `workspace.topic_routing`,
  `learning/local.py` (new schema)
- Tests: 25 by the slice-tester in `tests/contract/analysis_rules/` (sealed; Q1, Q2 `taken`), green;
  continuous-analysis: objection round 1, 17 `test_wrong` — carried over to the set, green
- Live (AC3, PR-27 verified): `scripts/analyze_owner_conversation.py` → `.engine/artifacts/analysis-rules/
  owner-t-84d1517cb1c1.md` — attempt 1 no (stuck t15, t17 only); attempt 2 after one general edit of the
  instruction: stuck t5, t11, t15, progress t9, t13, card opportunity-tree; the old analyzer — one observation, t18
- Smoke: `scripts/smoke_test_skel_learning.py`, `tests/smoke/test_e2e_local.py` carried over to the set — green
- Blocked (overseer BLOCK #1 20261027T174608Z-f15f28 — the exit criterion asks those tests carried over): 19
  sealed tests of skel-learning and 2 of the walking-skeleton block pin the old single observation; both
  slices used their 2 dispute rounds — `tasks/blocked/720-…`, `721-…` (owner: A — carry over, advised)
- Open for next slice: S3 synthesizer reads `read_all`

## Slice synthesizer — S3 of learning-loop, tracer part 2 (DONE 2026-10-27)

- Module: `src/thinkhow/learning/synthesize.py` (`synthesize` — new observations under aliases o<k>, one call,
  the change through `apply_memory`, the run record last; `runs`; `answer_schema`), `learning/job.py`
  (`synthesize`), `learning/local.py` (three scripted schemas), `src/thinkhow/web/learning.py` + `templates/
  learning.html` (`/learning`: feed, refused, observations; `POST /learning/rollback/{rev}`, owner only), the home
  link `learning_link` in 76 catalogs; `docs/deploy.md` §9a and `docs/deploy-sonko.md` — Scheduler
  `thinkhow-synthesize-daily`; INDEX F12 and the map — daily
- Tests: 56 by the slice-tester in `tests/contract/synthesizer/` (sealed; Q1, Q2 `taken`), green
- Live (PR-29 verified): `tests/live/test_synthesize_live.py` — the owner's 7 observations → 3 notes, citing only
  its input; 200 synthetic → schema accepted (`.engine/artifacts/synthesizer/live.txt`)
- Smoke (tracer, PR-30 verified): `scripts/smoke_test_learning_loop.py` — PASS (`.engine/artifacts/synthesizer/
  smoke.txt`)
- Surprises: pydantic writes `const` for a one-value Literal — the local script reads both
- Open for next slice: S4 — readers must read the current revision on every reply (the app reads it once at start)

## Slice notes-readers — S4 of learning-loop (CODE COMPLETE — 2 old sealed tests wait for the owner, 2026-10-27)

- Module: `facilitation/route.py` (`router` notes as «Досвід:» lines in their cards' sections, the reading rule after
  `CARDS_HEAD` only with notes of a current card), `facilitation/respond.py` (the facilitator's memory — only its own
  card's `facilitator` notes), `converse.py` docstring; self-added B-live (`.engine/slices/notes-readers.behaviors.md`):
  `web/app.py` `LiveKnowledge` — facilitation reads the current revision on every reply (a new card revision still
  waits for the restart), `knowledge.latest_pair`
- Tests: 13 by the slice-tester in `tests/contract/notes_readers/` (sealed; Q2, Q3 `taken`), green; B-live —
  `tests/web/test_live_knowledge.py` (3); objections: spoken-replies round 1 (2 `test_wrong`, the oracle
  `respond|beta|one|…`), knowledge-versions round 2 (`measure` test, `test_wrong`)
- Smoke: `scripts/smoke_test_notes_readers.py` — PASS (`.engine/artifacts/notes-readers/smoke.txt`)
- Blocked: 2 sealed tests of skel-facilitation pin «all memory, no filter by card»; that slice used its 2 rounds —
  `tasks/blocked/724-…` (owner: A — carry over, advised)
- Surprises: three sealed block tests pin `deps.facilitate` as `functools.partial(..., knowledge=…)` and that a
  started service keeps its cards — B-live keeps both
- Open for next slice: S5 starting notes (the router eval with notes)

## Slice starting-notes — S5 of learning-loop (DONE 2026-10-27)

- Content: `notes/<card>.yaml` × 25 — 50 notes (router: typical situations and the neighbour it is confused with;
  facilitator: where people get stuck and how to lead out without a ready answer), from desk research with 64
  sources (`.engine/artifacts/starting-notes/research.yaml`, `sources.md`); unopened sources marked in `basis`
- Module: `knowledge.read_notes`, Job `notes` (`learning/job.py` — adds only ids `notes` never published and no other
  writer holds; one revision through the version check), `scripts/router_eval.py --notes`, `Dockerfile` copies
  `notes/`, `docs/deploy.md` §8a, `docs/deploy-sonko.md`
- Tests: 29 by the slice-tester in `tests/contract/starting_notes/` (sealed; Q1–Q4 `taken`), green
- Job: `.engine/artifacts/starting-notes/job.txt` — rev 2 with 50 notes, a second run nothing; the real person-
  details check (`gemini-4-argon`, `eu`) passes all 50
- Router eval (AC2, PR-28 verified): base 118/119, with notes 118/119; ×5: `jt-3` 4/5 → 4/5, `wr-1` 3/5 → 4/5
  (`router-eval.compare.md`)
- Surprises: `router_eval.py` had old type errors (CountingLlm without `search_text`, the log patch) — fixed
- Open for next slice: S6 step results

## Slice step-results — S6 of learning-loop (DONE 2026-10-28)

- Module: `workspace/steps.py` (`pending_step`, `steps.json` read/write, `step_results_for_learning`),
  `workspace/topics.py` (on a return after a break with a chosen step not asked about: the question as ThinkHow's
  turn `#N+1`, the person `#N+2`, a record `asked_turn`; `recognize` after the answer `#N+3` and before `Answered`, in
  `reply` and `retry`; `TopicView.steps`, `.step_question` for the topic's owner), `facilitation/steps.py`
  (`recognize_step`, one `generate_json`, `StepOutcome` in `facilitation.types`), `web/server.py` (the question in the
  person's language, `Deps.recognize`), `web/app.py`, `templates/topic.html` (block «Кроки», the question line),
  9 words × 76 catalogs, `web/local.py` (scripted recognition), `learning/analyze.py` (the result line before
  `#N+2` without `clearer`, `kind: step`, the rule of analysis)
- Tests: 32 by the slice-tester in `tests/contract/step_results/` (sealed; Q2 `taken`; objection round 1: typed
  helpers instead of type-ignores); analysis-rules objection round 1: `kind` takes `step` (2 `test_wrong`)
- Live: `tests/live/test_step_recognize_live.py` — not_worked, unexpected, «про інше» → not answered
  (`.engine/artifacts/step-results/live.txt`)
- Smoke (the whole cycle, AC7): `scripts/smoke_test_learning_loop.py` — conversation → return after 25 h with the
  question → step result in `steps.json` and «Кроки» → no question again → analyze → synthesize → `/learning` →
  rollback, cards byte-for-byte (`.engine/artifacts/synthesizer/smoke.txt`, PASS)
- Surprises: the question's words live in `web` catalogs, `workspace` cannot import them — `open_topic`/`reply` take a
  `question` callable (the planner's reading of the seam)
