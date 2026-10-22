# Slice skel-web — planning artifact

Feature: `.engine/architecture/feature/walking-skeleton.md`, S5 (block: conversation) — **TRACER BULLET, частина
1**. Driven mode: frame supplied by the feature artifact, not asked. Depends on S1–S4 (50382d7, f8f5fb5, a617db4,
a1d5218).

## Goal
Найтонші частини F1/F2/F3 у `web` (INDEX.md, «Walking skeleton»): FastAPI-застосунок, де особа береться лише з
підписаного заголовка IAP (або фіксована в локальному режимі), сторінки «мої теми», «нова тема», розмова з якорями
`#t<n>`, репліка → відповідь потоком SSE через `fetch` POST, кнопка вимкнена до кінця потоку, «спробуйте ще раз»,
«завершити», чернетка репліки в браузері до підтвердження збереження; один обробник помилок; composition root.
Вимірна ціль: `pytest` зелений, зокрема локальний наскрізний тест `tests/smoke/test_e2e_local.py` (локальний режим:
локальна тека + сценарна модель + фіксована особа) до `conversation.md` і `map.json`; `uvicorn` з `PYTHONPATH=src`
стартує в локальному режимі, і сторінка відкривається.

## Premise verified
- FastAPI 0.159.1, Starlette 1.9.0, Jinja2 3.1.6 стоять (`fastapi[standard]`); `Jinja2Templates` вмикає
  `autoescape` для `.html` (`starlette/templating.py:95`, `select_autoescape()`); `python-multipart` стоїть (форми).
- `StreamingResponse` із синхронним ітератором Starlette ітерує в пулі потоків (A4: функції `platform` синхронні).
- S4: `reply`/`retry` кидають `TopicNotFound`/`PendingAnswer`/`NothingToRetry`/`ValueError` під час виклику, до
  ітератора; події — `Saved`, `Delta`, `Answered`, `Failed`. `all_topics_for_learning` — лише для `is_owner`
  (передумова S5). S3: `respond(ctx, knowledge, llm)`; `facilitate = partial(...)`. S2: `seed`, `current`.
  S1: `load_settings`, `make_storage`, `make_llm(settings, script)`, `make_identity`, `IdentityError`, `log.request_id`.
- `EventSource` уміє лише GET — тому `fetch` POST і читання `ReadableStream` (feature, рішення без HTMX).
- `node` v24 стоїть на машині розробки (`/home/lao/.nvm/versions/node/v24.19.0/bin/node`, probe critic-а
  2026-10-22) — `node --test` перевіряє JS сторінки без жодного пакета; тест знаходить `node` через `PATH` або
  змінну `THINKHOW_NODE`.
- Чи проходить потік SSE крізь IAP і чи не губиться репліка після кінця сесії IAP (PR-04) — лише на розгортанні
  власника (S7, `docs/deploy.md`); тут — локально.

## Out of scope (deliberately)
- Показ карти (F8), роутер (F5), оцінки (F9), голос (F13), сторінка спостережень (F10 повна).
- Показ закриття сесії тишею окремим повідомленням — сторінка показує сесії і їхній `closed_at`.
- HTMX (рішення фічі, escalations.md walking-skeleton-no-htmx), CDN, будь-які зовнішні скрипти.
- Розгортання, `Dockerfile` — S7.

## Seam (contract)
Пакет `src/thinkhow/web/`:
- `server.py` — `create_app(deps: Deps) -> FastAPI`; `@dataclass(frozen=True) Deps(storage: Storage, identity:
  IapIdentity | FixedIdentity, settings: Settings, facilitate: Facilitate, now: Callable[[], datetime])`. Тести
  будують `Deps` самі.
- `app.py` — **composition root**: `build_deps(environ: Mapping[str, str], cards_dir: Path) -> Deps` —
  `load_settings(environ)` → `make_storage` → у локальному режимі `knowledge.seed(storage, cards_dir)` (у хмарі посів
  — Job `seed`, S6/S7) → `knowledge.current(storage)` → `make_llm(settings, local_script)` → `facilitate =
  functools.partial(respond, knowledge=…, llm=…)` → `make_identity(settings)`; `now = lambda: datetime.now(UTC)`.
  `app = create_app(build_deps(os.environ, <repo>/cards))` на рівні модуля — точка входу `uvicorn
  thinkhow.web.app:app` (з `PYTHONPATH=src`). Тести `app.py` не імпортують без середовища.
- `local.py` — `local_script(system, contents, schema) -> str` — сценарна модель локального режиму: для схеми
  відповіді фасилітатора — JSON, де `reply` — **перший ключ** (інакше S1 не стрімить, S1 Q2a), з `reply` «(локальний режим) Уявіть, що план провалився. Що сталося першим?»,
  першою фазою з `enum` схеми, `phase_exit_met: false`, одним `add` у карту (`id` «i<turn_no>», `type` «plan»,
  текст поточної репліки, `turn` «t<turn_no>», номер із рамки `[Репліка людини #<n>]`); для схеми без `reply` — те
  саме без `reply`. Інших схем у кістяку `web` не викликає.
- Шар входу (залежність FastAPI): `request.headers` → `deps.identity.identify(headers)` → `access.current_user(
  identity, deps.settings)` → `workspace.ensure_profile(storage, user)`. **Особа ніколи не береться з адреси чи
  форми** (M3 A4). `IdentityError` → 401 з текстом «Потрібно увійти через Google».
- Ідентифікатор запиту: на кожен запит `platform.log.request_id` = заголовок `x-cloud-trace-context` до `/` або
  новий `uuid4().hex`; рядок журналу `http_request` (метод, шлях-шаблон маршруту, статус, `latency_ms` — до кінця
  тіла відповіді, для SSE — до кінця потоку) — без тексту реплік і без email. Чистий ASGI middleware (не
  `BaseHTTPMiddleware`); рядок журналу, написаний усередині потоку SSE (пул потоків), несе той самий
  `request_id` (контекст копіюється в ітератор).
- Маршрути (HTML, `text/html; charset=utf-8`, якщо не сказано інше):
  - `GET /` — «Мої теми»: `workspace.list_topics`; для `is_owner` ще розділ «Усі теми» — `all_topics_for_learning`
    + `open_topic` на кожен (назва, `uid`); форма «Нова тема» (поле `title`).
  - `POST /topics` (форма `title`) → `create_topic` → `303` на `/topics/<uid>/<topic_id>`.
  - `GET /topics/{uid}/{topic_id}` → `open_topic`; сторінка: назва; сесії з номерами; кожна репліка в елементі
    з `id="t<no>"` (якір `#t<no>`, G6), роль («Ви»/«Фасилітатор»), текст; закрита сесія позначена; форма репліки
    (`textarea name="text"`) і кнопки «Надіслати», «Спробуйте ще раз» (видно, якщо `awaiting_answer`),
    «Завершити сесію» — лише якщо `user.id == uid` (власник на чужій темі бачить сторінку без форми і кнопок).
  - `POST /topics/{uid}/{topic_id}/reply` (форма `text`) → `workspace.reply(...)` → `200 text/event-stream`;
    `POST /topics/{uid}/{topic_id}/retry` → `workspace.retry(...)` → те саме. Події SSE (кожна — `event:` і один
    рядок `data:` з JSON, порожній рядок після): `saved` `{"turn": n}`, `delta` `{"text": …}`, `answered`
    `{"turn": n}`, `failed` `{"reason": …}`. Заголовки: `Cache-Control: no-cache`, `X-Accel-Buffering: no`.
  - `POST /topics/{uid}/{topic_id}/close` → `close_session` → `303` на сторінку теми.
- Один обробник помилок (M3 A4): `TopicNotFound` → 404, `PendingAnswer` → 409, `NothingToRetry` → 409,
  `ValueError` → 400 (текст за маршрутом: «Порожню репліку не надіслано.» для `reply`, «Назва теми порожня.» для
  `POST /topics`, інакше «Запит не прийнято.»), `RequestValidationError` → 400 з тим самим текстом за маршрутом (поля форм
  оголошено `Form("")`, щоб порожній рядок доходив до `ValueError` S4; FastAPI 0.159.1 вважає `""` відсутнім полем
  — probe cold-reader-а), `IdentityError` → 401, будь-яке інше → 500; тіло — один HTML-фрагмент `<p
  class="error">…</p>` з людським текстом («Тему не знайдено.», «Спершу дочекайтеся відповіді або натисніть
  «Спробуйте ще раз».», «Порожню репліку не надіслано.», «Щось пішло не так — спробуйте ще раз.»), без трасування. «Будь-яке інше → 500» — обробник `Exception` (Starlette: у `ServerErrorMiddleware`, що потім
  кидає далі; тести — `TestClient(raise_server_exceptions=False)`); журнальний middleware, побачивши виняток,
  пише `http_request` зі `status: 500`.
  Помилка всередині потоку — подія `failed`, не 500: S4 сам перетворює винятки `facilitate`; `web` загортає
  ітератор подій, і будь-який інший виняток посеред потоку (зокрема сховища) → подія `failed {"reason":
  "Internal"}` і рядок журналу `stream_error` (клас винятку), після чого потік закривається.
- Сторінка розмови, свій JS (`static/conversation.js`, без бібліотек) з двома чистими частинами, які видно
  тестам (`module.exports` у node, `window.ThinkHow` у браузері): `createSseParser()` → `push(bytes: Uint8Array)
  -> Array<{event, data}>` (буфер між шматками; `TextDecoder("utf-8")` з `{stream: true}`; подія закінчується
  порожнім рядком; `data` — `JSON.parse`) і `createController({fetch, storage, ui, key})` — машина станів
  чернетки й кнопок (`ui` — об'єкт із методами `disable()`, `enable()`, `appendDelta(text)`, `showRetry()`,
  `showError(text)`, `reload()`, `setDraft(text)`). Текст у сторінку — лише через `textContent` (ніколи `innerHTML`). Поведінка: на «Надіслати» — зберегти
  текст у `localStorage` за ключем `draft:<uid>/<topic_id>`, вимкнути кнопки, `fetch` POST, читати
  `ReadableStream`, розбирати SSE; `saved` → прибрати чернетку; `delta` → дописати текст у нову репліку
  фасилітатора; `answered` → перезавантажити сторінку; `failed` → показати «Спробуйте ще раз», увімкнути кнопки;
  обрив мережі (відмова `fetch` чи потоку) → чернетка лишається, кнопки вмикаються, «Спробуйте ще раз» видно;
  відповідь не `ok` або не `text/event-stream` (401, 404, 409, 400, 500 з HTML-фрагментом) → чернетка лишається,
  кнопки вмикаються, `showError(<текст фрагмента>)` через `textContent`; потік закінчився без `answered` чи
  `failed` → як обрив (чернетка лишається, якщо `saved` не прийшов; кнопки вмикаються; `showRetry`).
  «Спробуйте ще раз» — той самий контролер з POST на `/retry`, без тексту і без запису чернетки (чернетку не
  чіпає). Під
  час відкриття сторінки чернетка з `localStorage` повертається в поле.
  Статика — `StaticFiles` під `/static`.
- Errors: як вище, одне місце. Dependencies (injected): `Deps`.
- import-linter: `web` — верхній шар; імпортує `workspace`, `access`, `facilitation`, `knowledge`, `platform`.
- Does NOT do: запис файлів поза `workspace`; особа з адреси/форми; HTMX; показ карти.

## Decisions (with WHY)
- Q1: `create_app(deps)` окремо від `app.py`. Чому: тести збирають застосунок із локальною текою, сценарним
  `facilitate` і фіксованою особою без змінних середовища; `app.py` — лише composition root (feature). Rejected:
  одна функція з `os.environ` — тести залежали б від середовища процесу (S1 Q4: середовище передається явно).
- Q2: локальний режим сам посіює Знання при старті, хмара — ні. Чому: локальна розробка без окремої команди; у
  хмарі в `knowledge/` пише лише Job (M3 «Посів Знань»). Rejected: посів і в хмарі на старті сервісу — другий
  записувач `knowledge/`.
- Q3: SSE-події з JSON у `data:` одним рядком. Чому: текст дельти може мати перевід рядка, а SSE ділить `data:`
  по рядках; JSON робить подію однозначною. Rejected: сирий текст у кількох `data:` — розбір складніший у JS.
- Q4: `answered` → перезавантаження сторінки. Чому: сторінку малює сервер з `conversation.md` (одне джерело
  правди), номери й якорі однакові. Rejected: JS сам вставляє репліку з номером — дубль шаблону в JS.
- Q5: власник на чужій темі — сторінка без форми (S4 Q2: власник не пише в чужу тему). Rejected: форма, що
  відповідає 404, — плутанина.

## Hardest seams (test-confidence points)
- **Seam 1: потік SSE через TestClient** — двійник `facilitate` дає дельти з `\n` і юнікодом: тіло відповіді
  розбирається на події `saved`, `delta`…, `answered` у цьому порядку; склеєні `delta` дорівнюють відповіді в
  `conversation.md`. Відкидає «тест, що лише дивиться на статус 200».
- **Seam 2: помилка до потоку і під час потоку** — чужа тема → 404 HTML-фрагмент без запису; `PendingAnswer` → 409;
  двійник, що падає посеред дельт → 200 і подія `failed`, репліка людини в `conversation.md`.
- **Seam 3: особа лише із заголовка** — `IapIdentity` з фейковим `verify`: без заголовка → 401; підробка `uid` в
  адресі не дає читати чужу тему; власник (email з налаштувань, інший регістр) бачить «Усі теми» і чужу сторінку
  без форми.
- **Seam 4: справжній запуск** — `uvicorn thinkhow.web.app:app` з `PYTHONPATH=src`, `THINKHOW_LOCAL=true`,
  тимчасовою `THINKHOW_LOCAL_DIR` і `THINKHOW_OWNER_EMAIL=owner@localhost` (інакше локальна особа — не власник,
  `owner_email` за замовчуванням порожній): `GET /` → 200 з «Усі теми» (smoke-скрипт).
- **Seam 5: SSE і чернетка в браузері** — `tests/web/test_conversation_js.py` запускає `node --test
  tests/web/conversation.test.mjs`: те саме тіло SSE (українською, з емодзі, з `\n` у `delta`), розрізане на
  **кожному** байті і на кожній парі байтів, дає рівно ті самі події; контролер із фейковими `fetch`
  (`ReadableStream` зі шматків), `localStorage` і `ui`: `saved` → чернетку прибрано; `failed` → кнопки ввімкнено,
  `showRetry`; обрив потоку до `saved` → чернетка лишилася; під час потоку `disable()` до кінця. Відкидає:
  розбиття кожного шматка за `\n\n`; декодування без `stream: true`; чернетку, що зникає до `saved`. Ще:
  `conversation.js` не містить `innerHTML`. Ще: відповідь 401/409 з HTML → кнопки ввімкнено, `showError` з текстом,
  чернетка лишилася; потік 200, що закрився після `saved` без `answered`/`failed` → кнопки ввімкнено, `showRetry`;
  «Спробуйте ще раз» → POST на `/retry`, чернетку не чіпає. Відкидає «вмикати кнопки лише на `failed` чи відмові
  `fetch`». Ще (Seam 2): `text=""` і `title=""` → 400 HTML-фрагмент, нічого не записано (відкидає `Form(...)` з
  типовою відповіддю 422 JSON). `node` відсутній → тест **падає** з поясненням (не пропускається): вихід slice-а залежить від `node`.

## Invariants (rules that hold for every input in the stated domain)
- **I1** — Особа кожного запиту — та, що дала `identify(headers)`; ні адреса, ні форма її не змінюють.
  - Domain: будь-який маршрут, будь-які `uid`/`topic_id` в адресі, будь-які поля форми, зокрема `uid`, `email`,
    `is_owner` у формі чи query.
  - Source: M3 A4 («Жоден маршрут не бере особу з адреси чи форми»); G4.
  - Broken by: маршрут, що бере `uid` з адреси як особу для запису.
- **I2** — Текст реплік і назва теми показуються як текст: жоден символ із них не стає розміткою сторінки.
  - Domain: будь-який текст, зокрема `<script>`, `"><img onerror=…>`, `&amp;`, маркери `<!-- thinkhow:`.
  - Source: G4 (чужа розмова не виконає код у браузері власника, який читає всі теми); M3 A4.
  - Broken by: фільтр `|safe` або `Markup` у шаблоні; вимкнений `autoescape`; `innerHTML` /
    `insertAdjacentHTML` для дельт у `conversation.js`.
- **I3** — Склеєні тексти подій `delta` одного потоку дорівнюють відповіді, яку той самий потік записав у
  `conversation.md` (після нормалізації S4).
  - Domain: будь-які дельти двійника `facilitate` (з `\n`, `\r\n`, лапками, юнікодом поза BMP), що закінчуються
    `answered`.
  - Source: feature S3 → S4 (дописується показане); S4 I1.
  - Broken by: кодування `data:` без JSON, яке губить переводи рядків; подія `delta` із нормалізованим текстом.

## Exit criterion
- `uv run pytest` зелений: контрактні тести slice-а; `tests/smoke/test_e2e_local.py` — локальний режим
  (`build_deps` з `THINKHOW_LOCAL=true`, тимчасова тека, `cards/`), TestClient: `GET /` → створити тему → POST
  репліки → події `saved`, `delta`, `answered` → POST `/close` → у `users/local-owner/<topic>/` є `conversation.md`
  з двома репліками і позначкою `closed 1` і `map.json` з пунктом `i1`; `tests/web/test_conversation_js.py` (Seam 5, `node --test`); A3 і
  попередні slices; `ruff`, `mypy`, `lint-imports` без помилок.
- `uv run python scripts/smoke_test_skel_web.py` — запускає `uvicorn thinkhow.web.app:app` у локальному режимі
  (тимчасова тека, вільний порт), чекає старту, `GET /` → 200 з «Мої теми», POST теми, POST репліки й читання SSE
  → `answered`; зупиняє сервер. Крізь IAP — лише на розгортанні власника (PR-04, S7).

## Deferred to later slices
- `Dockerfile`, `docs/deploy.md`, чекліст PR-04 — S7 — trigger: S7.
- `Dockerfile` мусить покласти `cards/` поруч із `src/` (шлях `build_deps` — від кореня репозиторію) — S7 — trigger: S7.
- Справжній браузер крізь IAP (кнопки, чернетка після кінця сесії IAP) — чекліст власника PR-04 у `docs/deploy.md` — S7.
- Частина 2 трасера (`analyze`, спостереження з якорем) — S6 розширює `tests/smoke/test_e2e_local.py`.
- Показ карти людині — F8 — trigger: задача F8.

## Open items requiring human decision (if any)
- None.

## Revisions during planning
- **Phases 2–5 (critic round 1) — challenge:** "the browser behaviour of the Goal (button, draft, failed, network break — PR-04) has no seam and no exit evidence" → **revised:** Seam 5, чисті `createSseParser`/`createController` у `conversation.js`, тест `node --test` у виході → **reason:** шматки `ReadableStream` не збігаються з межами подій і символів UTF-8; Python-тести не бачать JS.
- **Cold-reader — challenge:** "`fetch` does not reject on HTTP errors; a 401/409 or a stream ending without a terminal event leaves the buttons disabled" → **revised:** `!ok`/не SSE → `showError`; EOF без кінця → як обрив; обидва випадки в Seam 5 → **reason:** 401 — саме шлях PR-04 (сесія IAP скінчилася). Нотатки: тексти `ValueError` за маршрутом (2), 500 і журнал (3), `node` відсутній → тест падає (4), «Спробуйте ще раз» у контролері (5).
- **Cold-reader 2 — challenge:** "an empty form field gets FastAPI's 422 JSON and never reaches the one error handler" → **revised:** `Form("")`, `RequestValidationError` → 400 за маршрутом, тест `text=""`/`title=""` → **reason:** FastAPI 0.159.1 вважає `""` відсутнім полем; виправлено без третього прогону (escalations.md, skel-web-cold-reader). Нотатки: крок «завершити» в e2e (2), `THINKHOW_OWNER_EMAIL` у smoke (3), порядок Seam (4).
- Нотатки прийнято: помилка сховища посеред потоку → `failed Internal` (2), `textContent` і заборона `innerHTML` (3), тексти — AUTONOMOUS у escalations.md, skel-web-wording (4), `reply` першим у `local_script` (5), `latency_ms` до кінця потоку, ASGI middleware, `request_id` у потоці (6), `cards/` у Docker — Deferred (7).
