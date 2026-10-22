# Slice skel-knowledge — planning artifact

Feature: `.engine/architecture/feature/walking-skeleton.md`, S2 (block: conversation). Driven mode: frame
supplied by the feature artifact, not asked. Depends on S1 (`thinkhow.platform`, commit 50382d7).

## Goal
Найтонша частина F6 (INDEX.md, таблиця «Walking skeleton»): схема картки і запису пам'яті (pydantic),
одна картка Pre-mortem українською в `cards/pre-mortem.yaml`, `seed` створює ревізію 1 (пам'ять
порожня) «лише якщо ще немає», `current` читає чинну ревізію разом із пам'яттю. Вимірна ціль: `pytest`
зелений; `scripts/smoke_test_skel_knowledge.py` посіює й читає Знання в локальній теці.

## Premise verified
- `cards/pre-mortem.yaml` — дослівний перенос `sketches/gemini-eu/context/card-pre-mortem.md`, за якою
  PoC 101 вів 60 реплік (PR-02 `verified` 2026-10-21, `.engine/sketches/gemini-eu.md`); фази й їхні id —
  ті самі, що в схемі відповіді PoC (`sketches/gemini-eu/session.py`, `PHASES`).
- PyYAML 6.0.3 стоїть як залежність `fastapi[standard]` (`uv.lock`; `import yaml` у `.venv` — probe
  2026-10-22). Без `py.typed`: mypy потребує `ignore_missing_imports` для `yaml` (рішення фічі: у
  `pyproject.toml` залежність не дописується — пропозиція у звіті).
- `Storage.create_if_absent` / `list` / `read` — S1, I2 і Q3 (рядковий префікс, рекурсивно).

## Out of scope (deliberately)
- Перевірка версії (повнота, «без подробиць людей», бюджет розміру), записи змін поза `seed`, відкати,
  стрічка змін — F11 (feature «Deferred»). `n` у кістяку завжди 0: відкатів ніхто не пише.
- Маршрути між картками, роутер (F5) — половина для роутера лише в схемі й у файлі картки.
- 17 інших карток (F7); вміст пам'яті досвіду — лише схема й порожній стан.
- Кеш прочитаних версій у пам'яті процесу (M2 S6 дозволяє) — P5: не потрібен кістякові.
- Побудова `Storage` з налаштувань — composition root (S5 `web/app.py`, S6 `learning/job.py`).

## Seam (contract)
Пакет `src/thinkhow/knowledge/` (публічне — лише з `__init__.py`):
- `schema.py` — pydantic v2, `model_config = ConfigDict(frozen=True, extra="forbid")`:
  - `Phase(id: str, title: str, goal: str, how: list[str], skip_if: str | None = None, exit: str)` —
    `id` за `^[a-z0-9_]{1,64}$`; `goal`, `exit` непорожні.
  - `RouterHalf(needs: str, when_yes: list[str], when_no: list[str], signals: list[str])` — `when_yes`,
    `when_no` непорожні.
  - `Trap(name: str, text: str)`.
  - `FacilitatorHalf(purpose: str, stance: str, needs: str, phases: list[Phase], ending: str,
    traps: list[Trap], pairs_well: str)` — `phases` непорожні, `id` фаз різні.
  - `Card(id: str, title: str, router: RouterHalf, facilitator: FacilitatorHalf)` — `id` за
    `^[a-z0-9-]{1,64}$`.
  - `MemoryRecord(id: str, title: str, cards: list[str], noticed: str, do: str, basis: str)` — `id` за
    `^[A-Za-z0-9-]{1,64}$` (великі літери — бо записи PoC мають вигляд `M-001`; id картки — slug файлу).
  - `ChangeRecord(rev: int ≥ 1, what: str, why: str, cards: dict[str, str], memory: dict[str, str])` —
    повний перелік чинних версій: id → шлях файлу версії в bucket-і `system` (M2 S6).
- `prompt.py` — `card_prompt(card: Card) -> str`: половина для фасилітатора текстом (markdown,
  українською, як `card-pre-mortem.md`): назва, навіщо, позиція, що на вході, кожна фаза з `id`,
  метою, «як», «пропустити, якщо», виходом; чим закінчується; пастки; з чим поєднується. Половини для
  роутера в тексті немає (її читає роутер, F5).
- `store.py`:
  - Розкладка в bucket-і `system`: версія картки — `knowledge/cards/<card_id>/v<k>.json`; запис пам'яті —
    `knowledge/memory/<id>/v<k>.json`; запис зміни — `knowledge/changes/<rev:06d>.json`. Файли версій
    — `model_dump_json`, `application/json`; незмінні (пишуться лише `create_if_absent`).
  - «Запис зміни» — файл за `^knowledge/changes/(\d{6})\.json$`; той самий предикат у `seed` і
    `current` (сторонній файл в теці — не запис).
  - `seed(storage: Storage, cards_dir: Path) -> bool` — якщо під `knowledge/changes/` уже є хоч один
    запис зміни — нічого не пише (і нічого не читає з `cards_dir`), `False`. Інакше: читає всі `*.yaml` з `cards_dir` (`yaml.safe_load` →
    `Card.model_validate`; ім'я файлу без `.yaml` має дорівнювати `card.id`, інакше `ValueError`;
    порожня тека → `ValueError`), спершу створює кожен файл версії `v1.json` (`create_if_absent`), і
    останнім — `knowledge/changes/000001.json` (`create_if_absent`) з `ChangeRecord(rev=1, what="посів:
    <N> стартових карток", why="ревізія 1 з теки cards/ репозиторію", cards={id: шлях}, memory={})`.
    Повертає результат цього останнього `create_if_absent`.
  - `current(storage: Storage) -> CurrentKnowledge` — перелічує `knowledge/changes/`, бере файли за
    `^knowledge/changes/(\d{6})\.json$`, обирає найбільший `rev` (як число); читає `ChangeRecord`
    (`ChangeRecord.rev` ≠ числу з імені → `KnowledgeCorrupt`), читає кожен названий файл версії (`Card` / `MemoryRecord`). Немає жодного запису →
    `KnowledgeMissing`; названий файл відсутній → `KnowledgeCorrupt`; невалідний вміст →
    `pydantic.ValidationError`.
  - `@dataclass(frozen=True) CurrentKnowledge(rev: int, n: int, cards: dict[str, Card], memory:
    list[MemoryRecord])` + `rev_pair() -> platform.llm.KnowledgeRev` (контракт фічі S2 → S1, S2 → S3).
    `memory` — у порядку `id`. `n = 0` у кістяку (відкати — F11).
- `cards/pre-mortem.yaml` (корінь репозиторію, M3 A1) — `Card` з `id: pre-mortem`; половина для
  фасилітатора — дослівно з `sketches/gemini-eu/context/card-pre-mortem.md` (4 фази з id PoC:
  `phase_1_time_travel`, `phase_2_blind_spots`, `phase_3_triage`, `phase_4_mitigation_tripwires`);
  рядки фаз без свого поля («Правило: …» фази 1, «Ця фаза не пропускається ніколи» фази 4) — пунктами
  `how`; половина для роутера — з розділів картки «Що потрібно на вході», «Не той випадок», «Навіщо»; `signals` — ознаки з тих самих розділів (план чи обране рішення вже є; названо строк), нічого понад картку.
- `pyproject.toml`: `[[tool.mypy.overrides]] module = ["yaml"]`, `ignore_missing_imports = true` (з рядком
  `gate-allow`: PyYAML без `py.typed`, stubs — новий пакет, дозвіл власника).
- Значення незмінні лише поверхнево: поля-списки в frozen-моделях — `list`/`dict` (прийнято свідомо:
  ніхто в кістяку їх не змінює; `tuple` — коли з'явиться спільний кеш у процесі).
- Errors: `KnowledgeMissing`, `KnowledgeCorrupt` (обидва — `Exception`), `ValueError`,
  `pydantic.ValidationError`, `yaml.YAMLError` — кидаються; обробник у `web` (S5).
- Dependencies (injected): `storage`, `cards_dir`.
- import-linter: `knowledge` → `platform.storage`, `platform.llm` (лише `KnowledgeRev`) — стрілки M3;
  `knowledge` ↛ `access` уже в контракті S1.
- Does NOT do: перевірку версії, відкати, нові ревізії, кеш, знання про людей чи теми.

## Decisions (with WHY)
- Q1: файли версій у Cloud Storage — **JSON** (`model_dump_json`), YAML — лише стартові картки в
  репозиторії. Чому: версії пише й читає машина; JSON — та сама схема pydantic в обидва боки без
  PyYAML на читанні. Rejected: YAML і в bucket-і — те саме, але залежність на читанні кожного запиту;
  один файл зі всіма картками на ревізію — суперечить M2 S6 «кожна версія — новий незмінний файл».
- Q2: точка фіксації посіву — **запис зміни, створений останнім**. Чому: якщо посів упав посередині,
  `current` не бачить ревізії, а повторний `seed` дописує решту (файли версій `create_if_absent` з тим
  самим вмістом); два одночасні `seed` — запис зміни створить лише один (M2 S6). Rejected: спершу
  запис зміни — `current` бачив би ревізію з неіснуючими файлами.
  Прийнято: якщо між упалим посівом і повтором змінилась `cards_dir`, лишаються вже записані `v1.json`
  (незмінні) — ревізія 1 тоді відрізняється від репозиторію; для однієї картки кістяка це не
  трапляється практично.
- Q3: `seed` перевіряє «вже є будь-який запис зміни», не лише `000001.json`. Чому: «лише якщо ще
  немає» (M3 «Посів Знань») має діяти й тоді, коли навчання вже писало ревізії. Rejected: перевірка лише
  `000001` — те саме для кістяка, але тихо ламається, якщо ревізію 1 колись приберуть.
- Q4: найбільший `rev` — як число з імені файлу за регулярним виразом, а не останній у сортуванні
  рядків. Чому: стійкість до сторонніх файлів у теці. Rejected: `sorted(...)[-1]` — ламається на
  будь-якому файлі не того формату.
- Q5: `card_prompt` — у `knowledge` (не в `facilitation`). Чому: текст картки — вміст Знань (мова Знань
  A5), фасилітатор лише вставляє його в інструкцію; контракт фічі S2 → S3 так і називає. Rejected: у
  `facilitation` — тоді `facilitation` знала б внутрішню схему картки.
- Q6: половина для роутера заповнена вже в кістяку, хоча роутера немає. Чому: схема картки — «половина
  для роутера + половина для фасилітатора» (M1), і F5 не мусить міняти схему. Rejected: лише половина
  фасилітатора — схема змінилась би з F5.

## Hardest seams (test-confidence points)
- **Seam 1: посів, що впав посередині, і повторний посів** (одночасність двох посівів гарантує атомарний `create_if_absent` S1, тут не тестується) — фейк-сховище поверх `LocalStorage`, що
  кидає на N-му `create_if_absent`; після падіння `current` → `KnowledgeMissing`, повторний `seed` →
  `True` і повна ревізія 1. Другий `seed` після першого → `False`, жодного запису. Ще два випадки (I1):
  (a) другий `seed` з `cards_dir`, де є додаткова і змінена картка → `False`, і під `knowledge/` жоден
  файл не з'явився і не змінився (знімок усіх шляхів і вмісту до/після); (b) bucket, де єдиний запис
  зміни — `knowledge/changes/000002.json` (без `000001`) → `False`, нічого не записано; (c) у
  `knowledge/changes/` лише сторонній файл → `seed` посіює (`True`). Відкидає «тест лише щасливого
  посіву» і «перевірку лише `000001`».
- **Seam 2: справжня картка проти схеми** — `cards/pre-mortem.yaml` валідна, 4 фази з id PoC у тому ж
  порядку, кожна з непорожнім `exit`; `card_prompt` містить кожен id фази і кожен вихід. Відкидає
  «тест на вигаданій міні-картці, а справжня не проходить схему».
- **Seam 3: вибір чинної ревізії** — у теці `changes/` записи 1, 2, 10 і сторонній файл: `current`
  бере 10. Відкидає «останній у сортуванні рядків».

## Invariants (rules that hold for every input in the stated domain)
- **I1** — `seed` ніколи не змінює Знання, в яких уже є хоч один запис зміни.
  - Domain: будь-який стан bucket-а `system`, де під `knowledge/changes/` є ≥ 1 файл за форматом
    `\d{6}\.json`; будь-яка тека `cards_dir`.
  - Source: M3 «Посів Знань» («лише якщо ще немає»); M2 S2 (у `knowledge/` пише лише навчання).
  - Broken by: `seed`, що перевіряє лише `000001.json` або пише файли версій до перевірки.
- **I2** — `current` повертає рівно ті версії, які названо в записі зміни з найбільшим `rev`.
  - Domain: будь-який набір записів змін з різними `rev` (зокрема ≥ 10, різної кількості цифр у числі)
    і сторонні файли в `knowledge/changes/`.
  - Source: M2 S6 («у записі — повний перелік чинних версій»; «стрічка і є історія змін»).
  - Broken by: вибір останнього в сортуванні рядків; злиття версій з кількох записів.
- **I3** — Кожна фаза картки — її `id` і її вихід — є в `card_prompt(card)`.
  - Domain: будь-яка валідна `Card`.
  - Source: контракт фічі S2 → S3 (фасилітатор веде за фазами з `id`, метою, виходом; схема відповіді
    PoC називає `current_phase_id`).
  - Broken by: шаблон, що пропускає фази з `skip_if` або обрізає довгі.

## Exit criterion
- `uv run pytest` зелений (контрактні тести slice-а, `tests/test_a3_imports.py`, `tests/test_a3_google_sdk.py`);
  `uv run ruff check src tests scripts`, `uv run mypy src tests scripts` — без помилок;
  `PYTHONPATH=src uv run lint-imports` — код 0.
- `uv run python scripts/smoke_test_skel_knowledge.py` — у тимчасовій локальній теці: перший `seed` →
  `True`, другий → `False`; `current` → `rev 1, n 0, cards ['pre-mortem'], memory []`; друкує
  `card_prompt` (людина бачить українську картку з 4 фазами). Справжній bucket — лише на розгортанні
  власника (Job `seed`, S7 чекліст, PR-07).

## Deferred to later slices
- Перевірка версії, відкати, `n > 0`, нові ревізії — F11 — trigger: синтезатор (F12) почне подавати версії.
- 17 карток, маршрути — F7, F5 — trigger: задачі F7/F5 за порядком INDEX.md; `seed` уже читає всю
  теку, тож F7 лише додає файли.
- Кеш версій у процесі не потрібен: `web/app.py` читає `current` один раз при старті (контракт фічі S3 →
  S5); повертатися — коли F11 почне писати нові ревізії під час роботи застосунку.

## Open items requiring human decision (if any)
- None.

## Revisions during planning
- **Phases 2–5 (critic round 1) — challenge:** "Seam 1's test cannot catch I1's own «Broken by»" → **revised:** Seam 1 cases (a) змінена `cards_dir`, (b) лише `000002.json`, (c) сторонній файл → **reason:** з тим самим `cards_dir` `create_if_absent` маскує запис до перевірки.
- Нотатки критика прийнято: один предикат «запис зміни» (2), override mypy для `yaml` у Seam (3), тригер кешу (4), тригери F7/F5 (5), `rev` з імені vs з запису → `KnowledgeCorrupt` (6), рядки без поля → `how` (7), id пам'яті з великими літерами — WHY (9); 8 (поверхнева незмінність) прийнято свідомо, записано в Seam.

## Critic notes (non-blocking)
- Cold-reader: PASS. `ChangeRecord` ще без посилань на висновки й спостереження (M2 S6) — F11 додасть необов'язковим полем із типовим значенням (`extra="forbid"` старі записи прочитає). «`platform.llm` лише `KnowledgeRev`» — домовленість, import-linter рівня модуля її не перевіряє. Обрізаний локальний файл після падіння між створенням і записом — властивість `LocalStorage` S1, у Cloud Storage неможливо.
