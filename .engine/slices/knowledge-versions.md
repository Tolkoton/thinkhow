# Slice knowledge-versions — planning artifact

Feature: `.engine/architecture/feature/learning-loop.md`, slice **S1** (tracer bullet, part 1). Board task
`tasks/doing/309-close-learning-loop.md`, unattended. Driven mode: the frame is the feature artifact's S1 entry, its
«Inter-slice contracts» S1 → S3/S4/S5 and «Build parameters»; nothing asked.

## Goal
Пам'ять досвіду (нотатки до методів) змінюється ревізіями Знань, і будь-яку таку зміну можна відкотити, а картки при
цьому не змінюються ніколи. Одна функція пише зміну пам'яті як нову ревізію — тільки після перевірки версії (схема,
картки, бюджет розміру, «без подробиць людей»); одна функція пише відкат; `current()` дає чинний стан = останній
запис змін мінус відкати, з номером останнього відкату `n`; одна функція дає стрічку змін.

Вимірна ціль: (1) контрактні тести I1–I7 і кожної поведінки «Seam» зелені; (2) `scripts/smoke_test_knowledge_versions.py`
на `LocalStorage` з 25 картками `cards/`: `seed` → зміна пам'яті (сценарна перевірка) → `current().memory` має
запис → відкат → `current().memory` без нього, `rev_pair().n == 1`; байти файлів `knowledge/cards/` до і після
однакові; (3) live `tests/live/test_vet_live.py`: перевірка «без подробиць людей» на `gemini-4-argon`/`eu` відхиляє
запис з подробицею людини і пропускає узагальнений; (4) повний `uv run pytest`, ruff, mypy, import-linter — зелені.

## Premise verified
- PR-31 (вхідна межа моделі) — `falsified`, запасний шлях плану: `.engine/artifacts/spikes/learning-loop-2026-10-27/
  input-limit.out` (2026-10-27): `models.get("gemini-4-argon")` на `eu` дає `input_token_limit=None`. Бюджет бере
  задокументовану межу моделей класу Pro 1 048 576 вхідних токенів; там само виміряно 2.91 і 2.98 символу на токен
  для інструкцій роутера і фасилітатора — оцінка «2 символи на токен» обережна.
- `Storage.create_if_absent` і `Storage.list` — як у `src/thinkhow/platform/storage.py`, закріплено запечатаними
  тестами `tests/contract/skel_platform/` (зовнішньої поведінки поза цим немає).
- PR-32 (новий, live у цьому slice-і): `gemini-4-argon`/`eu` за `generate_json` з вузькою схемою `{ok, reason}`
  відрізняє запис пам'яті з подробицею конкретної людини (ім'я, місто, її сума) від узагальненого — `unverified`,
  перевіряє `tests/live/test_vet_live.py` (exit criterion 3). Не пройде — перевірка лишається, а premise і шов
  повертаються до feature-architect (інтерактивна межа).

## Out of scope (deliberately)
- Синтезатор, запис прогону `learning/synthesis/…`, сторінка `/learning` і маршрут відкату — S3.
- Читання нотаток роутером і фасилітатором (`audience`) — S4; тут поле лише з'являється.
- Стартові нотатки і команда `notes` — S5.
- Відкат змін карток (`publish`/`seed`) — не відкочуються: картки змінює лише задача власника.
- Самостійний відкат системою (G3) — відкладено фічею.
- Перевірка «повноти» запису понад схему pydantic (непорожні поля) — схеми досить.

## Seam (contract)
- **Схема** (`knowledge/schema.py`):
  - `MemoryRecord.audience: Literal["router", "facilitator"] = "facilitator"` (старі записи без поля читаються).
  - `ChangeRecord` + `observations: list[str] = []`, `by: str = ""`, `replaced: dict[str, str | None] = {}` — для
    кожного id пам'яті, який змінила ця ревізія, шлях попередньої версії (None — записа не було). Старі записи
    читаються.
  - Новий `Rollback(n: int ≥ 1, rev: int ≥ 1, reverts: dict[str, str | None], restore: dict[str, str | None],
    changed: list[str], at: datetime, by: str)` — файл `knowledge/rollbacks/<n:06d>.json`.
- **Новий модуль `knowledge/versions.py`** (ім'я — вибір builder-а в межах `knowledge`):
  - `MemoryChange(what: str, why: str, by: str, upsert: list[MemoryRecord], remove: list[str],
    observations: list[str] = [])` — frozen pydantic.
  - `apply_memory(storage: Storage, change: MemoryChange, vet: Vet, measure: Measure) -> int | None`.
    Потік: `current()` → перевірка версії (порядок нижче) → для кожного upsert-а, що відрізняється від чинного,
    `knowledge/memory/<id>/v<N>.json` (`create_if_absent`, N = найбільший наявний + 1) → запис змін
    `knowledge/changes/<rev+1:06d>.json` (`create_if_absent`) з `cards` = **словник шляхів карток чинного стану
    без змін**, `memory` = шляхи чинного стану (після відкатів) з upsert-ами й без remove, `replaced` (лише змінені
    id), `observations`, `by`, `what`, `why`. Повертає новий `rev`; `None` — upsert-и збігаються з чинними записами і
    remove порожній (нічого не змінює), або інший прогін створив файл першим (як `publish`).
  - Перевірка версії, по черзі, перша невдача → `VersionRejected(reason: str)`, **нічого не записано**:
    1. id у `upsert` різні; жоден id не стоїть і в `upsert`, і в `remove`;
    2. кожен id з `remove` є в чинній пам'яті;
    3. кожен запис має `cards` непорожнім і кожен id з `cards` є картою чинного стану;
    4. бюджет: `measure(prospective) > BUDGET_CHARS` → відмова «перевищено бюджет»; `prospective` —
       `CurrentKnowledge` з тими самими картками і новою пам'яттю; `BUDGET_CHARS = (1_048_576 − 200_000) × 2`
       (вікно класу Pro з PR-31, запас на розмову 200 000 токенів, 2 символи на токен — feature «Build parameters»;
       запас і оцінка — вибір архітектора, `PROVISIONAL — owner ratification pending`, стала в одному рядку);
    5. `vet(upsert_changed)` (лише записи, що справді змінюються; порожньо — не викликається) → рядок причини →
       відмова «подробиці людей: <причина>».
  - `Vet = Callable[[Sequence[MemoryRecord]], str | None]`; `Measure = Callable[[CurrentKnowledge], int]`.
  - `rollback(storage: Storage, rev: int, by: str, now: datetime) -> int` — повертає `n`. Відмови: немає запису
    `rev` → `KnowledgeCorrupt`-подібна `UnknownRevision`; `replaced` запису порожній (посів, `publish`) →
    `NotRollbackable`; є відкат з тим самим `rev` → `AlreadyRolledBack`; `now` без часового поясу → `ValueError`.
    `reverts` = {id: `memory.get(id)` запису `rev`} для id з `replaced`; `restore` = `replaced`; `changed` — id, на які цей відкат діє за правилом `current()` нижче в мить запису
    (може бути порожнім). `n` = найбільший наявний + 1;
    `create_if_absent` не вдався → перелічити знову і спробувати наступний номер, до 3 разів, далі `KnowledgeConflict`.
  - `changes(storage: Storage) -> list[ChangeView]`, найновіші першими; `ChangeView(rev, what, why, by,
    observations, upserted: list[MemoryRecord], removed: list[str], rolled_back: int | None, rollback_changed:
    list[str])` — `upserted` читаються зі шляхів запису для id з `replaced`, де новий шлях не None; `removed` — id з
    `replaced`, яких у `memory` запису немає; `rolled_back` — `n` відкату цієї ревізії або None (два одночасні відкати однієї ревізії — найменший `n`).
- **Чинний стан шляхами** — один приватний помічник `knowledge` (напр. `_current_paths(storage) -> (rev, n,
  cards: dict[str, str], memory: dict[str, str])`), яким користуються `current()`, `apply_memory`, `rollback`
  (`changed`) і `publish`; правило відкату записане лише в ньому.
- **Правило відкату (точне, за походженням, без порівняння значень):** беруться `cards`/`memory` останнього запису
  змін, потім відкати за зростанням `n`. Відкат `k` ревізії `R` діє на id з `reverts`, якщо **кожна** ревізія `S` > `R`,
  що має цей id у `replaced`, сама відкочена відкатом з номером < `k`, який подіяв на цей id. Тоді id отримує
  `restore[id]` (None — прибрати). Інакше id не чіпається: пізніша чинна зміна id перемагає — і та, що записана до
  відкату (I3), і та, що після нього (I7), бо обидві мають id у `replaced`. Ревізія, записана після відкату і без
  цього id у `replaced`, несе в `memory` або вже відновлене значення (побудована з `current()`), або сире значення
  з `reverts` (прогін, що писався одночасно й відкату не бачив) — в обох випадках відкат ставить `restore`, тож
  одночасний відкат не губиться. `n` = найбільший номер відкату, 0 без відкатів. Відкат, що називає `rev` більший за останній запис, →
  `KnowledgeCorrupt`.
- **`store.publish()`**: `memory` нового запису = шляхи пам'яті `current()` (після відкатів), не сирий попередній
  запис; `replaced` порожній (зміна карток не відкочується).
- **`learning/vet.py`** (ін'єкції для S3, S5): `vet_with(llm: Llm) -> Vet` — один `generate_json` з інструкцією
  українською і схемою `{ok: bool, reason: str}` над текстом записів; `ok=false` → `reason`; помилка моделі
  (`LlmUnavailable`, `ValidationError`) → прокидається (зміна не пишеться; викликач логує). `measure(knowledge) ->
  int` — довжина найдовшої з інструкцій: `facilitation.route.router_instruction(knowledge, None)` і
  `facilitation.respond.system_instruction(card, knowledge.memory, None, True)` для кожної картки — сьогодні з усією
  пам'яттю (обережна завищена оцінка); `measure` будує ті самі інструкції, що й читачі, тож коли S4 звузить пам'ять
  фасилітатора до його картки, `measure` іде за ним без зміни контракту.
- **`knowledge/__init__.py`** експортує нові імена; `pyproject.toml` import-linter: `ignore_imports` + рядок
  `thinkhow.knowledge.versions -> thinkhow.platform.storage` (той самий ланцюжок ADR-0003, що й `store`).
- Errors: `VersionRejected`, `UnknownRevision`, `NotRollbackable`, `AlreadyRolledBack`, `KnowledgeConflict` —
  винятки `knowledge`; повернення `None` лише в `apply_memory` (як `publish`).
- Dependencies (injected): `storage`, `vet`, `measure`, `now`, `llm` (у `vet_with`).
- Does NOT do: не пише файлів `knowledge/cards/…` і не змінює `cards` запису змін; не відкочує картки; не знає людей
  (лише рядок `by`); не викликає модель сам (`knowledge`), лише через `vet`.

## Decisions (with WHY)
- Q1: Зміна пам'яті сама пише, що вона замінила (`replaced`), а відкат бере `reverts`/`restore` з цього — chosen
  because ревізія будується з `current()` після відкатів, тож різниця сирих записів `rev` і `rev−1` змішала б зміну з
  ефектом давніших відкатів. Rejected: (a) обчислювати різницю `rev` і `rev−1` — хибна після відкату між ними;
  (b) відкат як нова ревізія змін (`changes/<rev+1>` зі старими шляхами) — тоді відкат пише Job-файл, який за M2 пише
  лише завдання навчання, а власник писав би `changes/`; M2 S6 прямо дає відкатам свій файл.
- Q2: Відкат діє на id, лише якщо жодна пізніша **чинна** (не відкочена) ревізія цього id не змінювала — за
  походженням (`replaced`), не за значенням — chosen because M2 S6: «щоб нові версії, записані після нього, не
  відкочувались», а «запису немає» (None) однакове для різних прибирань, тож порівняння значень повертало б прибране
  (два раунди critic-а). Ланцюжок у зворотному порядку: rev 2 `m1` p1→p2, rev 3 p2→p3; відкат rev 3, потім rev 2 →
  `m1` = p1 (rev 3 уже відкочено для `m1`). У прямому порядку: відкат rev 2 першим на `m1` не діє (його замінила
  чинна rev 3; `changed` без `m1`), потім відкат rev 3 → p2. Власник бачить це в стрічці («нічого не змінено» для
  першого). Rejected: (a) відкат «до стану rev−1» цілком — скасував би пізніші зміни; (b) порівняння значення з
  `reverts` — хибне для None (контрприклад critic-а: прибрати → повернути → прибрати → відкат першого повертає);
  (c) заборонити відкат зміни, після якої були інші — власник не міг би відкотити давню погану нотатку.
- Q3: Перевірка «без подробиць людей» — ін'єкція `vet` у `knowledge`, реалізація на моделі — у `learning` — chosen
  because шари M3: `knowledge` під `facilitation` і не кличе модель для бізнес-рішень, а `learning` вище й має `llm`;
  тести `knowledge` — зі сценарним `vet`. Rejected: (a) виклик моделі всередині `knowledge` — `knowledge` отримав би
  `llm` і логіку інструкції; (b) лише інструкція синтезатору без перевірки — відступ від M2 S6, A5 (feature critic,
  раунд 2).
- Q4: Бюджет міряє інструкції самих читачів (`measure` з `facilitation`), ін'єкцією — chosen because M2 S6 рахує те,
  що модель читає за один виклик, а текст інструкцій будує `facilitation`, яку `knowledge` імпортувати не може (шари).
  Rejected: (a) рахувати лише текст пам'яті — не те, що читає модель; (b) лічильник токенів моделі (`count_tokens`)
  — мережевий виклик на кожну перевірку заради межі, до якої інструкції не наблизяться (12 346 токенів сьогодні).
- Q5: `apply_memory` не приймає карток узагалі — chosen because AC1a: інваріант будовою — функція, що не має входу для
  карток, не може їх змінити. Rejected: загальна `apply(cards, memory)` з перевіркою «cards не змінились» — та сама
  гарантія обережністю.
- Q6: Відкат зміни карток (`publish`, `seed`) — відмова `NotRollbackable` — chosen because картки змінює лише задача
  власника (feature «Out of scope»); стрічка показує їх без кнопки. Rejected: відкочувати й картки — інший шлях
  зміни карток повз задачу власника.
- Q7: `None` з `apply_memory` для «нічого не змінює» і для «інший прогін першим» — chosen because так поводиться
  `publish`, і викликач в обох випадках не має нової ревізії. Rejected: окремий виняток для no-op — синтезатор, що
  запропонував те саме, не помилка.
- Q8: Дубль відкату тієї самої `rev` — `AlreadyRolledBack`; відкат, що нічого не змінює зараз, записується з
  порожнім `changed` — chosen because власник має бачити, що натиснув (feature, notes critic раунд 2). Rejected:
  мовчки ігнорувати no-op — стрічка показала б відкат, якого в даних немає.

## Hardest seams (test-confidence points)
- **Seam 1: відкат після пізнішої зміни того самого id.** rev 2 змінює `m1` v1→v2, rev 3 змінює `m1` v2→v3, відкат
  rev 2 → `m1` лишається v3, `changed` порожній. Тест будує записи через `apply_memory`, не руками, — інакше
  `replaced` вигаданий і тест хибно зелений.
- **Seam 2: ревізія після відкату.** rev 2 додає `m1`, відкат rev 2, потім `apply_memory` додає `m2` (rev 3) →
  `current().memory` = {`m2`} (а не {`m1`, `m2`}): rev 3 побудовано з `current()`. І те саме для `publish()` після
  відкату. Ловить «нова ревізія з сирого попереднього запису».
- **Seam 3: відмова нічого не пише.** Знімок усіх файлів `system/` до і після кожної відмови 1–5 однаковий; для 5 —
  `vet` викликано рівно з тими записами, що змінюються. Ловить «версії записано, запис змін — ні».
- **Seam 4: картки побайтно.** Після `apply_memory` і `rollback` файли під `knowledge/cards/` ті самі побайтно, а
  `cards` нового запису == `cards` попереднього. Перевірка через знімок теки, не через `current().cards`, бо інакше
  нова версія картки з тим самим вмістом пройшла б.
- **Seam 5: старі записи.** Запис змін без `observations`/`by`/`replaced` і запис пам'яті без `audience` (як у
  bucket-і з 2026-10-23) читаються; `current().n == 0` без відкатів (запечатаний `test_skelk_current.py`).
- **Seam 6: прибирання, що повторюються.** (а) rev 2 прибирає `m1`, відкат rev 2 (`m1` повертається), rev 3 прибирає
  `m1` знову → `current()` без `m1`, і після rev 4 (інший id) теж. (б) rev 2 прибирає `m1`, rev 3 додає `m1` знову,
  rev 4 прибирає → відкат rev 2 → `m1` відсутній, `changed` без `m1`. (в) ланцюжок Q2 в обох порядках. Записи — лише
  через `apply_memory` і `rollback`. (г) одночасний випадок: відкат rev 2, а запис змін rev 3 покладено руками, як
  прогін, що відкату не бачив (`replaced` іншого id, сирий `m1` = значення з `reverts`) → відкат усе одно діє на `m1`.

## Invariants (rules that hold for every input of the stated domain)
- **I1** — Зміна пам'яті не змінює карток: після будь-якого успішного `apply_memory` словник `cards` нового запису
  змін дорівнює словнику `cards` чинного стану, і жоден файл під `knowledge/cards/` не створено й не змінено.
  - Domain: будь-яка `MemoryChange`, будь-який чинний стан з ≥ 1 карткою.
  - Source: feature AC1a; Seam `apply_memory`.
  - Broken by: реалізація, що перезаписує версії карток чи будує `cards` з теки `cards/`.
- **I2** — Туди й назад: якщо зміна `R` — остання ревізія, то після `rollback(R)` `current().memory` дорівнює
  `current().memory` перед `apply_memory`, що створив `R`.
  - Domain: будь-яка успішна `MemoryChange` (upsert нових і наявних id, remove), після якої не було іншої ревізії.
  - Source: feature AC5, M2 S6 «відкат».
  - Broken by: відкат, що прибирає лише нові id, але не повертає замінені, або не відновлює прибрані.
- **I3** — Відкат не зачіпає пізнішого: для кожного id, який ревізія пізніша за `R` змінила, `current()` після
  `rollback(R)` дає ту саму версію, що й до нього.
  - Domain: будь-які послідовності `apply_memory` після `R`.
  - Source: M2 S6 «щоб нові версії, записані після нього, не відкочувались».
  - Broken by: відкат «до стану R−1» цілком.
- **I4** — Відмова нічого не пише: `VersionRejected` з `apply_memory` лишає файли `system/` такими самими.
  - Domain: кожна з п'яти причин відмови.
  - Source: Seam «перевірка версії… нічого не записано».
  - Broken by: запис версій пам'яті до перевірки.
- **I5** — Відкат тримається: після `rollback(R)` будь-яка наступна `apply_memory` чи `publish` не повертає записів,
  які відкат прибрав чи замінив, — хіба зміна сама їх upsert-ить.
  - Domain: будь-яка `MemoryChange`, `publish` з будь-якою текою карток.
  - Source: Seam «`publish`… після відкатів»; M2 S6.
  - Broken by: нова ревізія з сирого `memory` попереднього запису.
- **I6** — `n` — це найбільший номер відкату: `current().rev_pair() == KnowledgeRev(rev=найбільший rev, n=найбільший
  n або 0)`.
  - Domain: будь-яке число відкатів, 0 включно.
  - Source: M2 S6 «стан Знань = пара».
  - Broken by: `n` сталий 0 або число записів пам'яті.
- **I7** — Пізніша зміна тримається: зміна чи прибирання id ревізією, записаною після відкату, є в `current()` —
  відкат її не скасовує, і так само на всіх наступних ревізіях.
  - Domain: будь-яка послідовність з відкатом, зокрема відкат прибирання з наступним повторним прибиранням того самого
    id і відкат upsert-а з наступним upsert-ом.
  - Source: M2 S6 «щоб нові версії, записані після нього, не відкочувались»; Seam «Правило відкату».
  - Broken by: повтор `reverts` без межі — None порівнюється з відсутнім id і повертає прибраний запис.

## Exit criterion
- Контрактні тести slice-а (I1–I7 + поведінки Seam: порядок і причини відмов, `None`, `NotRollbackable`,
  `AlreadyRolledBack`, `UnknownRevision`, повтор номера відкату, `changes()` з `rolled_back`/`rollback_changed`,
  старі записи) — зелені; запечатані тести `skel_knowledge`, `cards_library` — зелені без змін.
- `scripts/smoke_test_knowledge_versions.py` (локальна тека, 25 справжніх карток, сценарний `vet`, справжній
  `measure`) друкує й перевіряє: rev після посіву, rev зміни, запис у `current().memory`, `n` після відкату = 1,
  запис зник, картки побайтно ті самі; вихід → `.engine/artifacts/knowledge-versions/smoke.txt`.
- `tests/live/test_vet_live.py` на `gemini-4-argon`/`eu`: запис «Олена з Львова втратила 3000 € на…» → причина
  (не None); узагальнений запис → None. Вихід → `.engine/artifacts/knowledge-versions/vet-live.txt`. Один прогін;
  значення «чи модель відрізняє» — так/ні, без порогу.
- `uv run pytest` (повний — наприкінці задачі; після slice-а — швидкий набір), ruff, mypy, `lint-imports` — зелені.

## Deferred to later slices
- Стрічка змін на сторінці і кнопка відкату — S3 (споживає `changes()`, `rollback()`).
- Запис причини відмови в прогін синтезатора — S3 (ловить `VersionRejected`).
- `audience` у читачах — S4 — revisit trigger: S4 починається.
- `BUDGET_CHARS` (`PROVISIONAL`) — revisit trigger: власник затвердить чи змінить його, або `measure` перейде 50 %
  межі.
- Причини `VersionRejected` до S3 ніде не видно (лише виняток викликачеві) — revisit trigger: S3 пише їх у запис
  прогону й `/learning`.

## Open items requiring human decision (if any)
- (немає)

## Critic notes (non-blocking)
- Раунд 1 (фази 2–5 разом): REVISE — повтор відкату без межі повертав пізніше прибирання → `Rollback.base`, умова (а)
  в `current()`, I7, Seam 6. Cold reader: REVISE — у проміжку (R, base] значення None все ще неоднозначне → правило за
  походженням без `base` і без порівняння значень, Q2 з ланцюжком у двох порядках, Seam 6 (б)–(г), помічник
  `_current_paths`, I1–I7 у цілі й виході. Cold reader 2: PASS; notes внесено — найменший `n` при подвійному
  відкаті, revisit trigger бюджету; `reverts` лишається у файлі як запис того, що ця ревізія поставила (для стрічки
  S3 і для читача файлу), правило його не читає; `measure` без `spoken` недооцінює на кілька рядків із ~1.7 млн —
  несуттєво. Notes: підпис `apply_memory`/`MemoryChange.by`/`ChangeView.rollback_changed` записано в
  feature «Inter-slice contracts»; `BUDGET_CHARS` позначено `PROVISIONAL`; `measure` іде за S4; рядок про невидимі
  відмови до S3.
