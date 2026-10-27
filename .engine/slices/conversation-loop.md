# Slice conversation-loop — planning artifact

Feature: `.engine/architecture/feature/voice-conversation-mode.md`, S2a (tracer bullet part 2, with S1
`voice-synthesis`; block voice). Driven mode, unattended: frame supplied by the feature artifact, not asked. Depends
on S1 (`POST /speak`, `data-voice` on `#reply-form`).

## Goal
Людина одним дотиком вмикає на сторінці своєї теми режим розмови, і далі цикл іде сам: сторінка слухає, чує початок
і кінець репліки (детектор тиші), розпізнає репліку тим самим `/voice`, надсилає її як репліку (`/reply` з
`spoken=1`), показує відповідь у `#live`, поки вона йде, озвучує її речення за реченням (`/speak`) і, коли голос
замовк, знову слухає. Другий дотик вимикає режим. Вимірна ціль: тести зелені; smoke у справжньому Chromium (локальний
режим, підроблений мікрофон, що говорить, коли сторінка слухає) — після одного дотику 3 цикли «репліка → текст →
відповідь → голос → знову слухаю» без дотику; на сторінці є позначки часу `talk:speech-end` і `talk:voice-start`.

## Premise verified
- S1 зібраний і пройшов аудит (overseer PASS 20261027T092954Z-d8ebb3): `POST /speak` (форма `text`) → 200
  `audio/mpeg`; 409/400/502 — фрагменти `<p class="error">`; `#reply-form[data-voice]`.
- `/voice` (сирі байти запису, `Content-Type` запису) → 200 `{"text"}` (F13, `scripts/smoke_test_voice_dictation.py`);
  `/reply` — SSE `saved`, `delta`, `answered`, `failed` (`server.py`); невідоме поле форми `spoken` FastAPI ігнорує
  (feature critic, перевірка 1).
- Chromium 1208 (Playwright 1.64, кеш цього сервера; `scripts/smoke_test_voice_dictation.py`) має `AudioContext`,
  `AnalyserNode`, `MediaRecorder` (`audio/webm;codecs=opus`), `decodeAudioData` MP3, `performance.mark(name,
  {startTime})` — стандартні Web API, які вже використовують smoke задач 106 і 206 (`MediaRecorder`) — решта
  перевіряється tracer-ом (PR-25).
- Тиша MP3 двійника (`src/thinkhow/platform/silence.mp3`, 4224 Б, 1 с) — справжній MP3 від Cloud TTS (проба
  `silence.out`); що `decodeAudioData` Chromium його приймає — PR-25, перевіряє smoke.
- Телефони (PR-24) — поза цим slice: десктопний Chromium доводить лише склеювання циклу (PR-25).

## Out of scope (deliberately)
- Правила помилок режиму (сигнал і знову слухати, автоматичний retry, пропуск речення), прибирання рядка «Джерела:»
  з голосу, Screen Wake Lock, повторне відкриття мікрофона, `resume()` контексту, «Торкніться, щоб продовжити» —
  S2b. У S2a будь-яка помилка циклу вимикає режим і показує помилку в `#error`.
- Що модель пише «для вуха» — S3 (S2a лише шле `spoken=1`).
- Перебивання голосу голосом, фон і вимкнений екран — feature, Out of scope.
- Звичайний режим: «Говорити», «Надіслати» під час запису (задача 206), перезавантаження після відповіді — не
  змінюються.

## Seam (contract)
Усе — у `src/thinkhow/web/static/conversation.js` (без бібліотек; текст на сторінку — лише `textContent`); експорт
для `node --test` через `ThinkHow`:

- `createSilenceDetector({ startLevel = 0.02, startMs = 150, silenceMs = 1600, calibrateMs = 300, maxMs = 870000 })`
  → `{ push(level, t), reset() }`. `level` — RMS кадру (0…1), `t` — мс (`performance.now()`). Повертає `null` або
  подію:
  - калібрування: кадри перших `calibrateMs` після створення чи `reset()` (від `t` першого кадру) не дають подій;
    рівень шуму після калібрування — найменший з їхніх `level` (мінімум, не середнє: людина, яка відповідає
    одразу, як голос замовк, не піднімає порогу своєю мовою);
  - поріг — `max(startLevel, 3 × рівень шуму)`; рівень шуму далі оновлюється ковзним середнім (`0.95·старе +
    0.05·level`) лише на кадрах нижче порогу і лише поки мови немає (кадри-кандидати ≥ порогу, коротші за `startMs`,
    і кадри мови його не змінюють);
  - `{ type: "speech-start" }` — коли `level >= поріг` без перерви щонайменше `startMs`;
  - `{ type: "speech-end", at }` — після `speech-start`, коли `level < поріг` без перерви щонайменше `silenceMs`;
    `at` — `t` останнього кадру з мовою (не мить спрацювання); також `speech-end` з `at` = `t`, коли від
  першого кадру після `reset()` (початку `listening`) минуло `maxMs` (14.5 хв — межа запису диктування), щоб безперервний звук не тримав `hearing` вічно.
  Після `speech-end` детектор знову чекає `speech-start`. `reset()` — забути все, зокрема рівень шуму (нове
  калібрування на початку кожного `listening`: шум машини міг змінитися).
- `splitSentences(text, final)` → `{ sentences: string[], rest: string }`. Речення закінчується на `.`, `!`, `?`,
  `…` або `\n`, за якими йде пробіл чи `\n` (або кінець тексту, коли `final`); порожні (з самих пробілів) відкидаються,
  краї обрізаються. Речення понад 1000 байт UTF-8 ріжеться на шматки до 1000 байт — по останній коми, а без неї — по
  останньому пробілу перед межею, а без пробілу — по межі символу. `final` — усе, що лишилося, теж іде (так само
  ріжеться); `rest` — `""`. Без `final` незакінчений хвіст іде в `rest`.
- `createTalk({ media, AudioContext, Recorder, fetch, controller, ui, voiceUrl, speakUrl, setInterval,
  clearInterval, now, mark })` → `{ start(), stop(), state() }`:
  - `start()` (лише в обробнику дотику) — `new AudioContext()` і `resume()`; `media.getUserMedia({ audio: {
    echoCancellation: true, noiseSuppression: true } })` (потік — на весь режим); `MediaStreamSource → AnalyserNode`
    (`fftSize` 1024); кожні 50 мс — RMS часової форми з аналізатора → детектор; стан `listening`, новий
    `MediaRecorder` (тип — перший підтримуваний з `["audio/webm;codecs=opus", "audio/mp4"]`, 64 кбіт/с, як у
    диктуванні) пише з початку `listening`. Відмова мікрофона → `ui.error("Немає доступу до мікрофона.")`, стан
    `off`.
  - `speech-start` у стані `listening` → стан `hearing`. `speech-end` у стані `hearing` → `mark("talk:speech-end",
    at)`, рекордер зупиняється, стан `thinking`, запис іде на `voiceUrl` (як у диктуванні: тіло — Blob,
    `Content-Type` — його тип) → `{text}`; порожній текст → знову `listening` (новий рекордер, детектор `reset`);
    інакше `ui.userTurn(text)` і `controller.send(text, { spoken: "1" })`.
  - Події детектора в станах `thinking` і `speaking` нічого не роблять (половинний дуплекс); рекордер у цих станах
    не пише.
  - Відповідь: дельти (через `ui` контролера, див. `attach`) показуються в `#live` — кожна відповідь у новому
    `<p class="turn model">` після `<p class="turn user">` її репліки; текст для голосу — `хвіст + дельта`, де хвіст —
    `rest` попереднього виклику: `splitSentences(хвіст + дельта, false)`, його `sentences` — у чергу голосу, `rest` —
    новий хвіст (уже поставлені в чергу речення вдруге не ставляться); `answered` → `splitSentences(хвіст, true)` у
    чергу і позначка «відповідь уся». Черга грається по одному реченню: `POST speakUrl` (форма `text`) →
    `arrayBuffer` → `decodeAudioData` → `BufferSource` → `start()`; перше речення відповіді → стан `speaking` і
    `mark("talk:voice-start", now())` у мить `start()`; `ended` → наступне речення. Черга порожня і «відповідь уся»
    → знову `listening` (новий рекордер, детектор `reset`).
  - Будь-яка помилка (`/voice` або `/speak` не 200, мережа, `failed` у потоці відповіді, `decodeAudioData` не вдався)
    → `ui.error(<текст фрагмента або «Режим розмови зупинено — спробуйте ще раз.»>)` і `stop()` без перезавантаження.
  - `stop()` — зупиняє інтервал, рекордер, доріжки потоку, джерело звуку, закриває контекст; стан `off`;
    `ui.reload()` лише коли вимкнула людина (дотик), щоб сторінка стала звичайною зі збереженою розмовою.
  - Стан видно на кнопці: `ui.state(name)` ставить `#talk[data-state]` = `listening` | `hearing` | `thinking` |
    `speaking` | `""` (off) і `aria-pressed`.
- `ui` режиму для контролера має всі гачки, які кличе `run()`: `disable`, `enable` (нічого не роблять — кнопки й так
  вимкнені режимом), `appendDelta`, `reload`, `showRetry`, `showError`, `setDraft`.
- `createController(...)`: `send(text, fields = {})` — тіло `new URLSearchParams({ text, ...fields })`; решта без
  змін (звичайне «Надіслати» шле як досі, без полів).
- `attach(doc, win)`: якщо `#reply-form[data-voice="yes"]`, є `win.AudioContext` і `navigator.mediaDevices` —
  показує кнопку `#talk` (у шаблоні вона `hidden`); дотик — `talk.start()` / `talk.stop()` (з `reload`). Поки режим
  увімкнено, контролер отримує `ui` режиму: `appendDelta` → показ і черга голосу, `reload` (на `answered`) → «відповідь
  уся» (сторінка не перезавантажується), `showRetry`/`showError` → помилка режиму. Поза режимом — `ui` як досі.
  `#mic`, `#send`, поле — `disabled`, поки режим увімкнено.
- `mark(name, t)` на сторінці — `performance.mark(name, { startTime: t })`; `now` — `performance.now()`.

`src/thinkhow/web/templates/topic.html`: `<button id="talk" class="icon" type="button" aria-label="Режим розмови"
aria-pressed="false" hidden>{{ icon("talk") }}<span class="spinner" aria-hidden="true"></span></button>` у
`.actions` перед `#mic`. `icons.html`: значок `talk` (навушники). `style.css`: `#talk[data-state]` — `listening`
(пульсує кільце), `hearing` (заповнена), `thinking` (спінер), `speaking` (хвиля/заповнена іншим кольором).

- Errors: усе в межах сторінки — `ui.error`, `stop()`.
- Dependencies (injected): `media`, `AudioContext`, `Recorder`, `fetch`, `controller`, `ui`, таймери, `now`, `mark`.
- Does NOT do: правил повтору й пропуску, сигналів, Wake Lock (S2b); зміни сервера; зберігання звуку.

## Decisions (with WHY)
- Q1: детектор тиші — енергія (RMS) з адаптивним порогом, у браузері. Чому: P5 (без моделей і бібліотек), шум машини
  — рівний фон, який ковзне середнє бере в поріг. Rejected: VAD-модель у браузері (Silero через ONNX) — бібліотека й
  мегабайти; кінець репліки моделлю на сервері (Live API) — постійне з'єднання (feature, Out of scope); Web Speech API
  — не ЄС (S8).
- Q2: 1.6 с тиші — константа фічі (Build parameters). `startMs` 150 мс — щоб клацання і поштовх не ставали реплікою;
  `startLevel` 0.02 — нижня межа порогу в тиші кімнати. Технічні константи, ціна розвороту — один рядок.
- Q3: потік мікрофона один на весь режим, рекордер — новий на кожну репліку. Чому: повторний `getUserMedia` на
  телефоні — ще один дозвіл і перемикання аудіосесії (`browsers.md`, п. 1, 3); новий рекордер дає окремий цілий файл
  для `/voice`. Rejected: один рекордер з `timeslice` — шматки webm без заголовка не є окремим файлом.
- Q4: відповідь — той самий `createController` з іншим `ui`. Чому: одна логіка SSE і чернетки; різниця лише в тому,
  що робиться з дельтами й кінцем. Rejected: окремий клієнт SSE для режиму — дублювання парсера й помилок.
- Q5: речення — до 1000 байт. Чому: Gemini-TTS на ~3900 байтах дає 502, межа сервера 4000 (S1); коротке речення —
  раніше перший звук. Rejected: усю відповідь одним запитом — довго до першого звуку і понад межу.
- Q6: озвучення через той самий `AudioContext`, створений у дотику. Чому: на iOS контекст, розблокований дотиком,
  грає далі без дотику (`browsers.md`, п. 2); `<audio>` вимагав би розблокування елемента. Rejected: `HTMLAudioElement`
  — на iOS потребує жесту на кожен новий `src` у частині версій.
- Q7: помилка в S2a вимикає режим. Чому: найтонший tracer; правила стійкості — S2b на тих самих станах.
- Q8: позначки часу — `performance.mark` зі `startTime`. Чому: live-скрипт читає їх з `performance.getEntriesByType
  ("mark")` без зміни сторінки; `talk:speech-end` — на останньому кадрі з мовою (feature critic, round 2, note 1).

## Hardest seams (test-confidence points — distinct from the contract Seam above)
- **Seam 1: детектор на рівнях у часі.** Тест подає послідовності `(level, t)`: тиша → мова 200 мс → тиша 1600 мс →
  `speech-end` з `at` = час останнього кадру мови; мова 100 мс (клацання) → жодної події; рівний шум 0.05 від
  першого кадру після `reset()` (машина), потім мова 0.3 → калібрування взяло шум, `speech-start` лише на мові, після
  неї — `speech-end`; мова 0.3 з 200 мс після `reset()` (усередині калібрування; шум до неї 0.01) → `speech-start`;
  пауза 1000 мс посеред мови → не кінець; звук без перерви довше `maxMs` → `speech-end`.
  Відкидає «кінець на першому тихому кадрі», `at` = мить спрацювання і рівень шуму, що стартує з 0 (рівний шум
  машини ставав би мовою, а `speech-end` не приходив би).
- **Seam 2: нарізка.** Межі речень, «…», кінець без розділового знака при `final`, речення 2500 байт кирилиці →
  шматки ≤ 1000 байт по комах/пробілах, з'єднані назад дають текст (I3). Відкидає `length` замість байтів.
- **Seam 3: цикл з підробками.** Фальшиві `AudioContext` (аналізатор віддає задані рівні), `Recorder`, `fetch`
  (`/voice` → `{text}`, `/reply` → SSE з дельтами, `/speak` → байти), таймери: дотик → `listening` → рівні мови й
  тиші → `POST /voice` → `POST /reply` з `spoken=1` → `delta`×N → `POST /speak` по реченнях у порядку тексту, одне
  за раз (наступний `/speak` — лише після `ended` попереднього) → `answered` → після останнього `ended` знову
  `listening`, новий рекордер. Друга репліка — те саме без жодного виклику `start()`.
- **Seam 4: половинний дуплекс.** Рівні мови під час `thinking` і `speaking` не дають ні `hearing`, ні запису, ні
  `/voice` (I1).
- **Seam 5: звичайний режим не зачеплено.** Наявні тести `send_stops_recording.test.mjs` зелені без змін; без дотику
  на `#talk` «Надіслати» шле тіло лише з `text`; `answered` перезавантажує сторінку.
- **Seam 6: справжній браузер.** Smoke у Chromium (нижче) — єдина перевірка, що `decodeAudioData` бере MP3 двійника,
  `AnalyserNode` дає рівні від підробленого мікрофона і цикл іде без дотику (PR-25).

## Invariants (rules that hold for every input in the stated domain)
- **I1** — Поки стан режиму `thinking` або `speaking`, жоден рівень з мікрофона не починає запису і не надсилає
  `/voice`.
  - Domain: будь-яка послідовність рівнів (зокрема гучна мова) в цих станах.
  - Source: feature, Build parameters P5 «половинний дуплекс (сторінка не слухає, поки говорить)».
  - Broken by: детектор, що працює й під час голосу (власний голос сторінки чи шум машини стають реплікою).
- **I2** — Жоден запит `/speak` не несе тексту понад 1000 байт UTF-8.
  - Domain: будь-який текст відповіді, зокрема без розділових знаків і з багатобайтовими літерами.
  - Source: feature, Build parameters («клієнт ріже відповідь на речення і шматки до 1000 байт»).
  - Broken by: нарізка за `length` або лише за розділовими знаками.
- **I3** — Шматки нарізки, з'єднані пробілом, дають той самий текст, що й вхід, з точністю до пробілів: жодного слова
  не загублено і не додано, порядок той самий.
  - Domain: будь-який текст і будь-яке розбиття його на дельти (`splitSentences` по накопиченому, потім `final`).
  - Source: feature, AC1 і AC3 (людина чує відповідь — усю).
  - Broken by: загублений хвіст після останнього розділового знака, подвоєне речення між двома викликами.

Локальні двійники, на яких іде smoke: `/voice` — `ScriptedSpeech` повертає непорожній текст «(локальний режим)
розпізнаний текст» на будь-який запис; `/reply` — сценарна модель; `/speak` — `ScriptedTts` (1 с тиші MP3).

## Exit criterion
- `uv run pytest -q` зелений: нові тести slice (`node --test` через pytest, як `tests/web/test_send_stops_recording.py`)
  і всі наявні; `uv run ruff check scripts tests src`, `uv run mypy` — чисто.
- Smoke: `uv run --with playwright==1.64.1 python scripts/smoke_test_conversation_mode.py` — справжній uvicorn у
  локальному режимі, Chromium 1208; сторінці підкладено `getUserMedia`, що повертає потік з власного `AudioContext`
  і грає записану репліку людини (`tests/fixtures/voice/`), щойно `#talk[data-state]` стає `listening`. Після одного
  `click` на `#talk`: 3 цикли (`listening` → `hearing` → `thinking` → `speaking` → `listening`), у `#live` — 3
  репліки людини і 3 відповіді, на сервер пішли 3 `/voice`, 3 `/reply` (з `spoken=1`), ≥ 3 `/speak`; на сторінці по 3
  позначки `talk:speech-end` і `talk:voice-start`, кожна `voice-start` пізніше своєї `speech-end`. Вивід — у
  `.engine/artifacts/conversation-loop/smoke.txt`. Порогів немає.

## Deferred to later slices
- Правила помилок, сигнали, прибирання «Джерела:», Wake Lock, захисти iOS — S2b — revisit trigger: S2b наступний у DAG.
- Live на справжніх моделях (≥ 5 реплік ×2 мови, затримка) — після S2b і S3 (feature, Integration exit criterion) —
  revisit trigger: S3 закрито.

## Open items requiring human decision (if any)
- (немає)

## Critic notes (non-blocking)
- Cold reader 2 — PASS; внесено його примітки: калібрування за мінімумом, `maxMs` від початку `listening`. Стан
  «вимкнено» на кнопці — `data-state=""` (у feature — `off`; це те саме значення). Smoke не перезапускає запис
  репліки, поки попередній ще грає, і бере коротку репліку.
- Детектор не має окремого інваріанта (стан і порядок подій) — його поведінку закривають випадки Seam 1.
- Раунд 1 і cold reader — REVISE: стартове значення рівня шуму не задане (проби обох: з 0 рівний шум 0.05 давав
  `speech-start` за 150 мс і вічний `hearing`); виправлено калібруванням `calibrateMs` після кожного `reset()` і
  оновленням лише на тихих кадрах; додано `maxMs` (14.5 хв), гачки `ui` режиму, нарізку `хвіст + дельта`, новий `<p>`
  на кожну відповідь, локальні двійники smoke.
