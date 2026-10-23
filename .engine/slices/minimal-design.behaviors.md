# minimal-design — the builder's notes beside the sealed contract

- Behaviours: the 13 sealed contract tests in `tests/contract/minimal_design/` (tester, contract mode) plus the checks of
  `scripts/screenshots_minimal_design.py` (Seams 1–3). RED before the code: `.engine/artifacts/minimal-design/red-2026-10-23.txt`
  (13 failed); GREEN: `.engine/artifacts/minimal-design/green-2026-10-23.txt` (13 passed).
- self-added: a saved facilitator answer has no blank lines from the template. Observed on the first screenshots: the
  rule `.turn.model { white-space: pre-wrap }`, carried over unchanged (and already in the old inline style), also
  applies to `<article class="turn model">`, so the template's own line breaks around `.who` and `.text` showed as
  empty lines. Not visible at Step 3: no test renders the page. Fix: `article.turn.model { white-space: normal; }` after
  the carried-over rule; `.turn .text` keeps `pre-wrap`, and `#live`'s `<p class="turn model">` keeps it. Checked by the
  script (a saved answer under 200 px high, its `.text` `pre-wrap`).
- The `#send:disabled ~ #pending` rule is written as `#send:disabled ~ .pending` (the same single element).
