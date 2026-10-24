# Feature walking-skeleton — decomposition

Задача: `tasks/doing/105-walking-skeleton.md` (редакція 2, у роботу поставив власник 2026-10-21).
Джерело складу: `.engine/architecture/INDEX.md`, таблиця «Walking skeleton»; будова — M2/M3 у
`.engine/architecture/architecture-map.md`; ADR-0001, ADR-0002. Робота без нагляду: Phase 1 виведено
з файлу задачі й карт, не спитано (`/feature-architect`, «Unattended operation»).

> **Змінено задачею 202 (2026-10-23):** кнопки «завершити», `close_session`, `closed_sessions` і `s<n>.json`
> більше немає; `analyze` бере нові з минулого прогону репліки (`.engine/slices/continuous-analysis.md`). Нижче —
> історичний запис функції, як її будували.

## Goal
Найтонший наскрізний ланцюжок ThinkHow, що доводить: усі контейнери M2 стикуються.
Запрошена людина входить через IAP → створює тему → пише репліку → `gemini-4-argon` на `eu` веде її за
однією карткою (Pre-mortem, українською) і відповідає потоком (SSE) → `conversation.md` і `map.json`
лежать у Cloud Storage → людина завершує сесію → нічне завдання `analyze` (Cloud Run Job з того самого
образу, право лише читати `users`) одним викликом Gemini пише одне спостереження з посиланням на якір
репліки в `system/learning/`. Код — за M3 (папки за частинами, `platform` — єдиний, хто знає про
Google, чотири запобіжники A3). Інструкція розгортання для власника — `docs/deploy.md`.

## Acceptance criteria (owner-ratified)
Дослівно з «Готово, коли» задачі 105, яку власник поставив у роботу (це і є його рамка):
- AC1. Наскрізний ланцюжок працює на розгортанні власника; у журналі — `SKELETON_VERIFIED`.
- AC2. PR-04 `verified` з посиланням на докази: вхід Gmail, email, потік SSE крізь IAP, репліка після
  закінчення сесії IAP не губиться.
- AC3. PR-07 `verified` з посиланням на докази: файли пишуться й читаються з Cloud Run.
- AC4. Тести A3 зелені: без циклів; лише `platform` імпортує SDK Google; теки людей пише лише
  `workspace`, чужа тема недоступна, власник бачить усе; Знання змінюються лише через `knowledge`.
- AC5. Не пройшло → premise `falsified`, повернення до M2/M3 (Art. 8).

Розгортання — дія власника (задача 105, «Розгортання робить власник за інструкцією»). Тому AC1–AC3
агент довести не може: агент будує код і `docs/deploy.md`, доводить ланцюжок локально (локальний
режим) і живою перевіркою Vertex, а AC1–AC3 закриває власник за чеклістом у `docs/deploy.md` —
задача йде в `blocked/` з цим питанням (не в `done/`), доки власник не відповість.

## Build parameters (owner-authorized, from Phase 1e)
- Budgets/thresholds: жодних нових (P5: ліміти, яких не вимагає рядок цілей, не будуємо). Технічні
  значення, які потрібні коду, беруться з M2/M3: закриття сесії тишею — 24 год (domain map);
  тайм-аут виклику моделі й кількість повторів — технічне значення агента (P4: час лише записуємо);
  тайм-аут Job — явно в `docs/deploy.md` (M2, примітки critic).
- Policies:
  - помилки — один обробник у `web` → шматок сторінки «спробуйте ще раз» (M3 A4); недоступність
    моделі — окремий вид помилки з `platform.llm`;
  - журнали — JSON у stdout з ідентифікатором запиту; рядок на кожен виклик моделі (модель, токени,
    затримка, ревізія Знань `rev`/`n`); текст розмов у журнали не пишеться (M2, M3 A4);
  - дані — порядок записів M2: спершу репліка людини в `conversation.md`, потім відповідь, потім
    `map.json`; «спробуйте ще раз» генерує відповідь на вже збережену репліку, не дописує її вдруге;
    кожен файл пише одна задача (S2); шляхи `users/<id>/…` будує лише `workspace` з id від сервера.
  - локальний режим — один перемикач, усі двійники разом; відмовляється стартувати, якщо є `K_SERVICE`.
- Risk tolerance: auto-spike = yes (≤15 хв проти справжньої системи, яку агент має право кликати —
  Vertex через ADC); proceed on a PASSing spike = yes. Створення bucket-ів, сервісів, IAP — не spike,
  а розгортання власника.
- Autonomy: будувати всі slices автоматично; переривання — лише критичний набір. (Задача в режимі
  «конвеєр» без нагляду; файл задачі — дозвіл власника.)
- Principles that bear on the slices (словами, slices не читають goals):
  - P4 — якість ведення понад швидкість і ціну: модель `gemini-4-argon` (не Flash); час і токени лише
    записуємо в журнал, жодних обмежень довжини відповіді заради швидкості.
  - P5 — найпростіша форма понад запобіжники наперед: жодних порогів, лімітів, черг, кешів, rate limit,
    яких не вимагає M2/M3; що знадобиться — у «Deferred».
  - P2 — глибина: історія сесії подається моделі повністю (без обрізання в кістяку).
  - P6 — нічого обов'язкового для людини, крім самої репліки.
  - N1 — фасилітатор не дає готових відповідей: правило в системній інструкції (з PoC 101).
  - C4 — фасилітатор відповідає мовою останньої репліки людини.
  - G4 — людина бачить лише свої теми; власник — усе.

## Premises verified
- PR-01, PR-02, PR-03 — `verified` 2026-10-21 (PoC 101, `.engine/sketches/gemini-eu.md`).
- SDK-premise (нова, slice-рівень, для S1): `google-genai` 2.32.0 з `vertexai=True, location="eu"`
  стрімить `gemini-4-argon` зі `response_schema` — PASS, spike
  `.engine/artifacts/spikes/walking-skeleton-genai-eu-2026-10-21.txt` (2026-10-21).
- PR-04, PR-07 — `verified` 2026-10-24 на розгортанні власника (AC2, AC3; межі перевірки PR-04 — у
  `.engine/premises/premise-log.md`), докази `.engine/artifacts/spikes/skeleton-deploy-verify-2026-10-24.txt`.
- PR-09 (нова, feature): усі slices стикуються в один ланцюжок «HTTP-запит → workspace → facilitation →
  knowledge → platform.llm/storage → файли → learning» — перевіряє tracer (локальний e2e smoke S5 і S6).

## Out of scope (deliberately)
- Роутер, профіль проблеми, `routing.json` (F5) — картка одна, фіксована.
- 17 інших карток (F7); пам'ять досвіду — лише схема і порожній стан.
- Повна карта й показ карти людині (F8) — `map.json` пишеться, але сторінка його не показує.
- Кроки, оцінки D1, `steps.json` (F9).
- Версії Знань, стрічка змін, відкати (F11); синтезатор (F12).
- Голос і вибір мови, `profile.json` з мовою (F13); `profile.json` пише лише email.
- Сторінка спостережень для власника (повна F10) — власник бачить файл у Cloud Storage.
- Закриття сесії «тишею 24 год» у застосунку (показ) — аналізатор рахує його сам з часу останньої репліки.
- Саме розгортання (bucket-и, сервіси, IAP, Scheduler) — дія власника за `docs/deploy.md`.
- План Б (другий виклик для карти) — PoC 101 показав, що одного виклику досить (PR-02).

## Звірка з цілями
- служить: G4 (AC4 — лише `workspace` пише теки людей, чужа тема недоступна, власник бачить усе);
  G2 (розмова й карта у файлах теми, повернення до теми); G6 (спостереження з посиланням на якір
  репліки); G3 (друге завдання навчання — каркас самонавчання); G1/N1 (фасилітатор веде за карткою без
  готових відповідей). Повністю жодну ціль кістяк не закриває — він знімає архітектурний ризик під усі.
- вибір між варіантами розв'язав: склад — правило walking skeleton з INDEX.md; P5 — без запобіжників
  наперед; P4 — модель за якістю; решта (розбиття на slices, порядок) — принципи не розрізняють, вибір
  технічний.
- не-цілі й обмеження: N1 — у системній інструкції фасилітатора; N2 — IAP лише для запрошених; N3,
  N4 — нічого не будуємо; C1 — `europe-west3` + `eu` endpoint; C3 — IAP; C4 — мова відповіді = мова
  репліки; C5 (голос у першій версії) — не в кістяку, F13 (повна версія ще не перша).

## Slices (the DAG)
- **S1 skel-platform** — delivers: `platform.config` (pydantic-settings; локальний режим відмовляє при
  `K_SERVICE`), `platform.log` (JSON у stdout, request id), `platform.storage` (Cloud Storage +
  локальна тека: read/write/list/create_if_absent), `platform.identity` (перевірка IAP JWT
  `x-goog-iap-jwt-assertion` + фіксована особа), `platform.llm` (Vertex `google-genai` streaming зі
  structured output + сценарний двійник; тайм-аут, повтори з backoff+jitter, рядок журналу;
  `KnowledgeRev(rev: int, n: int)` визначено тут — непрозорі для `platform` поля журналу);
  запобіжник A3.2 «лише `platform` імпортує SDK Google» — з першого дня як pytest-тест, що розбирає
  (AST) усі модулі `src/thinkhow/` поза `platform/` (росте разом з кодом); import-linter
  (`[tool.importlinter]` у `pyproject.toml`) з контрактами «без циклів» і «дозволені стрілки M3» —
  з першого дня, і кожен наступний slice дописує в них свій пакет; pytest-тест запускає `lint-imports` ·
  contract out: див. «S1 → *» · depends on: — · block: foundation
- **S2 skel-knowledge** — delivers: pydantic-схеми `Card` (половина роутера + половина фасилітатора з
  фазами) і `MemoryRecord`; `cards/pre-mortem.yaml` (з `sketches/gemini-eu/context/card-pre-mortem.md`);
  `knowledge.seed(storage)` створює ревізію 1 «лише якщо ще немає»; `knowledge.current(storage)`
  повертає чинну ревізію з картками й пам'яттю (порожня) · depends on: S1 · block: conversation
- **S3 skel-facilitation** — delivers: `facilitation.respond(context, llm)` — системна інструкція з
  PoC 101, один виклик, потік дельт поля `reply` + фінальне валідне `FacilitatorUpdate` (фаза, зміни
  карти); невалідне оновлення — повтор лише оновлення · depends on: S1, S2 · block: conversation
- **S4 skel-workspace** — (depends on: S1, S3; не на S2 — Знання сюди не імпортуються) delivers: пакет `access` — `CurrentUser(id, email, is_owner)` і правило
  власника `access.current_user(identity: Identity, settings) -> CurrentUser` (`is_owner` — email збігся
  з `owner_email` у `platform.config`, без урахування регістру); теми (створити / перелічити свої / відкрити; власник — усі),
  `profile.json` (email; `ensure_profile(user)` — «лише якщо ще немає», кличе шар входу `web` на
  кожному запиті), `conversation.md` з номерованими репліками й сесіями, позначка «завершено»,
  `map.json` (застосування `map_updates`), функція «відповісти на репліку» (зберегти репліку → потік
  від facilitation → дописати відповідь → map), «спробуйте ще раз», читання всіх людей для owner/
  learning; кожна функція отримує `storage` аргументом, а «відповісти» — ще й `facilitate`
  (див. контракт S3 → S4) · depends on: S1, S3 · block: conversation
- **S5 skel-web** — delivers: FastAPI-застосунок: шар входу (лише з'єднує `platform.identity.Identity` →
  `access.current_user` → `workspace.ensure_profile`), маршрути `/topics/<uid>/<topic_id>` для своїх і
  (власник) чужих тем,
  сторінки (список тем, нова тема, розмова з якорями `#t<n>`), POST репліки → SSE, кнопка вимкнена до
  кінця потоку, «спробуйте ще раз», «завершити», чернетка репліки в браузері живе до підтвердження
  збереження сервером (PR-04: репліка після закінчення сесії IAP не губиться); потік читає сторінка
  через `fetch` POST і `ReadableStream` тіла `text/event-stream` (EventSource вміє лише GET); без
  HTMX — кілька рядків власного JS (див. «Рішення»); один обробник помилок;
  **composition root** застосунку (`web/app.py` будує `Storage`, `Llm` з `platform.config`, читає
  `knowledge.current(storage)` і зв'язує `facilitate`); локальний e2e smoke
  `tests/smoke/test_e2e_local.py` до `conversation.md` + `map.json` · depends on: S2, S4 · block:
  conversation · **TRACER BULLET, частина 1**
- **S6 skel-learning** — delivers: `learning.analyze(storage, llm, now)` — закриті сесії (кнопка або
  24 год тиші) без спостереження → один виклик Gemini → `system/learning/observations/<uid>/<topic>/
  s<k>.json` з якорем репліки (стале ім'я — повтор перезаписує); `learning/job.py` — точка входу
  `python -m thinkhow.learning.job seed|analyze` — **composition root** завдання (будує `Storage`, `Llm`);
  розширює `tests/smoke/test_e2e_local.py` до `analyze` і якоря спостереження — **TRACER BULLET, частина
  2**: PR-09 `verified` лише після S6 · depends on: S1, S2, S4 · block: learning
- **S7 skel-guards-deploy** — delivers: pytest-тести, що разом із import-linter (S1, росте з кожним
  slice), тестом A3.2 з S1 і тестами G4 з S4 становлять чотири запобіжники A3: «шляхи `users/` будує
  лише `workspace`» і «у `system/knowledge/` пише лише `knowledge`»; зведений тест-перелік AC4; `Dockerfile`; `docs/deploy.md` (bucket-и з версіями, service accounts і права, Cloud Run service
  з IAP і OAuth «External», Job `seed`/`analyze`, Scheduler, регіон журналів ЄС) з чеклістом власника
  для PR-04/PR-07/AC1 · depends on: S5, S6 · block: guards

## Inter-slice contracts
- S1 → S2/S4/S6: `Storage` протокол — `read(bucket: Bucket, path: str) -> bytes | None`,
  `write(bucket, path, data: bytes, content_type: str) -> None`, `create_if_absent(bucket, path, data,
  content_type) -> bool`, `list(bucket, prefix) -> list[str]`; `Bucket = Literal["users", "system"]`
  (логічні імена; справжні імена — з config).
- S1 → S3/S6: `Llm` протокол — `stream_json(system: str, contents: list[Turn], schema: type[BaseModel],
  rev: KnowledgeRev | None) -> Iterator[LlmEvent]`, де `LlmEvent` = `ReplyDelta(text)` | `Done(raw_json:
  str, usage)`; `generate_json(system, contents, schema, rev) -> BaseModel`; помилка недоступності —
  `LlmUnavailable`. `Turn(role: Literal["user","model"], text: str)`.
- S1 → S5: `make_identity(settings).identify(headers) -> Identity(id: str, email: str)` або `IdentityError`.
- S2 → S3: `CurrentKnowledge(rev: int, n: int, cards: dict[str, Card], memory: list[MemoryRecord])`;
  `Card.facilitator` — фази з `id`, метою, виходом; текст картки для промпту — `card_prompt(card) -> str`.
- S3 → S5 (зв'язування): `respond(ctx: FacilitationContext, knowledge: CurrentKnowledge, llm: Llm)
  -> Iterator[ReplyDelta | FacilitatorUpdate]`; `web` робить з нього
  `facilitate = functools.partial(respond, knowledge=..., llm=...)` типу
  `Facilitate = Callable[[FacilitationContext], Iterator[ReplyDelta | FacilitatorUpdate]]` (тип — у
  `facilitation`).
- S3 → S4: `FacilitationContext(card_id: str, history: list[Turn], problem_map: ProblemMap,
  turn_no: int, text: str)`, `Facilitate`, `ReplyDelta`, `FacilitatorUpdate`, `ProblemMap`, `MapUpdate`
  — типи з `thinkhow.facilitation.types` (стрілка M3 workspace → facilitation; імпорт лише цього
  підмодуля, skel-facilitation Q6); `workspace` не бачить ні Знань, ні `Llm`;
  `FacilitatorUpdate(reply, current_phase_id, phase_exit_met, map_updates: list[MapUpdate])` — схема
  з PoC 101 (`sketches/gemini-eu/session.py`).
- S4 → S5: усі функції `workspace` мають першим іменованим аргументом `storage: Storage` (ручний DI,
  M3 A2), `reply`/`retry` — ще й `facilitate: Facilitate`. `workspace.list_topics(user)`, `create_topic(user, title) -> TopicId`,
  `open_topic(user, ref: TopicRef) -> TopicView`, `reply(user, ref, text) -> Iterator[ReplyEvent]`
  (`Saved(turn_no)` → `Delta(text)`… → `Answered(turn_no)` | `Failed`), `retry(user, ref)` (skel-workspace),
  `close_session(user, ref)`, `ensure_profile(user)`; `user` — `access.CurrentUser(id, email,
  is_owner)`. `TopicId` — `str`, який видає сервер (`t-` + 12 hex, перевіряється регулярним виразом);
  `TopicRef(uid: str, topic_id: TopicId)` — тема адресується парою; `uid` — стабільний id від IAP
  (перевіряється регулярним виразом, а доступ — правилом: `user.id == ref.uid` або `user.is_owner`,
  інакше `TopicNotFound`, не «заборонено» — щоб не видати існування). Людина відкриває свою тему і
  власник — чужу тим самим маршрутом `/topics/<uid>/<topic_id>`.
- S6 → власник (G6): спостереження містить `uid`, `topic_id`, `session_no`, `turn` і `link` =
  `/topics/<uid>/<topic_id>#t<turn>` — у формі маршруту S5.
- S2 → S1 (значенням): `CurrentKnowledge.rev_pair() -> platform.llm.KnowledgeRev`.
- S4 → S6: `workspace.all_topics_for_learning() -> Iterator[TopicRef]`,
  `workspace.closed_sessions(topic_ref, now) -> list[ClosedSession(session_no, turns:
  list[NumberedTurn], closed_at)]`, `NumberedTurn(no: int, role: Literal["user","model"], text: str)` —
  лише читання. Номер має **кожна** репліка сесії (і людини, і фасилітатора) — наскрізно в межах теми;
  якір `#t<no>`.
- S5, S6 → S7: пакети `thinkhow.{web,access,workspace,facilitation,knowledge,learning,platform}`
  існують; точки входу `uvicorn thinkhow.web.app:app` і `python -m thinkhow.learning.job` з `PYTHONPATH=src` (без `[build-system]`, skel-platform Q8).

## Integration exit criterion
Локально: `tests/smoke/test_e2e_local.py` (локальний режим: локальна тека + сценарна модель + фіксована
особа) проходить увесь ланцюжок seed → створити тему → репліка → SSE → `conversation.md` + `map.json`
→ завершити → `analyze` → файл спостереження з якорем `#t<n>` існуючої репліки. Живо: `pytest -m live`
— один справжній виклик `gemini-4-argon` на `eu` через `platform.llm` (S3: facilitation на реальній
моделі). Хмарно (AC1–AC3): чекліст власника в `docs/deploy.md`.

## Рішення архітектора (дрібні, двосторонні двері)
- **Composition roots** — `web/app.py` і `learning/job.py` будують адаптери `platform.storage`/
  `platform.llm` з `platform.config` і передають їх аргументами; це уточнення стрілок M3 (діаграма
  називала лише `web → identity`): composition root може імпортувати `platform`. `workspace` не
  імпортує ні `knowledge`, ні `platform.llm` — Знання й модель приходять у `workspace` як `facilitate`.
  Записано AUTONOMOUS у `.engine/overseer/escalations.md` (2026-10-21, walking-skeleton-wiring).
- Картка — YAML (`cards/pre-mortem.yaml`, M3 A1); PyYAML стоїть лише як залежність `fastapi[standard]`
  (як `google-auth`); у `pyproject.toml` не дописується — пропозиція у звіті.
- `google-auth` (і `requests` для його транспорту) не дописано в `pyproject.toml`: це залежності
  `google-cloud-storage`/`google-genai`, що вже стоять, а M3 A2 прямо називає `google-auth` для
  перевірки IAP. Додати пакет — дія з дозволу власника; явне оголошення пропонується у звіті.
- Без HTMX (M2 S5 його називав): кістякові досить звичайних форм і ~30 рядків JS; HTMX не треба
  завантажувати чи тягти з CDN. Повернути — дешево.

## Deferred to later features
- Перевірка версії Знань і `changes/<rev>` поза `seed` — F11 — коли синтезатор почне писати версії.
- Показ карти, роутер, оцінки, голос — F5, F8, F9, F13 за порядком INDEX.md.
- Тримати екземпляр теплим — під час розгортання (власник, двосторонні двері).

## Open items requiring human decision (if any)
- Critic: 2 раунди (REVISE: немає slice для `access` → виправлено; REVISE: композиція ламала стрілки
  M3, немає composition root, import-linter запізно → виправлено в цій редакції). Третього раунду немає
  (правило «два раунди»); залишок — двосторонні двері, записано AUTONOMOUS в escalations.md.
- AC1–AC3 потребують розгортання власника — питання в `blocked/` з чеклістом наприкінці задачі.
  Закрито 2026-10-24: `SKELETON_VERIFIED` (`.engine/PROGRESS.md`).
