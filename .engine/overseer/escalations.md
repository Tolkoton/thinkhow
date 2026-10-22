# Overseer escalations log

> **History only.** Everything open lives on the task board (`tasks/`) and is closed by moving to `tasks/done/`. This file is only appended to; nothing in it is marked closed, and nothing reads it to learn what is open.

Records every PRODUCT_DECISION / BLOCKER_CLASSIFICATION / DESIGN_FORK /
ADR_RATIFICATION escalation and the human's resolution. Used in the
2-week audit to tune escalation thresholds.

## Entry format

```
## <ISO timestamp UTC> — <category> — <slice slug>
- Question: <text>
- Options offered: <list>
- Recommendation: <overseer's pick + one-line rationale>
- Human chose: <final decision>
- Latency to decision: <minutes/hours>
- Notes: <if human changed mind, if recommendation was wrong, etc.>
```

## Audit signal interpretation (re-read at the 2-week mark)

- **Human waved through immediately, picked recommendation as-is** → next
  time, this class of question can likely be handled without escalation.
  Propose change in audit.md.
- **Human reversed the recommendation** → overseer is over-confident on
  this class. Tune the check prompt; consider weakening the recommendation
  language.
- **Human deliberated long, chose other** → correct escalation, healthy
  use of human time.

---

## Second entry format — AUTONOMOUS two-way-door decisions

The format above has no slot for a decision the AI made itself: every field
(`Human chose`, `Latency to decision`) presumes a human answered. But the engine
rules' verdict routing says a two-way door is *logged here and continued*, not
escalated. A decision with nowhere to be recorded stays open in working memory
and gets re-raised turn after turn, which is a stop wearing a question mark.
Hence this second shape:

```
## <ISO timestamp UTC> — AUTONOMOUS — <item id>
- Decision: <what was decided, in one line>
- Door: two-way
- Cost to reverse: <concretely, what it would take>
- Why not escalated: <which Article 5 test it passes>
- Evidence: <what made this the right call>
- Falsified by: <the observation that would make this wrong>
- Status: CLOSED
```

**CLOSED means closed.** Once an entry exists here, the decision is not an open
question. Re-raising it with the owner is not diligence — it is an illegitimate
stop, because it asks a human to ratify something Article 5 assigns to the AI.
If new evidence genuinely falsifies it, append a NEW entry that supersedes this
one; do not reopen the old one in conversation.

---

## 2026-10-21T23:30Z — AUTONOMOUS — walking-skeleton-wiring
- Decision: composition roots `web/app.py` і `learning/job.py` будують адаптери `platform.storage`/`platform.llm` з `platform.config` і передають аргументами; `workspace` отримує Знання й модель лише як `facilitate` (callable з `facilitation`), не імпортує `knowledge` і `platform.llm`; import-linter з контрактами M3 — з S1, росте з кожним slice.
- Door: two-way
- Cost to reverse: перенести побудову адаптерів в інше місце — кілька рядків у двох файлах і контракт import-linter.
- Why not escalated: технічна деталь у межах M3 (ручний DI, A2/§9.3); не продукт і не one-way door.
- Evidence: feature-critic, раунд 2 (`.engine/architecture/feature/walking-skeleton.md`, «Рішення архітектора»); M3 component diagram не має стрілок workspace → knowledge/llm.
- Falsified by: import-linter вимагає стрілки, якої M3 не має, або власник у огляді M3 вирішить інакше.
- Status: CLOSED

## 2026-10-21T23:30Z — AUTONOMOUS — walking-skeleton-no-htmx
- Decision: кістяк без HTMX (M2 S5, M3 A6 його називали): звичайні форми + ~30 рядків власного JS; потік відповіді — `fetch` POST + `ReadableStream` (EventSource і HTMX sse вміють лише GET).
- Door: two-way
- Cost to reverse: підключити HTMX одним `<script>` і переписати кілька шаблонів.
- Why not escalated: технічний вибір без впливу на продукт; HTMX не в переліку пакетів власника, його копія чи CDN — зайве питання.
- Evidence: feature-critic, раунди 1–2 (примітки про POST-потік і HTMX).
- Falsified by: сторінкам знадобиться часткове оновлення, яке без HTMX дає помітно більше JS.
- Status: CLOSED

## 2026-10-21T23:55Z — AUTONOMOUS — skel-platform-cold-reader
- Decision: друге BLOCK cold-reader-а на skel-platform (фейки повтору мають падати на першому `next()`) виправлено в контракті й запечатано без третього прогону, замість зупинки за /plan-slice («blocks again → stop»).
- Door: two-way
- Cost to reverse: перепланувати й перепечатати контракт власником; код ще не написано.
- Why not escalated: виправлення — уточнення тестів, не продукт і не one-way door; engine-rules «BLOCK you can resolve → fix it, log it, continue».
- Evidence: `.engine/slices/skel-platform.md`, «Revisions during planning»; probe `inspect.isgeneratorfunction(Models.generate_content_stream)` → True.
- Falsified by: overseer на коді S1 знайде, що повтор не працює проти лінивого потоку.
- Status: CLOSED

## 2026-10-22T16:45Z — AUTONOMOUS — skel-facilitation-cold-reader
- Decision: друге BLOCK cold-reader-а на skel-facilitation (два формулювання, що лишилися до Q6: `history` як `platform.llm.Turn`, дельти «як є») виправлено в контракті й запечатано без третього прогону, замість зупинки за /plan-slice («blocks again → stop»).
- Door: two-way
- Cost to reverse: перепланувати й перепечатати контракт; код ще не написано.
- Why not escalated: узгодження тексту з уже ухваленим Q6, не продукт і не one-way door; engine-rules «BLOCK you can resolve → fix it, log it, continue» (як skel-platform-cold-reader).
- Evidence: `.engine/slices/skel-facilitation.md`, «Revisions during planning»; probe cold-reader-а (підклас pydantic ≠ базовому класу).
- Falsified by: тестувальник або overseer знайде ще одне протиріччя Seam і Q6.
- Status: CLOSED

## 2026-10-22T16:50Z — AUTONOMOUS — facilitation-indirect-storage
- Decision: import-linter contract «facilitation stores nothing and knows no person» (S1) gets `allow_indirect_imports = true`: facilitation's own modules still may not import `access` or `platform.storage`, but the M3 chain facilitation → knowledge → platform.storage is lawful.
- Door: two-way
- Cost to reverse: one line in `pyproject.toml`.
- Why not escalated: M3 diagram has both arrows (facil → knowledge, knowledge → storage); the contract meant direct use. The workspace contract stays strict (skel-facilitation Q6).
- Evidence: `lint-imports` 2026-10-22: BROKEN via `thinkhow.knowledge.store -> thinkhow.platform.storage` once facilitation imported knowledge.
- Falsified by: facilitation gains a path that writes through knowledge (knowledge exposes a write function facilitation calls).
- Status: CLOSED

## 2026-10-22T16:55Z — AUTONOMOUS — facilitation-indirect-storage (superseded)
- Decision: the entry facilitation-indirect-storage above is superseded by `docs/adr/0003-facilitation-reads-knowledge-not-storage.md`: `allow_indirect_imports` removed; `ignore_imports` for the one M3 edge `thinkhow.knowledge.store -> thinkhow.platform.storage`.
- Door: two-way
- Cost to reverse: one line in `pyproject.toml`.
- Why not escalated: overseer ADR_REQUIRED (request 20261022T164551Z-90467c) on a reversible decision → ADR and continue.
- Evidence: `lint-imports` → 6 kept after the change.
- Status: CLOSED

## 2026-10-22T17:10Z — AUTONOMOUS — skel-workspace-cold-reader
- Decision: друге BLOCK cold-reader-а на skel-workspace (нормалізація відповіді фасилітатора не названа) виправлено в контракті й запечатано без третього прогону, замість зупинки за /plan-slice.
- Door: two-way
- Cost to reverse: перепланувати й перепечатати контракт; код ще не написано.
- Why not escalated: уточнення поведінки в межах уже ухваленого правила нормалізації, не продукт; engine-rules «BLOCK you can resolve → fix it, log it, continue» (як skel-platform, skel-facilitation).
- Evidence: `.engine/slices/skel-workspace.md`, «Revisions during planning»; `respond.py` без нормалізації.
- Falsified by: тестувальник або overseer знайде ще одну неназвану поведінку в цьому ж місці.
- Status: CLOSED

## 2026-10-22T17:35Z — AUTONOMOUS — skel-web-wording
- Decision: тексти, які бачить людина в кістяку (помилки «Тему не знайдено.», «Спершу дочекайтеся відповіді або натисніть «Спробуйте ще раз».», «Порожню репліку не надіслано.», «Щось пішло не так — спробуйте ще раз.», «Потрібно увійти через Google», підписи кнопок і сторінок), пише агент.
- Door: two-way
- Cost to reverse: рядки в шаблонах і одному обробнику помилок.
- Why not escalated: власник вирішив «спершу прототип» (задача 105) і відклав дрібниці до знайомства з ним; слова — не продуктове рішення.
- Evidence: `.engine/slices/skel-web.md`, Seam; critic note 4.
- Status: CLOSED

## 2026-10-22T17:55Z — AUTONOMOUS — skel-web-cold-reader
- Decision: друге BLOCK cold-reader-а на skel-web (порожнє поле форми — 422 JSON FastAPI повз один обробник) виправлено в контракті (`Form("")`, `RequestValidationError` → 400) і запечатано без третього прогону.
- Door: two-way
- Cost to reverse: перепланувати й перепечатати контракт; код ще не написано.
- Why not escalated: технічна деталь в межах уже ухваленого «один обробник помилок» (M3 A4); engine-rules «BLOCK you can resolve → fix it, log it, continue».
- Evidence: `.engine/slices/skel-web.md`, «Revisions during planning»; probe cold-reader-а (FastAPI 0.159.1, `dependencies/utils.py:906`).
- Status: CLOSED

## 2026-10-22T18:20Z — AUTONOMOUS — skel-learning-cold-reader
- Decision: друге BLOCK cold-reader-а на skel-learning (Seam 2 не досяжний для `run`, що не приймає `llm`) виправлено в контракті (доказ коду 0 через зламаний `conversation.md`) і запечатано без третього прогону.
- Door: two-way
- Cost to reverse: перепланувати й перепечатати контракт; код ще не написано.
- Why not escalated: уточнення тестової досяжності вже ухваленого Q3; engine-rules «BLOCK you can resolve → fix it, log it, continue».
- Evidence: `.engine/slices/skel-learning.md`, «Revisions during planning».
- Status: CLOSED

## 2026-10-22T18:33Z — AUTONOMOUS — learning-identity-edge
- Decision: контракт import-linter «learning needs no identity» отримує `ignore_imports` одного ребра `thinkhow.access.user -> thinkhow.platform.identity`; ADR-0003, Amendment 1.
- Door: two-way
- Cost to reverse: один рядок у `pyproject.toml`.
- Why not escalated: та сама форма, що вже ухвалена в ADR-0003 (один названий виняток, непряма перевірка лишається).
- Evidence: `lint-imports` BROKEN 2026-10-22 18:31 через `thinkhow.access.user -> thinkhow.platform.identity (l.6)`.
- Status: CLOSED
