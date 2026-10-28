# Overseer cross-slice memory

Entries here are added only when a pattern recurs across 3+ slices, OR when
the user has manually ratified a pattern. Empty initially.

## Citation-or-prune rule (load-bearing)

Every entry in this file MUST cite at least two ledger.md entries by
date+slice. Uncited entries are deleted on next read. This prevents
memory pollution and confabulation amplification.

## Source-of-truth pointers

- Project conventions: `CLAUDE.md`
- Slice ledger: `.engine/PROGRESS.md`
- Architectural decisions: `docs/adr/`
- TDD discipline: slice-builder skill
- Overseer ledger: `.engine/overseer/ledger.md`
- Human escalations log: `.engine/overseer/escalations.md`
- Self-improvement proposals: `.engine/overseer/audit.md`

## Cross-slice patterns

## 2026-10-28 — A smoke script asserts each fact its exit criterion names (turn order, the analyzer's inpu

A smoke script asserts each fact its exit criterion names (turn order, the analyzer's input line, the second run's outcome, the artifact path), not only exit codes or the presence of a text; the overseer blocked twice on smokes that printed OK for things they did not check.

Cited: 2026-10-28T00:24:54Z step-results OVERSEER_BLOCK 20261028T002152Z-d47deb; 2026-10-27T20:29 synthesizer catch-up Q1: the second synthesize's outcome (proposed/723). Origin: lesson #1c1279e9 (overseer, notes-readers.behaviors, 2026-10-28).
