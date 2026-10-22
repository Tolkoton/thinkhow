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
