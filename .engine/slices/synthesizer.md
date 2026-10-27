# Slice synthesizer — planning artifact

Feature: `.engine/architecture/feature/learning-loop.md`, slice **S3** (F12, стрічка змін F11; tracer bullet, part 2).
Board task `tasks/doing/309-close-learning-loop.md`, unattended. Driven mode: the frame is the feature artifact's S3
entry, contracts S1 → S3 (`.engine/slices/knowledge-versions.md`) і S2 → S3 (`.engine/slices/analysis-rules.md`),
«Build parameters»; nothing asked.

## Goal
Щодня завдання навчання `synthesize` бере спостереження, яких ще не врахувала жодна зміна чи прогін, чинні нотатки і
відкочені зміни, одним викликом моделі виводить зміни нотаток до методів (для роутера і для фасилітатора) і **сам**
вносить їх новою ревізією через перевірку версії S1; власник на сторінці `/learning` бачить стрічку змін з посиланнями
на спостереження і на місця в розмовах, відхилені перевіркою версії, спостереження — і відкочує будь-яку зміну одним
натиском.

Вимірна ціль: (1) контрактні тести поведінок і інваріантів зелені; (2) `scripts/smoke_test_learning_loop.py` (локальний
режим, сценарна модель): репліки в темі → `analyze` → `synthesize` → нова ревізія лише з пам'яттю, `current().memory`
має нотатку → `/learning` показує зміну з посиланням `/topics/…#t<n>` → «Відкотити» → `current().memory` без неї,
`/learning` показує «відкочено»; повторний `synthesize` без нових спостережень нічого не пише; файли `knowledge/cards/`
побайтно ті самі (tracer S1→S2→S3, PR-30); (3) live `tests/live/test_synthesize_live.py` (`gemini-4-argon`/`eu`) на
спостереженнях live-прогону S2 (`.engine/artifacts/analysis-rules/…`): валідні зміни, кожна цитує лише id зі свого
входу, перевірка «без подробиць людей» пропускає (PR-29); (4) ruff, mypy, import-linter, швидкий набір — зелені.

## Premise verified
- PR-29 — `unverified`, перевіряє exit criterion (3).
- PR-30 — `unverified`, перевіряє exit criterion (2).
- Контракти S1, S2 — запечатані slice-контракти (`knowledge-versions`, `analysis-rules`), будуються до цього slice-а.
- Cloud Scheduler кличе `:run` Job-а з `--args` (команда) — так уже працює `analyze` (`docs/deploy.md` §9, розгорнуто
  2026-10-23). Новий розклад — лише інструкція; розгортає власник (Сонько).

## Out of scope (deliberately)
- Самостійний відкат системою (G3) — відкладено фічею.
- Результати кроків — S6 (до синтезатора доходять через спостереження `kind: step`, нічого тут не змінюється).
- Розгортання розкладу — дія власника.
- Мова сторінки `/learning` — українська (M3 A5: «стрічку змін читаєте ви»), не каталог 76 мов.
- Будь-яка зміна карток — синтезатор не має для них виходу (S1 Q5).

## Seam (contract)
- **`learning/synthesize.py`**: `synthesize(storage: Storage, llm: Llm, now: datetime, vet: Vet, measure: Measure)
  -> SynthesisReport(rev: int | None, considered: int, outcome: "applied"|"nothing_new"|"no_change"|"rejected"|
  "failed")`. Потік:
  1. `knowledge.current()`, `learning.observations.read_all()`, `knowledge.changes()`, усі записи прогонів
     `learning/synthesis/*.json`.
  2. `consumed` = id з `observations` усіх записів змін ∪ `considered` усіх записів прогонів; `new` = спостереження
     не з `consumed`. Порожньо → `nothing_new`, жодного виклику, жодного файлу.
  3. Один `llm.generate_json(SYNTHESIZER, [Turn("user", text)], schema, rev_pair)`. Текст: картки (id, метод,
     заголовок — без фаз), чинні нотатки (id, audience, cards, title, noticed, do), відкочені зміни (`rolled_back`
     не None і `rollback_changed` непорожній: що пропонували — `upserted`, `removed`) під заголовком «Відкочено
     власником — не пропонуй знову», нові спостереження — кожне під коротким псевдонімом `o<k>` (k = 1…N за порядком
     `read_all`) з card_id, kind, cause, worked, finding; код тримає відповідність `o<k>` → `Observation.id`.
  4. Схема: `{what: str, why: str, upsert: list[{id: ^[A-Za-z0-9-]{1,64}$, audience: router|facilitator, cards:
     list[enum id карток чинного стану] ≥1, title, noticed, do, observations: list[enum "o1"…"oN"] ≥1}], remove:
     list[{id: ^[A-Za-z0-9-]{1,64}$, observations: list[enum "o1"…"oN"] ≥1}]}` (порожні списки дозволено). Обидва
     `enum` ніколи не порожні: карток ≥ 1 після посіву, а виклику без нових спостережень немає (крок 2). `remove[].id`
     — рядок без `enum` (порожня пам'ять після `seed` дала б порожній `enum`, якого pydantic не будує): id, якого немає
     в чинній пам'яті, відкидає `apply_memory` (S1, перевірка 2 → `rejected`). Псевдоніми `o<k>`, а не повні id, —
     щоб `enum` лишався коротким і на першому прогоні, що бере всю історію спостережень.
  5. Обидва списки порожні → запис прогону `no_change`. Інакше `MemoryChange(what, why, by="synthesizer", upsert=
     [MemoryRecord(..., basis=…)], remove, observations=усі процитовані id)`; `basis` — детерміновано: для наявної
     нотатки — її `basis` + `; спостереження: <id, …>`, для нової — `спостереження: <id, …>` (G6); `<id>` — повні
     `Observation.id`, відновлені з псевдонімів.
  6. `knowledge.apply_memory(storage, change, vet, measure)`: rev → `applied`; `None` → `no_change`;
     `VersionRejected(reason)` → `rejected` з причиною.
  7. Наприкінці — запис прогону `learning/synthesis/<now:%Y%m%dT%H%M%SZ>.json` (`create_if_absent`; ім'я вже є —
     суфікс `-2`, `-3`…) = `SynthesisRun(at, considered: list
     [id усіх new], outcome, rev: int | None, rejected: str | None)`. Помилка моделі (`LlmUnavailable`,
     `ValidationError` — і в `vet`) → `failed`, **запису прогону немає** (наступного дня ті самі спостереження),
     лог `synthesize_failed` (тип помилки). Лог `synthesize_done` (outcome, rev, considered) без тексту.
- **`learning.synthesize.runs(storage) -> list[SynthesisRun]`** — усі записи прогонів за назвою; ним користуються
  крок 1 і сторінка `/learning`.
- **`SYNTHESIZER`** — інструкція українською: ти вчиш ThinkHow з досвіду всіх людей; змінюєш лише нотатки до методів —
  `router` (у яких ситуаціях пропонувати метод, з яким його плутають і як розрізнити) і `facilitator` (коли допомагає,
  де застрягають, як застосувати в типовій ситуації, як вивести із застрягання, не даючи готової відповіді — N1);
  фази, мета й хід методу — стандарт, їх не змінюєш і не переписуєш у нотатках; узагальнюй з кількох випадків, без
  подробиць людей і без цитат; кожна зміна цитує спостереження, з яких зроблена; краще оновити наявну нотатку, ніж
  додати схожу; відкочене не пропонуй знову; якщо спостереження нічого нового не дають — порожні списки.
- **`learning/job.py`**: команда `synthesize` (USAGE `seed|cards|analyze|synthesize`): `synthesize(storage, llm,
  now(), vet_with(llm), measure)`; `learning/local.py` — сценарна відповідь синтезатора в локальному режимі (одна
  нотатка `facilitator` до першої картки з першим псевдонімом з `enum`; локальна сценарна відповідь `vet` — `ok`).
  Розпізнавання, на яку з трьох схем відповідати (аналізатор, синтезатор, `vet`), — за назвою схеми; відповідь
  аналізатора — як до slice-а (smoke skel-learning не змінюється).
- **Сторінка `/learning`** (`web`, лише власник; інший — той самий 404, що й чужа тема, `err_topic_not_found`):
  українською (A5). Розділи: «Стрічка змін» — `changes()` найновіші першими: rev, what, why, by, нотатки
  (`upserted`: audience, картки, title, noticed, do, basis), прибрані id, спостереження зміни — кожне посиланням
  на його `link` (місце в розмові, G6), позначка «відкочено (відкат n)» або «відкочено — нічого не змінено» (порожній
  `rollback_changed`), кнопка-форма «Відкотити» `POST /learning/rollback/{rev}` лише для зміни з непорожнім
  `upserted`/`removed` і без відкату; «Відхилено перевіркою» — записи прогонів `rejected`: час, «відхилено
  перевіркою: <причина>»; «Спостереження» — `read_all()` найновіші першими (`analyzed_at`): kind, cause, card_id,
  finding, посилання.
- **`POST /learning/rollback/{rev}`** (лише власник): `knowledge.rollback(storage, rev, by=user.email, now)` → 303 на
  `/learning`; `AlreadyRolledBack`, `NotRollbackable` → 409 фрагмент, `UnknownRevision` → 404 фрагмент (тексти —
  українською, як сторінка).
- Головна сторінка власника: посилання «Навчання» на `/learning` під `{% if user.is_owner %}` (ключ каталогу
  `learning_link` у всіх каталогах — правило задачі 208: кожне слово інтерфейсу в кожній мові).
- **Документи**: `docs/deploy.md` (новий крок: Scheduler `thinkhow-synthesize-daily` щодня, через годину після `analyze` (зсув
  часу, не залежність: прогін, що перекрився з `analyze`, просто не бачить новіших спостережень), `--args …,synthesize`; частота — один рядок cron), `docs/deploy-sonko.md` (той самий крок для Сонька),
  `.engine/architecture/INDEX.md` F12 «тижневе» → «щоденне (задача 309)», `architecture-map.md` діаграма «щотижня» →
  «щодня».
- Errors: див. потік; сторінка — як помилки M3 A4.
- Dependencies (injected): `storage`, `llm`, `now`, `vet`, `measure`.
- Does NOT do: не пише карток і `knowledge/` інакше як через `apply_memory`; не читає `users/` (лише спостереження);
  не відкочує сам; не нагадує нікому.

## Decisions (with WHY)
- Q1: Синтезатор вносить зміни сам, без «так» власника — chosen because власник: «Значить, 1Б» (задача 309, «Рішення
  власника»; прочитання «Б» — вносить сам, з відкатом) і G3 «кожну зміну власник не затверджує». Rejected: черга
  пропозицій на схвалення — проти G3 і слова власника.
- Q2: «Спожите» = процитоване зміною ∪ враховане прогоном — chosen because примітка master-critic M2 (вхід обмежений
  позначкою «спожито»), і спостереження без зміни інакше подавались би щодня назавжди. Rejected: (a) вікно N днів —
  число без рядка цілей (P5); (b) лише процитовані — неспожиті назавжди.
- Q3: Відхилене перевіркою теж спожите (запис прогону `rejected`) — chosen because та сама причина повторювалась би
  щодня; власник бачить відхилене в стрічці. Наслідок, свідомо: відмова «перевищено бюджет» — про розмір пам'яті, не
  про спостереження, — теж їх споживає; двосторонні двері (бюджетну відмову можна зробити неспоживною одним рядком), а
  бюджет у 1.7 млн символів сьогодні не досяжний. Rejected: повторювати — щоденна та сама відмова.
- Q4: Невдача моделі — без запису прогону — chosen because спостереження не втрачаються, наступний прогін бере їх
  (як `analyze`, continuous-analysis Q2). Rejected: записати `failed` прогін зі `considered` — спостереження загублено.
- Q5: `basis` будує код — chosen because G6 (посилання на джерело) не має залежати від моделі, а стартові джерела
  нотатки (S5) не мають губитися при оновленні. Rejected: `basis` від моделі — модель може загубити джерела чи
  вигадати.
- Q6: Сторінка `/learning` українською — chosen because M3 A5: стрічка змін і вміст Знань українською, читає власник.
  Rejected: каталог 76 мов для сторінки власника — тексти про Знання, які й так українською.
- Q7: Щодня — chosen because слово власника «Давай поки що зробимо кожен день»; частота — рядок cron у розкладі.
  Rejected: щотижня (M4 F12) — замінено словом власника.

## Hardest seams (test-confidence points)
- **Seam 1: спожите.** Два прогони поспіль на тих самих файлах: другий — `nothing_new`, жодного виклику моделі (лічить
  сценарний `llm`). Після `rejected` і `no_change` — так само. Після `failed` — другий прогін подає ті самі id.
- **Seam 2: відкочене у вході.** Зміна → відкат → новий прогін: текст для моделі містить розділ «Відкочено власником»
  з вмістом відкоченої нотатки; відкат з порожнім `rollback_changed` — не подається.
- **Seam 3: `enum` цитат і порожня пам'ять.** Схема має `enum` лише з псевдонімів `new`; відповідь з чужим псевдонімом
  не проходить схему (сценарна модель → `failed`). Перший прогін після `seed` (пам'ять порожня): схема будується,
  відповідь з upsert → `applied`; відповідь з `remove` неіснуючого id → `rejected`, Job не падає.
- **Seam 4: сторінка і відкат через HTTP.** `TestClient` з ідентичністю власника: кнопка є, POST → 303, сторінка
  показує «відкочено», `current().memory` без нотатки; не-власник — 404 на GET і POST, файлів відкату немає.
- **Seam 5: tracer наскрізно.** Smoke через справжній `job.run(["analyze"])`, `job.run(["synthesize"])` з локальним
  сценарієм і справжній `create_app` — не через виклики функцій напряму.

## Invariants (rules that hold for every input of the stated domain)
- **I1** — Синтезатор не змінює карток: після будь-якого прогону словник `cards` останнього запису змін і файли
  `knowledge/cards/` ті самі, що до нього.
  - Domain: будь-яка відповідь моделі, що проходить схему; будь-який outcome.
  - Source: feature AC1, AC1a; Seam «Does NOT do».
  - Broken by: синтезатор, що пише картки чи кличе `publish`.
- **I2** — Кожне спостереження враховується не більше одного разу: множини `considered` усіх записів прогонів попарно
  не перетинаються.
  - Domain: будь-яка послідовність прогонів один за одним (не одночасних) з будь-якими outcome, нові спостереження
    між ними.
  - Source: Seam крок 2; master-critic M2 «вхід обмежений».
  - Broken by: `consumed` лише з записів змін.
- **I3** — Кожна застосована зміна посилається лише на спостереження свого входу: `observations` запису змін ⊆
  `considered` запису прогону з тим самим `rev`, і кожне з них є в `read_all()`, а його `link` у `/learning` дорівнює
  `Observation.link` (`/topics/<uid>/<topic>#t<turn>`).
  - Domain: будь-який прогін `applied`.
  - Source: G6; Seam крок 4–5.
  - Broken by: цитати поза `enum` чи з минулих прогонів.

## Exit criterion
- Контрактні тести (поведінки Seam, I1–I3) — зелені.
- `scripts/smoke_test_learning_loop.py` — як у «Goal» (2); вихід → `.engine/artifacts/synthesizer/smoke.txt`.
- `tests/live/test_synthesize_live.py` — як у «Goal» (3), плюс один виклик з ≈200 синтетичними спостереженнями
  (схема з `enum` o1…o200 приймається Vertex — перший прогін у розгортанні бере всю історію); вихід → `.engine/artifacts/synthesizer/live.txt`; так/ні,
  без порогу.
- ruff, mypy, `lint-imports`, швидкий набір — зелені.

## Deferred to later slices
- Результати кроків у повному циклі smoke — S6 доповнює `scripts/smoke_test_learning_loop.py` — revisit trigger: S6.
- Помилковий `vet` («подробиці людей») споживає спостереження назавжди (Q3) — revisit trigger: у розгортанні з'явився
  прогін `rejected` з причиною від `vet`.
- Невдалі прогони (`failed`) видно лише в журналі — revisit trigger: два `synthesize_failed` поспіль.
- Самостійний відкат — фіча «Deferred» — revisit trigger: перші результати кроків від людей поза власником.

## Open items requiring human decision (if any)
- (немає)

## Critic notes (non-blocking)
- Раунд 1 (фази 2–5 разом): REVISE — порожній `enum` id нотаток після `seed` → `remove[].id` рядком, перевірка в
  `apply_memory`; Seam 3 з першим прогоном. Notes: псевдоніми `o<k>` замість довгих id у `enum` (розмір схеми),
  `runs()`, `create_if_absent` з суфіксом, I2 «один за одним», I3 перевірне, бюджетна відмова в Q3, три схеми в
  `local.py`. Cold reader: PASS; notes внесено — live з ≈200 псевдонімами, зсув часу в розкладі, два revisit triggers;
  `None` з `apply_memory` = `no_change` і для «інший прогін першим» — свідомо (I2 «один за одним»).
