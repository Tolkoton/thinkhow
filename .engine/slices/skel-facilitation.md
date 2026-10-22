# Slice skel-facilitation — planning artifact

Feature: `.engine/architecture/feature/walking-skeleton.md`, S3 (block: conversation). Driven mode: frame
supplied by the feature artifact, not asked. Depends on S1 (`platform.llm`, 50382d7) і S2 (`knowledge`, f8f5fb5).

## Goal
Найтонша частина F4 (INDEX.md, «Walking skeleton»): один виклик Gemini (`gemini-4-argon` на `eu`) за
карткою — поле `reply` потоком + структуроване оновлення (фаза, чи виконано вихід фази, зміни карти),
системна інструкція з PoC 101 (N1 — без готових відповідей; C4 — мова останньої репліки людини; одне
питання за раз). Вимірна ціль: `pytest` зелений; `pytest -m live` — один справжній виклик через
`facilitation.respond`; `scripts/smoke_test_skel_facilitation.py` веде одну репліку за Pre-mortem проти
справжнього Vertex і друкує відповідь і оновлення.

## Premise verified
- PR-01, PR-02 `verified` 2026-10-21 (PoC 101, `.engine/sketches/gemini-eu.md`): один виклик на репліку
  веде фазу картки й повертає валідне оновлення; 60/60 валідних з першої спроби. Схема оновлення й
  системна інструкція — `sketches/gemini-eu/session.py` (`SCHEMA`, `SYSTEM`, `main`).
- S1: `Llm.stream_json` дає дельти `reply`, якщо `reply` — перше поле схеми, і один `Done` з сирим JSON;
  `reply` не перший → нуль дельт, `Done` цілий (S1 Q2a); помилки → `LlmUnavailable`. Порядок полів
  pydantic = порядок у потоці (`.engine/artifacts/spikes/skel-platform-field-order-2026-10-21.txt`).
- S2: `CurrentKnowledge.cards`, `card_prompt(card)`, `rev_pair()`, `Card.facilitator.phases[].id`.

## Out of scope (deliberately)
- Роутер, профіль, вибір картки (F5): картку називає `ctx.card_id`.
- Застосування `map_updates` до карти і запис файлів — `workspace` (S4).
- «Час змінити метод» як окреме поле — у кістяку лише текстом у `reply` (правило інструкції, як у PoC).
- Обрізання історії (P2: історія подається повністю), ліміти довжини (P4, P5).

## Seam (contract)
Пакет `src/thinkhow/facilitation/` (публічне — з `__init__.py`):
- `types.py` — **не імпортує ні `thinkhow.knowledge`, ні `thinkhow.platform`** (Q6; S4 імпортує лише
  `thinkhow.facilitation.types`); pydantic v2, `ConfigDict(frozen=True, extra="forbid")`:
  - `@dataclass(frozen=True) Turn(role: Literal["user", "model"], text: str)` і `@dataclass(frozen=True)
    ReplyDelta(text: str)` — власні типи `facilitation` тієї самої форми, що й у `platform.llm`;
    `respond` перекладає їх у типи `platform.llm` і назад.
  - `ItemType = Literal["goal", "plan", "option_considered", "assumption", "missing", "blind_spot",
    "emotion", "change_mind", "threat", "mitigation", "tripwire", "chosen_step", "router_note"]` (PoC
    `ITEM_TYPES`).
  - `MapItem(id: str, type: ItemType, text: str, turn: str)`.
  - `ProblemMap(items: list[MapItem] = [], phase_id: str | None = None, last_turn: int = 0)`.
  - `MapUpdate(op: Literal["add", "update", "remove"], id: str, type: ItemType, text: str, turn: str)`.
  - `FacilitatorUpdate(reply: str, current_phase_id: str, phase_exit_met: bool, map_updates:
    list[MapUpdate])` — у цьому порядку полів (`reply` першим — для потоку S1); `reply` непорожній.
  - `@dataclass(frozen=True) FacilitationContext(card_id: str, history: list[Turn], problem_map:
    ProblemMap, turn_no: int, text: str)` — `history: list[facilitation.types.Turn]` — попередні репліки теми, без поточної; `turn_no` — номер `no` поточної репліки людини в наскрізній нумерації **всіх** реплік
    теми (і людини, і фасилітатора; `NumberedTurn.no`, контракт фічі S4 → S6), тож `t<turn_no>` — її
    якір `#t<turn_no>`; `text` — її текст.
  - `Facilitate = Callable[[FacilitationContext], Iterator[ReplyDelta | FacilitatorUpdate]]`
    (`ReplyDelta` — `facilitation.types.ReplyDelta`).
  - `FacilitationError(Exception)` — модель відповіла, але оновлення невалідне й після повтору.
- `respond.py` — `respond(ctx: FacilitationContext, knowledge: CurrentKnowledge, llm: Llm) ->
  Iterator[ReplyDelta | FacilitatorUpdate]`:
  - картка — `knowledge.cards[ctx.card_id]`; немає → `ValueError` (до будь-якого виклику моделі).
  - системна інструкція — `system_instruction(card, memory)`: правила PoC 101 (`SYSTEM` з `session.py`
    дослівно, з двома замінами (Q5): `turn` — «t<номер з рамки репліки>» замість «s2#<номер репліки
    людини>»; приклад id нового пункту — «i3» замість «t3») + `# Картка` + `card_prompt(card)` + `# Пам'ять досвіду` + усі записи
    пам'яті (без фільтра за карткою: у кістяку їх нема, а роутера, що відбирає, ще нема) у форматі `sketches/gemini-eu/context/memory.md` (`### <id> — <title>`, «Картки:» — id карток через кому, «Що
    помітили:», «Що робити:», «Підстава:»; порожня → «(поки порожня)»).
  - `contents` = `ctx.history`, перекладена в `platform.llm.Turn` (та сама роль і текст), + один `Turn("user", "[Карта проблеми зараз]\n<problem_map JSON>\n\n
    [Репліка людини #<turn_no>]\n<text>")` (PoC `main`: карта їде з найновішою реплікою).
  - схема виклику — `FacilitatorUpdate`, у якої `current_phase_id` звужено до `Literal` id фаз картки
    (`answer_schema(card)`, `pydantic.create_model`) — модель не може назвати чужу фазу.
  - `rev` = `knowledge.rev_pair()`.
  - Потік: кожну `platform.llm.ReplyDelta` з `llm.stream_json` перекладає у
    `facilitation.types.ReplyDelta` з тим самим текстом і віддає далі; на `Done` розбирає `raw_json` за
    схемою. Валідне: якщо дельт не було (`reply` прийшов не першим) — віддає одну `ReplyDelta(reply)`;
    потім рівно один `FacilitatorUpdate`, чий `reply` — **показаний текст** (склеєні дельти), коли
    дельти були. Невалідне — **повтор лише оновлення**: якщо дельти були (людина
    вже бачить текст), один `llm.generate_json` з тими самими `system` і `contents` + `Turn("model",
    <показаний текст>)` + `Turn("user", "Поверни лише оновлення до своєї відповіді вище: фаза, вихід,
    зміни карти.")` за схемою без `reply` (`update_schema(card)`); результат + показаний текст →
    `FacilitatorUpdate`. Якщо дельт не було — один `llm.generate_json` за повною схемою, потім
    `ReplyDelta(reply)` і `FacilitatorUpdate`. Повтор теж невалідний (`ValidationError`) →
    `FacilitationError`. `LlmUnavailable` проходить далі без змін.
  - Усе, що віддає `respond`, — екземпляри класів `facilitation.types` (`ReplyDelta`, саме
    `FacilitatorUpdate`, не підклас схеми виклику: результат перевалідовано з `model_dump()`).
- `__init__.py` експортує `respond` і всі типи `types.py` — для `web` (S5), який імпортує і `knowledge`.
  `workspace` (S4) імпортує лише `thinkhow.facilitation.types` (імпорт підмодуля не створює ребра до
  `__init__`, probe cold-reader-а 2026-10-22).
- `pyproject.toml`: новий forbidden-контракт import-linter «facilitation types are plain values» —
  `source_modules = ["thinkhow.facilitation.types"]`, `forbidden_modules = ["thinkhow.knowledge",
  "thinkhow.platform"]` — падає вже в цьому slice, а не в S4.
- `.engine/architecture/feature/walking-skeleton.md`, контракт S3 → S4: шлях імпорту
  `thinkhow.facilitation.types` (уточнення, не зміна змісту).
- Errors: `ValueError`, `FacilitationError`, `LlmUnavailable` — кидаються; обробник у `web` (S5).
- Dependencies (injected): `knowledge`, `llm` (S5 зв'язує їх `functools.partial` у `Facilitate`).
- import-linter: `facilitation` → `knowledge`, `platform.llm`; ↛ `access`, `platform.storage` (контракт
  S1), ↛ `workspace`, `learning` (шари).
- Does NOT do: зберігання, застосування карти, вибір картки, знання про людину.

## Decisions (with WHY)
- Q1: `current_phase_id` звужено до фаз картки самою схемою виклику. Чому: PoC 101 мав `enum` фаз у
  схемі (`session.py` `SCHEMA`) — 60/60 валідних; так фаза завжди одна з картки (I3). Rejected: вільний
  рядок і перевірка після — частіший повтор; одна статична схема на всі картки — не вміщує різні фази.
- Q2: повтор лише оновлення, коли текст уже показано (feature S3; S1 Q3: повтор після першої дельти
  дав би людині інший текст). Rejected: повтор усього потоку — другий текст поверх показаного;
  `FacilitationError` одразу — людина втрачає вже показану відповідь.
- Q3: карта — у найновішій репліці, а не в системній інструкції (PoC `main`: системна частина й історія
  лишаються сталим префіксом для неявного кешу Vertex). Rejected: карта в інструкції — рве префікс щоразу.
- Q4: `Turn` у `history` — тексти реплік без службових рамок; лише поточна репліка несе рамку з картою.
  Чому: так у PoC (60 реплік). Rejected: рамка в кожній репліці — історія більшає без користі.
- Q5: інструкція — дослівно PoC, крім двох рядків. Чому: P4 — якість ведення перевірено саме на ній
  (власник прийняв 60 реплік, задача 101). Відхилення: (1) `turn` — «t<номер з рамки>», бо якір теми —
  `#t<no>` у наскрізній нумерації (S4 → S6), а PoC рахував лише репліки людини; (2) приклад id нового
  пункту «t3» → «i3»: у PoC модель копіювала приклад (id `t1…t6` у `runs/session.jsonl`), і з новим
  форматом `turn` id і якір мали б однаковий вигляд — модель могла б узяти якір за id, і два `add` в одній
  відповіді злилися б у S4. Ці два рядки PoC не перевіряв — їх перевіряє live-тест і smoke. Ще: карта,
  яку бачить модель, — `ProblemMap` (`items`, `phase_id`, `last_turn`), а не `map.json` PoC з `problem` і
  `card`; `SYSTEM` цих ключів не називає. Rejected: переписати інструкцію — нова неперевірена;
  лишити «s2#» — якорі S5 не знайдуть репліку.

- Q6: власні `Turn`/`ReplyDelta` у `facilitation.types`, а не реекспорт `platform.llm`. Чому: контракт
  import-linter S1 «workspace gets knowledge and the model only as facilitate» не дозволяє непрямих
  імпортів, і `workspace → facilitation (__init__) → knowledge, platform.llm` — порушення (probe
  cold-reader-а). Rejected: `allow_indirect_imports = true` — послаблює запобіжник A3 для всіх
  посередників; реекспорт — S4 не збереться.

## Hardest seams (test-confidence points)
- **Seam 1: невалідне оновлення після показаного тексту** — сценарний `Llm`-двійник (фейк протоколу
  `Llm`, а не `ScriptedLlm`), чий `stream_json` дає дельти й `Done` з JSON, де `current_phase_id` —
  не фаза картки (або `map_updates` зламані); перевіряється: показаний текст не повторено, викликано
  рівно один `generate_json` із показаним текстом у `contents` і схемою без `reply`, `FacilitatorUpdate.
  reply` == показаному. Ще: повтор теж невалідний → `FacilitationError` після тих самих дельт. Двійник
  також перевіряє, що рамка поточної репліки містить «#<turn_no>».
  Відкидає «тест лише валідної відповіді».
- **Seam 2: `reply` не першим** — `Done` з валідним JSON, дельт нуль → одна `ReplyDelta(reply)` перед
  `FacilitatorUpdate`.
- Тести Seam 1–2 і інваріантів — у `tests/contract/skel_facilitation/` (пише незалежний тестувальник).
- **Seam 3: справжня модель** — `tests/live/test_facilitation_live.py` (`-m live`): одна репліка
  українською за `cards/pre-mortem.yaml` через `make_llm` → дельт ≥ 2, `FacilitatorUpdate` валідний,
  `current_phase_id` — фаза картки; і smoke-скрипт.

## Invariants (rules that hold for every input in the stated domain)
- **I1** — Склеєні `ReplyDelta`, віддані `respond`, дорівнюють `FacilitatorUpdate.reply`.
  - Domain: будь-яка відповідь двійника: валідна з `reply` першим, валідна з `reply` не першим,
    невалідна з дельтами (повтор оновлення), невалідна без дельт (повний повтор).
  - Source: Seam («Потік»); контракт фічі S3 → S4 (workspace дописує в `conversation.md` те, що
    показано).
  - Broken by: повний повтор після показаних дельт (людина бачить два тексти); `reply` з повтору замість
    показаного.
- **I2** — `respond` віддає рівно один `FacilitatorUpdate`, останнім елементом, або кидає виняток.
  - Domain: усі шляхи Seam, зокрема `LlmUnavailable` з двійника посеред потоку.
  - Source: Seam; feature S4 (`Answered` лише після оновлення).
  - Broken by: оновлення до кінця дельт; два оновлення (з потоку й з повтору).
- **I3** — `FacilitatorUpdate.current_phase_id` — завжди id фази картки `ctx.card_id`.
  - Domain: будь-яка картка з будь-якими фазами; будь-яка відповідь двійника, зокрема з чужою фазою.
  - Source: Q1; PoC `SCHEMA` (`enum` фаз).
  - Broken by: схема з вільним рядком без перевірки.

## Exit criterion
- `uv run pytest` зелений (контрактні тести slice-а, A3); `uv run ruff check src tests scripts`,
  `uv run mypy src tests scripts`, `PYTHONPATH=src uv run lint-imports` — без помилок.
- `uv run pytest -m live tests/live/test_facilitation_live.py` — зелений проти `gemini-4-argon` на `eu`.
- `uv run python scripts/smoke_test_skel_facilitation.py` — посіює Знання в тимчасову теку, веде одну
  репліку людини українською за Pre-mortem через справжній Vertex; друкує відповідь, кількість знаків «?» у ній
  (довідково, як у PoC; не умова виходу — якість ведення оцінює власник, P4), `current_phase_id`,
  кількість дельт і зміни карти; перевіряє, що дельт ≥ 2 (технічний доказ потоку), склеєні дельти ==
  `reply`, фаза — з картки.

## Deferred to later slices
- Окреме поле «час змінити метод» — F5 (роутер пропонує іншу картку) — trigger: задача F5.
- Обрізання або стискання історії — коли журнал `llm_call` покаже `prompt_tokens`, що наближаються до
  вікна моделі (A4 записує токени).

## Open items requiring human decision (if any)
- None.

## Revisions during planning
- **Phases 2–5 (critic round 1) — challenge:** "Q5's one change to the PoC instruction holds only under one reading of `turn_no`, and makes `turn` look like the example item id" → **revised:** `turn_no` = наскрізний `no` (S4 → S6); приклад id «i3»; друге відхилення названо в Q5 → **reason:** PoC рахував лише репліки людини, а модель PoC копіювала приклад id.
- **Cold-reader — challenge:** "re-exporting `platform.llm` types through `facilitation` breaks the S1 import-linter contract as soon as S4 imports it" → **revised:** Q6, власні типи в `facilitation.types`, новий forbidden-контракт → **reason:** probe import-linter: непрямий ланцюг — порушення, імпорт підмодуля — ні.
- **Cold-reader 2 — challenge:** "two leftovers from before Q6 (history as `platform.llm.Turn`, deltas passed «як є») contradict Q6" → **revised:** `history: list[facilitation.types.Turn]`, переклад дельт, усе віддане — класи `facilitation.types` (і не підклас схеми), пам'ять — усі записи, «Картки:» — id → **reason:** формулювання до Q6 лишилися; виправлено без третього прогону (escalations.md, skel-facilitation-cold-reader).
- Нотатки прийнято: тести в `tests/contract/skel_facilitation/` (2), `reply` = показаний текст (3), «?» довідково (4), формат пам'яті (5), форма карти (6).

## Critic notes (non-blocking)
- Cold-reader: `additionalProperties: false` і `minLength` у `response_json_schema` на Vertex не spiked — live-тест ловить відмову з першого прогону; builder запускає його першим після GREEN. Тести й smoke не беруть `sketches/gemini-eu/context/map.json` за фікстуру (у ньому поля, яких `MapItem` не приймає).
