# notes-readers — behaviours beside the sealed contract

- **B-live** (`self-added`, 2026-10-27): the web app's facilitation reads the current revision of the Knowledge on
  every reply — again only when a newer change record or rollback is listed (`knowledge.latest_pair`, two listings) —
  so the notes S3 writes and the owner's rollbacks reach the router and the facilitator at once.
  - Observed: `web/app.py` read `knowledge.current` once at start (`functools.partial(respond, knowledge=current)`),
    so a synthesizer change or a rollback acted only after the next restart of the service, while M2 S6 says «відкат
    діє одразу». Not visible at planning: the contract spoke of what the readers read, not of when the app reads it.
  - A revision with other cards (`job cards`) is not taken: new cards still come with a restart, as the sealed
    block tests `test_ac6_…` (thinking-models-router, product-thinking-pack) and the method captions expect.
  - Within the seam and «Out of scope»: the readers' instructions are unchanged; only the moment of reading is.
  - Test: `tests/web/test_live_knowledge.py`.
