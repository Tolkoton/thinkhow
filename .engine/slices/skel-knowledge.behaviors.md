# skel-knowledge — the builder's readings of the tester's open questions (no held test)

The sealed contract is not edited; these are the readings the code takes (testing ledger, hand-in 2026-10-22).
- Q2 — refusal means the stored state is unchanged; `seed` checks for a change record before reading `cards_dir`.
- Q3 — «порожня тека» = no `*.yaml` in it → `ValueError`.
- Q4 — `memory` in plain string order of `id`.
- Q5 — a storage failure inside `seed` propagates (nothing swallowed).
- Q6 — «Якщо план і строк уже названо…» of phase 1 is a `how` item, not `skip_if`.
