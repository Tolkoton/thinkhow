# Slice skel-workspace — planning artifact

Feature: `.engine/architecture/feature/walking-skeleton.md`, S4 (block: conversation). Driven mode: frame
supplied by the feature artifact, not asked. Depends on S1 (`platform`, 50382d7) і S3 (`facilitation.types`,
a617db4); не на S2 — Знання сюди не імпортуються.

## Goal
Найтонші частини F1 (особа → `CurrentUser`) і F2/F3 у `workspace` (INDEX.md, «Walking skeleton»): створити,
перелічити, відкрити тему; папка `users/<uid>/<topic_id>/`; `conversation.md` з номерованими репліками й
сесіями, позначка «завершено»; `map.json`; «відповісти на репліку» в порядку M2 (репліка → потік →
відповідь → карта); «спробуйте ще раз»; `profile.json`; читання всіх тем для власника й навчання;
«чужа тема недоступна, власник бачить усе» (G4). Вимірна ціль: `pytest` зелений; smoke-скрипт веде дві
репліки через сценарну модель у локальній теці й друкує `conversation.md` і `map.json`.

## Premise verified
- S1 `Storage`: `read`, `write`, `create_if_absent`, `list` (рядковий префікс, рекурсивно — S1 Q3);
  шляхи без `..`/порожніх сегментів (I3 S1). Дописування в кінець файлу Storage не вміє — `conversation.md`
  читається й переписується цілим (одна задача — один файл, M2 S2; подвійне надсилання — «останній запис
  перемагає», M2, прийнятий залишковий ризик).
- S3 `facilitation.types`: `FacilitationContext`, `Facilitate`, `ReplyDelta`, `FacilitatorUpdate`,
  `ProblemMap`, `MapItem`, `MapUpdate`, `Turn`, `FacilitationError`; `turn_no` — наскрізний номер репліки
  людини (S3 Q5).
- S1 `platform.identity.Identity(id, email)`; `platform.config.Settings.owner_email`.
- Сесія закривається кнопкою «завершити» або після 24 год без реплік (domain map, «Сесія»; feature «Build
  parameters»: 24 год). Закрита сесія не відкривається знову; продовження — нова сесія.

## Out of scope (deliberately)
- Показ закриття сесії тишею людині (feature «Out of scope») — S5 і пізніше; **обчислення** закриття тут,
  бо його потребує контракт S4 → S6 (`closed_sessions(ref, now)`, сталий `s<k>.json`).
- `routing.json`, вибір картки (F5): картка кістяка — стала `CARD_ID = "pre-mortem"` у `workspace`.
- `steps.json`, оцінки, «чи стало ясніше?» (F9); мова в `profile.json` (F13).
- Показ карти людині (F8) — `map.json` лише пишеться й читається.
- Будь-які HTTP, сторінки, SSE — S5.
- Блокування від подвійного надсилання (M2: прийнятий ризик).

## Seam (contract)
Пакет `src/thinkhow/access/`:
- `@dataclass(frozen=True) CurrentUser(id: str, email: str, is_owner: bool)`.
- `current_user(identity: Identity, settings: Settings) -> CurrentUser` — `is_owner` = `identity.email` і
  `settings.owner_email` збігаються без урахування регістру й пробілів по краях; порожній `owner_email` →
  ніхто не власник. Нічого не пише.

Пакет `src/thinkhow/workspace/` (публічне — з `__init__.py`; імпортує лише `thinkhow.facilitation.types`,
`thinkhow.access`, `thinkhow.platform.storage`):
- Ідентифікатори: `TopicId = str` за `^t-[0-9a-f]{12}$` (видає `create_topic`: `"t-" + secrets.token_hex(6)`);
  `uid` за `^[A-Za-z0-9_-]{1,128}$` (S1 identity); `@dataclass(frozen=True) TopicRef(uid: str, topic_id:
  str)`. `TopicNotFound(Exception)` — тема не існує, ідентифікатор не за виразом, або чужа (правило
  доступу); один і той самий виняток, щоб не видати існування.
- Правило доступу: **читати** (`open_topic`) — `user.id == ref.uid` або `user.is_owner`; **писати**
  (`reply`, `retry`, `close_session`) — лише `user.id == ref.uid` (власник читає чужі теми, але не пише в
  них). Інакше `TopicNotFound`.
- Розкладка bucket-а `users`: `<uid>/profile.json`; `<uid>/<topic_id>/conversation.md`;
  `<uid>/<topic_id>/map.json`. Шляхи будує лише `workspace` з `uid` від сервера (`user.id`) і `TopicId`,
  який видав сервер (M3 A3.3).
- `conversation.md` (`text/markdown; charset=utf-8`) — людиночитний і розбірний:
  ```
  <!-- thinkhow:format 1 -->
  # <title>
  <!-- thinkhow:session 1 -->
  <!-- thinkhow:turn 1 user 2026-10-22T16:00:00Z -->
  <текст репліки>
  <!-- thinkhow:turn 2 model 2026-10-22T16:00:09Z -->
  <текст відповіді>
  <!-- thinkhow:closed 1 2026-10-22T16:30:00Z -->
  ```
  Рядок тексту, що починається з `<!-- thinkhow:` або з `\`, пишеться з додатковим `\` попереду; при
  читанні один такий `\` знімається (I1). Текст **кожної** репліки (людини й фасилітатора) нормалізується при збереженні: `\r\n` і `\r` →
  `\n`, обрізання пробілів по краях; текст людини, порожній після цього → `ValueError` (під час виклику);
  відповідь фасилітатора, порожня після цього → `Failed("EmptyReply")` (репліка людини лишається,
  `map.json` не змінено). `title` — один рядок (переводи
  рядків → пробіли, обрізання; порожній → `ValueError`), екранується так само. Формат може лише
  розширюватися (нові види маркерів); рядок `format` — для читача, що прийде після.
- `map.json` (`application/json`) — `ProblemMap.model_dump_json()`; немає файла → `ProblemMap()`.
- Типи: `@dataclass(frozen=True) NumberedTurn(no: int, role: Literal["user", "model"], text: str, at:
  datetime)`; `Session(no: int, turns: list[NumberedTurn], closed_at: datetime | None)` (закрита
  кнопкою — час позначки; тишею — час останньої репліки + 24 год; відкрита — `None`); `TopicView(ref,
  title, sessions: list[Session], problem_map: ProblemMap, awaiting_answer: bool)` (`awaiting_answer` —
  остання репліка теми — людини, без відповіді, **і остання сесія відкрита на `now`**; репліка людини
  без відповіді в закритій сесії лишається її останньою реплікою); `TopicSummary(ref, title)`;
  `ClosedSession(session_no, turns: list[NumberedTurn], closed_at: datetime)`.
- Події відповіді: `Saved(turn_no)`, `Delta(text)`, `Answered(turn_no)`, `Failed(reason: str)` — frozen
  dataclasses; `ReplyEvent` — їх об'єднання.
- Функції (першим іменованим аргументом — `storage: Storage`; час — параметром `now: datetime`, UTC;
  `now` без часового поясу → `ValueError`; час у файл пишеться з точністю до секунди (`now` обрізано), і тиша рахується від записаного значення):
  - `ensure_profile(storage, user) -> None` — `create_if_absent` `<uid>/profile.json` з `{"email": …}`.
  - `create_topic(storage, user, title, now) -> TopicId` — пише `conversation.md` (заголовок і сесія 1,
    без реплік) і `map.json` (`ProblemMap()`).
  - `list_topics(storage, user) -> list[TopicSummary]` — лише теми `user.id`, у порядку `topic_id`.
  - `all_topics_for_learning(storage) -> Iterator[TopicRef]` — усі теми всіх людей (з шляхів
    `<uid>/<topic_id>/conversation.md`, що відповідають виразам); **єдина** функція читання всіх людей
    (M3 A3.3): власникові її дає `web` лише для `is_owner` (передумова S5 — `user` тут немає; запобіжник
    G4 у S7), навчанню — `learning`. Назви тем для списку власника — `open_topic` на кожен `ref`.
  - `open_topic(storage, user, ref, now) -> TopicView` — читання за правилом доступу.
  - `reply` і `retry` перевіряють правило доступу, нормалізують `text` (`ValueError`) і кидають
    `PendingAnswer` / `NothingToRetry` **під час виклику, до повернення ітератора** (звичайна функція, що
    перевіряє й повертає внутрішній генератор); через ітерацію приходять лише `Saved`, `Delta`,
    `Answered`, `Failed` (Q4: `web` перетворює винятки на відповідь до відкриття потоку SSE).
  - `reply(storage, facilitate, user, ref, text, now) -> Iterator[ReplyEvent]` — правило запису; якщо
    `awaiting_answer` — `PendingAnswer(Exception)` (спершу «спробуйте ще раз»); якщо остання сесія закрита
    (кнопкою або тишею на `now`) — дописує маркер нової сесії. Порядок (M2): (1) дописати репліку людини в
    `conversation.md` → `Saved(n)` (`n` = найбільший номер у темі + 1); (2) викликати `facilitate`
    (`FacilitationContext(card_id=CARD_ID, history=` репліки поточної сесії до `n`, не включно (S3: «без
    поточної»; Q6 звужує «попередні репліки теми» S3 до поточної сесії), `problem_map`, `turn_no=n`,
    `text)`), кожну `ReplyDelta` → `Delta`; (3) дописати відповідь (`FacilitatorUpdate.reply`) номером
    `n+1` → (4) записати `map.json` (застосувати `map_updates` по черзі: `add`/`update` — пункт `MapItem(id, type,
    text, turn)` за `id` (наявний `id` — заміна на місці; новий — у кінець переліку), `remove` — прибрати за `id`, невідомий `id` у `update`/`remove` — пропустити;
    `phase_id = current_phase_id`; `last_turn = n+1`) → `Answered(n+1)`. Виняток з `facilitate` (будь-який)
    → `Failed(<назва класу>)`; `facilitate` закінчився без `FacilitatorUpdate` → `Failed("NoUpdate")`; в
    обох випадках репліка людини лишається, `map.json` не змінено, нічого не кидається далі. Перший
    `FacilitatorUpdate` закінчує потік; що `facilitate` віддав би після нього, не читається.
  - `retry(storage, facilitate, user, ref, now) -> Iterator[ReplyEvent]` — якщо `awaiting_answer` (тобто
    й остання сесія відкрита на `now`): кроки (2)–(4) для вже збереженої останньої репліки людини (її `n`,
    без повторного запису; `Saved` не віддається); інакше `NothingToRetry(Exception)`. Після закриття
    (кнопкою чи тишею) репліка без відповіді лишається в закритій сесії; `reply` відкриває нову (Q7).
  - `close_session(storage, user, ref, now) -> None` — дописує маркер `closed` останньої відкритої сесії;
    якщо вона вже закрита (кнопкою чи тишею) — нічого.
  - `closed_sessions(storage, ref, now) -> list[ClosedSession]` — лише читання, без правила доступу
    (для `learning`; `ref` — з `all_topics_for_learning`); `ref` не за виразом або тема не існує →
    `TopicNotFound`; сесії без жодної репліки не віддаються. Сесія без реплік не закривається тишею (немає «останньої
    репліки»); лише кнопкою.
- `CARD_ID = "pre-mortem"`; `SILENCE = timedelta(hours=24)`.
- Errors: `TopicNotFound`, `PendingAnswer`, `NothingToRetry`, `ValueError` — кидаються; обробник у `web`.
- Dependencies (injected): `storage`, `facilitate`, `now`.
- import-linter: `workspace` → `facilitation.types`, `access`, `platform.storage`; ↛ `knowledge`,
  `platform.llm` (контракт S1, непрямо теж — статично: граф імпортів не рахує `__init__` батьківського
  пакета, який під час виконання імпортує `respond`; S3 Q6). `access` ↛ `platform.storage` (новий forbidden-контракт
  «access writes nothing»).
- Does NOT do: виклик моделі, Знання, HTTP, вибір картки, оцінки.

## Decisions (with WHY)
- Q1 (ADR-0004): `conversation.md` з маркерами-коментарями HTML. Чому: файл читає людина (markdown), а розбирає
  код; коментарі не видно в показаному markdown. Екранування `\` робить будь-який текст репліки
  безпечним (людина не підробить номер чи сесію). Rejected: JSON Lines — не «розмова» для людини (M2 S2
  «conversation.md»); заголовки `### t3` — їх може написати сама людина.
- Q2: власник читає чужі теми, але не пише в них. Чому: G4 «власник бачить усе» — про читання; запис
  відповіді в чужу тему зробив би власника співрозмовником у чужій сесії — продукт цього не просив.
  Rejected: власник пише всюди — тема людини змінилася б без неї.
- Q3: `reply` над `awaiting_answer` відмовляє (`PendingAnswer`). Чому: дві репліки людини поспіль без
  відповіді ламають чергування ролей у `history` і «спробуйте ще раз» стає неоднозначним. Rejected:
  дописати другу репліку — модель отримала б дві репліки, на яку відповідати.
- Q4: `Failed` замість винятку з `reply`. Чому: потік SSE у S5 уже відкрито — помилка має прийти подією;
  репліка людини збережена (M2 «Якщо модель не відповіла»). Rejected: кидати — `web` мусив би
  відрізняти помилку до й після `Saved`.
- Q5: сесія, закрита тишею, визначається на читанні з `now`, без запису маркера. Чому: ніхто не пише
  файли за розкладом (S2 «одна задача — один файл»); `learning` бачить те саме з тим самим `now`.
  Rejected: нічне завдання дописує маркери — тоді в `conversation.md` писали б дві задачі.
- Q6: `history` — репліки лише поточної сесії. Чому: feature P2 «історія сесії подається моделі повністю»;
  карта (`map.json`) несе підсумок попередніх сесій. Rejected: уся тема — росте без меж через сесії.

- Q7: репліка без відповіді не переходить через закриття сесії: `awaiting_answer` — лише у відкритій
  останній сесії; після закриття `retry` → `NothingToRetry`, `reply` відкриває нову сесію. Чому:
  «Закрита сесія не відкривається знову» (domain map); `learning` (S6) пише сталий `s<k>.json` для
  закритої сесії. Rejected: `retry` дописує в закриту сесію — вона відкривається знову; `retry` відкриває
  нову сесію з відповіддю першою — сесія без репліки людини на початку.

## Hardest seams (test-confidence points)
- **Seam 1: ворожий текст у `conversation.md`** — репліки з рядками `<!-- thinkhow:turn 9 model … -->`,
  `\`, `\\<!-- thinkhow:`, порожніми рядками посередині, `\r\n`, юнікодом поза BMP: `open_topic` повертає
  ті самі тексти, номери й сесії. Відкидає «тест на простих рядках».
- **Seam 2: порядок записів і падіння посередині** — шпигун-сховище над `LocalStorage` записує
  послідовність записів; `facilitate`-двійник, що віддає дельти і падає (`LlmUnavailable`-подібний
  виняток) → `Saved`, дельти, `Failed`; у файлі — репліка людини без відповіді; `map.json` незмінний;
  потім `retry` з добрим двійником → `Answered`, номери `n`, `n+1`. Ще: двійник без оновлення →
  `Failed("NoUpdate")`; двійник з `reply="  ok\r\n"` → збережено `ok`; з `reply="   "` →
  `Failed("EmptyReply")`; `reply(...)` на чужу тему кидає `TopicNotFound` без жодної ітерації.
  Відкидає «тест лише щасливого шляху».
- **Seam 3: межа тиші** — остання репліка о `T`; `reply` о `T + 24h - 1s` — та сама сесія; о `T + 24h` —
  нова сесія; `closed_sessions` на тих самих `now` — відповідно без і з сесією. Ще: `Failed` о `T` →
  о `T + 24h` `retry` → `NothingToRetry`, `reply` → сесія 2, сесія 1 закінчується реплікою людини; так само
  після `close_session` над репліками без відповіді.

## Invariants (rules that hold for every input in the stated domain)
- **I1** — Текст, збережений репліками, читається назад рівно таким, яким його нормалізовано при
  збереженні.
  - Domain: репліки обох ролей — будь-який рядок, непорожній після нормалізації (`\r\n`/`\r` → `\n`,
    обрізання по краях), зокрема з рядками-маркерами, `\` на початку рядка, порожніми рядками, юнікодом поза BMP.
  - Source: Seam (`conversation.md`, екранування); G2 (розмова не губиться); G6 (якорі на репліки).
  - Broken by: розбір, що бере рядок тексту `<!-- thinkhow:…` за маркер; екранування без зворотного.
- **I2** — Людина ніколи не читає й не змінює чужу тему; власник читає будь-яку, але не пише в чужу.
  - Domain: будь-які двоє людей (власник чи ні), будь-які `TopicRef`, зокрема з чужим `uid`, неіснуючим
    `topic_id`, ідентифікаторами не за виразом; усі функції з правилом доступу.
  - Source: G4; M3 A3.3; feature S4 → S5 (правило доступу, `TopicNotFound`).
  - Broken by: перевірка лише `topic_id` без `uid`; шлях з `ref.uid` для запису замість `user.id`.
- **I3** — Номери реплік теми — 1…N без пропусків і повторів, наскрізно через сесії; кожна репліка (людини
  й фасилітатора) має свій номер.
  - Domain: будь-яка послідовність `reply`, `retry`, `close_session`, падінь `facilitate` і проміжків часу
    (зокрема > 24 год).
  - Source: feature S4 → S6 («Номер має кожна репліка… наскрізно в межах теми»); G6.
  - Broken by: нумерація в межах сесії; номер відповіді, що зсувається після `Failed` і `retry`.
- **I4** — Репліка людини записана до першого виклику `facilitate` і не зникає після його падіння.
  - Domain: будь-який `facilitate`, що кидає будь-який виняток до, посеред або після дельт.
  - Source: M2 «Репліка: спершу дописується `conversation.md`, потім `map.json`. Якщо модель не
    відповіла…»; PR-04 (репліка не губиться).
  - Broken by: запис репліки разом із відповіддю наприкінці.

- **I5** — Сесія, закрита на `now`, не отримує жодної репліки ні на якому пізнішому `now`.
  - Domain: будь-яка послідовність `reply`, `retry`, `close_session`, падінь `facilitate` і `now`, що не
    спадають, зокрема репліка без відповіді на межі закриття.
  - Source: domain map, «Сесія» («Закрита сесія не відкривається знову»); feature S6 (сталий `s<k>.json`).
  - Broken by: `retry`, що дописує відповідь у сесію, закриту тишею чи кнопкою.

## Exit criterion
- `uv run pytest` зелений (контрактні тести, A3, попередні slices); `uv run ruff check src tests scripts`,
  `uv run mypy src tests scripts`, `PYTHONPATH=src uv run lint-imports` — без помилок.
- `uv run python scripts/smoke_test_skel_workspace.py` — у тимчасовій теці: власник і людина; людина
  створює тему, дві репліки через сценарний `facilitate` (дельти + оновлення карти; перша спроба другої
  репліки падає → `Failed`, потім `retry` → `Answered`), завершує сесію;
  друкує `conversation.md` і `map.json`; перевіряє: номери 1–4, сесія 1 закрита, у карті пункти з
  оновлень, людина 2 не відкриває тему (`TopicNotFound`), власник відкриває, `all_topics_for_learning`
  дає тему, `closed_sessions` — одну сесію з 4 репліками. Справжній bucket — PR-07, розгортання власника.

## Accepted risks
- Падіння сховища між кроками (3) і (4): відповідь у `conversation.md`, `map.json` застарілий,
  `awaiting_answer` хибне — `retry` цього не виправить. Наслідок порядку записів M2 і прийнятого
  залишкового ризику («кожен файл пише одна задача», без транзакцій на кілька файлів, ADR-0001); наступна
  відповідь пише карту знову з тих оновлень, що прийдуть.

## Deferred to later slices
- `routing.json`, вибір картки — F5 — trigger: задача F5 (тоді `CARD_ID` зникає).
- «Чи стало ясніше?», оцінки, кроки — F9.
- Запис власника в чужу тему — якщо власник попросить (G4 v2 зараз — лише читання).

## Open items requiring human decision (if any)
- None.

## Revisions during planning
- **Phases 2–5 (critic round 1) — challenge:** "an unanswered human turn crossing a session close is unspecified, and `retry` reopens a silence-closed session" → **revised:** Q7, `awaiting_answer` лише у відкритій сесії, I5, випадки Seam 2/3 → **reason:** «Закрита сесія не відкривається знову» і сталий `s<k>.json` S6.
- **Cold-reader — challenge:** "when `reply`/`retry` raise their pre-stream errors is unspecified" → **revised:** перевірки під час виклику, до повернення ітератора; випадок у Seam 2 → **reason:** S5 мусить відповісти 404/фрагментом до відкриття SSE (Q4).
- Нотатки cold-reader-а прийнято: час до секунди (2), сесія без реплік не закривається тишею (3), заміна на місці/порядок (4), перший `FacilitatorUpdate` закінчує потік (5), прийнятий ризик (3)→(4) (6). Уточнення контракту фічі S4 → S5: `retry(storage, facilitate, user, ref, now)` — за `ref`, не `topic_id` (7).
- **Cold-reader 2 — challenge:** "the facilitator's reply text is not normalized and the I1 domain covers only the person's" → **revised:** нормалізація обох ролей, `Failed("EmptyReply")`, I1 Domain — обидві ролі, випадки Seam 2 → **reason:** `respond` не нормалізує, `min_length=1` пропускає `"  "`; виправлено без третього прогону (escalations.md, skel-workspace-cold-reader). Нотатки: Out of scope про показ тиші (2), ADR-0004 (3), «статично» (4), `closed_sessions` → `TopicNotFound` (5), `now` без поясу → `ValueError` (7).
- Нотатки прийнято: `history` до `n` не включно (N1, N2), `Failed("NoUpdate")` (N3), передумова S5 для `all_topics_for_learning` (N4), рядок `format` і екранування назви (N5), Failed → retry у smoke (N6).
