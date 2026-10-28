# Slice voice-synthesis — planning artifact

Feature: `.engine/architecture/feature/voice-conversation-mode.md`, S1 (tracer bullet with S2a; block voice). Driven
mode, unattended: frame supplied by the feature artifact, not asked.

## Goal
Застосунок уміє сказати голосом Google текст мовою людини: `POST /speak` з реченням відповіді → MP3 голосом
Chirp 3 HD (або Gemini-TTS для 21 мови без Chirp 3 HD) з Cloud Text-to-Speech на ендпоінті `eu`; для мови без голосу
— зрозуміла відмова; сторінка теми знає, чи є голос для мови людини. Вимірна ціль: pytest зелений; live-тест на `eu`
повертає MP3 для `uk-UA` (Chirp 3 HD) і `ka-GE` (Gemini-TTS); smoke — справжній uvicorn у локальному режимі:
`/speak` → 200 `audio/mpeg`, сторінка теми з `data-voice="yes"`.

## Premise verified
- PR-22: Cloud TTS `https://eu-texttospeech.googleapis.com/v1/text:synthesize` з `{"input": {"text"}, "voice":
  {"languageCode", "name": "<code>-Chirp3-HD-Kore"}, "audioConfig": {"audioEncoding": "MP3"}}` і токеном ADC
  (`Authorization: Bearer`) → 200 `{"audioContent": base64}`; 1.2–2.4 с на речення:
  `.engine/artifacts/spikes/voice-conversation-2026-10-27/latency.out` (2026-10-27).
- PR-23: таблиця мов — `voices.out` (Chirp 3 HD для 46 кодів профілю точно і 3 під іншим кодом), `gemini_langs.out`
  (Gemini-TTS — `"name": "Kore", "modelName": "gemini-2.5-flash-tts"` — для 21 коду), та сама проба.
- Помилки API: неіснуючий голос → 400 `INVALID_ARGUMENT`; без токена → 403 (`silence.out`, та сама проба).
- SSML `<speak><break time="1s"/></speak>` дає 1 с тиші MP3 4224 байти — це аудіо локального двійника
  (`silence-1s.mp3`, `silence.out`).
- Межа тексту: Gemini-TTS на `eu` — 4000 байт (400 понад це), ~3900 байт грузинської — 502 від Google
  (`gemini_limit.out`, та сама проба); Chirp 3 HD — 5000 байт (документація Cloud TTS).
- `google.auth` уже в залежностях (через `google-genai`; `platform/identity.py` імпортує `google.auth.transport`);
  `httpx` — пряма залежність. Нових пакетів не треба.
- Cloud Text-to-Speech API увімкнений у проєкті (`gcloud services list --enabled`, README проби §1). Чи вистачає
  service account сервісу прав без нової ролі — перевіряє розгортання (пункт чекліста в `docs/deploy.md`); локально
  виклик ішов з ADC без заголовка `x-goog-user-project`.

## Out of scope (deliberately)
- Цикл режиму розмови в браузері — S2a/S2b.
- Ознака «людина слухає» для моделі — S3.
- Потоковий синтез, вибір голосу людиною, швидкість — feature, Out of scope / Deferred.
- Зберігання звуку — M2 S8: MP3 лише йде у відповідь.
- Кеш синтезованих речень — P5, ніхто не просив.

## Seam (contract)
`src/thinkhow/platform/tts.py` (лише `platform` імпортує `google.*` і `httpx` — A3.2):
- `class TtsUnavailable(Exception)` — синтез не вдався після повторів.
- `class NoVoice(Exception)` — для коду мови немає голосу Google.
- `@dataclass(frozen=True) class Voice: name: str; language: str; model: str | None` — те, що йде в `voice` запиту.
- `def voice_for(code: str, name: str = "Kore") -> Voice | None` — Flow: псевдонім коду (`ALIASES`: `cmn-Hans-CN` →
  `cmn-CN`, `yue-Hant-HK` → `yue-HK`, `pa-Guru-IN` → `pa-IN`) → код у `CHIRP3` → `Voice(f"{code}-Chirp3-HD-{name}",
  code, None)`; код у `GEMINI` → `Voice(name, code, "gemini-2.5-flash-tts")`; інакше `None`. `CHIRP3` і `GEMINI` —
  `frozenset` кодів, виписані з `voices.out` і `gemini_langs.out` проби (49 і 21 після псевдонімів).
- `class Tts(Protocol): def synthesize(self, text: str, language: str) -> bytes: ...` — MP3; `NoVoice`, якщо
  `voice_for(language)` — `None`; `TtsUnavailable` після повторів.
- `class CloudTts` — `__init__(post, token, endpoint: str, voice_name: str, timeout_s: float, attempts: int,
  sleep=time.sleep, clock=time.monotonic)`, де `post(url, headers, json, timeout) -> httpx.Response` (за
  замовчуванням `httpx.post`) і `token() -> str` (токен ADC, оновлюється, коли застарів: `google.auth.default(scopes=
  ["https://www.googleapis.com/auth/cloud-platform"])` + `refresh` з `google.auth.transport.requests.Request()`).
  `synthesize`: `voice_for(language, voice_name)` (немає → `NoVoice`, без запиту) → до `attempts` спроб `POST
  {endpoint}/v1/text:synthesize` з тілом вище (`"modelName"` — лише коли `voice.model`) і `Authorization: Bearer
  <token()>`; 200 → `base64.b64decode(json["audioContent"])`; `response.raise_for_status()` для решти; повтор — за
  `platform._retry.retryable` (після розширення нижче) з `backoff_s`; не повторюване або останнє → `TtsUnavailable`.
  Будь-яка помилка після `voice_for` усередині спроби — `httpx.HTTPError` (зокрема `HTTPStatusError`, `TransportError`),
  помилка токена (`google.auth.exceptions.GoogleAuthError`), відповідь без `audioContent` чи не base64 (`KeyError`,
  `ValueError`) — стає `TtsUnavailable`, ніколи не виходить назовні як `ValueError` (400) чи 500; повторюються лише ті,
  що `retryable` (тайм-аут, 429, ≥ 500).
  Один рядок журналу `tts_call` на виклик: `voice`, `model` (`chirp3-hd` або назва моделі), `language`, `chars`,
  `bytes`, `latency_ms`, `attempts`, `outcome` (`ok` | `unavailable`); тексту немає.
- `class ScriptedTts(audio: bytes = SILENCE_MP3)` — двійник: повертає `audio`; `NoVoice` за тим самим `voice_for`;
  пам'ятає виклики `(text, language)`. `SILENCE_MP3` — байти `src/thinkhow/platform/silence.mp3` (1 с тиші, з проби).
- `def make_tts(settings: Settings) -> Tts` — локальний режим → `ScriptedTts()`; інакше `CloudTts(httpx.post,
  <ADC token()>, settings.tts_endpoint, settings.tts_voice, settings.tts_timeout_s, settings.llm_attempts)`.
- `platform.config.Settings`: `tts_endpoint: str = "https://eu-texttospeech.googleapis.com"`, `tts_voice: str =
  "Kore"`, `tts_timeout_s: float = 30.0`.

`src/thinkhow/platform/_retry.py`: `retryable` також повертає `True` для `httpx.HTTPStatusError` зі статусом 429 або
≥ 500 (решта — як була).

`src/thinkhow/workspace/` (публічне з `__init__.py`):
- `MAX_SPEAK_BYTES = 4000`.
- `speak(storage, tts: Tts, user, text: str) -> bytes` — Flow: `language(storage, user)` (`NoLanguage`) → `text`
  обрізаний по краях; порожній або довший за `MAX_SPEAK_BYTES` байт UTF-8 → `ValueError` → `tts.synthesize(text,
  language.code)`. Нічого не пише, теми не потребує.
- `has_voice(storage, user) -> bool` — `voice_for(language(storage, user).code) is not None`.

`src/thinkhow/web/`:
- `Deps` отримує поле `tts: Tts = field(default_factory=ScriptedTts)` (після `speech`, перед `cards`); `build_deps`
  — `make_tts(settings)`.
- `POST /speak` (форма `text`) — `async def`, синхронний `workspace.speak` через `run_in_threadpool` → 200
  `Response(content=mp3, media_type="audio/mpeg")`, `Cache-Control: no-store`. Помилки — єдиний шар: `NoLanguage` →
  409 (наявний), `NoVoice` → 409 фрагмент «There is no voice for your language.» англійською для будь-якої мови (окремий обробник, не `MESSAGES`; власник, задача 208, 2026-10-27), `ValueError` → 400
  фрагмент «Текст для голосу не прийнято.» (гілка `_bad_request` для шляху `/speak`), `TtsUnavailable` → 502
  фрагмент «Не вдалося озвучити — спробуйте ще раз.».
- Сторінка теми: `<form id="reply-form" … data-voice="yes|no">` за `workspace.has_voice` (`topic` — лише для власної
  теми, де є форма).
Docs (той самий slice):
- `.engine/architecture/architecture-map.md`: рядок A2 і розділ портів — п'ятий порт «синтез голосу» (Cloud TTS `eu` /
  тиша в MP3); M2 S8 — абзац «Голос у відповідь» (режим розмови, Cloud TTS `eu`, звук відповіді не зберігається).
- `docs/deploy.md`: змінні `THINKHOW_TTS_ENDPOINT`, `THINKHOW_TTS_VOICE`, `THINKHOW_TTS_TIMEOUT_S` (типові значення —
  задавати не треба); пункт чекліста «на сторінці теми `/speak` дає звук; у журналі `tts_call outcome=ok`; при 403 —
  service account бракує права на Cloud Text-to-Speech».
- Errors: кидаються (`NoVoice`, `TtsUnavailable`, `NoLanguage`, `ValueError`); один шар у `web`.
- Dependencies (injected): `tts` (Deps), `post`/`token`/`sleep`/`clock` (CloudTts).
- Does NOT do: зберігати звук, кешувати, різати текст на речення (це клієнт S2a), знати тему чи розмову.

## Decisions (with WHY)
- Q1: Cloud TTS на `eu`, голос Chirp 3 HD, MP3. Чому: C1 + M2 S3 (Google, обробка в ЄС: регіональний ендпоінт `eu`);
  1.2–2.4 с на речення — найшвидше з виміряного; MP3 грає кожен браузер (`browsers.md`, п. 6); API уже ввімкнений,
  REST через наявний `httpx`. Rejected: Gemini-TTS на Vertex `europe-west4` — 4.5–8 с цілком; потоком перший шматок
  за 1.3 с, але сирий PCM 24 кГц (~48 КБ/с) і відтворення шматками в браузері — складність, якої тепер не треба
  (feature, Deferred); синтез у браузері (Web Speech API) — голоси не Google і не в ЄС (S8); пакет
  `google-cloud-texttospeech` — нова залежність заради одного POST.
- Q2: голос за кодом мови — дві виписані множини з проби, а не запит `voices.list` під час роботи. Чому: таблиця —
  контракт з людиною (як `LANGUAGES`); без зайвого виклику на кожен запуск. Найкраще за `voices.list`: нові голоси
  Google з'являлися б самі; але тоді вибір голосу залежить від мережі під час старту і не перевіряється тестом.
  Ціна розвороту — один модуль.
- Q3: для 21 мови без Chirp 3 HD — Gemini-TTS через той самий ендпоінт (4–8 с на речення). Чому: C4 (мова людини) —
  повільний голос краще, ніж жодного. Rejected: голоси Standard/Wavenet — є лише для частини цих мов і звучать гірше.
- Q4: `POST /speak` не прив'язаний до теми. Чому: синтез не читає розмови — лише мову людини; G4 не зачіпається (людина
  озвучує лише текст, який сама надіслала). Rejected: `/topics/{uid}/{topic_id}/speak` — перевірка теми без потреби.
- Q5: межа тексту 4000 байт UTF-8 — менша з меж API: Gemini-TTS відмовляє понад 4000 байт («longer than the limit of
  4000 bytes», `gemini_limit.out`), Chirp 3 HD — понад 5000. Чому одна межа для всіх голосів: межа — для захисту від
  явно хибного запиту, не для нарізки; клієнт ріже на речення і шматки до 1000 байт (S2a), бо Gemini-TTS уже на
  ~3900 байтах дає 502. Rejected: межа за моделлю голосу (`Voice.max_bytes`) — друга величина без користі для клієнта,
  який і так шле до 1000 байт.
- Q6: повтори — те саме правило `platform._retry`, розширене статусами `httpx.HTTPStatusError` 429/5xx. Чому: A4
  «тайм-аут, обмежені повтори»; одне правило для всіх викликів Google. Rejected: свій класифікатор у `tts` — правило в
  двох місцях. Тайм-аут спроби 30 с: найдовше виміряне речення — 7.8 с (Gemini-TTS), 30 с — виявлення зависання.
- Q7: `Deps.tts` зі значенням за замовчуванням (двійник). Чому: 10 допоміжних файлів тестів будують `Deps` без нього;
  продакшн завжди будує через `build_deps` → `make_tts`; тест перевіряє, що `make_tts` поза локальним режимом дає
  `CloudTts`. Rejected: обов'язкове поле (як `speech`) — правка 10 файлів тестів інших slices без зміни поведінки.
- Q8: голос «Kore» (`tts_voice`). Чому: той самий голос у Chirp 3 HD і Gemini-TTS, спокійний; у пробах. Рішення
  двосторонніх дверей (змінна середовища).
- Q9: токен ADC оновлює `platform.tts` сам (`google.auth`), а не клієнт `google-genai`. Чому: REST-виклик поза Vertex;
  `google.auth` дає токен і на Cloud Run (metadata server), і локально.

## Hardest seams (test-confidence points — distinct from the contract Seam above)
- **Seam 1: тіло запиту і вибір голосу.** Тест з підробленим `post`, що записує `url`, `headers`, `json`: `uk-UA` →
  `name: "uk-UA-Chirp3-HD-Kore"`, без `modelName`; `ka-GE` → `name: "Kore"`, `modelName: "gemini-2.5-flash-tts"`;
  `cmn-Hans-CN` → `languageCode: "cmn-CN"`; `kk-KZ` → `NoVoice` і жодного виклику `post`. Відкидає «тест лише на 200».
- **Seam 2: повтори на HTTP-статусах.** Підроблений `post` дає 429, потім 200 → MP3 і `attempts=2` у журналі; 400 →
  одразу `TtsUnavailable` без сну; 503 ×`attempts` → `TtsUnavailable`. `sleep` підроблений. Відкидає повтор на 400 і
  «повтор лише на тайм-аут».
- **Seam 3: журнал без тексту.** `tts_call` має `chars` і не має тексту ні в жодному полі (текст-маркер у запиті не
  з'являється в рядку журналу).
- **Seam 4: межа 4000 байт — у байтах, не символах.** Текст з 2000 кириличних літер (4000 байт) приймається,
  2001 (4002 байти) — `ValueError`/400. Відкидає `len(text)`.
- **Seam 5a: усе після `voice_for` — `TtsUnavailable`.** 200 без `audioContent` → `TtsUnavailable` → 502 (не 400);
  `post` кидає `httpx.ConnectError` → `TtsUnavailable`; `token()` кидає `GoogleAuthError` → `TtsUnavailable`.
- **Seam 5: маршрут.** TestClient: 200 `audio/mpeg` з байтами двійника; мова без голосу (`kk-KZ`) → 409 фрагмент;
  порожній текст → 400; `TtsUnavailable` → 502; без обраної мови → 409 наявного обробника. Сторінка теми:
  `data-voice="yes"` для `uk-UA`, `"no"` для `kk-KZ`. `make_tts` поза локальним режимом → `CloudTts`.
  Тест I1 — цикл по всіх 85 кодах `workspace.LANGUAGES` проти таблиці, виписаної в тест дослівно з `voices.out` і
  `gemini_langs.out` (не з множин коду). Файли: `tests/platform/test_tts.py`, `tests/web/test_speak.py`.

## Invariants (rules that hold for every input in the stated domain)
- **I1** — Для кожного коду з переліку мов профілю `voice_for` повертає голос тоді й лише тоді, коли код (після
  псевдоніма) є в одній з двох множин проби, і `Voice.language` — код, для якого Google має цей голос.
  - Domain: усі 85 кодів `workspace.LANGUAGES`.
  - Source: feature, AC4 і PR-23 (49 Chirp 3 HD, 21 Gemini-TTS, 15 без голосу).
  - Broken by: псевдонім, що не застосовано (голос `cmn-Hans-CN-Chirp3-HD-Kore` не існує → 400 на кожен запит),
    або мова, що потрапила не в ту множину.
- **I2** — Жоден рядок журналу `tts_call` не містить тексту, який озвучували.
  - Domain: будь-який текст, будь-який результат (`ok`, `unavailable`).
  - Source: feature, Policies «журнали — без тексту» (M3 A4).
  - Broken by: журнал з полем `text` чи першими словами для налагодження.

## Exit criterion
- `uv run pytest -q` зелений (нові тести slice + усі наявні); `uv run ruff check scripts tests src`, `uv run mypy`,
  `uv run lint-imports` — чисто.
- Live: `uv run pytest -m live tests/live/test_tts_live.py -s` — `make_tts` поза локальним режимом на `eu`: `uk-UA` і
  `ka-GE` дають байти MP3 (починаються з `ID3` або кадру `0xFFE…`), час записаний у вивід.
- Smoke: `uv run python scripts/smoke_test_voice_synthesis.py` — справжній uvicorn у локальному режимі: мова `uk-UA` →
  тема → сторінка має `data-voice="yes"` → `POST /speak` → 200 `audio/mpeg`, байти = `silence.mp3`; мова `kk-KZ` →
  `data-voice="no"`, `/speak` → 409.
- Docs: `grep -n "синтез" .engine/architecture/architecture-map.md` знаходить рядок A2 і абзац S8;
  `grep -n "THINKHOW_TTS\|tts_call" docs/deploy.md` — змінні й пункт чекліста.
Порогів немає (затримку лише записуємо, P4).

## Deferred to later slices
- Цикл у браузері, нарізка на речення — S2a — why later: окремий slice tracer bullet — revisit trigger: S2a наступний
  у DAG.
- Права service account на Cloud TTS — перевіряє розгортання — revisit trigger: `tts_call outcome=unavailable` з 403
  у журналі розгортання.

## Open items requiring human decision (if any)
- (немає)

## Critic notes (non-blocking)
- `MAX_SPEAK_BYTES = 4000` і `tts_timeout_s = 30.0` — технічні константи (ціна розвороту — один рядок); коментар у коді
  каже це.
- I1 охоплює 85 кодів профілю; `voice_for("xx-XX")` → `None` — один випадок у `test_tts.py`.
- 502 на ~3900 байтах Gemini-TTS повторюється як тимчасова помилка — прийнято свідомо: клієнт шле до 1000 байт.
- Тест «`make_tts` поза локальним режимом → `CloudTts`» перевіряє лише тип, без мережі (`token()` не викликається).
- Цикл критика: раунд 1 (фази 2–5 разом) — REVISE (документи A2, S8, `docs/deploy.md`); виправлено, межу 4000 байт
  виміряно; cold reader — PASS.
