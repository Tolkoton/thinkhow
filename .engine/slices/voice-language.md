# Slice voice-language — planning artifact

Feature: `.engine/architecture/feature/voice-and-language.md`, S1 (tracer bullet, part 1; one block — the
feature is small). Driven mode, unattended: frame supplied by the feature artifact, not asked. Depends on the
walking skeleton (`workspace`, `web`, `access` — PROGRESS slices 4, 5).

## Goal
Людина обирає свою мову при першому вході і змінює її будь-коли; мова лежить у `users/<id>/profile.json`;
російської в переліку немає і сервер її не приймає (feature AC1; слова власника в задачі 106). Поки мову не
обрано, сторінки ведуть на вибір мови. Вимірна ціль: `pytest` зелений; smoke-скрипт у справжньому uvicorn
(локальний режим) проходить «перший вхід → `/` переадресує на `/language` → обрати `pl-PL` → `/` показує
«Polski» → `profile.json` має `language: "pl-PL"` і `email`», і POST `ru-RU` дає 400 без зміни профілю.

## Premise verified
- Перелік мов і формат кодів — таблиця мов `gemini-3.5-transcribe` (docs.cloud.google.com/gemini-enterprise-
  agent-platform/models/gemini/3-5-transcribe, прочитано 2026-10-23; копія —
  `.engine/artifacts/spikes/voice-stt-2026-10-23/google_language_table.txt`, 86 рядків); коди `uk-UA`, `en-US`, `de-DE`,
  `pl-PL` прийнято моделлю в `language_codes` на `eu` (spike, `results.json`, 2026-10-23). Решта кодів
  перевіряється в S2 (live-тест кличе модель кожним кодом переліку — S2 вирішує, чи всіма).
- `Storage` (skel-platform): `read`, `write`, `create_if_absent`; `write` перезаписує файл цілим.
- `web.server.person` викликає `workspace.ensure_profile` на кожен запит (`create_if_absent` з `{"email"}`):
  профілі, створені до цього slice (власник, задача 105), мають лише `email`.
- Внутрішні: FastAPI `RedirectResponse(303)`, обробники винятків `app.add_exception_handler` — уже вжиті в
  `web/server.py`.

## Out of scope (deliberately)
- Розпізнавання голосу, мікрофон (S2), мова відповіді фасилітатора (S3).
- Перевірка мови в POST-маршрутах `reply`/`retry` (S3) і `voice` (S2) — S1 дає лише `language(...)`,
  `NoLanguage` і обробник.
- Мова інтерфейсу сторінок — лишається українською (feature, Out of scope).
- Автовизначення мови з браузера (`Accept-Language`) — мову обирає людина (слова власника).
- Прибирання пакета `google-cloud-speech` — пропозиція власникові (feature).

## Seam (contract)
Пакет `src/thinkhow/workspace/` (новий модуль `languages.py` для переліку; профіль — новий модуль `profile.py`
(`language`, `set_language`; `ensure_profile` лишається в `topics.py`); публічне — з `__init__.py`):
- `@dataclass(frozen=True) Language(code: str, name: str)` — `code` — BCP-47 рівно як у таблиці мов моделі
  (`.engine/artifacts/spikes/voice-stt-2026-10-23/google_language_table.txt`); `name` — назва мовою самої мови
  (ендонім).
- `LANGUAGES: tuple[Language, ...]` — рівно ці 85 пар (таблиця моделі без `ru-RU`), рівно в цьому порядку, назви
  символ у символ (джерело — `languages.tsv` у тій самій теці, зроблений `language_names.py`: CLDR через Babel,
  перша літера велика, крім грузинської; регіон чи письмо в дужках — лише коли в переліку кілька кодів однієї
  мови; вручну — `rup-BG`, `ka-GE`, `cmn-Hans-CN`; `sd-Arab-IN` — CLDR-назва з регіоном (особливий випадок у скрипті); порядок — за назвою без діакритики, `casefold`):

  | # | code | name |
  |---|---|---|
  | 1 | `af-ZA` | Afrikaans |
  | 2 | `rup-BG` | Armãneashti |
  | 3 | `az-AZ` | Azərbaycan |
  | 4 | `bs-BA` | Bosanski |
  | 5 | `ca-ES` | Català |
  | 6 | `ceb` | Cebuano |
  | 7 | `cs-CZ` | Čeština |
  | 8 | `da-DK` | Dansk |
  | 9 | `de-DE` | Deutsch |
  | 10 | `et-EE` | Eesti |
  | 11 | `en-AU` | English (Australia) |
  | 12 | `en-IN` | English (India) |
  | 13 | `en-GB` | English (United Kingdom) |
  | 14 | `en-US` | English (United States) |
  | 15 | `es-ES` | Español (España) |
  | 16 | `es-US` | Español (Estados Unidos) |
  | 17 | `es-419` | Español (Latinoamérica) |
  | 18 | `fil-PH` | Filipino |
  | 19 | `fr-CA` | Français (Canada) |
  | 20 | `fr-FR` | Français (France) |
  | 21 | `gl-ES` | Galego |
  | 22 | `ha-NG` | Hausa |
  | 23 | `hr-HR` | Hrvatski |
  | 24 | `id-ID` | Indonesia |
  | 25 | `is-IS` | Íslenska |
  | 26 | `it-IT` | Italiano |
  | 27 | `jv-ID` | Jawa |
  | 28 | `kea-CV` | Kabuverdianu |
  | 29 | `sw-KE` | Kiswahili |
  | 30 | `lv-LV` | Latviešu |
  | 31 | `lt-LT` | Lietuvių |
  | 32 | `ln-CD` | Lingála |
  | 33 | `hu-HU` | Magyar |
  | 34 | `mt-MT` | Malti |
  | 35 | `ms-MY` | Melayu |
  | 36 | `nl-NL` | Nederlands |
  | 37 | `nb-NO` | Norsk bokmål |
  | 38 | `uz-UZ` | O‘zbek |
  | 39 | `pl-PL` | Polski |
  | 40 | `pt-BR` | Português (Brasil) |
  | 41 | `pt-PT` | Português (Portugal) |
  | 42 | `ro-RO` | Română |
  | 43 | `sk-SK` | Slovenčina |
  | 44 | `sl-SI` | Slovenščina |
  | 45 | `fi-FI` | Suomi |
  | 46 | `sv-SE` | Svenska |
  | 47 | `vi-VN` | Tiếng Việt |
  | 48 | `tr-TR` | Türkçe |
  | 49 | `el-GR` | Ελληνικά |
  | 50 | `be-BY` | Беларуская |
  | 51 | `bg-BG` | Български |
  | 52 | `ky-KG` | Кыргызча |
  | 53 | `mk-MK` | Македонски |
  | 54 | `mn-MN` | Монгол |
  | 55 | `sr-RS` | Српски |
  | 56 | `tg-TJ` | Тоҷикӣ |
  | 57 | `uk-UA` | Українська |
  | 58 | `kk-KZ` | Қазақ тілі |
  | 59 | `hy-AM` | Հայերեն |
  | 60 | `he-IL` | עברית |
  | 61 | `ar-EG` | العربية |
  | 62 | `sd-Arab-IN` | سنڌي (ڀارت) |
  | 63 | `fa-IR` | فارسی |
  | 64 | `ne-NP` | नेपाली |
  | 65 | `mr-IN` | मराठी |
  | 66 | `hi-IN` | हिन्दी |
  | 67 | `as-IN` | অসমীয়া |
  | 68 | `bn-BD` | বাংলা (বাংলাদেশ) |
  | 69 | `bn-IN` | বাংলা (ভারত) |
  | 70 | `pa-Guru-IN` | ਪੰਜਾਬੀ (ਗੁਰਮੁਖੀ) |
  | 71 | `pa-IN` | ਪੰਜਾਬੀ (ਭਾਰਤ) |
  | 72 | `gu-IN` | ગુજરાતી |
  | 73 | `or-IN` | ଓଡ଼ିଆ |
  | 74 | `te-IN` | తెలుగు |
  | 75 | `kn-IN` | ಕನ್ನಡ |
  | 76 | `ml-IN` | മലയാളം |
  | 77 | `th-TH` | ไทย |
  | 78 | `my-MM` | မြန်မာ |
  | 79 | `ka-GE` | ქართული |
  | 80 | `ko-KR` | 한국어 |
  | 81 | `am-ET` | አማርኛ |
  | 82 | `km-KH` | ខ្មែរ |
  | 83 | `cmn-Hans-CN` | 中文 (简体) |
  | 84 | `ja-JP` | 日本語 |
  | 85 | `yue-Hant-HK` | 粵語 |

  Коди й назви унікальні; жоден код не `ru-RU` і не починається з `ru-`. Перелік у коді — літерал (без Babel:
  це не залежність застосунку).
- `class NoLanguage(Exception)` — мову не обрано.
- `language(storage, user) -> Language` — читає `<uid>/profile.json`; повертає `Language` з `LANGUAGES` за полем
  `language`. Кидає `NoLanguage`, якщо файлу немає, поля немає, значення не рядок, коду немає в `LANGUAGES`
  (зокрема `ru-RU`), або файл не розбирається як JSON-об'єкт.
- `set_language(storage, user, code: str) -> None` — `code` не з `LANGUAGES` (точний збіг, з регістром) →
  `ValueError`, профіль не змінено. Інакше пише `<uid>/profile.json` цілим: `{"email": user.email, "language":
  code}` (`application/json`, UTF-8). Email — з `CurrentUser` (особа запиту), тож попередній вміст не читається.
- `ensure_profile` — без змін (`create_if_absent` з `{"email"}`), щоб не перетерти обрану мову.

Пакет `src/thinkhow/web/`:
- `GET /language` — сторінка вибору: `<select name="code">` з усіма `LANGUAGES` (`value` = `code`, текст =
  `name`), обрана поточна мова (`selected`), коли вона є; без мови — перший пункт-підказка «— оберіть мову —»
  з порожнім значенням; кнопка «Зберегти». Ця сторінка не вимагає мови.
- `POST /language` (форма `code`) → `set_language` → 303 на `/`. Код поза переліком, порожній чи відсутній →
  400 через наявні обробники `ValueError` / `RequestValidationError`, у `_bad_request` додається гілка
  `POST /language` з текстом «Такої мови немає в переліку.»
- `GET /` і `GET /topics/{uid}/{topic_id}` викликають `workspace.language(...)` (для `/` — і показують
  «Мова: <name>» з посиланням «змінити» на `/language`).
- Один обробник `NoLanguage`: запит `GET` → 303 на `/language`; будь-який інший метод → 409 HTML-фрагмент
  `<p class="error">Спершу оберіть мову (сторінка «Мова»).</p>` (форма фрагмента — як у `_fragment`). Це окремий
  обробник, не рядок `MESSAGES` (рядок дав би 409 і на GET) — уточнення до feature-артефакту («рядок `MESSAGES`,
  з S1»): S2 і S3 отримують 409 на POST саме з цього обробника.
- Посилання «Мова» — у `base.html` поруч з «ThinkHow», на кожній сторінці.
- Errors: `NoLanguage`, `ValueError` — кидаються; один шар обробки в `web` (M3 A4).
- Dependencies (injected): `storage` (Deps), `user` (шар входу).
- Does NOT do: розпізнавання, мова відповіді, перевірка мови в POST-маршрутах.

Наявні тести й smoke, які відкривають сторінки свіжим профілем, оновлюються в цьому slice (крок, що обирає мову
для особи тесту перед GET — через `POST /language` або `workspace.set_language`):
`tests/contract/skel_web/` (`skelweb_fakes.py`, `test_skelweb_routes.py`, `test_skelweb_invariants.py`,
`test_skelweb_local.py`, `test_skelweb_logging.py`), `tests/contract/skel_learning/` (`test_skell_chain.py` і
ті, що відкривають сторінки), `tests/contract/walking_skeleton_block/test_wsblock_connections.py`,
`tests/smoke/test_e2e_local.py`, `scripts/smoke_test_skel_web.py`, `scripts/smoke_test_skel_learning.py` — ті з
них, що падають на переадресації. Зміна в них — лише додати вибір мови; перевірки не послаблюються.

## Decisions (with WHY)
- Q1: перелік — усі мови таблиці моделі, крім російської (включно з «експериментальними» Google). Чому: слова
  власника — «Мова — вільний вибір людини… Російську забороняємо»; позначки «експериментальна» не просили
  (feature-critic, раунд 1). Rejected: лише «Supported» (28) — звужує вільний вибір без слова власника
  (напр. чеська — Experimental); список ISO-639 усіх мов — модель не прийме код поза таблицею.
- Q2a: назви — ендоніми з CLDR (Babel), записані літералом. Чому: людина шукає свою мову своєю мовою; CLDR — 
  стандартне джерело назв мов, не пам'ять агента. Rejected: українські назви — людині з Нідерландів шукати
  «Нідерландська» незручно; Babel як залежність застосунку — пакет заради 85 рядків, що не змінюються.
- Q2b: порядок — за назвою без діакритики, `casefold`. Чому: «Čeština» стоїть серед «C», а не після «Z».
  Rejected: порядок таблиці Google (за англійськими назвами) — випадковий для людини; простий `casefold` —
  латиниця з діакритикою опиняється в кінці латиниці.
- Q7 (AUTONOMOUS, тексти інтерфейсу): «— оберіть мову —», «Зберегти», «Мова: … · змінити», «Такої мови немає в
  переліку.», «Спершу оберіть мову (сторінка «Мова»).» — двосторонні двері; «Спершу оберіть мову» — з
  feature-артефакту. Посилання у фрагменті 409, яке згадує feature-артефакт, замінено словами «(сторінка «Мова»)»:
  фрагмент екранується (`_fragment`), клієнт S2 показує лише його текст, а посилання «Мова» є в `base.html` на
  кожній сторінці.
- Q3: `set_language` пише `{"email", "language"}` з `CurrentUser`, не читаючи файл. Чому: один запис, нічого
  губити — у профілі лише ці два поля (M2 S2: `profile.json` — email і мова); email з особи запиту — завжди
  чинний. Rejected: прочитати → змінити → записати — зайве читання і гілка на зіпсований файл.
- Q4: `language()` трактує зіпсований чи незнайомий вміст як «мову не обрано». Чому: файл пише лише
  `workspace`; м'який шлях — людина обирає знову, і `set_language` переписує файл. Rejected: кидати помилку —
  людина застрягла б на 500 без виходу.
- Q5: без мови `GET` переадресовує, інші методи — 409. Чому: сторінку можна показати замість іншої; POST
  (форма, `fetch`) — ні, клієнт показує текст фрагмента (feature, контракт S2). Rejected: переадресація для
  POST — `fetch` пішов би за нею й отримав HTML сторінки замість потоку чи JSON.
- Q6: мова обов'язкова лише на сторінках, які її потребуватимуть (`/`, тема); `POST /topics`, `/close` її не
  перевіряють. Чому: P5 — найпростіше; людина без мови все одно потрапляє на `/language` з `/`. Rejected:
  перевіряти всюди — зайві виклики без користі.

## Hardest seams (test-confidence points)
Нові контрактні тести — у `tests/contract/voice_language/`; перший RED — ланцюжок Seam 1.
- **Seam 1: петля переадресації.** `/language` викликається тим самим шаром входу; якщо обробник
  `NoLanguage` колись зачепить `/language`, людина ніколи не обере мову. Тест: свіжий профіль, `GET
  /language` → 200 із `select`; ланцюжок `GET /` → 303 `/language` → POST → 303 `/` → 200, з
  `follow_redirects=False` на кожному кроці (не «зрештою 200»). І: профіль з мовою → `GET /language` → 200, у
  `select` обрано саме цей код.
- **Seam 2: обрана мова не перетирається.** `person` кличе `ensure_profile` на кожен запит. Тест: обрати мову,
  зробити ще кілька запитів, `language()` — та сама; і навпаки: профіль з лише `email` (як у власника після
  задачі 105) → `GET /` переадресовує. Відкидає реалізацію, що в `ensure_profile` пише `language: null`.
- **Seam 3: російська не проходить жодним шляхом.** `POST /language` з `ru-RU`, `ru`, `RU-ru`, ` ru-RU `, а також
  з майже-правильними кодами дозволеної мови ` pl-PL `, `PL-pl`, `pl-pl`, `pl_PL` (клієнт тесту нічого не обрізає
  й не нормалізує; ті самі рядки — прямо в `set_language` для I3) → 400 / `ValueError`; тіло 400 — рівно
  фрагмент «Такої мови немає в переліку.» і для невідомого коду, і для порожнього чи відсутнього `code`
  (тест починає з уже наявного профілю — з мовою і без, — щоб порівнювати з файлом, а не з «немає»),
  профіль байт-у-байт той самий; `profile.json` з `language: "ru-RU"`, записаний повз `set_language` →
  `NoLanguage`. Відкидає перевірку лише HTML-переліку.
- **Seam 4: перелік — контракт із моделлю й людиною.** Тест порівнює `LANGUAGES` з таблицею «Seam» пара в пару
  і в тому ж порядку (код і назва символ у символ; таблиця вписана в тест літералом), і множину кодів — з
  `google_language_table.txt` без `ru-RU` (тест свідомо читає цей артефакт: рядки `code | name | status`,
  рядки з `#` пропускаються) (не «≥ 80 мов»).

- **Seam 5: обробник `NoLanguage` ділить за методом.** Жоден маршрут S1 не кидає `NoLanguage` на POST, тож тест
  доходить до обробника без маршруту продукту: додає до застосунку з `create_app` тестовий маршрут `POST`, що
  кидає `NoLanguage` (FastAPI дозволяє додати маршрут після створення), і такий самий `PUT`.
  Перевіряє: `POST` і `PUT` → 409, тіло рівно `<p class="error">Спершу оберіть мову (сторінка «Мова»).</p>`,
  без `Location`; `GET` на `/` і на сторінку власної теми (`/topics/{uid}/{topic_id}`) → 303,
  `Location: /language`. (`HEAD` на сторінки FastAPI 0.159.1 відповідає 405 ще до шару входу — поведінка
  фреймворку, поза цим slice.) Відкидає обробник, що переадресовує все,
  і рядок `NoLanguage` у `MESSAGES` (409 і на GET).
## Invariants (rules that hold for every input in the stated domain)
- **I1** — `language()` повертає лише мову з `LANGUAGES` і ніколи — російську.
  - Domain: будь-який вміст `<uid>/profile.json` (немає, порожній, не JSON, валідний JSON, що не об'єкт —
    `[]`, `"x"`, `null`, `5`, — байти, що не є UTF-8, JSON-об'єкт без поля, поле не рядок, будь-який рядок).
    На рівні web: зіпсований профіль → `GET /` 303, `GET /language` 200.
  - Source: слова власника в задачі 106 («Російську забороняємо»); «Seam», `language`.
  - Broken by: реалізація, що повертає `Language(code, code)` для невідомого коду, або перевіряє лише
    наявність поля.
- **I2** — `set_language` з кодом із `LANGUAGES`, потім `language()` повертає мову з тим самим кодом (туди й
  назад), а `profile.json` зберігає `email` особи.
  - Domain: кожен з 85 кодів `LANGUAGES`; будь-який попередній стан профілю (немає, лише email, інша мова,
    зіпсований).
  - Source: feature AC1; «Seam», `set_language`.
  - Broken by: запис коду в іншому регістрі чи обрізаного; втрата `email` при зміні мови.
- **I3** — `set_language` з кодом поза `LANGUAGES` не змінює `profile.json` і кидає `ValueError`.
  - Domain: будь-який рядок, що не дорівнює точно жодному коду `LANGUAGES` (зокрема `ru-RU`, порожній, з
    пробілами, в іншому регістрі).
  - Source: слова власника («Російську забороняємо»); «Seam».
  - Broken by: нормалізація регістру/пробілів перед перевіркою, або запис до перевірки.
- **I4** — `ensure_profile` не змінює наявний `profile.json`, хоч що в ньому (з мовою, без, зіпсований).
  - Domain: будь-який наявний вміст `profile.json`, будь-яка кількість викликів (зокрема через запити після
    `set_language`).
  - Source: «Seam», `ensure_profile` без змін; Seam 2.
  - Broken by: `ensure_profile`, що пише файл щоразу.

## Exit criterion
- Контрактні тести slice (I1–I4, Seams 1–5) і оновлені наявні тести зелені: `uv run pytest`; `uv run ruff check
  .`; `uv run mypy`; `uv run lint-imports`.
- Наявні smoke кістяка, які pytest не запускає (`testpaths = ["tests"]`): `uv run python
  scripts/smoke_test_skel_web.py` і `uv run python scripts/smoke_test_skel_learning.py` — кожен виходить з 0;
  їхні перевірки ті самі, додано лише вибір мови.
- Smoke `scripts/smoke_test_voice_language.py`: справжній uvicorn у локальному режимі в тимчасовій теці;
  `GET /` → 303 `/language`; `GET /language` → 200 з `<select name="code">`; `POST /language code=pl-PL` → 303
  `/`; `GET /` → 200, сторінка містить «Мова: Polski»; `users/local-owner/profile.json` у локальній теці
  (uid — `THINKHOW_LOCAL_USER_ID` за замовчуванням) як розібраний JSON дорівнює `{"email": "owner@localhost",
  "language": "pl-PL"}` (особа — за замовчуванням, smoke її не перевизначає). Перед тим smoke ще раз кладе
  профіль лише з `email` (як у власника після задачі 105) і бачить `GET /` → 303 `/language`; `POST /language
  code=ru-RU` → 400, `profile.json` не змінився. Вивід — `.engine/artifacts/spikes/voice-language-smoke-<дата>.txt`.

## Deferred to later slices
- Перевірка мови в `reply`/`retry` — S3 (`voice-reply-language`); у `voice` — S2 (`voice-dictation`) — why
  later: ці маршрути змінюють ті slices — revisit trigger: `.engine/slices/voice-dictation.md` і
  `.engine/slices/voice-reply-language.md` мають вимагати `NoLanguage` → 409.
- Розгортання — після всієї функції F13 (S1–S3), дією власника; власник після розгортання один раз обере мову
  (його профіль з задачі 105 має лише `email`) — why later: S1 сам по собі власникові нічого не дає — revisit
  trigger: звіт задачі 106.
- Чи приймає модель кожен з 85 кодів — S2 live-тест — why later: потребує `platform.speech` — revisit trigger:
  відмова моделі на коді → прибрати код з переліку.

## Open items requiring human decision (if any)
- Немає.

## Critic notes (non-blocking)
- Phase 2: `pa-IN` і `pa-Guru-IN` на практиці — одна мова (панджабі гурмукхі в Індії); лишено обидва, бо так у
  таблиці моделі (Q1).
- Phase 2: сильніша альтернатива до Q4 — окремий `CorruptProfile` з повідомленням; м'який шлях лишено, бо людина
  сама виправляє стан на `/language`.
- Cold reader: `profile.py` перевіряє uid тим самим правилом, що `topics.py` (`_uid`) — перевикористати, не
  копіювати. `json.JSONDecodeError` і `UnicodeDecodeError` — підкласи `ValueError`: `language()` має перетворити їх
  на `NoLanguage`, інакше `GET /` дасть 400 (I1 це ловить). Правило «кожна GET-сторінка вимагає мову» тримається
  викликом `language()` у кожному обробнику — нова сторінка мусить зробити так само.
- Phases 4–5: smoke ще раз кладе профіль лише з `email` — друга перевірка профілю власника з задачі 105.
