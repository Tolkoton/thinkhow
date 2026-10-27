# notes-readers — behaviours beside the sealed contract

- **B-live** (`self-added`, 2026-10-27): the web app's facilitation reads the current revision of the Knowledge on
  every reply: `respond` takes `knowledge.now()` once per reply; the app's `LiveKnowledge.now()` lists the newest change
  record and rollback once (`knowledge.latest_pair`, two listings) and reads the Knowledge again only when they are
  newer —
  so the notes S3 writes and the owner's rollbacks reach the router and the facilitator at once.
  - Observed: `web/app.py` read `knowledge.current` once at start (`functools.partial(respond, knowledge=current)`),
    so a synthesizer change or a rollback acted only after the next restart of the service, while M2 S6 says «відкат
    діє одразу». Not visible at planning: the contract spoke of what the readers read, not of when the app reads it.
  - A revision with other cards (`job cards`) is not taken: new cards still come with a restart, as the sealed
    block tests `test_ac6_…` (thinking-models-router, product-thinking-pack) and the method captions expect.
  - Within the seam and «Out of scope»: the readers' instructions are unchanged; only the moment of reading is.
  - Overseer BLOCK #1 (20261027T214157Z-023d21): the first form re-listed on every field read (54 listings a reply
    with 25 notes, fields of one reply from two revisions) → one `now()` a reply, a plain snapshot.
  - Test: `tests/web/test_live_knowledge.py` (one listing a reply with 25 notes, one revision a reply).
