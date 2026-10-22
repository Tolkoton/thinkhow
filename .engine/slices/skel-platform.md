# Slice skel-platform — planning artifact

Feature: `.engine/architecture/feature/walking-skeleton.md`, S1 (block: foundation). Driven mode: frame
supplied by the feature artifact, not asked.

## Goal
Шар `thinkhow.platform` — єдине місце, що знає про Google (M3 A3.2): налаштування, журнал, сховище
файлів, особа з IAP, виклик Gemini — кожне з реальною реалізацією і другою, що вже існує (M3 A2), плюс
каркас проєкту (src-layout, ruff/mypy/pytest/import-linter у `pyproject.toml`, порожні пакети частин)
і запобіжники A3.1–A3.2 з першого дня. Вимірна ціль: `pytest` зелений; `lint-imports` зелений з
контрактами M3; `scripts/smoke_test_skel_platform.py` проходить проти справжнього Vertex
(`gemini-4-argon`, `eu`) і локальної теки.

## Premise verified
- PR-10: `google-genai` 2.32.0, `vertexai=True, location="eu"`, `generate_content_stream` +
  structured output — `.engine/artifacts/spikes/walking-skeleton-genai-eu-2026-10-21.txt` (2026-10-21).
- Поле, оголошене першим у pydantic-моделі, приходить у потоці першим (`response_json_schema` і
  `response_schema`) — `.engine/artifacts/spikes/skel-platform-field-order-2026-10-21.txt` (2026-10-21).
- `google.oauth2.id_token.verify_token(token, request, audience, certs_url=
  "https://www.gstatic.com/iap/verify/public_key")` перевіряє IAP JWT (ES256) — docs
  cloud.google.com/iap/docs/signed-headers-howto; `untested — common knowledge` для справжнього
  заголовка: справжній заголовок буває лише за IAP — PR-04 перевіряє власник при розгортанні.
- Cloud Storage `upload_from_string(..., if_generation_match=0)` створює об'єкт лише якщо його нема,
  інакше `google.api_core.exceptions.PreconditionFailed` — docs (request preconditions);
  `untested — common knowledge` проти справжнього bucket-а (bucket-и створює власник; PR-07).

- Потік ліниві: `Models.generate_content_stream` у google-genai 2.32.0 — generator function
  (`inspect.isgeneratorfunction` → True, probe cold-reader-а 2026-10-21): запит іде на першому `next()`,
  тож 429/5xx/тайм-аут з'являються під час ітерації, не під час виклику.

## Out of scope (deliberately)
- `platform.speech` (F13) — голосу в кістяку немає.
- Будь-яка логіка частин (картки, теми, промпти) — slices S2–S6.
- Composition root (хто з налаштувань будує адаптери) — S5 (`web`), S6 (`learning.job`); тут лише
  функції-будівники `make_storage(settings)`, `make_llm(settings, script)`, `make_identity(settings)`.
- Кеш, rate limit, circuit breaker, черги (P5; M2 S7).
- Видалення файлів зі сховища — ніхто в кістяку не видаляє.

## Seam (contract)
Пакет `src/thinkhow/platform/`:
- `config.py`
  - `class Settings(BaseSettings)` (pydantic-settings, префікс `THINKHOW_`): `local: bool = False`,
    `project: str = "pocket-lawyer-431614"`, `location: str = "eu"`, `model: str = "gemini-4-argon"`,
    `users_bucket: str = ""`, `system_bucket: str = ""`, `local_dir: Path = Path(".local-data")`,
    `owner_email: str = ""`, `iap_audience: str = ""`, `local_user_id: str = "local-owner"`,
    `local_user_email: str = "owner@localhost"`, `llm_timeout_s: float = 300.0`, `llm_attempts: int = 3`.
  - `load_settings(environ: Mapping[str, str]) -> Settings` — `ConfigError`, якщо `local` і в
    `environ` є `K_SERVICE` або `CLOUD_RUN_JOB` (локальний режим у Cloud Run — G4); `ConfigError`, якщо
    не `local` і порожні `users_bucket`, `system_bucket` або `owner_email`.
- `log.py` — `request_id: ContextVar[str | None]`; `log_event(event: str, stream: TextIO = sys.stdout,
  **fields: object) -> None` пише один рядок JSON: `{"severity": "INFO", "event", "request_id", **fields}`
  (`severity` можна передати полем). Текст розмов сюди не передається (правило викликачів, M3 A4).
- `storage.py`
  - `Bucket = Literal["users", "system"]`
  - `class Storage(Protocol)`: `read(bucket, path) -> bytes | None` (None — нема);
    `write(bucket, path, data: bytes, content_type: str) -> None`;
    `create_if_absent(bucket, path, data, content_type) -> bool` (False — вже був, не перезаписано);
    `list(bucket, prefix: str) -> list[str]` (повні шляхи всередині bucket-а, відсортовано).
  - `LocalStorage(root: Path)` — `<root>/<bucket>/<path>`; `GcsStorage(client: storage.Client,
    names: Mapping[Bucket, str])`.
  - `path` — відносний шлях із `/`; порожній сегмент, `.`, `..`, початковий `/` → `ValueError` (обидві
    реалізації).
  - `make_storage(settings) -> Storage`.
- `identity.py`
  - `@dataclass(frozen=True) Identity(id: str, email: str)`; `IdentityError(Exception)`.
  - `IapIdentity(audience: str, verify: Callable[[str, str], Mapping[str, object]])` — `identify(headers:
    Mapping[str, str]) -> Identity`: заголовок `x-goog-iap-jwt-assertion` (без урахування регістру);
    `verify(token, audience)` повертає claims; `id` — частина `sub` після останнього `:`; `email` —
    claim `email`. Нема заголовка / `verify` кинув / нема `sub` чи `email` / `id` не відповідає
    `^[A-Za-z0-9_-]{1,128}$` → `IdentityError`.
  - `FixedIdentity(identity: Identity)` — `identify(headers) -> Identity` завжди повертає ту саму.
  - Контракт фічі S1 → S5 називав `identity.current_user(headers)`; тут — `make_identity(settings)
    .identify(headers)` (дві реалізації з одним методом); фічу оновлено.
  - `make_identity(settings) -> IapIdentity | FixedIdentity` (`verify` за замовчуванням —
    `google.oauth2.id_token.verify_token` з IAP certs URL).
- `llm.py`
  - `Turn(role: Literal["user", "model"], text: str)`, `KnowledgeRev(rev: int, n: int)`,
    `ReplyDelta(text: str)`, `Usage(prompt_tokens: int, output_tokens: int, thought_tokens: int)`,
    `Done(raw_json: str, usage: Usage)` — frozen dataclasses (як у контракті фічі S1 → S3/S6).
  - `LlmUnavailable(Exception)` — модель не відповіла після повторів або потік обірвався.
  - `class Llm(Protocol)`: `stream_json(system: str, contents: Sequence[Turn], schema: type[BaseModel],
    rev: KnowledgeRev | None) -> Iterator[ReplyDelta | Done]` — дельти рядкового поля `reply` (якщо воно
    перше в схемі) по мірі надходження, потім рівно один `Done` з повним сирим JSON;
    `generate_json(system, contents, schema: type[M], rev) -> M` — один виклик, результат
    `schema.model_validate_json`; невалідний JSON → `pydantic.ValidationError`.
  - `VertexLlm(client: genai.Client, model: str, timeout_s: float, attempts: int, sleep: Callable[[float],
    None] = time.sleep, clock: Callable[[], float] = time.monotonic)` — `response_mime_type=
    "application/json"`, `response_json_schema=schema.model_json_schema()`; повтор (до `attempts`, backoff
    `min(2**k, 30) * (0.5..1.0 jitter)`) лише на помилках до першої дельти: `google.genai.errors.APIError`
    з кодом 429 або ≥500, тайм-аут; помилка після першої дельти або вичерпано спроби → `LlmUnavailable`;
    4xx (крім 429) → `LlmUnavailable` без повтору. На кожен виклик — рядок журналу `llm_call`:
    `model`, `prompt_tokens`, `output_tokens`, `thought_tokens`, `latency_ms`, `attempts`, `rev`, `n`,
    `outcome` (`ok` / `unavailable`) — без тексту.
  - `ScriptedLlm(script: Callable[[str, Sequence[Turn], type[BaseModel]], str], chunk: int = 7)` —
    двійник: бере сирий JSON зі `script`, віддає його шматками по `chunk` символів через той самий
    витяг дельт, що й `VertexLlm`; `calls: list[tuple[str, list[Turn], type[BaseModel]]]` для тестів.
  - `make_llm(settings, script) -> Llm` — `local` → `ScriptedLlm(script)`, інакше `VertexLlm`.
- Каркас: `src/thinkhow/{web,access,workspace,facilitation,knowledge,learning}/__init__.py` (порожні);
  `pyproject.toml`: без `[build-system]` (Q8) — `[tool.pytest.ini_options] pythonpath = ["src"]`, маркер
  `live`, `addopts = "-m 'not live'"`; усе, що запускається поза pytest, отримує `PYTHONPATH=src`
  явно (`tests/test_a3_imports.py` передає його в `env` підпроцесу `lint-imports`; smoke-скрипт
  додає `src` у `sys.path` сам; `uvicorn`/`python -m` у S5–S7 і `Dockerfile` — `PYTHONPATH=src`); `[tool.ruff]`, `[tool.mypy]` (strict для
  `src/`); `[tool.importlinter]` з контрактами (Decisions Q5).
- Errors: `ConfigError`, `IdentityError`, `LlmUnavailable`, `ValueError` (шлях), `pydantic.ValidationError`
  — кидаються (не Result-об'єкти): обробник у `web` (S5) — одне місце (M3 A4).
- Dependencies (injected): `environ`, `client` (GCS, genai), `verify`, `sleep`, `clock`, `stream` для
  журналу, `script` для двійника.
- Does NOT do: голос; кеш; видалення; побудову адаптерів із застосунку (composition root — S5/S6);
  знання про будь-яку частину (`platform` не імпортує `thinkhow.*` поза собою).

## Decisions (with WHY)
- Q1: `Protocol` для `Storage` і `Llm` — бо друга реалізація вже існує (M3 A2), а mypy має перевіряти
  обидві. Rejected: ABC — те саме з успадкуванням, без вигоди; один клас з `if local` — змішує дві
  причини змін (§9.2).
- Q2: дельти `reply` витягаються з сирого JSON-потоку інкрементальним розбором рядкового значення
  першого поля (стан: шукати `"reply"`, `:`, `"`, далі декодувати екранування `\" \\ \n \uXXXX`,
  включно з сурогатними парами, що можуть розірватися між шматками). Чому: spike показав, що `reply`
  приходить першим; так людина бачить відповідь до кінця генерації (S5/PR-04 потік). Rejected: чекати
  кінця і віддати все разом — губить потік (M2 «відповідь потоком»); просити модель два окремі виклики
  (текст + JSON) — PR-02 перевірено на одному виклику.
- Q3: повтор лише до першої дельти — бо після неї людина вже бачить текст, а повтор дав би інший текст
  (S2: «спробуйте ще раз» — рішення людини). Rejected: повтор усього потоку — дублює показаний текст.
- Q4: `response_json_schema` з `model_json_schema()` — spike показав той самий порядок і швидший
  перший байт; `response_schema=Model` теж працює. Rejected: ручний dict-схема з `propertyOrdering` як у
  PoC — дублює модель pydantic.
- Q5: import-linter з першого дня (рішення фічі після critic): контракт `layers` (згори вниз: `web`;
  `learning`; `workspace`; `facilitation`; `knowledge`; `access`; `platform`) дає «без циклів» і напрям;
  `forbidden`-контракти — стрілок, яких M3 не має всередині дозволеного напряму: `workspace` ↛
  `knowledge`, `platform.llm`; `facilitation` ↛ `access`, `platform.storage`; `knowledge` ↛ `access`;
  `learning` ↛ `platform.identity` (job особи не потребує). pytest-тест `tests/test_a3_imports.py`
  запускає `lint-imports` і вимагає код 0. **A3.2 «SDK Google лише в `platform`»** — окремий
  pytest-тест `tests/test_a3_google_sdk.py`, як вимагає фіча: розбирає (AST) кожен `.py` у
  `src/thinkhow/` поза `platform/` і падає на будь-якому `import google…` / `from google… import`,
  включно з імпортами всередині функцій. Rejected: forbidden-контракт import-linter на
  `google.cloud`/`google.genai`/`google.auth`/`google.oauth2` — lint-imports 2.15 відкидає таку
  конфігурацію («subpackages of external packages are not valid», probe critic-а 2026-10-21);
  заборона всього `google` у import-linter працює, але фіча просить AST-тест, і S7 на нього спирається.
- Q6: локальний режим відмовляє і при `CLOUD_RUN_JOB`, не лише `K_SERVICE` — Job теж Cloud Run, а
  фіксована особа там зробила б навчання на чужих даних. Rejected: лише `K_SERVICE` (M3 A2 дослівно) —
  Job-сценарій не покрито.
- Q7: `uid` = частина `sub` після `:` (IAP `sub` має вигляд `accounts.google.com:<digits>`) з перевіркою
  регулярним виразом — бо `uid` іде в шляхи й адреси (M3 A3.3). Rejected: email як id — M2 S4 прямо
  відкидає.

- Q8: пакування — **без `[build-system]`, `PYTHONPATH=src` явно.** Чому: застосунок не публікується
  як пакет; `uv sync` нічого не будує, і не з'являється нового build-backend-а (hatchling тягнеться
  як пакет при збірці — дія з дозволу власника за правилами двигуна). Rejected: (A) `[build-system]`
  hatchling + editable install — `thinkhow` імпортується звідусіль без змінної, найзвичніше для uv;
  але додає build-залежність, що ставиться з мережі, і змінює, що робить `uv sync`; переходимо на (A)
  дешево, якщо `PYTHONPATH` почне заважати. (C) плоский layout без `src/` — M3 A1 називає `src/thinkhow/`.
- Q3a: межа повтору — **перша `ReplyDelta`, віддана викликачеві**, не перший шматок: шматок без тексту
  `reply` (напр. `{"`) людина не бачила, тож повтор безпечний (та сама причина, що в Q3). Помилка після
  першої дельти → `LlmUnavailable`.
- Q2a: якщо модель поставила `reply` не першим — `stream_json` не дає жодної дельти, а `Done` усе одно
  несе повний JSON (викликач покаже відповідь цілою); сканер шукає ключ `reply` лише як перший ключ
  об'єкта верхнього рівня, не всередині рядкових значень. Тест: «`reply` не перший → нуль дельт, `Done`
  цілий».
- Q9: тайм-аут — `http_options=HttpOptions(timeout=int(timeout_s*1000))` у `GenerateContentConfig`;
  тайм-аут до першої дельти = `httpx.TimeoutException` або `httpx2.TimeoutException` (обидва стоять,
  genai бере `httpx2`, якщо є) — повтор; після першої дельти — `LlmUnavailable`.
  Тайм-аут httpx — на операцію (з'єднання, пауза між байтами), не на весь запит: на потоці 300 с
  обмежують паузу між шматками, а не довжину відповіді. Повтор після тайм-ауту в межах одного
  веб-запиту Cloud Run (300 с за замовчуванням) практично не встигне — це прийнято; тайм-аут сервісу
  задає `docs/deploy.md` (S7).
- Q10: у `log_event` службові ключі перемагають: `event` і `request_id` з аргументів/контексту завжди
  переписують однойменні поля з `**fields`; `severity` за замовчуванням `INFO`, поле може його задати.

## Hardest seams (test-confidence points)
- **Seam 1: витяг дельт `reply` з JSON, що приходить довільними шматками** — тест подає той самий JSON,
  розрізаний на всіх можливих межах (кожен символ — межа, зокрема посеред `\uXXXX`, сурогатної пари й
  `\"`), і перевіряє, що склеєні дельти == `json.loads(raw)["reply"]`. Відкидає anti-pattern «тест на
  одному цілому шматку».
- **Seam 2: повтор лише до першої дельти** — фейковий `genai.Client` (об'єкт з
  `models.generate_content_stream`), де **кожен фейк, що падає, — генератор, який кидає на першому
  `next()`, а не під час виклику** (як справжній SDK): 429 двічі на першому `next()`, потім потік; і
  фейк, що кидає після шматка з першою дельтою. Перевіряються кількість викликів, `sleep`-затримки, `LlmUnavailable`, рядок журналу.
  Відкидає «мок, який ніколи не падає». `generate_json` іде тим самим шляхом повторів (одна приватна
  функція спроб для обох) — окремий тест: 429 → повтор → результат, і 400 → `LlmUnavailable` без повтору.
  Ще один фейк кидає `httpx.TimeoutException` до першої дельти — повтор, потім успіх.
- **Seam 3: `create_if_absent` у GCS** — без справжнього bucket-а: фейковий bucket/blob, що на
  `if_generation_match=0` кидає `PreconditionFailed`, перевіряє, що передано саме `if_generation_match=0`
  і що результат False. Справжня поведінка — у smoke власника (PR-07). Відкидає «реалізація ігнорує
  передумову, а фейк погоджується».
- **Seam 4: справжній Vertex** — `tests/live/test_llm_live.py` (`-m live`) і smoke-скрипт: один виклик
  `stream_json` до `gemini-4-argon` на `eu`, дельт ≥ 2, склеєне == `reply` з `Done`.

## Invariants (rules that hold for every input in the stated domain)
- **I1** — Склеєні дельти `reply` дорівнюють полю `reply` повного JSON, як би потік не був розрізаний.
  - Domain: будь-який валідний JSON-об'єкт, перше поле якого — рядок `reply` (зокрема порожній, з
    екрануванням, кирилицею, емодзі поза BMP), розрізаний на будь-які шматки (зокрема по 1 символу).
  - Source: Seam (`stream_json`: «дельти поля `reply`… потім `Done` з повним JSON»); feature «відповідь
    потоком».
  - Broken by: декодування кожного шматка окремо (розірване `\u` чи `\"` дає сміття або губить символ).
- **I2** — `create_if_absent` ніколи не змінює вже наявний файл.
  - Domain: будь-який шлях і вміст, обидві реалізації (`LocalStorage`, `GcsStorage` з фейком).
  - Source: M2 S6 «лише якщо ще немає» (`seed`, `changes/<rev>`).
  - Broken by: `write` замість умовного створення.
- **I3** — Шлях із `..`, `.`, порожнім сегментом чи початковим `/` ніколи не доходить до файлової
  системи чи Cloud Storage.
  - Domain: усі чотири методи `Storage`, обидві реалізації.
  - Source: M3 A3.3 (теки людей — лише з ідентифікаторів сервера); G4.
  - Broken by: `root / path` без перевірки (вихід за межі `local_dir`).
- **I4** — Локальний режим ніколи не стартує в Cloud Run.
  - Domain: будь-який `environ` з `THINKHOW_LOCAL` істинним і `K_SERVICE` або `CLOUD_RUN_JOB`.
  - Source: M3 A2; G4.
  - Broken by: перевірка лише `K_SERVICE`.

## Exit criterion
- `uv run pytest` зелений (тести `tests/platform/test_config.py`, `test_log.py`, `test_storage.py`,
  `test_identity.py`, `test_llm.py`, `tests/test_a3_imports.py`, `tests/test_a3_google_sdk.py`); `uv run ruff check src tests`,
  `uv run mypy src` — без помилок.
- `uv run pytest -m live tests/live/test_llm_live.py` — зелений проти `gemini-4-argon` на `eu`.
- `PYTHONPATH=src uv run lint-imports` — код 0.
- `uv run python scripts/smoke_test_skel_platform.py` — друкує: `LocalStorage` write/read/list/
  create_if_absent OK; `stream_json` дав N≥2 дельт, склеєне == `reply`; рядок журналу `llm_call` з
  токенами. Справжній GCS і IAP — лише на розгортанні власника (PR-07, PR-04), не в цьому slice.

## Deferred to later slices
- `platform.speech` — F13 — trigger: задача 104 / F13.
- Перевірка GCS і IAP на справжніх ресурсах — S7 (`docs/deploy.md`, чекліст власника) — trigger:
  розгортання власника.

## Open items requiring human decision (if any)
- None.

## Revisions during planning
- **Phases 2–5 (critic round 1) — challenge:** "Q5 relies on import-linter forbidding `google.cloud`/… lint-imports 2.15 refuses this config" → **revised:** A3.2 як AST pytest-тест (як вимагає фіча), import-linter лише для шарів і стрілок → **reason:** probe critic-а показав, що конфігурацію відкидає сам інструмент.
- Нотатки 2–5 critic-а прийнято: `Done.usage`, назва `identify` (фічу оновлено), тест повторів `generate_json`, заборона `learning ↛ platform.identity` без винятку.

- **Cold-reader 2 — challenge:** "a fake that raises on call lets an implementation that wraps only the call in the retry pass every test" → **revised:** Seam 2 — фейки-генератори, що кидають на першому `next()`; premise «потік лінивий»; Q3a (межа повтору — перша дельта), Q2a (`reply` не перший), примітка до Q9 → **reason:** probe `inspect.isgeneratorfunction` → True. Друге блокування cold-reader-а виправлено, а не відкладено (engine-rules «BLOCK you can resolve → fix it, log it, continue»; escalations.md, skel-platform-cold-reader).
- **Cold-reader — challenge:** "`pythonpath = ["src"]` leaves `thinkhow` unimportable outside pytest" → **revised:** Q8 (явний `PYTHONPATH=src` для `lint-imports`, smoke, точок входу), Q9 (тайм-аут), Q10 (ключі журналу), тест тайм-ауту → **reason:** перевірено critic-ом у scratch-копії: `lint-imports` rc=1 без `PYTHONPATH`.

## Critic notes (non-blocking)
- Розмір slice-а на межі (≈6 модулів + каркас) — прийнято як фундамент фічі.
