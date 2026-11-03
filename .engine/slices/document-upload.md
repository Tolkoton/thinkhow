# Slice document-upload — planning artifact

Driven mode: frame supplied by `.engine/architecture/feature/document-upload.md` (S1, the tracer bullet and the whole
feature); task `tasks/doing/311-document-upload.md`; unattended — nothing asked.

## Goal
Людина на сторінці своєї теми натискає скріпку, обирає PDF, DOCX, TXT чи MD — і в розмові з'являється її репліка
`📎 <назва файла>`, а фасилітатор одразу відповідає потоком, як на повідомлення, маючи перед собою текст документа;
на кожній наступній репліці теми (і після перезавантаження, і через тиждень) модель знову бачить цей текст. Файл, що не
читається або завеликий для платформи, дає повідомлення мовою людини, і нічого не зберігається.
Measurable: contract tests of the seam below green; `scripts/smoke_test_document_upload.py` (real uvicorn in local
mode, real Chromium) prints `OK:` — the button with its `aria-label`, a PDF and a DOCX each give a `📎` turn and an
answer, both stay after reload, an unreadable file shows the message and adds no turn.

## Premise verified
- PR-33 — `pypdf` reads text (Cyrillic too) of a PDF Chromium prints; image-only → empty text; broken →
  `pypdf.errors.PdfStreamError`; encrypted → `pypdf.errors.FileNotDecryptedError` —
  `.engine/artifacts/spikes/document-upload-2026-11-03/spike.out` — 2026-11-03 (pypdf 6.21.4). The spike's files
  `resume.pdf`, `scan.pdf`, `encrypted.pdf`, `resume.docx` lie beside it and may be copied as test fixtures.
- PR-34 — DOCX text is `w:t` inside `w:p` of `word/document.xml`; `zipfile` + `xml.etree` read it — same `spike.out`.
- `python-multipart` 0.0.32 is installed through `fastapi[standard]` (`uv pip list`, 2026-11-03) — FastAPI
  `UploadFile` works without a new dependency.
- PR-35 (the model answers concretely from the document) is the feature's live check AC6, not this slice's exit;
  falsified → only the frame wording changes.

## Out of scope (deliberately)
- Keeping the file's bytes, showing or downloading the file — nobody reads them (P5; see «Deferred»).
- Formats beyond PDF, DOCX, TXT, MD (`.markdown` counts as MD) — the message «не читається» covers them.
- OCR of scans (see «Deferred»); one document for several topics; removing one document from a topic.
- The nightly `analyze` and every learning reader: unchanged, they see the turn `📎 <назва>` only.
- A guard against a ZIP bomb in DOCX (see «Deferred»).

## Seam (contract)
- `thinkhow.platform.documents.extract(name: str, data: bytes) -> str` — the format by the file name's extension,
  case-insensitive: `.pdf` (pypdf, pages joined by `\n`), `.docx` (paragraphs of `word/document.xml` joined by `\n`),
  `.txt` / `.md` / `.markdown` (UTF-8, a UTF-8 BOM dropped; UTF-16 with a BOM). Returns the text with `\r\n`/`\r` → `\n`
  and trimmed edges, never empty.
  - Errors: `Unreadable(reason)`, `reason: Literal["format", "empty", "broken", "encrypted"]` — another extension;
    no text after trimming (a scan); the bytes do not parse (any exception of the parser, a ZIP without
    `word/document.xml`, a DOCX part with a `<!DOCTYPE`, a text file that is not valid in its encoding); a PDF that
    needs a password.
  - Does NOT do: read the content type, OCR, store anything, log the text.
- `thinkhow.facilitation.types.document_turn(name: str, text: str) -> str` — the turn as the model reads it: a header
  naming the document «<name>» the person gave the topic, the text between a begin and an end line, and the ask:
  first what you see in it for this topic (concretely, from the document), then one question. A plain function of
  values.
- `thinkhow.workspace.add_document(storage, facilitate, user, ref, name, data, now, recognize=None, question=None)
  -> Iterator[ReplyEvent]` — eager checks, in this order: `now` has a zone; `_can_write` (else `TopicNotFound`); no
  pending answer (else `PendingAnswer`; a missing topic is `TopicNotFound` when its conversation is read); the name cleaned (`clean_name` below); `extract` (its `Unreadable` passes
  up); the topic's documents together with this one ≤ `MAX_DOCUMENT_CHARS` (else `DocumentTooLarge`). Nothing is
  written before all checks passed. The returned iterator runs `_reply_flow` with the turn text `📎 <name>` and a new
  parameter `document: tuple[str, str] | None` (name, text; `None` for `reply`): the step question on a return (S6) as
  before, the entry `{turn, name, text}` appended to `users/<uid>/<topic>/documents.json` (`name` is `clean_name(name)`), **then** the turn into
  `conversation.md` (Q7a), → `Saved` → the answer (`Delta`…, `Answered` | `Failed`).
  - `clean_name(name)`: the part after the last `/` or `\`, every run of whitespace (newlines too) → one space,
    trimmed; empty → `document`.
  - `MAX_DOCUMENT_CHARS = 200_000` — half of the conversation's reserve of the model window: the window (1 048 576
    tokens, PR-31) is divided in `knowledge/versions.py:29-31` (`BUDGET_CHARS`: the knowledge gets all but 200 000
    tokens, the conversation's reserve), 2 characters a token (PR-31) → 400 000 characters, half to the topic's
    documents. Platform-derived, `PROVISIONAL` (one line to reverse; AUTONOMOUS in `escalations.md`, 2026-11-03).
  - The eager checks mirror `reply`'s (the order above); the rest of the start is `_reply_flow`'s own, not a copy: a
    new session after the break, the S6 question when due.
  - `documents.json` follows `research.json`'s convention: a parse error is not recovered (every reply of that topic
    fails) — accepted knowingly: only this module writes the file, with pydantic.
- `_answer` (every reply, retry and upload of a topic — the one place): reads `documents.json` once into «turn number →
  entries» and gives `facilitate` the history and the current turn (`ctx.text`, also when a retry answers the document
  turn itself) with the text of each **user** turn whose stored text is exactly `📎 <X>` and whose number has an entry
  named `X` replaced by `document_turn(X, text)` of the last such entry; every other turn — and a turn whose number has
  entries but none named as its text says (an orphan entry) — as stored (Q7b). When the turn being answered is a document turn (it has a matching entry),
  `_answer` does not run `recognize`, whether the answer comes from the upload or from a retry: a document is not the
  person's answer to a step question (S6); the step record stays as asked.
- `POST /topics/{uid}/{topic_id}/document`, multipart field `file` → the SSE stream of `/reply` (`saved`, `delta`,
  `answered` | `failed`). Errors as fragments in the person's language: `Unreadable` → 422 `err_document_unreadable`;
  `DocumentTooLarge` → 413 `err_document_too_large`; the existing `TopicNotFound` 404, `PendingAnswer` 409; no
  `file` field → 400 `err_not_accepted`.
- Page: `button#attach.icon` with the paperclip icon, `aria-label` = `ui.upload_document`, between the mic and «Надіслати»,
  and a hidden `input#document[type=file]` with `accept=".pdf,.docx,.txt,.md,.markdown"`; choosing a file posts it
  (the controller's `upload(file)`, the same disable / pending / delta / reload / retry handling as `send`). A file
  over 32 MiB (Cloud Run's request limit, HTTP/1) is not sent: the page shows `js_document_too_large`. An error answer
  whose body is ThinkHow's own fragment (`<p class="error">…`) shows that fragment, as `send` does — so the server's
  `DocumentTooLarge` shows `err_document_too_large`; only a 413 without that fragment (Cloud Run's own page) shows
  `js_document_too_large`.
- Words: `upload_document`; `err_document_unreadable`; `err_document_too_large` — the topic's documents together
  would exceed `MAX_DOCUMENT_CHARS`; `js_document_too_large` — the file exceeds the upload limit (32 MiB); in all 76
  catalogs (`test_every_listed_language_has_every_word_with_the_same_placeholders`).
- Logs: `document_added` (uid, topic_id, turn, format, bytes, chars); `document_unreadable` WARNING (format, reason,
  bytes). Never the name or the text.
- Dependencies (injected): `storage`, `facilitate`, `now`, as `reply`. New package: `pypdf` (pure Python, BSD).

## Decisions (with WHY)
- Q1: the server extracts the text and the model reads text — chosen because one path for all four formats (Gemini
  takes PDF but not DOCX), the facilitation turn stays `(role, text)` so router, facilitator and every fake are
  untouched, an unreadable file is known before anything is saved, and the text stays in the topic for every later
  call. Rejected: the PDF itself as an inline part to Gemini — reads scans too, but DOCX needs a second path, every
  later reply re-sends the bytes through a new kind of turn the facilitation types do not have, and «not readable» is
  learned only after the turn is saved.
- Q2: the text lives in `documents.json`, the turn in `conversation.md` is `📎 <name>` — chosen because the person and
  the owner read `conversation.md` (ADR-0004) and a résumé pasted into it would bury the conversation, and `analyze`
  reading turns gets the name, not the person's material. Rejected: the text inside the turn — the page and analyze
  would show pages of it; a new marker in `conversation.md` — a format change ADR-0004 tests pin.
- Q3: one `documents.json` per topic (appended, as `research.json`) — chosen because the topic's other files follow the
  pattern, one read gives all documents to `_answer`. Rejected: one file per document — a listing per reply for no gain.
- Q4: the frame text is `facilitation.types.document_turn` — chosen because prompts are facilitation's, and workspace
  imports only `facilitation.types` by the existing convention (no import-linter contract enforces it). Rejected: a line in `rules.md` — rules.md is pinned
  verbatim by sealed tests and the golden copies in fakes; the frame in workspace — a prompt in the store layer.
- Q5: extraction in `platform.documents`, called by workspace — chosen because parsing file formats is an adapter like
  storage; web stays a route. Rejected: web extracts and passes text — then a foreign topic is parsed before
  `_can_write` refuses it, and the check order lives in two layers.
- Q7a: the entry first, the turn second — chosen because storage has no transaction (`GcsStorage.write`) and this
  order fails cleanly: if the entry's write fails nothing of the upload is stored (a due S6 question's step record may
  remain, as with `reply`); if the turn's write fails an entry is left with no
  turn — invisible, the person sees `failed`, uploads again, and the new entry usually takes the same turn number (the
  last wins, Q7b); with a due S6 question it is one lower (the step record stays, no question the second time), so the
  orphan sits on a model turn — harmless, Q7b swaps user turns only. Accepted costs: such an orphan's text counts toward `MAX_DOCUMENT_CHARS` (Q6) until the topic is deleted;
  two entries can share a number. Rejected: the turn first — its failure leaves the turn `📎 <name>` unanswered, the page
  offers «Спробуйте ще раз», and that retry answers from the name alone, without the document (breaks the Goal on the
  path the page itself offers).
- Q7b: the swap only on a user turn whose stored text is exactly `📎 ` + the entry's name, the last entry of that number
  with that name winning — chosen because an orphan entry (Q7a, or a race of two tabs) may share its number with the person's next
  ordinary turn, and a swap by number alone would replace their words with the document in every later call, silently.
  Accepted cost: a person who types exactly `📎 <name>` as a plain message at an orphan's number gets the document in
  its place — negligible. Two tabs uploading at the same moment can both pass the size check and together exceed
  `MAX_DOCUMENT_CHARS` (I4 holds for uploads one after another) — accepted, as `reply`'s own race. Rejected: swap by number alone (that); a marker in `conversation.md` (ADR-0004, Q2).
- Q8: a document turn never answers a step question — chosen because the S6 recognizer reads the person's words about
  how a step went; a résumé's text or a file name is not that, and a wrong outcome would teach the learning loop (G3).
  Cost: a step asked right before an upload stays asked without an outcome and is not asked again — as when the person
  skips the question (P6). Rejected: carrying the open step to the next ordinary turn — its best case is a person who
  answers after giving the file, but the recognizer matches only the turn right after the question
  (`asked_turn == turn_no - 1`), so it means a change to S6 itself, beyond this slice.
- Q6: the per-topic limit counts all documents' text — chosen because every document stays in every later call; a
  per-file limit lets two files together overflow the window and the topic answers never again. Rejected: no limit
  (P5) — the platform's window requires it.

## Hardest seams (test-confidence points — distinct from the contract Seam above)
- **Seam 1: real file bytes** — test approach: the spike's real `resume.pdf` (Chromium-printed, Cyrillic),
  `scan.pdf`, `encrypted.pdf`, `resume.docx` as fixtures, plus broken bytes; no mocked parser (a mock would pass with
  pypdf absent or its exceptions renamed). A PDF pypdf cannot decrypt without the `cryptography` package
  (`DependencyError`) is `broken`, not `encrypted` — acceptable, the message is the same.
- **Seam 2: what the model sees later** — test approach: a recording `facilitate` fake; upload, answer, then a plain
  `reply`: the recorded history holds `document_turn(...)` at the document's turn number; an upload whose answer
  `Failed`, then `retry` of that document turn itself: `ctx.text` is the frame (`last.text` is `📎 <name>`); the stored
  `conversation.md` holds only `📎 <name>`; rules out a substitution done once at upload time.
  Two uploads named `resume.pdf` with different texts: each turn number gets its own text in the recorded history.
  An upload while an S6 question is due, its answer `Failed`, then `retry`: `recognize` is not called and the step
  record keeps `outcome=None`.
- **Seam 2b: a write that fails mid-upload** — test approach: a storage fake that fails only one path's write (the
  pattern of `ArmedStorage`, `tests/contract/finish_answer/fin_fakes.py`, made selective by path). (i) The
  `conversation.md` write fails during an upload: the upload's iterator raises that error before `Saved`;
  `documents.json` holds the orphan entry; a plain `reply` next (nothing is pending) — its text reaches `facilitate`
  unchanged (Q7b). (i-b) A separate scenario: the `conversation.md` write fails during the upload of `resume.pdf` with
  text T1, and the very next action uploads `resume.pdf` with a different text T2 (the same turn number N): its answer's
  `ctx.text == document_turn("resume.pdf", T2)`; a variant with an orphan `a.pdf` at N, then `b.pdf` at N: `b.pdf`'s
  frame is used. (ii) The `documents.json` write fails: the iterator raises before `Saved` and `conversation.md` is untouched
  (pins Q7a's order). (iii) An entry planted for a turn number whose stored text is an ordinary message — that message
  reaches `facilitate` unchanged.
- **Seam 3: nothing written on refusal** — test approach: snapshot every path under the topic prefix before and after
  each refusal (unreadable, too large, pending, foreign topic, a zone-less `now`); rules out a write before the last check.
- **Seam 4: the page** — test approach: Playwright in the smoke (real input[type=file] with `set_input_files`), not
  a template string match only; a buffer over 32 MiB and a `/document` request answered 413 by `page.route` cover the
  page's two «too large» paths.
- **Seam 5: the limit's edge** — test approach: documents totalling exactly `MAX_DOCUMENT_CHARS` accepted, one
  character more refused (catches `<` for `≤`).

## Invariants (rules that hold for every input of a stated domain)
- **I1** — every reply and retry of a topic gives `facilitate` each document turn of the history (and the current
  turn, when it is a document) as `document_turn(name, text)` of its entry, and every other turn unchanged.
  - Domain: any topic with zero or more documents, any later turn by `reply`, `retry` or `add_document`, including a
    topic where a write failed during an upload and a topic with an entry whose turn holds other text.
  - Source: AC3 «далі в темі пам'ятає документ»; Seam `_answer`; Q7a, Q7b.
  - Broken by: replacing the text only on the upload's own answer; an
    orphan entry swapped into an ordinary turn of the same number; matching an entry by `name` only, so a second
    upload of the same file name gets the first one's text; the first entry of a shared turn number winning.
- **I2** — a refused upload leaves every stored file of the topic byte-identical.
  - Domain: `Unreadable` of every reason, `DocumentTooLarge`, `PendingAnswer`, `TopicNotFound`, a zone-less `now`.
  - Source: AC4 «розмова не ламається»; Seam «Nothing is written before all checks passed».
  - Broken by: appending to `documents.json` before the size or pending check.
- **I3** — `conversation.md` never holds a document's text: the document turn is exactly `📎 ` + `clean_name(name)`.
  - Domain: every accepted file, any name (paths, newlines, empty).
  - Source: Q2; AC3 «видно назву файла».
  - Broken by: writing the extracted text or the frame as the turn.
- **I4** — after any accepted upload the topic's documents (the entries of `documents.json`, matched by a turn or
  not) together hold ≤ `MAX_DOCUMENT_CHARS` characters of text.
  - Domain: any sequence of uploads into one topic.
  - Source: build parameters (the model window); Q6.
  - Broken by: checking each file alone.
- **I5** — a TXT or MD file in UTF-8 (BOM optional) or UTF-16 with a BOM comes back from `extract` as its own text, newlines normalised and edges trimmed.
  - Domain: any non-blank text in UTF-8 (with or without a BOM) or UTF-16 with a BOM, any of the three text
    extensions in any case.
  - Source: Seam `extract`.
  - Broken by: dropping inner whitespace or lines; decoding as Latin-1.

## Exit criterion
- Contract tests of the seam (`tests/contract/document_upload/`) and the I1–I5 tests green; ruff, ruff format, mypy,
  import-linter clean; the interface-language test green with the four new keys in 76 catalogs.
- `scripts/smoke_test_document_upload.py` prints `OK:` — real uvicorn in local mode, real Chromium: screenshot of the
  topic page with `#attach` (no words, `aria-label` set); `resume.pdf` → a `📎 resume.pdf` turn and a model answer;
  `resume.docx` → the same; reload → both turns still there and `documents.json` holds both texts; `scan.pdf` → the
  message `err_document_unreadable` visible and the turn count unchanged; a file over 32 MiB (a `set_input_files`
  buffer; Cloud Run's request limit — a platform fact, not an owner threshold) → `js_document_too_large` visible and no `/document` request sent; a `/document` answered 413 (`page.route`)
  with Cloud Run's own HTML → the same words; a `/document` answered by the server's `DocumentTooLarge` (a topic
  whose `documents.json` already holds `MAX_DOCUMENT_CHARS` characters) → `err_document_too_large` visible; turn count
  unchanged after all three.
- Feature AC7 in this slice: `.engine/architecture/architecture-map.md` A2 gets a row for `platform.documents` (pypdf;
  no double — the same code in local mode) and the topic's files name `documents.json`; `docs/deploy.md` needs no
  change because the image installs from `uv.lock` (`Dockerfile`: `uv sync --frozen --no-dev`) — the report says so
  and carries the ready request text for Сонько.

## Deferred to later slices
S1 is the feature's only slice; «later» here means after this slice inside task 311, or a later feature.
- The live check on `gemini-4-argon` (feature AC6) — why later: it is the feature's acceptance, run after the
  tester's tests are sealed (`scripts/live_document_upload.py`) — revisit trigger: this slice green, before task 311
  moves to `done/`.
- Keeping the file's bytes — revisit trigger: the person or the owner asks to open their file from a topic.
- OCR of scans — revisit trigger: the message «немає тексту» on a real file of a person.
- A ZIP bomb guard for DOCX — revisit trigger: the first person outside the close circle (goals Q1, P3).
- A learning reader of document contents — revisit trigger: an observation that needs the material; it would read
  `documents.json`; today observations cite the document's turn number.

## Open items requiring human decision (if any)
- None.

## Critic notes (non-blocking)
- Local mode's scripted model puts the current turn's text into a map item (`web/local.py`): an uploaded document
  becomes one long map item in local mode only — harmless; the smoke may check that item holds the document's text,
  an end-to-end sign that `_answer` swapped it in.
- The smoke reloads without a follow-up reply; I1 (reply/retry against stored `documents.json`) covers «after reload».
- `MAX_DOCUMENT_CHARS` is platform-derived (a split of the reserve beside `BUDGET_CHARS`) and logged AUTONOMOUS; no
  exit line carries its number. The cold reader suggested the «owner ratification pending» mark; not taken — the value
  follows from `BUDGET_CHARS`, whose own ratification is already pending, and the split is a logged two-way door.
- Critic rounds: phase 2 — 4 (PASS), phase 3 — 4 (the fourth fix applied, then the cold reader; AUTONOMOUS in
  `escalations.md`), phase 4 — 2 (PASS), phase 5 — 2 (PASS); cold reader — 2 (PASS).
