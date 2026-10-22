# Slice skel-guards-deploy — planning artifact

Feature: `.engine/architecture/feature/walking-skeleton.md`, S7 (block: guards). Driven mode: frame supplied by the
feature artifact, not asked. Depends on S5, S6 (afacd9a, 669a07e).

## Goal
Закрити кістяк: (1) два запобіжники A3, яких ще нема автоматичною перевіркою, — «шляхи `users/` будує лише
`workspace`» і «у `system/knowledge/` пише лише `knowledge`» (разом з import-linter S1–S6, AST-тестом A3.2 і тестами G4
S4 це чотири запобіжники AC4); (2) `Dockerfile` одного образу для сервісу й Job; (3) `docs/deploy.md` — інструкція
власникові й чекліст PR-04, PR-07, AC1. Вимірна ціль: `pytest` зелений із новими тестами запобіжників; `tests/test_dockerfile.py` статично
перевіряє `Dockerfile` і `.dockerignore` за контрактом. Збирає образ власник (`gcloud builds submit` — Cloud Build,
крок 5 `docs/deploy.md`); у агента є лише клієнт Docker без доступу до демона.

## Premise verified
- Docker 29.1.3 — **лише клієнт**: демон агентові недоступний (`permission denied … /var/run/docker.sock`, `lao` не в
  групі `docker`; `sudo` заборонено) — probe critic-а 2026-10-22. Google Cloud SDK 589.0.0 стоїть; `uv` стоїть;
  `uv.lock` у репозиторії.
- `gcloud run deploy` має `--[no-]iap`, `--max-instances`, `--min-instances`, `--timeout`, `--no-cpu-throttling`;
  `gcloud iap web add-iam-policy-binding` має `--resource-type`, `--service`, `--region`; `gcloud logging settings
  update --storage-location` — **лише для організації чи теки** (не для проєкту без організації); `gcloud scheduler jobs create http` з `--oauth-service-account-email` (довідка CLI,
  probe 2026-10-22). Самі команди розгортання агент не виконує — це дія власника (задача 105).
- Аудиторія IAP для Cloud Run з прямим IAP — `/projects/<PROJECT_NUMBER>/locations/<REGION>/services/<SERVICE>`
  (docs cloud.google.com/iap/docs/signed-headers-howto) — `untested — common knowledge`; чекліст власника перевіряє
  (вхід працює ⇒ аудиторія правильна).
- Звичайні Gmail-акаунти потребують власного OAuth-клієнта «External» (PR-04, `docs.cloud.google.com/iap/docs/
  oauth-client-creation`) — кроки консолі, не CLI.
- S5: `build_deps` шукає `cards/` від кореня репозиторію (`Path(__file__).parents[3]`), тож у образі `src/` і `cards/`
  лежать поруч в одній теці (S5 Deferred).

## Out of scope (deliberately)
- Виконання будь-якої команди розгортання, `docker push`, `docker run` з мережею Google (ask-gated / дія власника).
- CI, Terraform, кілька середовищ (P5).
- Перевірка PR-04, PR-07, AC1 — лише власник на своєму розгортанні.

## Seam (contract)
- `tests/test_a3_guards.py`:
  - `storage_calls(source: str) -> list[StorageCall]` — розбір AST модуля: кожен виклик методу `read`, `write`,
    `create_if_absent`, `list`, чий перший аргумент — рядкова константа `"users"` чи `"system"`
    (`StorageCall(method, bucket, line)`).
  - Строго: кожен виклик цих методів поза `platform/` мусить мати **рядкову константу** першим позиційним
    аргументом; змінна, іменований аргумент `bucket=` чи константа модуля — порушення (тест падає) — так сьогодні
    в усіх частинах.
  - `test_users_paths_are_built_only_by_workspace` — у кожному `.py` під `src/thinkhow/` поза `workspace/` і
    `platform/` нема жодного виклику з `bucket == "users"` (M3 A3.3).
  - `test_knowledge_files_are_written_only_by_knowledge` — виклики `write`/`create_if_absent` з `"system"` є лише в
    `knowledge/` і `learning/`; у `learning/` кожен такий виклик має шлях, що починається з `"learning/"` (рядкова
    константа чи f-рядок із цим початком, або змінна, якій у тій самій функції присвоєно такий рядок) (M3 A3.4).
  - `test_the_guards_see_a_planted_breach` — на вигаданих рядках коду (`storage.write("users", …)` у функції,
    `self.storage.create_if_absent("system", "knowledge/x", …)`, `b = "users"; storage.write(b, …)`,
    `storage.write(bucket="users", …)`) перевірка знаходить кожне; це доказ, що запобіжник не мовчить.
- `tests/test_ac4.py` — один тест на кожен із чотирьох пунктів AC4, що **запускає** вже наявні перевірки й вимагає
  зеленого результату (перелік, який читає власник): «без циклів» — `lint-imports` (контракт шарів); «лише
  `platform` імпортує SDK Google» — `tests/test_a3_google_sdk.py`; «теки людей пише лише `workspace`, чужа тема
  недоступна, власник бачить усе» — `tests/test_a3_guards.py::test_users_paths_are_built_only_by_workspace` і
  `tests/contract/skel_workspace/test_skelw_invariants.py::test_I2_…`; «Знання змінюються лише через `knowledge`» —
  `tests/test_a3_guards.py::test_knowledge_files_are_written_only_by_knowledge`. Кожен тест запускає `sys.executable -m pytest` чи
  `lint-imports` з тієї самої `.venv` підпроцесом за точним id і вимагає код 0 (зламаний пункт видно назвою пункту AC4).
- `Dockerfile` (корінь): `python:3.13-slim`; `uv` з офіційного образу `ghcr.io/astral-sh/uv` (копія бінарника, без
  `curl | sh`); `uv sync --frozen --no-dev` у `/app/.venv`; `COPY src/ /app/src/` і `COPY cards/ /app/cards/` (дві інструкції, бо `COPY src/ cards/ /app/` копіює вміст тек); `ENV PYTHONPATH=/app/src
  PATH=/app/.venv/bin:$PATH UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy`; спершу `COPY pyproject.toml uv.lock`, потім
  `uv sync`; користувач без root; `CMD exec uvicorn thinkhow.web.app:app --host 0.0.0.0 --port ${PORT:-8080}`
  (shell-форма для `$PORT`, `exec` — uvicorn стає PID 1 і отримує SIGTERM від Cloud Run). Job — той самий образ з `--command python --args -m,thinkhow.learning.job,
  analyze|seed`. `.dockerignore`: `.env*`, `.venv`, `.git`, `.engine`, `.claude`, `tests`, `sketches`, `tasks`, `docs`,
  `.local-data`, кеші.
- `docs/deploy.md` (українською, технічні терміни англійською; команди з місцями `<PROJECT_NUMBER>` тощо):
  1. Змінні: проєкт `pocket-lawyer-431614`, регіон `europe-west3`, Vertex `eu`.
  2. Журнали в ЄС: bucket журналів у `europe-west3` і маршрут `_Default` туди (`gcloud logging buckets create`,
     `gcloud logging sinks update _Default`); `gcloud logging settings update --storage-location` — лише для
     організації, проєкту без неї не стосується; bucket `_Required` (журнали аудиту Google) лишається глобальним —
     названо власникові.
  3. Bucket-и для логічних `users` і `system` (імена в Cloud Storage глобально унікальні — напр.
     `<project>-thinkhow-users`, `<project>-thinkhow-system`; ці імена йдуть у `THINKHOW_USERS_BUCKET` /
     `THINKHOW_SYSTEM_BUCKET`) у `europe-west3`, uniform access, **object versioning** (старі версії — M2).
  4. Service accounts: `thinkhow-web` (`roles/storage.objectAdmin` на `users`, `roles/storage.objectViewer` на
     `system` — сервіс у хмарі Знання лише читає, `roles/aiplatform.user`) і
     `thinkhow-job` (`roles/storage.objectViewer` на `users`, `roles/storage.objectAdmin` на `system`,
     `roles/aiplatform.user`) — Job лише читає `users` (M2 S2).
  5. Образ: Artifact Registry `europe-west3`, `gcloud builds submit --tag …` (збирає Cloud Build у хмарі).
  6. OAuth-клієнт «External» і consent screen (Testing, тестові користувачі — запрошені Gmail), кроки консолі.
  7. Cloud Run Job `thinkhow-learning` (той самий образ, `--service-account thinkhow-job`, `--set-env-vars
     THINKHOW_USERS_BUCKET=<…>,THINKHOW_SYSTEM_BUCKET=<…>,THINKHOW_OWNER_EMAIL=<…>` — `load_settings` вимагає їх і
     для Job, `--task-timeout 3600s` (технічне значення агента: десятки сесій по кілька секунд на виклик із запасом),
     `--max-retries 0`; збережені аргументи за замовчуванням — `-m,thinkhow.learning.job,analyze`, бо Scheduler
     кличе `:run` без змін), один запуск `seed` з повним `--args=-m,thinkhow.learning.job,seed` (`--args` замінює весь збережений
     перелік; право `run.jobs.runWithOverrides` — у ролі власника) (`gcloud run jobs execute … --args …seed`), далі `analyze`.
  8. Cloud Run service `thinkhow` (лише після `seed` кроку 7: у хмарі сервіс читає Знання при старті, без посіву —
     `KnowledgeMissing`, ревізія не стартує): `--service-account thinkhow-web`, `--max-instances 1 --min-instances 0`,
     `--timeout 3600` (довгий потік SSE), `--no-cpu-throttling` не потрібно, `--iap`, `--no-allow-unauthenticated`,
     змінні `THINKHOW_USERS_BUCKET`, `THINKHOW_SYSTEM_BUCKET`, `THINKHOW_OWNER_EMAIL`, `THINKHOW_IAP_AUDIENCE`
     (`/projects/<PROJECT_NUMBER>/locations/europe-west3/services/thinkhow`); доступ IAP — `gcloud iap web
     add-iam-policy-binding … --role roles/iap.httpsResourceAccessor` для кожного запрошеного.
     Агент сервісу IAP (`service-<PROJECT_NUMBER>@gcp-sa-iap.iam.gserviceaccount.com`) отримує `roles/run.invoker` на
     сервіс (`untested — common knowledge`, docs IAP для Cloud Run).
  9. Cloud Scheduler: щоночі `POST https://run.googleapis.com/v2/projects/<PROJECT>/locations/europe-west3/jobs/
     thinkhow-learning:run` з OAuth service account, що має `roles/run.invoker` на Job.
  10. **Чекліст власника** (кожен пункт — що зробити, що має вийти, куди записати): PR-04 — вхід запрошеним Gmail,
      сторонній Gmail не входить, на сторінці «Мої теми» (власник — «Усі теми»), відповідь іде потоком (видно, як
      текст росте), репліка після кінця сесії IAP не губиться (написати текст, видалити cookie IAP / вийти, натиснути
      «Надіслати» → повідомлення про вхід, текст лишився в полі; увійти знову → надіслати); PR-07 — тема переживає
      нову ревізію сервісу (розгорнути ще раз, тема на місці), файли видно в `gcloud storage ls`; AC1 — завершити
      сесію, запустити Job `analyze`, файл `system/learning/observations/…/s1.json` з `link`, що відкриває репліку.
      Наприкінці — що відповісти в задачі (рядок для `SKELETON_VERIFIED` пише агент після відповіді).
- Errors: нема нових. Dependencies: нема.
- Does NOT do: виконання розгортання; секрети в образі; `.env` у образі.

## Decisions (with WHY)
- Q1: два запобіжники — AST-тести, не import-linter. Чому: правило про **значення** аргументу (bucket `"users"`), не
  про імпорт; import-linter цього не бачить. Rejected: обгортки сховища на кожен bucket — нова абстракція заради
  тесту (§10.4); runtime-перевірка в `Storage` — `platform` мусив би знати частини.
- Q2: `tests/test_ac4.py` запускає наявні перевірки, а не копіює їх. Чому: одна правда на пункт; власник бачить
  чотири назви. Rejected: лише документ із переліком — не падає, коли пункт зламано.
- Q3: `uv` у образі з офіційного образу. Чому: engine-rules забороняють `curl | sh`; `uv.lock` дає ті самі версії.
  Rejected: `pip install -r` з експорту — другий файл залежностей.
- Q4: `--max-instances 1`. Чому: feature/M2 — один екземпляр («кожен файл пише одна задача» без блокувань).
  Rejected: автомасштаб — два екземпляри писали б один `conversation.md`. Залишок: під час викладки нової ревізії
  стара й нова можуть недовго працювати разом — прийнятий ризик M2; `docs/deploy.md` радить розгортати не посеред
  сесії.

## Hardest seams (test-confidence points)
- **Seam 1: запобіжник, що мовчить** — `test_the_guards_see_a_planted_breach` на вигаданих рядках; без нього
  порожній `storage_calls` проходив би всі тести. Відкидає «тест, що нічого не знаходить, бо нічого не шукає».
- **Seam 2: образ, який агент не може зібрати** — `tests/test_dockerfile.py` статично: базовий образ
  `python:3.13-slim`; `COPY --from=ghcr.io/astral-sh/uv`; `pyproject.toml` і `uv.lock` скопійовано до `uv sync
  --frozen --no-dev`; `COPY src/ /app/src/` і `COPY cards/ /app/cards/` дослівно; `ENV PYTHONPATH=/app/src`; `USER` не root; `CMD` з
  `exec`, `thinkhow.web.app:app` і `${PORT:-8080}`; `.dockerignore` виключає `.env*`, `.venv`, `.git` і **не** виключає `src` чи `cards` (жоден рядок не збігається з
  ними). Справжня
  збірка — `gcloud builds submit` власника; локальна перевірка (`docker build`, `docker run … -e
  THINKHOW_LOCAL=true`, `GET /`) — у `docs/deploy.md` для власника.
- **Seam 3: інструкція відповідає коду** — тест `tests/test_deploy_doc.py`: кожна змінна `THINKHOW_*`, яку вимагає
  `load_settings` у хмарному режимі (`users_bucket`, `system_bucket`, `owner_email`), стоїть **окремо** і в команді
  `gcloud run jobs deploy`/`create`, і в команді `gcloud run deploy thinkhow`; `iap_audience` — у команді сервісу; назви команд Job (`seed`, `analyze`) і точка входу `thinkhow.web.app:app` є в `Dockerfile` чи
  `docs/deploy.md`; рядок `gcloud run jobs execute` із `seed` стоїть **раніше** за рядок `gcloud run deploy
  thinkhow` (відкидає інструкцію, де сервіс розгортається до посіву — він не стартує).

## Invariants (rules that hold for every input in the stated domain)
- None — це запобіжники й інструкція, перевірені випадок за випадком; правила самого коду — інваріанти S1–S6.

## Exit criterion
- `uv run pytest` зелений: `tests/test_a3_guards.py`, `tests/test_ac4.py`, `tests/test_deploy_doc.py`, усі
  попередні; `ruff`, `mypy`, `lint-imports` без помилок.
- `tests/test_dockerfile.py` зелений (Seam 2); збірка образу — крок власника (`gcloud builds submit`), бо демон
  Docker агентові недоступний. Smoke-скрипта в цьому slice нема: запуск образу — дія власника за `docs/deploy.md`.
- `docs/deploy.md` з чеклістом; AC1–AC3 — дія власника (задача йде в `blocked/` з питанням).

## Deferred to later slices
- CI, автоматичне розгортання — коли з'явиться другий розробник чи друге середовище.
- `--min-instances 1` (тепла інстанція) — feature Deferred: власник при розгортанні, двосторонні двері.

## Open items requiring human decision (if any)
- None (розгортання — дія власника, вже назване задачею 105).

## Revisions during planning
- **Phases 2–5 (critic round 1) — challenge:** "the agent has no Docker daemon access; `docker build` in the exit criterion can never be met" → **revised:** статичний `tests/test_dockerfile.py`, збірка — `gcloud builds submit` власника → **reason:** probe: `permission denied` на сокеті, `sudo` заборонено. Перед цим самим планувальником: `docker run` — ask-gated, зі smoke прибрано.
- Нотатки прийнято: строгий запобіжник (константа bucket-а) і посаджені порушення (2), налаштування журналів лише для організації, `_Required` глобальний (3), `exec` у CMD (4), аргументи Job за замовчуванням (5), перекриття ревізій (6), `sys.executable -m pytest` (7), `UV_PYTHON_DOWNLOADS=never`, порядок `COPY` (8).
- **Cold-reader — challenge:** "the service is deployed (step 7) before seed (step 8); in cloud mode it cannot start without the Knowledge" → **revised:** Job і `seed` — крок 7, сервіс — крок 8; тест порядку в `tests/test_deploy_doc.py` → **reason:** `build_deps` у хмарі кличе `knowledge.current` → `KnowledgeMissing`. Нотатки: `objectViewer` на `system` для сервісу (2), `run.invoker` агентові IAP (3), `--task-timeout 3600s` (4); порожній `iap_audience` не відмовляє при старті — пропозиція у звіті (1).
- **Cold-reader 2 — challenge:** "the Job step sets no `THINKHOW_*` variables, so `seed` fails with `ConfigError`, and Seam 3 passes anyway" → **revised:** `--set-env-vars` у кроці 7; Seam 3 перевіряє змінні в кожній команді окремо → **reason:** `job.py` кличе той самий `load_settings`; виправлено без третього прогону (escalations.md, skel-guards-deploy-cold-reader). Нотатки: точні `COPY` (2), справжні імена bucket-ів (3), повний `--args` (4), `.dockerignore` не виключає `src`/`cards` (5).
