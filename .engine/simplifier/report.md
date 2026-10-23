# Simplifier — findings for the owner

Nothing listed here was removed.

## 2026-10-18T16:34:31Z — architecture, before M4

### confirm (1)
- `F-5c9e6ac2` **.engine/architecture/domain-map.md:120** — invented_requirement: The 'Маршрут' (routes between cards) entity in Знання can probably go. No goal or owner statement asks for it. The same document decides not to plan a route ahead ('одна картка, потім пропозиція наступної'). Neither M2 nor M3 gives it a file, a writer or a module. The lines that would also go are 30, 48, 112, 165, 188 and the glossary row at 259. What stays the same without it: the router still reads cards and memory, and the facilitator still proposes the next card.
  - evidence: read .engine/architecture/domain-map.md:218 'Один маршрут не плануємо наперед: одна картка, потім пропозиція наступної (research 01 L1199)'; read .engine/architecture/architecture-map.md:195-199 The M2 system bucket file table lists knowledge/cards, knowledge/memory, changes, rollbacks and learning. There are no route files.; read .engine/architecture/architecture-map.md:457 M3 knowledge/ package: 'картки (схема pydantic), пам'ять, changes/rollbacks, чинний стан, перевірка версії'. Routes are not in it.; grep .engine/architecture/domain-map.md:120 Outside docs/research, 'маршрут' in the routes sense appears only in domain-map.md. The two hits in architecture-map.md mean web routes.; read .engine/goals.md:19-24 None of G1 to G6, D1 or P1 to P4 asks for card-to-card routes.
  - test safety none, reversal risk medium, protected false, traces to: none found (it comes from the research shortlist, not from a goal line)

### flag_only (3)
- `F-78ff61ee` **.engine/architecture/domain-map.md:70** — invented_requirement: Access as a context does not need to hold the person's language ('мова людини (C4)', also at lines 23 and 45). M2 says C4 does not touch the system level because the facilitator answers in the person's language. M3's CurrentUser is (id, email, is_owner), with no language. C4 stays met without the field.
  - evidence: read .engine/architecture/architecture-map.md:304-306 'C4 … системний рівень не зачіпає: фасилітатор відповідає мовою людини'; read .engine/architecture/architecture-map.md:454 'access/ CurrentUser (id, email, is_owner) і правило «хто власник»; нічого не пише'; read .engine/goals.md:41 C4 only says each user leads sessions in their own language. It does not ask for a stored language setting.
  - test safety none, reversal risk low, protected false, traces to: C4 is cited, but M2 and M3 meet it without Access holding a language
- APPLIED BY THE ARCHITECT `F-275f2714` **.engine/architecture/architecture-map.md:342-347** — duplication: Two of the 'Примітки для M3' notes have been superseded by M3 A3 point 3 and now contradict it, so they can go. Line 342 says Доступ writes the email next to the id; A3 says workspace writes it, 'не access'. Line 346 asks for a test that only the storage module touches the users bucket; A3 says only workspace builds users/… paths. Any change to this rule would otherwise have to be made in two places.
  - applied to the plan 2026-10-18T16:34:45Z: Removed the two superseded M2 notes (access writes email; storage-only test) and pointed them to M3 A3 point 3 — nothing is asked of the owner
  - evidence: read .engine/architecture/architecture-map.md:342-347 'Доступ записує поруч з ідентифікатором людини її email…' and 'тест, що до bucket-а users звертається лише модуль сховища'; read .engine/architecture/architecture-map.md:493-499 A3.3: 'шляхи users/… будує лише workspace … Email поруч з id пише workspace … не access'. It also adds the cross-user read test.
  - test safety none, reversal risk low, protected false, traces to: G4, which M3 A3 point 3 now carries
- APPLIED BY THE ARCHITECT `F-691f0eb5` **.engine/architecture/architecture-map.md:211-215** — duplication: The same decision is stated twice: old versions and soft delete protect against overwriting a file, not against losing the project or a bucket, so a backup is deferred. It appears in S2 here and again under 'Надійність і нагляд' at lines 321-325. The two already differ: S2 says it is deferred together with Q2, while 321-325 cite the owner's decision and task 103. Keeping only the 321-325 statement would leave nothing out.
  - applied to the plan 2026-10-18T16:34:45Z: S2 now points to 'Надійність і нагляд' for the backup decision; the duplicate statement was removed — nothing is asked of the owner
  - evidence: read .engine/architecture/architecture-map.md:211-215 'захищають від випадкового перезапису … але не від втрати всього проєкту чи bucket-а … це рішення відкладено разом із Q2'; read .engine/architecture/architecture-map.md:321-325 'Захист від перезапису, не резервна копія … Рішення власника (2026-10-18): поки що пропускаємо … tasks/proposed/103-backup-before-volume.md'
  - test safety none, reversal risk low, protected false, traces to: Q2 and the owner's decision of 2026-10-18 (task 103)

## 2026-10-18T16:34:31Z — requirements, before M4

### confirm (1)
- `F-4e4653f4` **.engine/goals.md:22** — duplication: The owner's exception in G4 ('Виняток — власник: він читає всі сесії всіх людей… (P3)') states again the rule that P3's example already states at .engine/goals.md:29 ('у першій версії власник читає всі сесії'). The two copies already differ: G4 gives the exception with no condition, while P3 limits it to the first version and says that when the circle widens only sessions the person marked can be viewed. So any change to who-reads-what has to be made in both lines. If G4 only pointed to P3 (for example 'Виняток — власник, за P3'), it would keep its meaning and leave one place to change.
  - evidence: read .engine/goals.md:22 G4: 'Виняток — власник: він читає всі сесії всіх людей, щоб система вдосконалювалась (P3).' Unconditional.; read .engine/goals.md:29 P3 example: 'у першій версії власник читає всі сесії; коли коло розшириться — дивитися можна лише сесії, які людина позначила сама.' Conditional on the first version.; read .engine/goals.md:53 The v2 changelog edited both lines for one decision: 'G4 і приклад у P3: власник читає всі сесії (запит 001)'. The rule was already changed twice once.; read .engine/goals/requests/001.md:49 The owner's single decision 'власник читає все' was carried into two lines.; grep .engine/architecture/architecture-map.md:255 The architecture cites 'G4 v2' for 'власник… бачить усе'. The domain map cites P3 for the same rule (.engine/architecture/domain-map.md:299). Decisions already trace one rule to two lines.; judgement  Chesterton: G4 needs some exception, or it contradicts P3. The duplicate part is the restated content, not the fact that there is an exception. A pointer to P3 is enough. These are the owner's lines, so the most I can propose is confirm.
  - test safety none, reversal risk low, protected true, traces to: request 001 owner decision (.engine/goals/requests/001.md:49); P3
  - validator: protected set to true: the path is in a protected zone

### flag_only (1)
- `F-01fc9baf` **.engine/goals.md:29** — duplication: The second half of P3's example ('коли коло розшириться — дивитися можна лише сесії, які людина позначила сама') settles in advance the item that Q1 at .engine/goals.md:47 lists as still open ('позначки «можна подивитись» самою людиною'). It also concerns a state no current decision covers, since the owner rejected marks for now. Keeping it in one place (the open question Q1) would leave P3's present-day meaning unchanged and remove the conflict between 'decided' and 'open'.
  - evidence: read .engine/goals.md:29 P3 states as decided: after the circle widens, only sessions the person marked can be viewed.; read .engine/goals.md:47 Q1 lists 'позначки «можна подивитись» самою людиною' as an open question for people outside the close circle.; read .engine/goals/requests/001.md:49 Owner: 'більше не треба нічого вигадувати… Без позначок «можна подивитись»'.; grep .engine/architecture/domain-map.md:276 The only architectural mention of the marks records them as rejected by the owner. No decision cites the future-marks clause or Q1 (grep for Q1 in .engine/architecture, docs/adr, tasks/proposed: none).; judgement  Chesterton: the clause says what happens when the circle widens, a future the intro (.engine/goals.md:11-12) does foresee. So it may be wanted back. These are the owner's lines and the state is a future one, so this is flag_only.
  - test safety none, reversal risk medium, protected true, traces to: Q1 (open); no decision cites the future-marks clause
  - validator: protected set to true: the path is in a protected zone

## 2026-10-21T22:50:45Z — walking-skeleton requirements

### confirm (0)

### flag_only (0)

## 2026-10-21T22:50:45Z — walking-skeleton architecture

### confirm (0)

### flag_only (0)

## 2026-10-22T14:24:43Z — code, nightly 2026-10-22

### confirm (0)

### flag_only (0)

## 2026-10-23T16:25:25Z — F13 plan, requirements

### confirm (1)
- `F-a5c66d41` **pyproject.toml:7** — redundant_dependency: The google-cloud-speech dependency can go: the F13 design replaces Chirp 3 / Speech-to-Text v2 with gemini-3.5-transcribe through google-genai, so nothing in src/ or tests/ imports google.cloud.speech. Its only user is the spike probe .engine/artifacts/spikes/voice-stt-2026-10-23/chirp3_probe.py, which cannot run anyway because the API is turned off. The architecture keeps the package only because removing a package needs permission (voice-and-language.md:119-120), and that is a reason to ask the owner, not a reason to keep it. Of the other signals, S-0411a0a7, S-18535cf9 and S-0d4b52d2 are false positives: google-cloud-storage is imported at src/thinkhow/platform/storage.py:115, google-genai at src/thinkhow/platform/llm.py:249, and jinja2 is used through Jinja2Templates at src/thinkhow/web/server.py:19.
  - evidence: signal S-c4ffaf73 pyproject: google-cloud-speech is declared and no module named google_cloud_speech is imported; grep .engine/artifacts/spikes/voice-stt-2026-10-23/chirp3_probe.py:2 the only import of google.cloud.speech_v2 in the repository is in the spike probe; nothing under src/ or tests/ imports it; read .engine/architecture/feature/voice-and-language.md:119 'Пакет google-cloud-speech лишається (прибирання пакета — дія з дозволу; пропозиція в звіті)': the package is kept because removal needs the owner's permission, not because anything uses it; read .engine/architecture/feature/voice-and-language.md:106 S2's real implementation is gemini-3.5-transcribe on Vertex eu through google-genai; the INDEX/architecture-map update replaces 'Chirp 3' with 'gemini-3.5-transcribe, google-genai'; read tasks/doing/106-voice-and-language.md:29 the task says 'google-cloud-speech уже стоїть' (it was added earlier for the Chirp 3 plan) and lets the agent choose dependencies; no line asks for this package to stay; read .engine/architecture/feature/voice-and-language.md:148 Chirp 3 as a second implementation is deferred and only comes back if the owner enables the API; the package can be added again then; judgement  the mypy override for google.cloud.* in pyproject.toml must stay because google.cloud.storage still uses it; only the dependency line goes
  - test safety none, reversal risk medium, protected false, traces to: none found: no goal, owner statement or F13 acceptance criterion needs google-cloud-speech once ADR-0005 replaces the model; C1 (Google only) is met by google-genai

### flag_only (0)

## 2026-10-23T16:25:25Z — F13 plan, architecture

### confirm (1)
- `F-8c53a644` **.engine/architecture/feature/voice-and-language.md:119-120** — redundant_dependency: The plan keeps `google-cloud-speech` even though S2 does speech recognition with `gemini-3.5-transcribe` through `google-genai` and ADR-0005 replaces Chirp 3. The only importer is the spike probe `.engine/artifacts/spikes/voice-stt-2026-10-23/chirp3_probe.py`, so the slice could drop the package (pyproject.toml:7, and the `google.cloud.*` mypy override if nothing else needs it) with no change in behaviour. The plan already defers the removal to the owner as an ask-gated act.
  - evidence: signal S-c4ffaf73 google-cloud-speech is declared and its module is not imported; grep .engine/artifacts/spikes/voice-stt-2026-10-23/chirp3_probe.py:2 the only import of google.cloud.speech_v2 in the repository is in a spike artifact. src/ and tests/ do not import it; read .engine/architecture/feature/voice-and-language.md:106-107 S2's real implementation is gemini-3.5-transcribe on Vertex eu, and line 117 names google-genai as the SDK; read .engine/architecture/feature/voice-and-language.md:148-149 Chirp 3 is deferred. The revisit trigger is the owner enabling speech.googleapis.com, so the package may be wanted back then; read tasks/doing/106-voice-and-language.md:29 the owner's task only notes that google-cloud-speech is already installed. It does not ask for the package to be kept; judgement  Signals S-0411a0a7, S-18535cf9 and S-0d4b52d2 are false positives. google.cloud.storage is imported at src/thinkhow/platform/storage.py:115, google.genai at src/thinkhow/platform/llm.py:15 and jinja2 through fastapi.templating at src/thinkhow/web/server.py:19. The tool mapped dashes to underscores and missed these imports
  - test safety none, reversal risk medium, protected false, traces to: none found: no goal or AC1-AC6 needs Speech-to-Text v2. The tie is the deferred Chirp 3 comparison

### flag_only (0)

## 2026-10-23T22:37:55Z — code, nightly 2026-10-23

### confirm (1)
- `F-d9849f25` **pyproject.toml:7** — redundant_dependency: The google-cloud-speech dependency can go: speech recognition now runs on gemini-3.5-transcribe through google-genai (platform/speech.py), nothing in src or tests imports google.cloud.speech, and ADR-0005 says the package is no longer needed. Behaviour stays the same without it. The only importer left is the archived spike .engine/artifacts/spikes/voice-stt-2026-10-23/chirp3_probe.py, and .engine/architecture/architecture-map.md:523 still lists google.cloud.speech, which would need a one-word update.
  - evidence: signal S-c4ffaf73 google-cloud-speech is declared and no module named google_cloud_speech is imported; grep src/thinkhow/platform/speech.py:11 speech imports google.genai types; no google.cloud.speech import anywhere in src or tests; grep docs/adr/0005-speech-gemini-transcribe.md:61 ADR-0005: the google-cloud-speech package is no longer needed; grep .engine/slices/voice-dictation.md:40 the slice leaves removing the package as a proposal to the owner, so it was kept on purpose until the owner decides; read tasks/done/403-cleanup-2026-10-22/report.md:57 an earlier cleanup kept the deps because the walking skeleton was not built yet. That reason has expired for this package: the speech code exists and uses genai; judgement  Removing a package is ask-gated, so this needs the owner's word. The other three dependency signals are false: google-genai is imported in llm.py, speech.py and _retry.py; google-cloud-storage in storage.py:115 as google.cloud.storage; jinja2 through fastapi.templating.Jinja2Templates at web/server.py:20
  - test safety characterization_exists, reversal risk medium, protected false, traces to: none found: no goal or F13 criterion needs google-cloud-speech once ADR-0005 put gemini-3.5-transcribe in place

### flag_only (1)
- `F-c05ced66` **src/thinkhow/platform/speech.py:91-98** — duplication: speech._text applies the same rule as llm._chunk_text (src/thinkhow/platform/llm.py:189-196): walk response.candidates, take candidate.content.parts when content exists, keep part.text where part.thought is false, and join them. speech only adds .strip(). A change to how answer text is pulled out (for example how thought parts are treated) would have to be made in both places.
  - evidence: read src/thinkhow/platform/speech.py:91 _text: for candidate in response.candidates or []; for part in (candidate.content.parts if candidate.content else None) or []; if part.text and not part.thought: append; join, strip; read src/thinkhow/platform/llm.py:189 _chunk_text: the same loops, the same condition, join without strip; read src/thinkhow/platform/speech.py:3 the docstring says speech retries the way platform.llm does, through the shared platform._retry. The text extraction was copied and not shared
  - test safety characterization_exists, reversal risk low, protected false, traces to: M3 A2 (platform owns the Google SDK); no requirement needs two copies
