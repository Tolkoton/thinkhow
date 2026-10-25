# Slice research-display — planning artifact

Feature: `.engine/architecture/feature/research-in-conversation.md`, S1b (block quick). Driven mode, unattended: frame
supplied by the feature artifact, not asked. Depends on S1 `research-quick` (DONE: `Found`, `ResearchEvent`,
`research.json`, `sources_line`).

## Goal
Людина бачить джерела відповіді як справжні адреси сторінок і клікає їх, а під відповіддю з пошуком — Search
suggestions Google такими, як прийшли (умова Google WGE). Посилання-перенаправлення Google
(`vertexaisearch.cloud.google.com/grounding-api-redirect/…`) розгортаються в адресу сторінки ще до того, як рядок
джерел піде в потік, тож у `conversation.md` і `research.json` лежать адреси, що не залежать від того, скільки живе
посилання Google (feature: G2 — знайдене пам'ятається; AC4). Вимірна ціль: pytest зелений (запечатані тести — без
змін); live: репліка з пошуком на `eu` → у рядку джерел і в `research.json` немає `grounding-api-redirect`, якщо Google
відповів перенаправленням; сторінка теми показує `<a href>` на ці адреси і `<iframe>` з suggestions під відповіддю.

## Premise verified
- Посилання-перенаправлення Google на HEAD без переходу відповідає 302 з `Location` = адреса сторінки:
  `.engine/artifacts/spikes/research-design-2026-10-25/entry.out` (2026-10-25, свіжа; 6 з 6 посилань — 302 на
  meinauto.de, carwow.de…), скрипт `entry.py`.
- `search_entry_point.rendered_content` — самодостатній HTML (~4.5–5 КБ: `<style>` і «чипи»-посилання на пошук
  Google) — там само; live S1 (`research-quick-live-2026-10-25T084129Z.txt`: 4 741 і 4 526 символів).
- Search suggestions — два-кілька `<a class="chip" href="https://vertexaisearch.cloud.google.com/grounding-api-redirect/…">`
  **без `target`**, без `<base>`, без `<script>` і обробників подій: проба
  `.engine/artifacts/spikes/research-display-probe-2026-10-25/probe.out` (2026-10-25; повний HTML — 5 054 символи, 2
  посилання). Тож у `iframe` з `sandbox` клік відкрив би посилання в самому кадрі; потрібен `<base target="_blank">`.
- `httpx` 0.28.1 уже встановлений (залежність `google-genai`), але не оголошений у `pyproject.toml`.
- Сторінка теми рендерить текст репліки як `{{ t.text }}` у `<p class="text">` з автоекрануванням Jinja
  (`web/templates/topic.html`); після події `answered` сторінка перезавантажується (`conversation.js` `ui.reload()`),
  тож показ після відповіді — серверний.
- S1 не розгорнуто (feature: «S1 не розгортається до S1b»), тож рядків джерел з посиланнями Google на сервері немає;
  локальні теми розробника їх можуть мати.

## Out of scope (deliberately)
- Розгортання старих рядків джерел у `conversation.md` (вхід із S1): на сервері їх немає — S1 не розгорнуто; локальні
  — не варті міграції (P5). Старе посилання Google на сторінці лишається клікабельним, як і будь-яке інше.
- Живий показ suggestions під час потоку (окрема подія SSE) — після `answered` сторінка перезавантажується.
- Markdown у тексті реплік, крім посилань (жирний, списки) — лише посилання `[назва](https://…)`.
- Дія «answer», глибоке дослідження — S2, S3.
- Прив'язка речень до джерел (`grounding_supports`) — feature Deferred.

## Seam (contract)
`src/thinkhow/platform/links.py` (новий; лише `platform` знає про Google, A3.2):
- `def resolve_link(url: str, head: Head, timeout_s: float = 3.0) -> str` — якщо `url` починається з
  `https://vertexaisearch.cloud.google.com/grounding-api-redirect/`: `head(url, timeout_s)` → статус 301, 302, 303, 307
  чи 308 з непорожнім абсолютним `Location` з `http://` чи `https://` → `Location`; будь-що інше (інший статус, немає
  `Location`, будь-який `Exception` — не `BaseException`) → `url` без змін. Інша адреса → `url` без виклику `head`.
- `Head = Callable[[str, float], tuple[int, str | None]]` — статус і `Location`, без переходу.
- `def httpx_head(url: str, timeout_s: float) -> tuple[int, str | None]` — `httpx.head(url, follow_redirects=False,
  timeout=timeout_s)`; повертає `(status_code, headers.get("location"))`.
`links.py` не імпортує `llm.py` (рядки на вході й виході).

`src/thinkhow/platform/llm.py`:
- `def resolve_sources(sources: Sequence[Source], resolve: Callable[[str], str]) -> tuple[Source, ...]` — паралельно
  (`ThreadPoolExecutor`, до 8 потоків) кличе `resolve` для кожного `url`, зберігає порядок і `title`; після
  розгортання — без повторів за новим `url` (перший лишається).
- `VertexLlm.__init__(..., search: bool = False, resolve: Callable[[str], str] | None = None)`; коли `found` не `None` і
  `resolve` не `None` — `found` з `sources = resolve_sources(found.sources, resolve)` **до** `Done` (і до `llm_call`).
  Без `resolve` — як у S1.
- `make_llm(...)` поза локальним режимом передає `resolve=functools.partial(resolve_link, head=httpx_head)` (лише
  коли `search=True`).
- `pyproject.toml`: `httpx` оголошено залежністю (вже встановлений; `uv add httpx`, `uv.lock` у тому ж commit-і).

`src/thinkhow/workspace/model.py`, `topics.py`:
- `@dataclass(frozen=True) class ResearchView: turn: int; suggestions_html: str | None` і
  `TopicView.research: tuple[ResearchView, ...] = ()` (останнім полем, із замовчуванням).
- `open_topic` читає `research.json` (немає — `()`), по одному `ResearchView` на запис, у порядку файлу. Правило
  читання — те саме, що для теми (своя або власник).

`src/thinkhow/web/text.py` (новий):
- `def turn_html(text: str) -> markupsafe.Markup` — у **сирому** тексті знаходить кожне `[назва](адреса)`, де `назва`
  непорожня і не містить `[` `]`, а адреса починається з `https://` чи `http://` і не містить пробілів, `(`, `)`, `"`, `<`, `>`;
  кожне таке стає `<a href="адреса" rel="noopener noreferrer" target="_blank">назва</a>` (назва й адреса —
  екрановані `markupsafe.escape`), увесь інший текст — екранований (`markupsafe.escape`). Переноси рядків лишаються,
  як і досі (CSS `white-space`).
- `web/server.py` реєструє `turn_html` фільтром `TEMPLATES.env.filters["turn_html"]`.

`src/thinkhow/web/templates/topic.html`:
- `<p class="text">{{ t.text | turn_html }}</p>`.
- під репліцею моделі, для якої в `view.research` є запис з її `turn` і непорожнім `suggestions_html`:
  `<iframe class="search-suggestions" sandbox="allow-popups allow-popups-to-escape-sandbox"
  srcdoc="{{ '<base target="_blank">' ~ html }}" title="Пошук Google"></iframe>` — значення `srcdoc` = рядок
  `<base target="_blank">`, за ним HTML Google байт у байт; атрибут екранує Jinja. Кілька записів на один `turn` — по
  одному iframe. Шаблон бере записи з `view.research` (`turn` == номер репліки), окремого словника в контексті немає.
- `web/static/style.css`: `.search-suggestions { width: 100%; border: 0; height: 64px; }`.

- Errors: розгортання не буває помилкою (лишається посилання Google); адреса з `"`, `<`, `>` чи пробілом показується
  текстом, а не посиланням (у `research.json` — як є); `research.json`, що не читається, — виняток як
  і з `routing.json` (не відновлюється).
- Dependencies (injected): `head` у `resolve_link`, `resolve` у `VertexLlm` і `resolve_sources`.
- Does NOT do: старі рядки, живий показ suggestions, Markdown понад посилання, «answer», глибоке.

## Decisions (with WHY)
- Q1: розгортає `platform` у `VertexLlm` до `Done` — chosen because тоді рядок джерел у потоці, `reply`,
  `conversation.md` і `research.json` — одна й та сама справжня адреса (I1 S1 тримається), а `facilitation` про Google
  не знає (A7: «посилання-перенаправлення Google розгортає теж `platform`»). Rejected: розгортати в `workspace` перед
  записом — тоді показане потоком ≠ записане; розгортати в `web` при показі — у файлах лишаються посилання, що
  старіють (G2).
- Q2: HEAD без переходу, `httpx` timeout 3 с (на кожну фазу з'єднання — до ~9 с у найгіршому разі), паралельно, будь-яка невдача → посилання Google — chosen because проба дала 302 з
  `Location` на 6 з 6, а відповідь людині не має чекати чи падати через одне посилання (feature Build parameters).
  Rejected: GET з переходами — довше й завантажує сторінку; без межі часу — одне повільне посилання тримає відповідь.
- Q3: `httpx` — chosen because уже встановлений з `google-genai`, має `follow_redirects=False` і `timeout`; оголошуємо
  явно, бо тепер його імпортує наш код. Rejected: `urllib.request` — переходить за перенаправленнями сам, треба свій
  `HTTPRedirectHandler`; `requests` — нова залежність.
- Q4: suggestions — `iframe srcdoc` з `sandbox` без `allow-scripts` — chosen because їхні `<style>` не зачіпають
  сторінку і навпаки, HTML показано «exactly as provided» (умова WGE), а чипи-посилання відкриваються в новій вкладці
  (`allow-popups`) — для цього перед HTML у `srcdoc` стоїть `<base target="_blank">`: проба показала, що в посилань
  Google `target` немає, і без нього клік вів би сам кадр на google.com, який у кадрі не показується. Вміст HTML
  Google не змінюється (жодного байта всередині); `<base>` лише задає кадру ціль посилань за замовчуванням — це
  показ «exactly as provided». Rejected: `allow-top-navigation-by-user-activation` — клік забирає людину з розмови; вставити HTML у сторінку — стилі Google ламають сторінку, і це чужий HTML у нашому DOM;
  не показувати — умова Google (власник прийняв ризик решти умов, а не цієї; feature Build parameters).
- Q5: посилання в тексті — лише `[назва](http…)` після повного екранування — chosen because рядок джерел пише код
  (S1, `sources_line` прибирає `[ ]` з назв і `( )` з адрес), а екранування до заміни не дає тексту моделі чи людини
  вставити HTML. Rejected: бібліотека Markdown — нова залежність і весь Markdown, якого ніхто не просив (P5).
- Q6: без повторів після розгортання — chosen because два різні посилання Google можуть вести на ту саму сторінку
  (у live S1 — три `skoda-auto.de`), а I3 S1 обіцяє кожну адресу один раз. Rejected: лишити повтори — рядок з трьома
  однаковими адресами.

- Q7: `TopicView.research: tuple[ResearchView, ...]` з власним значенням `ResearchView(turn, suggestions_html)`, а не
  `ResearchEntry` файлу, як у контракті feature-а — chosen because `TopicView` — значення `workspace/model.py`, а
  `ResearchEntry` — модель файлу в `topics.py` (як `RoutingFile` лишається всередині); сторінці потрібні лише `turn` і
  HTML. Rejected: `ResearchEntry` назовні — `model.py` імпортував би `topics.py`, і `web` залежав би від формату файлу.
  Відхилення від контракту feature-а — у назві типу, не у змісті (S4 читає `research.json` прямо).
- Q8: висота кадру — 64 px — chosen because чипи Google стоять в один рядок з горизонтальною прокруткою (`<style>`
  HTML Google, проба); без скриптів кадр не підлаштовує висоту сам; live-вивід зберігає HTML, щоб його відкрити й
  подивитись. Rejected: `allow-scripts` для автовисоти — скрипт у кадрі з HTML, якого ми не пишемо.

## Hardest seams (test-confidence points)
- **Seam 1: розгортання до потоку** — тест через фейковий клієнт genai (як `rq_fakes.SearchClient`) і фейковий
  `resolve`: `Done.found.sources` уже з новими адресами, і через `lead` рядок джерел у потоці й `reply` має нові
  адреси, а `resolve` кликано рівно для кожного джерела. Anti-pattern: тест `resolve_link` окремо, без доказу, що
  `VertexLlm` його застосовує до `Done`.
- **Seam 2: невдача розгортання нічого не ламає** — `resolve_link` з фейковим `head`: 302 з `Location` → адреса; 200;
  302 без `Location`; 302 з відносним `Location`; виняток (`httpx.TimeoutException`, `OSError`) → `url`; адреса не
  Google → `head` не кликано. Anti-pattern: лише щасливий 302.
- **Seam 3: паралельно, з порядком** — `resolve_sources` з `resolve`, що для різних адрес чекає різний час (через
  `threading.Event` з `wait(timeout=…)`, щоб послідовна реалізація падала, а не висіла), → порядок джерел той самий; дві адреси, що розгорнулись в одну, → одна. Anti-pattern:
  послідовна реалізація, що випадково зберігає порядок.
- **Seam 4: безпечний показ** — `turn_html`: `<script>` у тексті — екрановано; `[x](javascript:alert(1))` — не
  посилання; `[a](https://e.org/?q="x")` — не посилання (у
  сирій адресі `"`), екрановано; звичайне посилання — `<a href=…>`; `[t](https://a.example/?x=1&y=2)` → рівно
  `href="https://a.example/?x=1&amp;y=2"` (без подвійного екранування). Сторінка теми через
  `TestClient` (локально, тема з `research.json` і рядком джерел) → `<a href="https://…">` і `<iframe … srcdoc=`, чиє значення (після розекранування атрибута) =
  `<base target="_blank">` + HTML Google байт у байт, **після** `<article id="t{turn}"` і до наступної репліки; чужа тема — як і досі 404. Anti-pattern: перевіряти фільтр без сторінки.

## Invariants (rules that hold for every input in the stated domain)
- **I1** — `resolve_link` повертає або вхідну адресу, або абсолютну `http(s)` адресу з `Location` перенаправлення
  Google; ніколи не падає.
  - Domain: будь-який рядок `url`, будь-яка відповідь `head` (статус, `Location` чи `None`) і будь-який виняток `head`.
  - Source: цей контракт, Seam — «будь-що інше … → `url` без змін»; feature Build parameters — «не вийшло — лишається
    посилання Google».
  - Broken by: виняток з `head` проходить нагору; відносний `Location` стає адресою; розгортання не-Google адрес.
- **I2** — `resolve_sources` зберігає порядок першої появи і дає кожну розгорнуту адресу рівно один раз, з назвою її
  першого джерела.
  - Domain: будь-яка послідовність `Source` (порожня, з повторами до і після розгортання) і будь-який `resolve`,
    зокрема повільний для окремих адрес.
  - Source: цей контракт, Seam і Q6; S1 I3 — «кожну адресу … рівно один раз, у порядку першої появи».
  - Broken by: порядок завершення потоків замість порядку джерел; повтори після розгортання.
- **I3** — HTML, який `turn_html` повертає, не містить жодного тегу, крім `<a href="http…" rel="noopener noreferrer"
  target="_blank">`, і весь інший текст репліки в ньому — екранований.
  - Domain: будь-який текст репліки (людини чи моделі), зокрема з `<`, `>`, `&`, `"`, `javascript:`, вкладеними
    дужками і незакритими `[`.
  - Source: цей контракт, Q5 — «екранування до заміни не дає тексту … вставити HTML».
  - Broken by: `<a>` вставлено в сирий текст, а решту не екрановано; або екрановано все разом із тегами; `href` з
    `javascript:`; `"` в адресі, що закриває атрибут.

## Exit criterion
- `uv run pytest -q` зелений: нові тести (Seams 1–4, I1–I3) і всі запечатані тести без змін; `ruff check`, `mypy`
  чисті; `tests/test_a3_*` зелені; новий тест (поруч із `test_a3_google_sdk.py`): `httpx` імпортує лише
  `thinkhow.platform`.
- Live (закриває slice): `tests/live/test_research_live.py` доповнено: у запису #17 і в запитанні про ціну —
  жодне джерело в `research.json` і в рядку джерел не починається з `https://vertexaisearch.cloud.google.com/
  grounding-api-redirect/`, хіба Google не відповів перенаправленням: кожне посилання Google, що лишилось, тест сам перевіряє прямим
  `httpx.head(..., follow_redirects=False)` — 3xx з абсолютним `Location` → тест **падає** (розгортання не спрацювало),
  інша відповідь → друкує статус (знахідка, не повтор); `llm_call` (`latency_ms` — увесь виклик, разом з розгортанням) записано у вивід. Тоді сторінка теми цієї локальної
  теки через `TestClient` має `<a href="https://` на ці адреси і `<iframe class="search-suggestions"` під #18 (якщо Google не дав `search_entry_point` — друкується як
  знахідка, не падіння); HTML suggestions зберігається у вивід, щоб його відкрити й подивитись (висота кадру). Вивід —
  у `.engine/artifacts/spikes/research-display-live-<час>.txt`. Порогу часу немає (P4).

## Deferred to later slices
- Розгортання старих рядків джерел — why later: на сервері їх немає (S1 не розгорнуто) — revisit trigger: тема з
  посиланням Google у рядку джерел на сервері.
- Живий показ suggestions до перезавантаження — why later: сторінка перезавантажується одразу після `answered` —
  revisit trigger: власник бачить «стрибок» сторінки як ваду.

- Автовисота кадру suggestions — why later: чипи в один рядок з прокруткою (Q8) — revisit trigger: live-вивід чи
  власник показують обрізані чипи. Ціна потім — один `allow-scripts`-вільний спосіб (більша фіксована висота).

## Open items requiring human decision (if any)
- (немає)

## Critic notes (non-blocking)
- Phase 2, раунд 1 (`CRITIC_PREMISE_PROBE_REQUIRED`) і раунд 2 (`CRITIC_REVISE` на старому тексті — правка не
  застосувалась): проба `research-display-probe-2026-10-25` — `target` немає, скриптів немає → `<base target="_blank">`
  у `srcdoc` (Q4, Seam 4); нотатки: Q7 (`ResearchView`), одне джерело даних для шаблону, `resolve_sources` у `llm.py`,
  сира адреса, Q8 (висота), тест на `httpx` лише в `platform`.
- Phase 2, раунд 3 — `CRITIC_PASS`; нотатки: непорожня назва, адреса з `"` — текстом, `latency_ms` — увесь виклик; 64 px і 8
  потоків — технічні константи, не умови виходу; `<base>` — прочитання «exactly as provided», two-way door.
- Phase 3, раунд 1 — `CRITIC_PASS`; нотатки (`&` в адресі, `wait(timeout)`, `Exception`, формулювання I3, місце кадру) —
  враховано.
- Phases 4–5, раунд 1 — `CRITIC_PASS` обидві; нотатки N4.1 (пряма перевірка залишених посилань), N4.2 (без suggestions —
  знахідка), N5.2 (автовисота в Deferred) — враховано; N4.3 — прогалину вже закрито (commit e958de6, `queries ≥ 1`).
- Cold reader — `CRITIC_PASS`. Нотатки для збирача: порожня назва джерела → текстом (за Errors); `<base>` живе лише в
  документі кадру; номер відповіді в live-тесті брати з `Answered.turn_no`, не писати 18.
