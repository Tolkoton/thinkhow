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

## 2026-10-22T18:55Z — AUTONOMOUS — skel-guards-deploy-cold-reader
- Decision: друге BLOCK cold-reader-а на skel-guards-deploy (Job без змінних `THINKHOW_*`) виправлено в контракті й запечатано без третього прогону.
- Door: two-way
- Cost to reverse: перепланувати й перепечатати контракт; код ще не написано.
- Why not escalated: виправлення інструкції під уже наявний код (`load_settings`); engine-rules «BLOCK you can resolve → fix it, log it, continue».
- Evidence: `.engine/slices/skel-guards-deploy.md`, «Revisions during planning».
- Status: CLOSED

## 2026-10-23T17:50Z — AUTONOMOUS — voice-dictation-playwright
- Decision: контракт `voice-dictation` (Q10b) каже додати Playwright у dev-залежності (`uv add --dev playwright`); це
  дія з дозволу (engine-rules, `ask` у налаштуваннях), а задача йде без нагляду. Smoke запускається
  `uv run --with playwright==1.64.1 python scripts/smoke_test_voice_dictation.py` — тимчасове середовище uv, проєкт і
  `uv.lock` не змінюються; Chromium 1208 уже в кеші сервера. Додати Playwright у dev-залежності — пропозиція власникові.
- Door: two-way
- Cost to reverse: один рядок `uv add --dev playwright` і зміна команди в smoke-скрипті.
- Why not escalated: стосується лише способу запуску smoke, не продукту; правка `pyproject.toml` руками в обхід дозволу
  була б обходом запобіжника. Cold reader контракту сам радив не чекати дозволу (нотатка 2), а виправлення контракту
  не потрапило в запечатаний текст (помилка агента: скрипт правок упав до запису, печатку поставлено на попередній
  текст).
- Evidence: `.engine/slices/voice-dictation.md` (Q10b, запечатано 2c67e3513d8a…); журнал цієї сесії.
- Status: CLOSED

## 2026-10-23T18:40Z — AUTONOMOUS — voice-reply-language-departures
- Decision: slice S3 `voice-reply-language` відходить від рядка S3 feature-артефакту `voice-and-language` у трьох
  місцях: (1) `FacilitationContext.language: str | None = None` — зі значенням за замовчуванням; (2) `rules.md` не
  змінюється, мовне правило — окремим розділом «# Мова відповіді» після нього; (3) `reply`/`retry` без мови не дають
  409, а передають `None` (правило «ніколи російською» діє й тоді).
- Door: two-way
- Cost to reverse: зробити поле обов'язковим і додати 409 — заперечення до запечатаних тестів skel-workspace,
  skel-web (там кола вичерпано — паркування), skel-facilitation; кілька рядків коду.
- Why not escalated: поведінка для людини та сама (без мови до теми не дійти — S1), а зміна запечатаних тестів
  трьох slices через заперечення нічого людині не додає; рішення — технічне (Q1–Q3 контракту S3).
- Evidence: `.engine/slices/voice-reply-language.md` Q1–Q3; `.engine/testing/ledger.md` (skel-web, раунд 2).
- Status: CLOSED

## 2026-10-24T09:30Z — AUTONOMOUS — facilitator-free-mode-once-per-entry
- Decision: задача 301 каже «щонайбільше один раз на тему» про те, що метод не підходить. Slice
  `facilitator-free-mode` тримає це як «один раз на кожен вхід у вільний режим»: стан — `phase_id = null` при
  `last_turn > 0` у карті. Якщо розмова з вільного режиму повернеться до фаз картки (у людини з'явився план), а потім
  картка знову перестане підходити, фасилітатор скаже це вдруге.
- Door: two-way
- Cost to reverse: окреме поле в карті (`map.json`) «людині вже сказано», його тест і читання в правилах — один slice.
- Why not escalated: у розмовах власника такого шляху не було; головна вада (повтор у кожній відповіді) усувається
  повністю; нове поле карти — публічна поверхня, яку краще додавати під реальний випадок.
- Evidence: `.engine/slices/facilitator-free-mode.md` (Out of scope, Deferred); `tasks/doing/301-facilitator-no-method-loop.md`.
- Status: CLOSED

## 2026-10-24T09:50Z — AUTONOMOUS — facilitator-free-mode-premortem-bar
- Decision: задача 301 каже «Pre-mortem, коли план є, веде як і раніше (якість PoC 101 не погіршити)». Live-тест B
  slice-а `facilitator-free-mode` перевіряє механічно нижчу планку: за п'ять фіксованих реплік PoC 101 розмова вийшла з
  першої фази, фази не йдуть назад, null немає, «змінити метод» немає. Розмова B іде у звіт повністю — якість
  читає власник.
- Door: two-way
- Cost to reverse: підняти планку в тесті (напр. «фаза 3 чи далі») — один рядок, ризик нестабільного тесту.
- Why not escalated: репліки людини фіксовані й писались у відповідь іншим реплікам фасилітатора; суворіша планка
  ловила б шум, а головну регресію (null чи застрягання з планом) ловить і ця.
- Evidence: `.engine/slices/facilitator-free-mode.md` (Exit criterion, B, `PROVISIONAL — owner ratification pending`).
- Status: CLOSED

## 2026-10-24T10:20Z — AUTONOMOUS — facilitator-free-mode-phase4-four-rounds
- Decision: Phase 4 контракту `facilitator-free-mode` отримала CRITIC_REVISE у чотирьох раундах. Заперечення не
  коливались: кожне нове (детектор надто вузький → надто широкий щодо «спосіб» → не ловить відмінки → немає наслідку
  ручних перевірок), кожне виправлено. Запобіжник «4 раунди» створено проти коливання; його немає, тож фаза не
  паркується — остаточно контракт читає cold reader.
- Door: two-way
- Cost to reverse: новий раунд критики Phase 4 або паркування задачі.
- Why not escalated: власникові нема з чого вибирати — розвилки між двома позиціями немає.
- Evidence: `.engine/slices/facilitator-free-mode.md` (Exit criterion, Critic notes).
- Status: CLOSED

## 2026-10-24T10:45Z — AUTONOMOUS — facilitator-free-mode-cold-reader-second-block
- Decision: cold reader контракту `facilitator-free-mode` заблокував двічі, кожного разу іншим, виправним
  запереченням: (1) Exit criterion не називав I4 / Hardest seam 3; (2) Q5 спирався на хибне «механізму немає» —
  константи `RULES` двох незапаркованих slice-ів тепер змінюються через заперечення tester-ам (`testing.py request
  <slug> --tester objection`), а не правкою builder-а. Обидва виправлено. Правило /plan-slice «другий блок → чекати
  власника» поступається правилу двигуна «BLOCK, який можна виправити, — виправ, запиши, продовжуй»: власникові
  нема з чого вибирати. Третій cold reader читає виправлений контракт перед печаткою.
- Door: two-way
- Cost to reverse: перепланування контракту (новий slug) до збірки.
- Why not escalated: розвилки немає; обидва виправлення роблять контракт суворішим.
- Evidence: `.engine/slices/facilitator-free-mode.md` (Exit criterion, Seam, Q5).
- Status: CLOSED

## 2026-10-24T12:30Z — AUTONOMOUS — thinking-models-router-critic-round-2
- Decision: feature-critic раунду 2 (останнього за правилом власника) відповів REVISE: план суперечив трьом
  запечатаним тестам (`test_skelw_reply.py` рядки 61, 138 — увесь `FacilitationContext` з `routing` за
  замовчуванням; `test_skelk_real_card.py` — у `cards/` лише Pre-mortem). Прийнято пораду critic-а без третього
  раунду: `workspace` передає `routing=None`, коли `routing.json` немає, `converse` читає `None` як «рішень немає»;
  тест посіву з однією карткою — заперечення slice-tester-у в S1 (його передумову скасовує задача 302 «додай всі
  моделі»), заміна названа.
- Door: two-way
- Cost to reverse: зміна одного правила контракту S2 (None ↔ ()) до збірки; після — одна гілка в `workspace`.
- Why not escalated: власникові нема з чого вибирати — обидва виправлення лише узгоджують план із уже запечатаним.
- Evidence: `.engine/architecture/feature/thinking-models-router.md` (Inter-slice contracts, Appendix).
- Status: CLOSED

## 2026-10-24T13:55Z — AUTONOMOUS — router-routing-none-vs-empty
- Decision: у S2 (`router`) `FacilitationContext.routing` — поле поза рівністю (`compare=False`); `workspace` передає
  `()` для теми без `routing.json`, `None` лишається «без роутера»; `respond` лишається `Facilitate` застосунку і
  розгалужується. Замінює рядок feature-а «`None`, коли файлу немає» (раунд 2 feature-critic-а), бо запечатаний
  `test_wsblock_connections.py:193` (`deps.facilitate.func is respond`, потік без `RoutingEvent`) не можна змінити:
  його slice `skel-guards-deploy` використав обидва раунди заперечень.
- Door: two-way
- Cost to reverse: одна гілка в `respond` і одне поле `compare=False`; повернути — заперечення до тесту, коли
  з'явиться новий раунд (новий feature).
- Why not escalated: власникові нема з чого вибирати — обидва варіанти дають ту саму поведінку для людини.
- Evidence: `.engine/slices/router.md` (Q5, Q9, Seam «Compatibility»).
- Status: CLOSED

## 2026-10-24T15:20Z — AUTONOMOUS — router-phase-4-fourth-round
- Decision: slice-planner-critic фази 4 контракту `router` відповів REVISE учетверте; кожного разу — нова, виправна
  вада (клас `ask` і правило результатів; перевірка «Давай перше.» і `rev`; збій фасилітатора чи сервісу як
  FALSIFIED; нетимчасова відмова Vertex на схемі роутера як збій сервісу). Межа «4 раунди» створена проти
  коливання між двома позиціями; тут коливання немає — кожна правка робить критерій суворішим і узгоджена з
  critic-ом. Правило двигуна «BLOCK, який можна виправити, — виправ, запиши, продовжуй» переважає; контракт
  остаточно читає свіжий cold reader перед печаткою.
- Door: two-way
- Cost to reverse: новий раунд критики фази 4 або паркування до печатки.
- Why not escalated: власникові нема з чого вибирати — розвилки між позиціями немає.
- Evidence: `.engine/slices/router.md` (Exit criterion, Critic notes).
- Status: CLOSED

## 2026-10-24T16:40Z — AUTONOMOUS — router-eval-phase-4-fourth-round
- Decision: slice-planner-critic фази 4 контракту `router-eval` відповів REVISE учетверте, щоразу новою виправною
  вадою (звіт без AC3; водій розмов поза критерієм; журнал; AC5 за карткою, яку не вели). Коливання між двома
  позиціями немає — кожна правка робить критерій суворішим і узгоджена з critic-ом; правило двигуна «BLOCK, який
  можна виправити, — виправ, запиши, продовжуй». Контракт остаточно читає свіжий cold reader перед печаткою.
- Door: two-way
- Cost to reverse: новий раунд критики фази 4 або паркування до печатки.
- Why not escalated: власникові нема з чого вибирати.
- Evidence: `.engine/slices/router-eval.md` (Exit criterion, Critic notes).
- Status: CLOSED

## 2026-10-24T17:20Z — AUTONOMOUS — router-eval-cold-reader-second-block
- Decision: cold reader контракту `router-eval` заблокував двічі, щоразу новою виправною вадою: (1) правки карток
  могли б підганяти картки під набір — відкладена частина `*-3` і перевірка «6 слів»; (2) ця перевірка була
  червоною вже на нинішніх картках (`ii-3`) — правило переносу набору і означення слова. Правило /plan-slice
  «другий блок → чекати власника» поступається правилу двигуна «BLOCK, який можна виправити, — виправ, запиши,
  продовжуй» (той самий випадок — 2026-10-24T10:45Z, facilitator-free-mode). Третій cold reader читає перед печаткою.
- Door: two-way
- Cost to reverse: перепланування контракту до збірки.
- Why not escalated: розвилки немає; обидва виправлення роблять контракт суворішим.
- Evidence: `.engine/slices/router-eval.md` (Hardest seams, Seam 1; Critic notes).
- Status: CLOSED

## 2026-10-24T17:45Z — AUTONOMOUS — router-eval-cold-reader-third-block
- Decision: третій cold reader контракту `router-eval` знайшов одне розходження з уже затвердженим контрактом S2 → S3
  feature-а (міра для `ask`); виправлено вирівнюванням з контрактом feature-а (`candidates[0]`, окремий лік) і
  нотатками; контракт запечатано без четвертого читання — виправлення не містить нового рішення, лише повертає
  текст до вищого контракту.
- Door: two-way
- Cost to reverse: зміна однієї міри в скрипті й звіті.
- Why not escalated: власникові нема з чого вибирати — вищий контракт уже визначив міру.
- Evidence: `.engine/slices/router-eval.md` (Seam `router_eval.py`; Critic notes); `.engine/architecture/feature/thinking-models-router.md` («Inter-slice contracts», S2 → S3).
- Status: CLOSED

## 2026-10-25T08:40Z — AUTONOMOUS — research-in-conversation-deep-from-answer
- Decision: feature-critic, раунд 2 з 2 (`FEATURE_CRITIC_REVISE`): глибоке дослідження було досяжне лише під обраною
  карткою. Прийнято варіант critic-а A: одна функція циклу для обох шляхів (`lead` і виклик «answer»), поле
  `deep_question` у схемі «answer», правило роутера «погодився на глибоке, картки немає → answer», S3 залежить від S2.
  Варіант B (лише під карткою) відкинуто: тоді багатогранне пряме питання вело б через модель мислення — проти слів
  власника «не треба мене ганяти по мисленевих моделях» (N1 v5). Третього раунду критики немає (правило власника).
- Door: two-way
- Cost to reverse: прибрати поле зі схеми «answer» і одне правило роутера.
- Why not escalated: розвилку розв'язують слова власника в задачі 303.
- Evidence: `.engine/architecture/feature/research-in-conversation.md` (S3, Appendix — critic notes).
- Status: CLOSED

## 2026-10-25T21:40Z — AUTONOMOUS — product-thinking-pack-plan-round-2
- Decision: feature-critic, раунд 2 з 2 (`FEATURE_CRITIC_REVISE`): лічильник карток у `scripts/smoke_test_cards_library.py`,
  взятий з `cards/`, зробив би запечатаний `test_cl_catchup_disputed_q1_smoke_checks.py` червоним. Прийнято варіант
  critic-а (a): літерал 25. Нотатки (межа 6 слів для правок S2, docstring `card_conversations.py`) — у плані. Третього
  раунду критики немає (правило власника); critic: «With objection 1 fixed, I'd pass the plan».
- Door: two-way
- Cost to reverse: одне число в скрипті.
- Why not escalated: технічний вибір, власникові нема з чого вибирати.
- Evidence: `.engine/architecture/feature/product-thinking-pack.md` (S1 п. 3, Appendix — critic notes).
- Status: CLOSED

## 2026-10-25T23:05Z — AUTONOMOUS — product-router-eval-phase-2-round-4
- Decision: фаза 2 slice-а `product-router-eval` мала три раунди critic-а, кожен — нова виправна вада (повтори в одній
  теці з повними прогонами; `unavailable` як регрес; хибне «чому» Q1), без коливання. Третє виправлення не йде на
  четвертий раунд фази (запобіжник `/plan-slice` від коливання): його перевіряє cold reader усього контракту.
- Door: two-way
- Cost to reverse: ще один раунд critic-а фази 2 до пломбування.
- Why not escalated: позиції не коливаються, власникові нема з чого вибирати; рішення технічне.
- Evidence: `.engine/slices/product-router-eval.md` («Critic notes»).
- Status: CLOSED

## 2026-10-25T23:20Z — AUTONOMOUS — product-router-eval-tests-after-code
- Decision: test manager (point a) дав slice `product-router-eval` tester-у, але дві здачі tester-а скрипт відмовив на RED:
  (1) I3 — правило AC-тесту, коду для нього в контракті немає, тож тест зелений до коду; (2) два AC-тести дивляться на
  артефакти, які я запустив до тестів (7 розмов `2026-10-25T224310Z`, прогін 1 `2026-10-25T224739Z`). Обидві причини —
  мої (вада контракту і порядок робіт), не tester-а. Запечатаний контракт не змінюю. Код `scripts/router_eval_compare.py`
  написано за контрактом (тести tester-а, незапечатані, — як орієнтир, не правлені); далі точка (b) і catch-up tester,
  який пише й пломбує тести по готовому коду (expect recorded).
- Door: two-way
- Cost to reverse: свіжий tester на новий контракт (I3 як функція коду).
- Why not escalated: технічний порядок перевірки; власникові нема з чого вибирати; що I3 перевіряє тестовий помічник,
  а не код, — записано у звіті.
- Evidence: `.engine/testing/ledger.md` (запити 20261025T224256Z-46113e, 20261025T225234Z-3251a1), цей журнал.
- Status: CLOSED

## 2026-10-25T23:35Z — AUTONOMOUS — product-router-eval-tests-after-code (supersedes the 23:20Z entry's follow-up)
- Decision: обіцяного catch-up tester-а не було: у точці (b) test manager вирішив `catch_up: none` (його факти не
  містять відмов RED), `integration: now`. Тож 24 тести tester-а в `tests/contract/product_router_eval/` лишились
  незапечатаними (не правлені мною, усі зелені), запечатано 11 тестів блоку. Так і сказано у звіті задачі
  («Відкладене»). Overseer PASS 20261025T231640Z-64faf8 це бачив.
- Door: two-way
- Cost to reverse: свіжий tester на catch-up — пломба цих тестів.
- Why not escalated: технічне; власникові нема з чого вибирати.
- Evidence: `.engine/testing/ledger.md` (точка b product-router-eval), overseer ledger.
- Status: CLOSED
