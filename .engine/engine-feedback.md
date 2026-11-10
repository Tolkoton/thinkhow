# Feedback for the engine

What the work learned that belongs in the engine's own repository.

## 2026-10-22 — business-analyst skill: ] -: The first conversation never asked which goals are the core; 

business-analyst skill: ] -: The first conversation never asked which goals are the core; the owner had stressed self-learning twice and the architect spread depth evenly. Ask «Якби працювала лише одна з цих цілей — яка

From: lesson #5ada6ca0 (analyst, -, 2026-10-21).

## 2026-10-22 — business-analyst skill: ] -: A goal the owner stated in their first answer (the system kno

business-analyst skill: ] -: A goal the owner stated in their first answer (the system knows when it lacks the right framework) reached no line because the analyst filed the sentence under 'mechanism'. Every clause of an owner's 

From: lesson #a77a2ec4 (analyst, -, 2026-10-21).

## 2026-10-22 — business-analyst skill: ] -: The analyst wrote its own reason into a non-goal (N3 'помилка

business-analyst skill: ] -: The analyst wrote its own reason into a non-goal (N3 'помилка там надто дорога') and a paraphrase in quotation marks into P1; the owner had to catch both. Reasons and quotes in lines must be the owner

From: lesson #9e63ef8d (analyst, -, 2026-10-21).

## 2026-10-22 — business-analyst skill: ] -: After three preseal rounds the owner stopped the analyst: que

business-analyst skill: ] -: After three preseal rounds the owner stopped the analyst: questions about thresholds and mechanisms that only a prototype can answer do not belong at level 0. Before raising a preseal finding, ask whe

From: lesson #60a9c4b0 (analyst, -, 2026-10-21).

## 2026-10-22 — slice-builder Step 5: a smoke script that inserts src into sys.path and then imports think

slice-builder Step 5: a smoke script that inserts src into sys.path and then imports thinkhow gets E402, and the noqa trips the bypass guard; the skill could show the importlib.import_module pattern (scripts/smoke_test_skel_platform.py:16) so builders do not reach for noqa.

From: lesson #e9c935f1 (gate, skel-platform, 2026-10-22).

## 2026-10-22 — slice-tester at point (a): the hand-in is refused at import when the module skeleton is no

slice-tester at point (a): the hand-in is refused at import when the module skeleton is not in the tree, and while the builder writes it and the tester re-hands in, the Stop gate blocks on the expected RED (counting toward GATE_MAX_BLOCKS). The flow could have the builder write the skeleton before the tester is called, and the gate could skip a slice whose hand-in is pending.

From: lesson #e07413f4 (gate, skel-knowledge, 2026-10-22).

## 2026-10-23 — DELETE GUARD treats a function MOVED to another module (llm._retryable → platform/_retry.r

DELETE GUARD treats a function MOVED to another module (llm._retryable → platform/_retry.retryable, as the sealed contract voice-dictation Q5a required, the move covered by tests/contract/voice_dictation/test_vd_catchup_retry.py) as a deletion of untested code and escalates to the owner (task 901). Either recognise a move (same body, new name in the same package, imported back) or let the builder write the test of the new home first and then the guard see it as touched; today the only way through is an owner's «так».

From: lesson #1875bff6 (gate, voice-dictation, 2026-10-23).

## 2026-10-23 — slice-tester can hand in sealed contract tests that carry '# type: ignore' (minimal-design

slice-tester can hand in sealed contract tests that carry '# type: ignore' (minimal-design, test_mdesign_invariants.py:123-125); the gate's bypass guard then blocks every Stop of the builder, who may not edit a sealed file, and the only way out is an objection round (rounds are capped at two). Suggest: the tester runs the gate's bypass guard (and mypy) on its own files before the hand-in, or testing.py record refuses a hand-in whose files add a type-ignore.

From: lesson #ed996fe0 (gate, minimal-design.behaviors, 2026-10-23).

## 2026-10-23 — a parked slice has no way back (testing.py, task 202)

A later, sealed slice contract (continuous-analysis) changes behaviour that an earlier slice's sealed tests pin down
(skel-web expects the «Завершити сесію» button the owner removed). The earlier slice had used its two dispute rounds
long ago for unrelated hygiene, so `request skel-web --tester objection` parks it at once, and nothing in testing.py
un-parks a slice or reseals its tests after the owner's answer. Suggest: count rounds per requesting contract (a new
sealed contract that names the change opens fresh rounds), or give the owner an `unpark <slug>` action-line.

From: task 202, builder.

## 2026-10-24 — After an OVERSEER_BLOCK whose fix touches only tests/ or .engine/ (no file under SOURCE_DI

After an OVERSEER_BLOCK whose fix touches only tests/ or .engine/ (no file under SOURCE_DIRS), the Stop hook does not inject a new OVERSEER_REQUEST on the re-claim (no code changed since the last request), so the unit stays at BLOCK until the builder runs overseer_verdict.py request by hand. Task 302, slice router: BLOCK 20261024T143036Z-d15c39, fix e62d85c (tests/live, PROGRESS), re-audit only through a hand request 20261024T143846Z-64fadd. Suggest: a re-claim of a unit whose last verdict is BLOCK triggers a request whatever path changed.

From: lesson #35b77262 (overseer, router, 2026-10-24).

## 2026-10-27 — The slice-tester added '# type: ignore' to a sealed contract test (a helper typed as objec

The slice-tester added '# type: ignore' to a sealed contract test (a helper typed as object); the builder's Stop gate then refuses the turn on the bypass guard, and only an objection round (scarce: 2 per slice) can fix a sealed file. Suggest: the testing hand-in check (handin_errors) refuses a hand-in whose files add a type-ignore, so the tester fixes the typing before sealing.

From: lesson #f6b535ce (gate, step-results, 2026-10-27).

## 2026-10-27 — The Stop gate ran only the tests named after the changed files, so a new learning/ module 

The Stop gate ran only the tests named after the changed files, so a new learning/ module that broke the project's static write guard (tests/test_a3_guards.py, tests/test_ac4.py — they scan every module) passed the gate and was caught only by the overseer. Suggest: project guard tests that read all sources (a list in project.env, e.g. GUARD_TESTS) run on every Stop where code changed.

From: lesson #23b6f003 (overseer, step-results, 2026-10-27).

## 2026-10-28 — commit_checkpoint.sh takes any first argument as the node id, --help included, and then ru

commit_checkpoint.sh takes any first argument as the node id, --help included, and then runs git add -u, sweeping in the owner's uncommitted changes (happened in tasks 703 and 713). The script should reject an unknown argument starting with '-' (and print its usage on --help) before staging anything.

From: lesson #dec79025 (agent, finish-answer, 2026-10-28).

## 2026-11-03 — The Stop gate type-checks a slice-tester's RED contract tests before the builder's skeleto

The Stop gate type-checks a slice-tester's RED contract tests before the builder's skeleton exists (attr-defined/import-not-found on names the sealed contract promises); the tester's own hand-in is refused for the same reason until a NotImplementedError skeleton exists. Suggest: when testing.py has a pending contract request, the gate skips typecheck of that request's new test files, and the tester's instructions say the builder adds the skeleton first (task 311, 2026-11-03).

From: lesson #d34aa232 (gate, document-upload, 2026-11-03).

## 2026-11-03 — The Stop gate type-checks spike scripts under .engine/artifacts/spikes/ although pyproject

The Stop gate type-checks spike scripts under .engine/artifacts/spikes/ although pyproject's ruff excludes .engine as 'spike and probe scripts, not working code'; mypy has no such exclusion (task 311, 2026-11-03).

From: lesson #95f78217 (gate, document-upload, 2026-11-03).

## 2026-11-10 — testing.py: five old parks stay PARKED and CHANGED; the repeat review comes early

Two things task 707 (the testing review after ten slices) saw in the ledger. (1) skel-web, skel-learning,
skel-guards-deploy, skel-facilitation and conversation-loop still show `seal: CHANGED … ; PARKED` in
`testing.py status`, although the owner answered each park (tasks 708, 718, 720, 721, 724 are in `done/`) and the
builder fixed the tests as told. `supersede` (v0.14.3) un-parks only when a new contract's round runs; for parks
that came before it, nothing clears the mark (the 2026-10-23 entry above). (2) `review_task` counts the slices no
`review_task` row has counted yet. The only row here is 707's (10 slices); engine task 504 reviewed 35 slices but
wrote no row in this ledger. So the next point-(b) decision will lay a repeat review over 27 slices, 25 of them
already in 504's review, and none of them built on v0.14.4. The owner's answer 1А to 504 asked for a review after
10 slices on the updated engine.

From: task 707, review.
