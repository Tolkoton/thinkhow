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
