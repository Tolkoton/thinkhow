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
