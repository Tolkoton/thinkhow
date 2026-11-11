# deep-research-confirm-first — behaviours

The contract tests are the independent tester's (`tests/contract/deep_confirm/`, 42 tests, sealed, decision at
point (a): tester). The builder's list is therefore the tester's hand-in (`.engine/testing/ledger.md`), not repeated
here. Builder-side changes beyond them:

- B-u1 (unsealed, updated): `tests/platform/test_hung_call.py` — the bug-003 proof of the plan's 60 s limit now goes
  through `propose` (contract Q10).
- B-u2 (unsealed, updated): `tests/research_deep/test_rd_gaps.py` — `run_deep` instead of `deep_research`; the rdp
  helpers imported through `importlib` (mypy on the single file).
- B-u3 (deleted): `tests/live/test_research_deep_live.py` — its scenario is gone; AC3 facts covered by
  `scripts/live_deep_confirm.py` (contract Q10).
