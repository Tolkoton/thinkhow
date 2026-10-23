# Slice minimal-design — planning artifact

Task: `tasks/doing/201-minimal-design.md` (клас 2, соло, без нагляду). Standalone mode, unattended: frame derived
from the task and the code, not asked.

## Goal
Сторінки ThinkHow мають простий охайний вигляд — «хоч мінімальний» дизайн (слова власника, задача 201): читабельна
типографіка, спокійні кольори, світла й темна тема, зручна ширина тексту, помітне поле введення й кнопки, видно,
де репліка людини, а де фасилітатора, видно стан «відповідь іде»; добре на телефоні. Поведінка (SSE, збереження
тексту в полі, IAP) не змінюється.

Вимірна ціль: (1) усі наявні тести зелені без змін у запечатаних файлах; (2) скрипт знімків
`scripts/screenshots_minimal_design.py` проходить свої перевірки (див. Exit criterion) у справжньому Chromium і
лишає знімки «Мої теми» і сторінки теми з розмовою на комп'ютері й на телефоні, у світлій і темній темі, плюс знімок
стану «відповідь іде»; (3) контрактні тести I1–I2 зелені.

## Premise verified
- P1: Playwright 1.64.1 з кешованим Chromium `~/.cache/ms-playwright/chromium-1208` запускається на цій машині
  через `uv run --with playwright==1.64.1` (Playwright — не залежність проєкту) — доказ:
  `.engine/artifacts/spikes/voice-dictation-smoke-2026-10-23-after-s3.txt` (2026-10-23) і спайк нижче.
- P2: цей Chromium (145.0.7632.6) застосовує `@media (prefers-color-scheme: dark)` під емуляцією Playwright
  (`color_scheme="dark"`) — доказ:
  `.engine/artifacts/spikes/minimal-design-has-and-dark-2026-10-23.txt` (2026-10-23).
- P3: Firefox відновлює вимкнений з JS стан `disabled` кнопки після `location.reload()`, якщо в елемента немає
  `autocomplete="off"` (Mozilla bug 654072) — `untested — common knowledge` (Firefox на машині немає). Тому
  `autocomplete="off"` на `#send` і `#retry` (Seam); у Chromium атрибут нічого не змінює (Seam 2 це перевіряє).
- P4: `conversation.js` під час запиту вимикає `#send` (`ui.disable()`) і вмикає його в кожній гілці кінця, а
  `answered` перезавантажує сторінку — прочитано в `src/thinkhow/web/static/conversation.js` (`run`). На цьому
  тримається стан «відповідь іде» без зміни JS.

## Out of scope (deliberately)
- Будь-яка зміна `src/thinkhow/web/static/conversation.js` — поведінка не змінюється (задача), а запечатані тести
  `node --test` читають його вихідний текст і будують фейковий DOM лише з відомих їм id.
- Зміна текстів сторінок, маршрутів, форм (`action`, `method`, `name`), id елементів і фрагмента помилки
  `<p class="error">…</p>` — на них тримаються тести й JS.
- Перемикач теми на сторінці — тема йде за налаштуванням пристрою (Q2).
- Розмітка Markdown у відповідях фасилітатора, іконки, логотип, favicon, мова інтерфейсу.
- CSS-фреймворк чи вебшрифти (задача: «без важких фреймворків»; Q1, Q6).

## Seam (contract)
- Новий файл `src/thinkhow/web/static/style.css` — уся стилізація; віддається наявним `app.mount("/static", …)`
  (`server.py`), нових маршрутів немає.
- `src/thinkhow/web/templates/base.html`: inline `<style>` прибирається; у `<head>` — `<meta name="color-scheme"
  content="light dark">` і `<link rel="stylesheet" href="/static/style.css">`; навігація (посилання `/` «ThinkHow» і
  `/language` «Мова» з тими самими текстами) — у `<header class="site">`, вміст сторінки — у `<main>`.
- `home.html`, `language.html`, `topic.html`: лише додаються класи й обгортки (`class="primary"` на головних кнопках
  «Створити», «Зберегти», «Надіслати»; `<div class="actions">` навколо кнопок форми відповіді — `#send`, `#pending` і `#retry` у ньому сусіди одного батька,
  інакше селектор `~` не спрацює; клас списку тем).
  У `topic.html` всередині `{% if own %}`, у `.actions` форми відповіді одразу після `#send`, додається один статичний
  елемент `<span id="pending" class="pending">Фасилітатор відповідає…</span>`. `#send` і `#retry` отримують
  `autocomplete="off"` — щоб Firefox не повертав після перезавантаження сторінки (`answered`) вимкнений стан кнопок
  (P3): це єдине свідоме виправлення поведінки; очікувано (Mozilla bug 654072, у Firefox не перевірено) воно лагодить і
  кнопку «Надіслати», що в Firefox лишалася б вимкненою після відповіді. Усі наявні id, `name`, `action`, `method`, тексти, порядок форм і `hidden` лишаються як є.
- Стан «відповідь іде» — лише CSS: `#pending` прихований; `#send:disabled ~ #pending` видимий; відповідь,
  що надходить у `#live` (`<p class="turn model">` від `appendDelta`), оформлена як репліка фасилітатора з підписом
  «Фасилітатор» через `#live .turn.model::before` — лише в `#live`, бо збережені репліки вже мають підпис у `.who`;
  порожній `#live` не має видимого блоку.
- `style.css` містить `[hidden] { display: none !important; }`: `#recognize` і `#retry` ховає атрибут `hidden`, який
  перемикає JS, а будь-яке авторське правило з `display` для кнопок перебиває слабке правило браузера `[hidden]` —
  і приховані кнопки з'явилися б завжди.
- Правило, що вже зараз змінює поведінку, переходить у `style.css` без змін: `white-space: pre-wrap` для `.turn .text` і
  `.turn.model` (зокрема `#live .turn.model`) — інакше розриви рядків і абзаци в репліках злилися б в один блок;
  довгі слова переносяться (`overflow-wrap: anywhere`), а не прибирається `pre-wrap`.
- `#pending` читають лише CSS і скрипт знімків, не JS — це не контракт для `conversation.js`.
- Новий скрипт `scripts/screenshots_minimal_design.py` (не тест, як інші `scripts/smoke_*`): справжній uvicorn у
  local mode + справжній Chromium; `--out <dir>`; сам перевіряє і друкує кроки.
- Сторінки й `style.css` не тягнуть жодного ресурсу з іншого походження (сервіс за IAP; Q6).
- Errors: нових немає. Dependencies: жодних нових (Playwright — `uv run --with`, як у
  `scripts/smoke_test_voice_dictation.py`).
- Does NOT do: зміну JS, маршрутів, текстів, перемикач теми; не оголошує стан читачам екрана.

## Decisions (with WHY)
- Q1: один власний `style.css` (~150 рядків, CSS custom properties), підключений з `base.html`. Чому: кешується
  браузером, одне місце для обох тем, без нової залежності. Rejected: classless-фреймворк (Pico.css, water.css) —
  найсильніше за нього: охайні типові стилі й перевірена доступність без жодних зусиль дизайну; проте це vendored копія,
  яку треба оновлювати, і його вигляд ми однаково переписували б під репліки й стан «відповідь
  іде»; задача прямо каже «без важких фреймворків». Rejected: розширити inline `<style>` — повторюється в кожній
  відповіді сервера і не кешується. Ціна кешування: після розгортання браузер може якийсь час тримати старий
  `style.css` (як і `conversation.js` уже зараз; `StaticFiles` дає `ETag`/`Last-Modified`) — прийнято, сторінка лишається
  робочою, лише вигляд оновиться пізніше.
- Q2: темна тема — `@media (prefers-color-scheme: dark)` і `color-scheme: light dark`, без перемикача. Чому: нуль
  JS, тема телефону вже обрана людиною. Rejected: перемикач із `localStorage` — новий JS і новий стан, а задача
  просить мінімум і не змінювати поведінку.
- Q3: «відповідь іде» — статичний `#pending` після `#send`, показаний `#send:disabled ~ #pending`. Чому: `#send`
  вимкнений рівно тоді, коли запит триває — за JS (P4) і за браузером, бо `autocomplete="off"` не дає Firefox
  відновити `disabled` після перезавантаження (P3); тож CSS читає наявний стан і JS не змінюється; сусідній селектор
  працює в усіх браузерах. Рядок стоїть у ряду кнопок — там, куди людина щойно натиснула. Rejected:
  `body:has(#send:disabled) #pending` під `#live` — ближче до тексту відповіді, але `:has()` немає у Firefox < 121
  і старіших Safari (спайк перевіряв і його — працює в нашому Chromium). Rejected: показувати стан з
  `conversation.js` (`ui.disable/enable`) — зміна JS, яку читають запечатані тести з фейковим DOM; `getElementById`
  нового id там повертав би `undefined`. Rejected: анімований курсор лише в `#live` — до першого `delta` (а
  перший токен моделі приходить за секунди) людина нічого не бачила б.
- Q4: репліки людини й фасилітатора — блоки на всю ширину колонки: людина — тонований фон з акцентною смугою
  ліворуч, фасилітатор — нейтральна картка; підписи «Ви» / «Фасилітатор» лишаються. Rejected: «бульбашки» чату
  ліворуч/праворуч — довгі вдумливі тексти у вузьких бульбашках гірше читаються на телефоні.
- Q5: ширина тексту — колонка `max-width: 42rem` (≈ 65–75 знаків), розмір шрифту 1.0625rem, міжрядковий 1.6;
  поле введення на всю ширину з висотою ≥ 7rem, кнопки з відступами ≥ 0.6rem і висотою ≥ 2.75rem (дотик на
  телефоні). Числа — смак, не поріг продукту: їх не перевіряє жоден тест, крім I2 і «немає горизонтальної
  прокрутки».
- Q6: системні шрифти (`system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`). Чому: жодного запиту за межі
  сервісу (за IAP), нуль ваги. Rejected: Inter чи інший вебшрифт — зовнішній запит або vendored файл.
- Q7: знімки — окремий скрипт з Playwright sync API, завантаженим через `importlib` (як у
  `smoke_test_voice_dictation.py`, щоб ruff не вимагав залежності): обробник маршруту `/reply` тримає запит — запам'ятовує
  `route`, скрипт перевіряє `#pending` і робить знімок стану «відповідь іде», поки запит справді триває, і лише тоді
  викликає `route.continue_()`. Rejected: затримка таймером на 2 с — залежить від швидкості машини. Rejected: вимкнути кнопку
  руками з `evaluate` — постановочний знімок, не справжній стан.

- Q8: `autocomplete="off"` на `#send` і `#retry`. Чому: без нього Firefox після `answered` (перезавантаження)
  відновлює вимкнені кнопки (P3) — «Надіслати» не натискається, а `#pending` світився б на готовій сторінці. Rejected:
  не додавати й відкласти до перевірки у Firefox — найсильніше: «поведінка не змінюється» буквально і P3 не
  перевірено; але тоді новий рядок стану брехав би в Firefox, а атрибут у Chromium нічого не змінює. Двосторонні
  двері: прибрати атрибут — одна правка шаблону.

## Hardest seams (test-confidence points)
- **Seam 1: темна тема справді вмикається.** Тест-рядок у CSS (`prefers-color-scheme` є) пройде й для блоку, що
  нічого не перевизначає. Тому скрипт знімків у контексті `color_scheme="dark"` читає обчислений
  `getComputedStyle(document.body).backgroundColor` і колір тексту та перевіряє, що фон темний (відносна яскравість <
  0.2 — технічна межа тесту «фон темний», не поріг продукту) і відрізняється від світлого контексту.
- **Seam 2: «відповідь іде» видно лише під час запиту.** Скрипт: до надсилання `#pending` невидимий; після кліку
  «Надіслати» з затриманим `/reply` — видимий; після `answered` і перезавантаження — невидимий і `#send` увімкнений, а в розмові дві
  нові репліки. Друга гілка кінця: `/reply`, на який маршрут відповідає 500 з фрагментом `<p class="error">…</p>` → `#pending`
  знову невидимий, `#send` увімкнений. Відкидає `#pending`, показаний завжди, і селектор, що ніколи не спрацьовує.
  Оголошення стану читачам екрана (`aria-live`, підпис `::before`) не обіцяється (див. Deferred).
  Приховані кнопки лишаються прихованими: на щойно завантаженій своїй сторінці теми `#recognize` і `#retry` невидимі
  (у кожному з контекстів: комп'ютер і телефон, світла й темна тема); гілка обриву мережі (маршрут `/reply` →
  `route.abort()`, JS викликає `showRetry`) → `#retry` видимий. Відкидає правило `display` для кнопок, що перебиває
  `[hidden]`. До надсилання `#live` не має видимого блоку (висота 0), а збережена репліка фасилітатора має рівно один
  підпис «Фасилітатор» — відкидає `::before` на всіх `.turn.model` і порожню картку `#live`.
  Розриви рядків лишаються: збережена репліка людини з `\n` (надіслана скриптом) має обчислений `white-space` рівно
  `pre-wrap` і займає щонайменше два рядки; `<p class="turn model">`, вставлений скриптом у `#live` як зразок
  (`evaluate`, лише для перевірки правила), має обчислений `white-space` `pre-wrap`. Відкидає `style.css` без `pre-wrap`.
- **Seam 3: телефон.** Скрипт у контексті 390×844 (і 360×740): `document.documentElement.scrollWidth <=
  window.innerWidth` на «Мої теми» і на сторінці теми з довгою реплікою без пробілів (60 знаків `ааа…`) і з темою, чия
  назва — одне слово з 60 знаків (`<h1>` теми, `<li>` у «Мої теми» й «Усі теми») — відкидає
  поле чи `pre-wrap` текст, що розпирає сторінку.
- **Seam 4: поведінка не змінилась.** Наявні тести (усі `node --test` для `conversation.js`, `skel_web`,
  `voice_dictation`, `voice_language`) без змін і `scripts/smoke_test_voice_dictation.py` (мікрофон → текст у полі →
  надіслати → відповідь) зелені після зміни розмітки.

## Invariants (rules that hold for every input in the stated domain)
- **I1** — кожна сторінка, яку сервіс рендерить із шаблону, підключає `/static/style.css` і не тягне жодного ресурсу з іншого
  походження.
  - Domain: кожен HTML-шаблон у `src/thinkhow/web/templates/` в кожній гілці рендеру — «Мої теми» власника і не
    власника, «Мова» з мовою і без, сторінка теми своя (з формою) і чужа (без форми); і сам `style.css`.
  - Source: «Seam» (рядок «не тягнуть жодного ресурсу з іншого походження»; Q6 — сервіс за IAP); задача 201 («без
    важких фреймворків»).
  - Broken by: шаблон, що не наслідує `base.html`; `<link>`/`<script src>`/`@import`/`url(…)` з `http(s)://` чи
    `//` (CDN шрифту чи фреймворку).
- **I2** — основний текст і текст кнопок мають контраст із фоном ≥ 4.5:1 (WCAG 2.x AA) в обох темах.
  PROVISIONAL — owner ratification pending.
  - Domain: кожна пара «колір тексту / фон», на якій `style.css` ставить текст, у `:root` і в блоці
    `prefers-color-scheme: dark`: `--fg` на `--bg`, `--surface`, `--user-bg`, `--field-bg`; `--muted` (підписи «Ви» /
    «Фасилітатор», `#pending`, `::before`) на `--bg`, `--surface`, `--user-bg`; `--error` на `--bg`; `--link` на
    `--bg`, `--surface`, `--user-bg`; `--primary-fg` на `--primary-bg`; `--fg` на `--button-bg`. І друга частина
    правила: поза цими двома блоками кожне оголошення `color`, `background`, `background-color`, `border-color`,
    `outline-color` у `style.css` бере значення лише через `var(--…)` (або `transparent`, `inherit`, `currentColor`) —
    (а також скорочення `border`, `border-left` тощо — їхня частина кольору) без буквальних hex, `rgb()`, `hsl()` чи
  назв кольорів, тож кольори тексту сторінки беруться лише з палітри (нова пара змінних поза переліком — див. Critic notes).
  - Source: задача 201 («читабельна типографіка, спокійні кольори»); поріг 4.5:1 — WCAG AA для звичайного тексту.
  - Broken by: «спокійний» сірий на сірому (`#999` на `#fff` = 2.8:1); темна тема, що перевизначає фон, але лишає
    темний текст; сумісна палітра, а в правилі `.who { color: #999 }` чи `button.primary { background: #6aa0ff }`
    буквально; `--muted` на `--user-bg`, якого немає в палітрі світлої чи темної теми.

## Exit criterion
- `uv run pytest` (усі, разом із `node --test` тестами, що запускає pytest), `uv run ruff check .`, `uv run mypy`
  — зелені; запечатані файли не змінені (`python3 .claude/hooks/testing.py check` для skel-web, voice-dictation,
  voice-language, voice-reply-language — «match»; skel-guards-deploy уже до цього slice-а показує CHANGED для
  `tests/contract/walking_skeleton_block/test_wsblock_connections.py` — не наслідок цієї зміни). Контрактні тести I1–I2 — у `tests/contract/minimal_design/`.
- Smoke (кожен рядок з `set -o pipefail`, щоб `tee` не ховав код виходу): `uv run --with playwright==1.64.1 python scripts/screenshots_minimal_design.py --out
  tasks/done/201-minimal-design/screens | tee .engine/artifacts/spikes/minimal-design-screens-<дата>.txt` — перевірки
  Seams 1–3 пройдені (скрипт падає на першій невдалій), знімки: `home-desktop-light.png`, `home-desktop-dark.png`,
  `home-phone-light.png`, `home-phone-dark.png`, `topic-desktop-light.png`, `topic-desktop-dark.png`,
  `topic-phone-light.png`, `topic-phone-dark.png`, `topic-pending-phone-light.png`. Розмова на знімку теми — щонайменше
  дві репліки людини і дві фасилітатора (local mode).
- `uv run --with playwright==1.64.1 python scripts/smoke_test_voice_dictation.py | tee
  .engine/artifacts/spikes/voice-dictation-smoke-<дата>-after-design.txt` — OK (Seam 4).
- `uv run python scripts/smoke_test_skel_web.py` і `uv run python scripts/smoke_test_voice_language.py` — OK
  (HTTP-smoke розмітки, яку змінює slice; зокрема `'<select name="code"'` — атрибути `select` не змінюються).
- `tasks/done/201-minimal-design/report.md` показує всі 9 знімків відносними шляхами
  (`![topic-phone-dark](screens/topic-phone-dark.png)`), кожен з підписом сторінка · пристрій · тема, і посилається на
  `.engine/artifacts/spikes/minimal-design-screens-<дата>.txt` як на запис пройдених перевірок.
- Контраст I2 — `PROVISIONAL — owner ratification pending` (4.5:1, WCAG AA); відмова від порогу не ламає нічого,
  крім одного тесту.

## Deferred to later slices
- Перемикач теми на сторінці — why later: мінімум, тема пристрою — revisit trigger: власник чи людина попросить
  іншу тему, ніж на пристрої; ціна потім — маленький
  скрипт у `<head>` до малювання (без спалаху теми) і `localStorage`.
- Markdown у відповідях фасилітатора (списки, жирний) — why later: зміна рендеру тексту, не стилю, і безпечність
  тексту (I2 skel-web: текст лише як текст) — revisit trigger: у репліках моделі в
  розмовах з'являються рядки, що починаються з `- ` чи `1. `; ціна потім — безпечний рендер підмножини Markdown.
- Сторінка-фрагмент помилки (`<p class="error">…</p>` після звичайного POST форми без JS, напр. порожня назва теми)
  лишається без стилю — why later: фрагмент — контракт тестів і JS, рідкісний шлях — revisit trigger: людина чи
  власник потрапить на голу сторінку помилки; ціна потім — окремий шаблон для не-JS запитів.
- Перевірка `autocomplete="off"` у справжньому Firefox (P3) — why later: Firefox на машині немає, а
  `playwright install firefox` — нова установка; атрибут нешкідливий — revisit trigger: власник чи людина побачить
  «Фасилітатор відповідає…» чи вимкнену «Надіслати» на сторінці з уже готовою відповіддю.

- Оголошення стану «відповідь іде» читачам екрана — why later: `aria-live` на елементі, що з'являється з
  `display:none`, читачі часто не оголошують; потрібен JS — revisit trigger: прохання власника чи людини про підтримку читача екрана або зміна
  `conversation.js` з іншої причини.

## Open items requiring human decision (if any)
- Поріг контрасту I2 4.5:1 (WCAG AA) — question: «Чи підходить вимога контрасту тексту 4.5:1 (стандарт WCAG AA)?»
  Recommended: так — це загальний стандарт читабельності, і він не обмежує вибір спокійних кольорів. Ціна
  відмови: прибрати один тест. Без нагляду питання йде власнику розділом «Питання до власника» у звіті задачі 201
  (поріг не блокує роботу: slice іде з PROVISIONAL).

## Critic notes (non-blocking)
- Phase 2: три раунди (Firefox відновлює `disabled` після перезавантаження → `autocomplete="off"` і сусідній селектор
  замість `:has()`; `[hidden]` перебивається авторським `display` → `[hidden] { display:none !important }`). Phase 3: два
  раунди (I2 — домен лише палітри → усі пари тексту і заборона буквальних кольорів поза палітрою). Phases 4–5: два
  раунди (звіт мусить показувати знімки).
- I2 не ловить нову пару змінних, якої немає в переліку (напр. `--link` на `--primary-bg`); за потреби — обчислений
  контраст на справжніх елементах у скрипті знімків.
- Гілки кінця `failed` і обрив мережі для `#pending` у справжньому браузері не перевіряються окремо — їх покривають
  тести `node --test` для `ui.enable()`.
- Firefox також відновлює значення `textarea` після перезавантаження — наявна поведінка, поза цим slice-ом.
- Версія в адресі `style.css` (`?v=`) не додається: затримка оновлення вигляду після розгортання — лише косметика.
