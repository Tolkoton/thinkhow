# Slice starting-notes — planning artifact

Feature: `.engine/architecture/feature/learning-loop.md`, slice **S5**. Board task `tasks/doing/309-close-learning-loop.md`,
unattended. Driven mode: frame from the feature's S5 entry, AC2, contracts S1 → S5 (`.engine/slices/knowledge-versions.md`)
і S4 (`.engine/slices/notes-readers.md`); nothing asked.

## Goal
Для кожного з 25 методів у пам'яті досвіду лежать стартові нотатки з дослідження типових випадків, з джерелами: одна
`router` (у яких типових ситуаціях пропонувати метод, з яким сусіднім методом його плутають і як розрізнити) і одна
`facilitator` (коли допомагає, де застрягають, як застосувати в типовій ситуації, як вивести із застрягання без
готової відповіді). Нотатки лежать у репозиторії (`notes/*.yaml`) і потрапляють у Знання командою Job-а `notes` —
однією ревізією, через перевірку версії; картки не змінюються. Набір роутера з нотатками не гірший за базу.

Вимірна ціль: (1) контрактні тести зелені; (2) `notes/` має 50 записів — по два на кожну картку `cards/`, кожен з
`basis`, де хоча б одне джерело — з автором, назвою, роком і адресою; джерело, сторінку якого не відкрито, позначено
так у `basis` (`sources.md` каже, що відкрито, що знайдено лише пошуком);
(3) `python -m thinkhow.learning.job notes` на локальній теці після `seed`: нова ревізія з 50 записами пам'яті, картки
побайтно ті самі; другий запуск — нічого; (4) `router_eval` у той самий день: база (без нотаток) і з нотатками
(`--notes notes/`) на всіх випадках `tests/fixtures/routing/cases.yaml`; жоден випадок, де в базі очікувана картка (або
справжня нічия) була першою, не перестає бути першим, а нестабільні (змінились) — повтор ×5 обох боків, як PR-20
(AC2 фічі); порівняння → `.engine/artifacts/starting-notes/router-eval.compare.md`.

## Premise verified
- PR-28 — `unverified`, перевіряє exit criterion (4). Регрес, що тримається на повторах ×5, — premise `falsified`:
  нотатки `router` правляться (до трьох різних правок, кожна записана) або AC2 іде до feature-architect.
- `router_eval.py` будує Знання з `seed` теки `cards/` (рядки 360–361) — нотатки додаються тим самим `notes` після
  посіву.
- Дослідження — desk research з веб-джерелами, `.engine/artifacts/starting-notes/research.yaml` і `sources.md`
  (агент дослідження, 2026-10-27); кожне джерело відкрито, неперевірене позначено «джерело не перевірено».

## Out of scope (deliberately)
- Зміна карток — нотатки лише поруч.
- Синтезатор (S3) — потім змінює ці нотатки сам; `notes` не перезаписує вже наявних id.
- Фасилітаторські прогони карток з нотатками (`card_conversations.py`) — не вимога AC2; лягає пропозицією.

## Seam (contract)
- **`notes/<card-id>.yaml`** (25 файлів) — список з двох записів `MemoryRecord` (`id`: `<card-id>-router`,
  `<card-id>-facilitator`; `audience`; `cards: [<card-id>]` (може називати й сусідню картку для `router`, якщо нотатка
  розрізняє обидві); `title`; `noticed`; `do`; `basis` — джерела). Українською (A5); назви методів і авторів — як у
  джерелі.
- **`knowledge.read_notes(notes_dir: Path) -> list[MemoryRecord]`** — читає `*.yaml` за назвою; файл не список чи
  запис не за схемою → `ValueError` з назвою файлу; два записи з одним `id` → `ValueError`.
- **`learning/job.py` команда `notes`** (USAGE `seed|cards|notes|analyze|synthesize`): `records = read_notes(NOTES_DIR)`;
  ті, чиїх `id` не upsert-ила **жодна** попередня зміна з `by="notes"` (`knowledge.changes()`, відкочена чи ні), → `apply_memory(storage, MemoryChange(what="стартові нотатки до методів:
  <N>", why="дослідження типових випадків застосування (задача 309)", by="notes", upsert=…, remove=[]), vet_with(llm),
  measure)`; жодного нового → нічого; лог `notes_published` (rev або None, кількість). `VersionRejected` → лог
  `notes_rejected` (причина), код 1; помилка моделі в `vet` (`LlmUnavailable`, `ValidationError`) — лог
  `notes_failed` (тип), код 1, нічого не записано. `NOTES_DIR` — `notes/` поруч із `cards/` у образі (`Dockerfile` копіює теку).
- **`scripts/router_eval.py --notes <dir>`**: після `seed` — ті самі записи з `read_notes` через `apply_memory` зі
  сценарним `vet` (нотатки вже перевірено `notes`; у прогоні оцінки модель не кличеться для перевірки) і справжнім
  `measure`; без прапорця — як зараз. Мітка прогону — `--label`.
- **`scripts/router_eval_compare.py`** — без змін: `--run/--base` уже порівнює всі випадки бази (частина «old»), а
  повтори ×5 — `--repeats18/--repeats25` (назви лишились від задачі 307). Порівняння пишеться поруч з прогоном, тож
  `router_eval --out .engine/artifacts/starting-notes/`.
- **`Dockerfile`**: `COPY notes/ /app/notes/`; **`docs/deploy.md`**, **`docs/deploy-sonko.md`**: крок «один раз після
  розгортання цієї версії: `--args …,notes`» (після `seed`/`cards`).
- Errors: див. вище.
- Dependencies (injected): `storage`, `llm` (у `vet_with`), шлях теки.
- Does NOT do: не змінює наявних записів пам'яті; не пише карток; не кличе роутера в `notes`.

## Decisions (with WHY)
- Q1: Нотатки в репозиторії + команда `notes` — chosen because власник читає їх у git, як картки; джерело правди після
  посіву — Знання в bucket-і (M2 S6), і синтезатор змінює їх там. Rejected: (a) нотатки в `cards/*.yaml` — «посів — у
  пам'ять досвіду, не в картки» (слова задачі); (b) один великий файл — 50 записів у одному файлі важко звіряти з
  картками.
- Q2: `notes` додає лише ті `id`, яких `notes` ще ніколи не публікувала — chosen because після посіву нотатки вчить
  синтезатор, а власник може відкотити ревізію `notes`: повторний `notes` не має ні стирати вивченого, ні повертати
  відкоченого чи прибраного синтезатором (S1 I5). Rejected: (a) «немає в чинній пам'яті» — найпростіше, без історії,
  але відкат чи `remove` повертались би наступним `notes`; (b) оновлювати наявні з репозиторію — затирало б зміни
  синтезатора.
- Q3: По одній нотатці кожної аудиторії на картку — chosen because AC2 «нотатки для всіх 25 методів» і два читачі
  S4; синтезатор потім уточнює чи додає. Rejected: кілька нотаток на випадок — більше тексту в кожному виклику без
  підстави.
- Q4: Порівняння з базою того самого дня, а не з артефактом 2026-10-25 — chosen because модель на `eu` могла змінитись
  за два дні, і різниця тоді була б не від нотаток. Rejected: стара база — змішує дрейф моделі з ефектом нотаток.

## Hardest seams (test-confidence points)
- **Seam 1: справжні 25 карток.** Тест читає `cards/` і `notes/` репозиторію: кожна картка має рівно `-router` і
  `-facilitator`, кожен `cards` — id наявних карток, кожен `basis` непорожній і містить хоча б одну адресу `http`.
- **Seam 2: повтор `notes`.** Другий запуск Job-а на тій самій теці — нова ревізія не створюється; після зміни
  синтезатором однієї нотатки `notes` її не повертає; після відкату ревізії `notes` і після `remove` однієї нотатки —
  `notes` нічого не повертає; нова нотатка в теці (id, якого `notes` не публікувала) — додається.
- **Seam 3: картки побайтно** після `notes` (як S1 Seam 4).

## Invariants (rules that hold for every input of the stated domain)
- **I1** — `notes` не змінює наявного: для будь-якого чинного стану кожен запис пам'яті, що був до `notes`, після нього
  той самий (той самий шлях версії).
  - Domain: будь-яка пам'ять, будь-яка тека нотаток.
  - Source: Q2; Seam «команда `notes`».
  - Broken by: upsert усіх записів теки.
- **I3** — Відкочене чи прибране не повертається: після будь-якої історії змін і відкатів `notes` не upsert-ить id,
  який колись upsert-ила зміна з `by="notes"`.
  - Domain: будь-яка історія змін (`notes`, синтезатор, `publish`) і відкатів.
  - Source: Q2; S1 I5.
  - Broken by: фільтр лише за `current().memory`.
- **I2** — `notes` ідемпотентна: другий запуск на тій самій теці не створює ревізії.
  - Domain: будь-яка тека нотаток, будь-який чинний стан.
  - Source: Seam; S1 Q7 (`None` для «нічого не змінює»).
  - Broken by: upsert записів, рівних чинним, як нових версій.

## Exit criterion
- Контрактні тести (Seam 1–3, I1–I2) — зелені.
- `notes/` — 50 записів (Goal 2); Job `notes` на локальній теці (Goal 3) → `.engine/artifacts/starting-notes/job.txt`.
- Live `router_eval` база і з нотатками того самого дня, порівняння і повтори ×5 нестабільних — Goal (4); так/ні за
  правилом AC2 фічі (те саме правило, що PR-20, задача власника 307).
- ruff, mypy, `lint-imports`, швидкий набір — зелені.

## Deferred to later slices
- Розмови карток з нотатками (`card_conversations.py`) — revisit trigger: власник побачить нотатки в стрічці і захоче
  перевірити ведення.

## Open items requiring human decision (if any)
- (немає)

## Critic notes (non-blocking)
- Раунд 1: REVISE — «немає в чинній пам'яті» повертало відкочені чи прибрані нотатки → «ніколи не публікувала
  `notes`» (`changes()`), I3, Seam 2. Notes: `basis` з адресою, помилка `vet`, compare без змін, `Dockerfile` і крок
  розгортання.
