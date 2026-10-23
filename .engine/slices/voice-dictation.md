# Slice voice-dictation — planning artifact

Feature: `.engine/architecture/feature/voice-and-language.md`, S2 (tracer bullet, part 2; one block). Driven mode,
unattended: frame supplied by the feature artifact, not asked. Depends on S1 `voice-language` (`workspace.language`,
`workspace.NoLanguage`, the `NoLanguage` handler: 409 on POST).

## Goal
Людина натискає мікрофон у полі введення, говорить, зупиняє; браузер записує (`MediaRecorder`) і надсилає запис
застосунку; застосунок розпізнає його `gemini-3.5-transcribe` на Vertex `eu` з закріпленою мовою людини
(`language_codes=[код з профілю]`); текст дописується в поле введення; людина править і надсилає звичайною
кнопкою. Запис лишається на сторінці, доки не з'явився текст, — «Розпізнати ще раз» (feature AC2). Вимірна ціль:
pytest зелений; live-тест на `eu` розпізнає записи справжнього Chromium (webm/opus) і mp4/AAC мовою `uk-UA`; smoke у
справжньому Chromium з фальшивим мікрофоном проводить «мова → тема → мікрофон → стоп → текст у полі →
Надіслати → відповідь».

## Premise verified
- PR-11: `gemini-3.5-transcribe`, Vertex `location="eu"`, `generate_content` з `Part.from_bytes(audio, mime)` і
  `GenerateContentConfig(audio_transcription_config=AudioTranscriptionConfig(language_codes=[code]))` приймає
  `audio/webm;codecs=opus` (тип, який дає Chromium), `audio/mp4;codecs=opus`, `audio/mp4` (AAC) і повертає текст у
  `response.parts[*].text`: `.engine/artifacts/spikes/voice-stt-2026-10-23/README.md`, `measure.py`,
  `results.json` (15 записів, медіана 1.0 с, WER 0), `near_limit_output.txt` (14.7 хв — 12–14 с, 8.6 МБ одним
  запитом); 2026-10-23. `google-genai` 2.32.0 має `AudioTranscriptionConfig` (перевірено в цій сесії).
- Chromium 1208 з `audioBitsPerSecond: 64000` пише ~64 кбіт/с (`uk0.webm` 94 580 Б замість 187 700 Б), і модель
  читає такі записи з WER 0 за ~1 с (`record64.py`, `results64.json`, 2026-10-23); 14.7 хв Opus ~64 кбіт/с — 8.6 МБ
  одним запитом за 12–14 с (`near_limit_output.txt`).
- Chromium 1208 `MediaRecorder.isTypeSupported`: `audio/webm;codecs=opus` і `audio/mp4;codecs=opus` — так,
  `audio/ogg;codecs=opus` і `audio/mp4;codecs=mp4a.40.2` — ні (spike, `record.py`). Safari пише `audio/mp4` (AAC) —
  з документації MDN, не перевірено в браузері; модель приймає AAC (spike `.m4a`).
- Помилки Vertex — ті самі, що в `platform.llm` (`google.genai.errors.APIError` з `code`, тайм-аути `httpx`):
  повтор на 429/5xx/тайм-аут (M2 «виклик моделі: тайм-аут, обмежені повтори» — architecture-map, A4).
- Service account сервісу вже має `roles/aiplatform.user` (`docs/deploy.md:70`) — нового права не треба.
- Playwright 1.64 з Chromium 1208 у кеші цього сервера, `--use-fake-device-for-media-stream` дає мікрофон
  (spike, `record.py`).

## Out of scope (deliberately)
- Розпізнавання потоком і проміжний текст (feature, Out of scope).
- Мова відповіді фасилітатора — S3.
- Зберігання звуку (M2 S8) — запис живе лише в пам'яті сторінки.
- Chirp 3 / Speech-to-Text v2 — API вимкнений у проєкті; друга реалізація відкладена (feature, Deferred).
- Прибирання пакета `google-cloud-speech` — пропозиція власникові (feature).

## Seam (contract)
`src/thinkhow/platform/speech.py` (лише `platform` імпортує SDK Google — A3.2):
- `class SpeechUnavailable(Exception)` — модель не дала тексту після повторів.
- `class Speech(Protocol): def transcribe(self, audio: bytes, mime: str, language: str) -> str` — `language` — код
  BCP-47 (`Language.code`); повертає розпізнаний текст (може бути порожній — тиша).
- `class GeminiSpeech` — `__init__(client, model: str, timeout_s: float, attempts: int, sleep=time.sleep,
  clock=time.monotonic)`; `transcribe`: `client.models.generate_content(model=model,
  contents=[types.Part.from_bytes(data=audio, mime_type=mime)], config=GenerateContentConfig(
  audio_transcription_config=AudioTranscriptionConfig(language_codes=[language]), http_options=HttpOptions(timeout=…)))`;
  текст — склеєні `text` усіх частин відповіді (без `thought`), обрізаний по краях. `Part` і `GenerateContentConfig`
  будуються всередині спроби: помилка SDK під час побудови — `SpeechUnavailable` (502), не `ValueError` (400). Повтор на ту саму помилку, що
  й у `platform.llm` (429, ≥ 500, тайм-аут; помічники `_retryable` і формула backoff (`min(2**attempt, 30) * uniform(0.5, 1.0)`) переносяться з
  `platform.llm` у новий `platform/_retry.py` (`retryable(exc)`, `backoff_s(attempt)`), і їх імпортують обидва — `platform.speech` не імпортує `platform.llm`, бо `workspace`
  його непрямо отримав би, а контракт import-linter це забороняє), до `attempts` разів з backoff; інше або останній — `SpeechUnavailable`.
  Один рядок журналу `speech_call` на виклик: `model`, `language`, `mime`, `bytes`, `latency_ms`, `attempts`,
  `outcome` (`ok` | `unavailable`); ні звуку, ні тексту.
- `class ScriptedSpeech(text: str)` — двійник: повертає `text`; пам'ятає виклики `(len(audio), mime, language)`.
- `make_speech(settings: Settings) -> Speech` — локальний режим → `ScriptedSpeech(LOCAL_TEXT)`, де `LOCAL_TEXT =
  "(локальний режим) розпізнаний текст"`; інакше `GeminiSpeech(genai.Client(vertexai=True, project, location),
  settings.speech_model, settings.speech_timeout_s, settings.llm_attempts)`. Регіон — спільний
  `settings.location` (`eu`): розпізнавання й модель фасилітатора за C1 обидва в ЄС, тож одне налаштування.
- `platform.config.Settings.speech_model: str = "gemini-3.5-transcribe"` (`THINKHOW_SPEECH_MODEL`),
  `speech_timeout_s: float = 120.0` (`THINKHOW_SPEECH_TIMEOUT_S`).

`src/thinkhow/workspace/` (публічне з `__init__.py`):
- `transcribe(storage, speech: Speech, user, ref: TopicRef, audio: bytes, mime: str) -> str` — Flow: правило
  запису теми тим самим помічником, що й `reply` (`_can_write`: формат `uid`/`topic_id` і `ref.uid == user.id`),
  і тема існує (`conversation.md` читається; немає — `TopicNotFound`: так само відповідає `reply`, і виклик моделі
  не платиться за неіснуючу тему) — G4 → `language(storage, user)` (`NoLanguage`) →
  `audio` порожній → `ValueError`; `mime` (до `;`, без пробілів, нижній регістр) не починається з `audio/` →
  `ValueError` → `speech.transcribe(audio, mime, language.code)` з `mime` як прийшов (нормалізація — лише для перевірки,
  моделі йде незмінний рядок). Нічого не пише.

`src/thinkhow/web/`:
- `Deps` отримує поле `speech: Speech` (обов'язкове, останнім); `build_deps` — `make_speech(settings)`. Наявні
  конструктори `Deps(...)` у тестах оновлюються в цьому slice (додати `speech=ScriptedSpeech(...)`):
  `tests/contract/skel_web/skelweb_fakes.py`, `tests/contract/voice_language/vl_fakes.py` (обидва — допоміжні, не
  запечатані); перевірки не змінюються.
- Маршрут `voice` — `async def`: тіло — `await request.body()`, тип — `request.headers.get("content-type", "")`,
  а синхронний `workspace.transcribe` — через `await run_in_threadpool(...)` (Starlette), щоб виклик моделі не
  тримав цикл подій (`--max-instances 1`, паралельні потоки SSE).
- `POST /topics/{uid}/{topic_id}/voice` — тіло — сирі байти запису, тип — заголовок `Content-Type` (порожній, якщо
  немає); → 200 `application/json` `{"text": "<текст>"}`. Помилки — через єдиний шар: `NoLanguage` → 409 (обробник
  S1), `TopicNotFound` → 404 (наявний рядок), `ValueError` (порожній запис або тип не `audio/…`) → 400 фрагмент
  «Запис не прийнято — спробуйте записати ще раз.» (нова гілка `_bad_request` для шляху, що закінчується на
  `/voice`), `SpeechUnavailable` → 502 фрагмент «Не вдалося
  розпізнати — спробуйте ще раз.» (новий рядок `MESSAGES`).
- Сторінка теми (лише власна, де є форма): кнопка `<button id="mic" type="button">` «🎤 Говорити» у формі поруч
  із полем; поруч `<button id="recognize" type="button" hidden>` «Розпізнати ще раз» і `<span id="mic-state">`.

`src/thinkhow/web/static/conversation.js` (без бібліотек, текст на сторінку — лише `textContent`):
- `createRecorder({ media, Recorder, fetch, ui, url, limitMs, setTimeout, clearTimeout })` → `{ start(), stop(),
  recognize() }`:
  - `start()` — `media.getUserMedia({ audio: true })`; тип — перший з `["audio/webm;codecs=opus", "audio/mp4"]`,
    для якого `Recorder.isTypeSupported` — так (жоден → без `mimeType`, тип вирішує браузер); `new Recorder(stream,
    { mimeType, audioBitsPerSecond: 64000 })` (без `mimeType`, коли жоден не підтримано); `ui.recording()`; таймер `limitMs` викликає `stop()` сам.
    Відмова в доступі до мікрофона → `ui.showError("Немає доступу до мікрофона.")`, стан — як до натискання.
  - `stop()` — лише якщо `recorder.state === "recording"` (інакше нічого: автозупинка й кнопка можуть збігтися);
    знімає таймер `limitMs`; викликає `recorder.stop()`. Частини запису збираються обробником `dataavailable`;
    обробник події `stop` рекордера (вона приходить ПІСЛЯ останнього `dataavailable`, окремою задачею — не
    всередині `recorder.stop()`) зупиняє доріжки потоку, збирає `Blob` з частин (тип — `recorder.mimeType`, а якщо
    він порожній — `"audio/webm"`), тримає його як «останній запис» і викликає `recognize()`.
  - `recognize()` — `ui.recognizing()`; `fetch(url, { method: "POST", body: blob, headers: { "Content-Type":
    blob.type } })`; 200 → `ui.insertText(json.text)` (дописати в поле: якщо поле не порожнє і не закінчується
    пробілом чи переводом рядка — через пробіл), «останній запис» забувається, `ui.idle()`; не 200 → текст
    HTML-фрагмента (теги прибрані, як `errorText` контролера) → `ui.showError(...)`, запис лишається,
    `ui.offerRecognize()`; відповідь, що не JSON і не фрагмент `<p class="error">` (напр. сторінка входу IAP після
    кінця сесії), — як мережева помилка нижче; мережева помилка (зокрема перехід на вхід Google, який `fetch` не пропускає) → `ui.showError("Не вдалося
    надіслати запис — спробуйте ще раз; якщо не вийде, увійдіть знову в новій вкладці.")`,
    `ui.offerRecognize()`. Порожній `text` (тиша) → `ui.showError("Не почули слів — спробуйте ще раз.")`, запис
    лишається, `ui.offerRecognize()`.
  - `limitMs` на сторінці — `14.5 * 60 * 1000` (межа файлу моделі 15 хв мінус запас; feature, Build parameters).
- `attach` під'єднує `#mic` (перемикає `start`/`stop`), `#recognize` (`recognize`), `#mic-state` (стан словами:
  «Запис… натисніть ще раз, щоб зупинити», «Розпізнаю…»); експорт `ThinkHow.createRecorder` для `node --test`.
- Errors: `SpeechUnavailable`, `NoLanguage`, `TopicNotFound`, `ValueError` — кидаються; один шар у `web`.
- Dependencies (injected): `speech` (Deps), `client`/`sleep`/`clock` (GeminiSpeech), `media`/`Recorder`/`fetch`/
  таймери (JS).
- Does NOT do: зберігання звуку, мову відповіді, потокове розпізнавання, збереження тексту як репліки (це робить
  звичайне «Надіслати»).

## Decisions (with WHY)
- Q1 (ADR-0005): модель — `gemini-3.5-transcribe` на Vertex `eu`, не Chirp 3 і не Gemini Flash з аудіо. Чому:
  критерії задачі 106 (мови, ЄС, формати браузерів, час): spike — 1 с на 10-секундний запис, WER 0 у 4 мовах і 3
  форматах; 14.7 хв одним запитом за 12–14 с; той самий Vertex і те саме право service account — розгортання не
  змінюється. Rejected: Chirp 3 — API Speech-to-Text у проєкті вимкнений, увімкнення — дія власника, не виміряно;
  Gemini 3.5 Flash з аудіо — 2–12 с і «причісує» (WER 0.008, «місці» замість «місті»).
- Q2: запис цілком одним запитом, не потоком і не шматками. Чому: 4 хв мови → 4 с, 14.7 хв → 14 с; шматки
  різали б слова на стиках (M2 S8, варіант 4). Rejected: `gemini-3.5-transcribe-live` — постійне з'єднання крізь
  IAP не перевірене (M2 S8, відкинуто), проміжний текст ніхто не просив.
- Q3: сирі байти в тілі з `Content-Type` запису, не multipart. Чому: один `fetch(blob)`, сервер бере тип як є;
  multipart — зайва обгортка. Найкраще за multipart: стандартна форма, `UploadFile` зливає великий файл на диск,
  стоїть поруч з наявними `Form()`-маршрутами; але запис ≤ ~9 МБ, а тип запису в multipart — ще одне поле. Rejected: base64 у JSON — +33 % розміру.
- Q4: `transcribe` живе у `workspace` і перевіряє правило запису теми. Чому: M3 — `workspace --> speech`; голос
  — частина репліки в темі людини (G4: диктувати можна лише у свою тему). Rejected: виклик `platform.speech`
  прямо з `web` — мова людини читається в `workspace`, і правило доступу дублювалось би.
- Q5a: повтори — як у `platform.llm` (429/5xx/тайм-аут, backoff, `llm_attempts`); правило — одне, у
  `platform/_retry.py`. Чому: A4 «Виклики моделі: тайм-аут, обмежені повтори»; той самий Vertex; `workspace` не
  може непрямо імпортувати `platform.llm` (контракт «workspace gets knowledge and the model only as facilitate»,
  import-linter без непрямих імпортів), тож спільне правило — в окремому модулі. Rejected: копія предиката в
  `speech` — правило у двох місцях; `ignore_imports` у контракті — послаблення запобіжника. Rejected: без повторів — тимчасова 429 губила б запис до ручного
  «Розпізнати ще раз».
- Q5b: тайм-аут спроби — свій, 120 с. Чому: найдовший виміряний запис (14.7 хв) — 14 с, тож 120 с — виявлення
  зависання, а не межа часу до тексту (P4 — час лише записуємо). Rejected: `llm_timeout_s` (300 с) — з трьома
  спробами людина чекала б до 15 хв на «Розпізнаю…».
- Q12: `audioBitsPerSecond: 64000`. Чому: Chromium за замовчуванням пише ~128 кбіт/с — 14.5 хв дали б ~14 МБ, яких
  ніхто не надсилав; 64 кбіт/с — виміряний випадок (14.7 хв ≈ 8.6 МБ одним запитом, WER 0.026; короткі записи
  Chromium 64 кбіт/с — WER 0; spike README, «Bitrate»). Rejected: типова якість браузера — розмір запиту
  вирішує браузер, не контракт; 32 кбіт/с — не виміряно.
- Q6: `speech` — обов'язкове поле `Deps` без значення за замовчуванням. Чому: двійник за замовчуванням у
  продукті — мовчазна підміна (G4-подібний ризик локального режиму, A2). Rejected: `speech: Speech =
  ScriptedSpeech(...)` — забутий `make_speech` дав би людям вигаданий текст.
- Q7: текст дописується в поле, не замінює його. Чому: людина могла вже щось написати; править вона сама
  (AC2 «людина править і надсилає»). Rejected: заміна — найкраще за неї: «Розпізнати ще раз» не дублює текст; але
  повтор буває лише після відмови (тексту тоді не було), а заміна губить надруковане.
- Q8: автозупинка на 14.5 хв. Чому: межа файлу моделі 15 хв (feature, Build parameters); запас 30 с на заголовки
  контейнера й похибку таймера. Rejected: 15:00 рівно — запис на межі міг би бути відкинутий моделлю.
- Q11: `stop()` лише просить рекордер зупинитись; запис збирається в події `stop`. Чому: у браузері останній
  `dataavailable` і `stop` приходять окремими задачами після `recorder.stop()` (spike `record.py` чекає `onstop`);
  `Blob`, зібраний одразу, був би порожній або без хвоста. Rejected: збирати в `stop()` — 400 на порожньому записі.
- Q13: поки запит розпізнавання в дорозі («Розпізнаю…»), кнопки «🎤 Говорити» і «Розпізнати ще раз» вимкнені —
  одночасно в дорозі не більше одного запиту. Після відмови (запис чекає) «🎤 Говорити» знову ввімкнена: новий
  запис замінює «останній запис». Чому: без перекриття відповідь завжди стосується останнього запису — немає
  застарілих відповідей; людина після відмови може просто сказати ще раз. Rejected: дозволити новий запис під час
  запиту — відповідь на старий запис мала б не чіпати новий (ще одне правило й таблиця станів, яких ніхто не
  просив); вимкнути мікрофон до появи тексту — після відмови людина не змогла б сказати ще раз.
- Q9 (AUTONOMOUS, тексти інтерфейсу): «🎤 Говорити», «Розпізнати ще раз», «Запис… натисніть ще раз, щоб
  зупинити», «Розпізнаю…», «Немає доступу до мікрофона.», «Не почули слів — спробуйте ще раз.», «Не вдалося
  надіслати запис — спробуйте ще раз; якщо не вийде, увійдіть знову в новій вкладці.», «Запис не прийнято — спробуйте записати ще раз.», «Не вдалося розпізнати —
  спробуйте ще раз.» — двосторонні двері.
- Q10b: Playwright — у dev-залежності (`uv add --dev playwright`), не в залежності застосунку. Чому: smoke і, за
  потреби, тести браузера мають ставитися відтворювано; Chromium 1208 уже в кеші сервера. Rejected: `uv run --with
  playwright` лише в скрипті — версія не закріплена в `uv.lock`. (Залежності обирає агент — задача 106.)
- Q10: smoke у справжньому Chromium через Playwright. Чому: AC4 «запис голосу і текст
  у полі працюють» — без браузера `MediaRecorder` і `fetch(blob)` не перевірити (PR-12). Rejected: лише `node
  --test` з підробками — доводить логіку контролера, не браузерні формати.

## Hardest seams (test-confidence points)
Нові контрактні тести — у `tests/contract/voice_dictation/`; JS — `node --test` так само, як `tests/contract/skel_web/test_skelweb_js.py`.
- **Seam 1: мова й тип доходять до моделі як є.** Тест `GeminiSpeech` з фейковим `client`: у
  `generate_content` прийшли `model`, одна частина з тими самими байтами й `mime_type` рівно як передано
  (`audio/webm;codecs=opus`), `language_codes == [language]`, `http_options.timeout == int(timeout_s * 1000)`
  (мілісекунди, як у `platform.llm`). Відповідь фейка з двома текстовими частинами, однією `thought` і пробілами по
  краях → склеєний обрізаний текст без `thought`. Модель повернула порожнє чи пробіли → `""` (через маршрут — 200
  `{"text": ""}`, не 502). Відкидає реалізацію, що обрізає `;codecs=`, не
  передає мову або передає `language_auto`.
- **Seam 2: мова — з профілю, не з запиту.** Тест через маршрут: для кожного з 85 кодів у профілі (і з
  `Content-Type: AUDIO/WebM; codecs=opus` хоч раз) двійник отримав саме цей код, а `mime` — рядок заголовка
  без змін (`AUDIO/WebM; codecs=opus`, не нормалізований); заголовок чи параметр запиту з іншою мовою нічого не змінює. Без мови → 409 фрагмент
  S1, двійник не викликано.
- **Seam 3: чужа тема.** `POST /topics/<чужий uid>/<topic>/voice` → 404 «Тему не знайдено.», двійник не
  викликано — навіть для власника (власник читає, але не пише в чужі теми).
- **Seam 4: повтор і відмова.** Лічильники явні: на 400 `generate_content` викликано рівно раз; на тайм-аут —
  рівно `attempts` разів, фейковий `sleep` — `attempts - 1`; наявні тести повторів `platform.llm` після переносу
  `_retryable` у `_retry.py` лишаються без змін і зелені. Фейковий `client`: 429 → потім текст → повертає текст, 2 спроби, один рядок
  `speech_call` з `attempts=2`; 400 (не повторюється) → `SpeechUnavailable` одразу; тайм-аут `attempts` разів →
  `SpeechUnavailable`. Через маршрут `SpeechUnavailable` → 502 фрагмент, у журналі немає тексту й байтів запису.
- **Seam 5: запис не губиться на відмові (JS, `node --test`).** Фейковий `Recorder` поводиться як браузер (W3C):
  `stop()` одразу ставить `state = "inactive"`, а `dataavailable` і тоді `stop` віддає ПІСЛЯ повернення з `stop()`
  (мікрозадачею чи `setTimeout`), не всередині; це відкидає
  реалізацію, що збирає `Blob` у самому `stop()` (вона надіслала б порожній запис). Фейкові `media`/`fetch`: перша спроба
  502 → `showError` з текстом фрагмента, `offerRecognize`, `recognize()` ще раз надсилає **той самий** `Blob` →
  200 → `insertText`; поле з «Привіт» + текст «світ» → «Привіт світ». Таблиця відповідей для I4 (400, 409, 502,
  мережева помилка, 200 зі сторінкою HTML замість JSON, 200 з порожнім `text`, у різному порядку й кілька разів
  поспіль) — після кожної інтерфейс не стоїть на «Розпізнаю…», пропонує «Розпізнати ще раз», а наступний
  `recognize()` надсилає той самий `Blob`; лише 200 з непорожнім текстом його забуває. Кілька початкових значень
  поля для I5 (порожнє, «Привіт», «Привіт », «рядок\n»). Поки `fetch` не відповів, `#mic` і `#recognize` вимкнені
  (`ui.recognizing()` вимикає, будь-який результат вмикає); після відмови `start()` → новий запис → `recognize()`
  надсилає новий `Blob`, не старий. Таймер `limitMs` зупиняє запис сам; таймер спрацював, а
  тоді натиснуто кнопку — рівно один `recorder.stop()` і один POST.
- **Seam 6: виклик моделі не тримає цикл подій.** Тест маршруту: двійник `speech` усередині `transcribe` записує
  `threading.current_thread()` і перевіряє, що `asyncio.get_running_loop()` у цьому потоці кидає `RuntimeError`
  (тобто він не в потоці циклу подій). Відкидає `async def voice(...)`, що кличе `workspace.transcribe` прямо, без
  `run_in_threadpool` — такий маршрут проходить усі інші перевірки, бо ті шлють по одному запиту.
- **Seam 7: 400 для `/voice`.** Порожнє тіло і `Content-Type: text/plain` → 400 з рівно фрагментом «Запис не
  прийнято — спробуйте записати ще раз.» (не загальне «Запит не прийнято.»), двійник не викликано.
- **Seam 8: помилка побудови запиту.** Фейковий `types`/`client`, що кидає під час побудови `Part` чи конфігурації
  → `SpeechUnavailable`, через маршрут — 502, не 400.
- **Seam 9: справжній браузер.** Smoke у Chromium (Playwright) з `--use-fake-device-for-media-stream`: після
  «стоп» у полі з'являється текст двійника, а запит `POST …/voice`, який бачить Playwright (`page.on("request")`),
  має заголовок `Content-Type`, що починається з `audio/webm`, і непорожнє тіло.

- **Seam 10: збирання в продукті.** Контрактний тест: `make_speech(load_settings({THINKHOW_LOCAL: "true", …}))` —
  `ScriptedSpeech` з `LOCAL_TEXT`; поза локальним режимом (з `genai.Client`, підміненим у тесті) — `GeminiSpeech` з
  `model == settings.speech_model == "gemini-3.5-transcribe"`, тайм-аутом `speech_timeout_s`, регіоном
  `settings.location == "eu"`; `build_deps` поза локальним режимом кладе в `Deps.speech` саме `GeminiSpeech`. Live-тест
  будує розпізнавання так само — через `make_speech(load_settings(...))`, як `tests/contract/skel_learning/
  test_skell_live.py` будує модель. Відкидає `make_speech`, що передає `settings.model` (модель фасилітатора) чи
  `llm_timeout_s`, і `build_deps`, що лишає `ScriptedSpeech` поза локальним режимом (Q6).

## Invariants (rules that hold for every input in the stated domain)
- **I1** — `transcribe` ніколи не кличе модель мовою, якої людина не обрала: код у виклику `speech.transcribe`
  завжди дорівнює коду з її `profile.json`.
  - Domain: будь-яка людина з будь-яким із 85 кодів у профілі, своя наявна тема; будь-який `Content-Type`, що
    проходить перевірку (`audio/…`, з параметрами чи без, у будь-якому регістрі), і будь-які непорожні байти.
  - Source: слова власника в задачі 106 («speech-to-text налаштовується на ту мову»); feature AC2; «Seam», `transcribe`.
  - Broken by: реалізація, що бере мову з запиту, з `Accept-Language` або вмикає автовизначення.
- **I2** — `GeminiSpeech.transcribe` передає моделі рівно ті байти й той `mime`, що отримав.
  - Domain: будь-які непорожні байти; будь-який рядок `mime` (з параметрами `;codecs=…` і без).
  - Source: «Seam», `GeminiSpeech`; PR-11 (модель приймає тип браузера як є).
  - Broken by: перекодування, обрізання параметрів типу, підміна на `audio/wav`.
- **I3** — журнал `speech_call` не містить ні байтів запису, ні розпізнаного тексту.
  - Domain: кожен виклик `GeminiSpeech.transcribe`, з будь-яким результатом (`ok`, `unavailable`).
  - Source: feature, Build parameters («ні звуку, ні тексту в журналах»); M3 A4.
  - Broken by: рядок журналу з полем `text` чи довжиною+початком тексту «для налагодження». Тест дивиться всі рядки
    журналу запиту (і `http_request`), для `ok` і `unavailable`: немає ні розпізнаного рядка (у тесті — помітний
    маркер, напр. «MARKER-TEXT-7f3a»), ні помітного шматка байтів запису (маркер у байтах).

- **I4** — запис лишається, доки не з'явився текст: «останній запис» забувається лише після відповіді 200 з
  непорожнім `text`; після будь-якої іншої відповіді `recognize()` надсилає той самий `Blob`.
  - Domain: будь-яка послідовність відповідей на `recognize()` — 400, 409, 502, мережева помилка, 200 з не-JSON,
    200 з порожнім `text` — у будь-якому порядку й будь-якої довжини, перед необов'язковою 200 з текстом.
  - Source: feature AC2 («Запис лишається на сторінці, доки не з'явився текст»); «Seam», `recognize()`.
  - Broken by: забути запис у `finally`, на будь-якій відмові, крім 502, або на порожньому тексті; виняток з
    `res.json()` на не-JSON, що лишає інтерфейс на «Розпізнаю…».
- **I5** — розпізнаний текст лише дописується: вміст поля до `insertText` — початок вмісту після нього.
  - Domain: будь-який вміст поля (порожній, без пробілу в кінці, з пробілом чи переводом рядка в кінці) і будь-який
    непорожній текст.
  - Source: Q7; feature AC2 («людина править і надсилає»).
  - Broken by: `field.value = text`; обрізання наявного вмісту перед дописуванням.

## Exit criterion
- Контрактні тести (I1–I5, Seams 1–8 і 10; Seam 9 — smoke) зелені: `uv run pytest`; `uv run ruff check .`; `uv run mypy`;
  `PYTHONPATH=src uv run lint-imports`; JS — `node --test` через наявний `tests/contract/skel_web/test_skelweb_js.py`
  або новий такий самий.
- Live: `uv run pytest -m live tests/live/test_speech_live.py` — розпізнавання, зібране `make_speech(load_settings(...))`
  поза локальним режимом (Seam 10), на Vertex `eu` з `uk-UA`
  розпізнає `tests/fixtures/voice/uk-short.webm` (записаний справжнім Chromium, spike) і `uk-short.m4a` (AAC):
  текст містить «нову роботу», «зарплата» і «друзів»; час кожного виклику друкується (у ADR). Окремий live-тест
  кодів: (1) контроль — той самий виклик з `xx-XX` мусить дати `SpeechUnavailable` (Vertex відповідає 400
  INVALID_ARGUMENT — `probe_codes_output.txt`, 2026-10-23), інакше тест червоний; (2) кожен з 85 кодів `LANGUAGES`
  — лише звіт: відкинуті коди друкуються й записуються в ADR, кожен стає пропозицією `proposed/` (прибрати мову
  з переліку — рішення власника, бо людина її бачить); slice готовий, коли тест пройшов контроль і список
  записано. Перевірка 85 кодів — під окремою позначкою `live_codes` (85 платних викликів), щоб перевірку фрази
  можна було повторювати дешево.
- Звіт задачі 106 веде власника до пункту «голос» у `docs/deploy.md` (і Safari/iPhone з розділу «Deferred»): що
  сказати, що має з'явитися в полі; відмова довгого запису з iPhone лишає запис на сторінці (I4).
- Smoke `scripts/smoke_test_voice_dictation.py` (`uv run python …`): uvicorn у локальному режимі в тимчасовій теці +
  Chromium (Playwright, `--use-fake-ui-for-media-stream`, `--use-fake-device-for-media-stream`): `/` (перший вхід
  переадресовує) → `/language` →
  `uk-UA` → нова тема → «🎤 Говорити» → 2 с → стоп → у полі «(локальний режим) розпізнаний текст» → «Надіслати» →
  з'являється відповідь фасилітатора (локальна) і сторінка перезавантажується з реплікою; запит `…/voice` мав
  `Content-Type`, що починається з `audio/webm`. Вивід — `.engine/artifacts/spikes/voice-dictation-smoke-<дата>.txt`.
- ADR `docs/adr/0005-speech-gemini-transcribe.md` із виміряним часом до тексту (spike + live-тест); поправки M2 S8,
  M3 A2/A6 і діаграми в `architecture-map.md`, рядка F13 в `INDEX.md`; пункт чекліста «голос» у `docs/deploy.md`;
  `docs/deploy-sonko.md` — без змін (у ньому немає кроків про Speech-to-Text; звіт це каже).

## Deferred to later slices
- Межа розміру тіла `voice` (хто додасть — тексти 400/413 узгодити з Seam 7) — why later: P5; рекордер обмежує 14.5 хв × 64 кбіт/с ≈ 7 МБ, Cloud Run — 32 МіБ —
  revisit trigger: `speech_call` з `bytes` понад ~7 МБ (стеля рекордера) або власник бачить 413.
- Мова відповіді фасилітатора — S3 `voice-reply-language` — why later: окремий шов `facilitation` — revisit
  trigger: контракт S3.
- Safari/iOS у справжньому браузері — why later: на сервері немає WebKit; модель приймає AAC (spike) — revisit
  trigger: перевірка власника на телефоні після розгортання (звіт задачі 106); Safari може не зважати на
  `audioBitsPerSecond` (~128 кбіт/с × 14.5 хв ≈ 14 МБ, у запиті Vertex base64 ≈ 18.6 МБ — не виміряно) — відмова
  довгого запису з iPhone; видно в журналі: `speech_call outcome=unavailable` з `mime` `audio/mp4…` і `bytes` понад
  ~10 МБ.
- Chirp 3 як друга реалізація — feature, Deferred.

## Open items requiring human decision (if any)
- Немає блокуючих.

## Critic notes (non-blocking)
- Phase 3 пройшла чотири раунди critic-а, і кожен знайшов інший, новий пробіл (Seam 7 — потік подій; I4/I5;
  перекриття запитів → Q13; збирання в продукті → Seam 10); позицій, що чергуються, не було, тож це не коливання.
  Виправлення четвертого раунду внесено без п'ятого раунду фази; весь контракт перевіряє свіжий cold reader.
- (за раундами)
