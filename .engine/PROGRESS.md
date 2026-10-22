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
