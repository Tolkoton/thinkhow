# Slice research-quick — planning artifact

Feature: `.engine/architecture/feature/research-in-conversation.md`, S1 — **TRACER BULLET** (Vertex з пошуком →
facilitation → workspace → `research.json`, `conversation.md` з джерелами). Driven mode, unattended: frame supplied by
the feature artifact, not asked. Depends on: —.

## Goal
Коли людина не знає факту про світ, фасилітатор (під роутером, з обраною карткою) сам шукає в інтернеті тим самим
потоковим викликом Gemini, коротко дає знайдене, а код дописує під відповіддю рядок джерел; знайдене лягає в
`research.json` теми і коротко — пунктом «fact» у карту (feature: G7, G1, G2; N1 v5 — факти дати можна, рішення за
людиною). Вимірна ціль: pytest зелений (запечатані тести всіх попередніх slice-ів — без жодної зміни); live-тест на
`gemini-4-argon`/`eu` з `enterprise_web_search`: репліка людини «не знаю, скільки це коштує / як це роблять інші» у
розмові під карткою → відповідь з рядком «Джерела:» щонайменше з одним посиланням, `research.json` з запитами і
джерелами (пункт `fact` у `map.json` записується — рішення моделі); репліка людини про себе → без пошуку (лише записується — модель вирішує,
PR-17).

## Premise verified
- PR-17 — `.engine/artifacts/spikes/research-design-2026-10-25/README.md` §2–§3 (2026-10-25, свіжа): потоковий
  JSON-виклик фасилітатора (`system_instruction` картки під роутером, `answer_schema`) з
  `tools=[Tool(enterprise_web_search=EnterpriseWebSearch())]` на Vertex `eu`, `gemini-4-argon` працює разом з
  `response_json_schema`; `candidate.grounding_metadata` приходить у чанках потоку з `web_search_queries`,
  `grounding_chunks[].web.{title, uri}` і `search_entry_point.rendered_content` (HTML ~5 КБ). На #17, #19, #21
  власника модель шукала (2 запити, 2–4 джерела), на #25 — ні. Посилання джерел — `vertexaisearch.cloud.google.com/
  grounding-api-redirect/…` (їх розгортає S1b).
- PR-16 — `accepted-as-risk`: пошук без гарантії ЄС і умови Google §20(k) — рішення власника (задача 303, питання 1 і 3).
- Запечатані фейки Llm (`tests/contract/*/…_fakes.py`) визначають `stream_json(self, system, contents, schema, rev)` з
  чотирма аргументами і будують `Done(raw, usage)` позиційно; `lead` кличе `stream_json` з чотирма аргументами
  (`respond.py:52`) — цей виклик не змінюється.
- Запечатані тести вимагають: `system_instruction(...)` починається з `RULES + "\n\n# Мова відповіді\n" + правило +
  "\n"` (`test_ffm_invariants.py:98`, `test_vrl_disputed_q1_rule_text_exact.py:17`); під роутером рядок
  `ROUTED_HEAD` стоїть між «# Мова відповіді» і «# Картка» (`test_rt_respond.py:51`). Тож `rules.md` і `routed.md` не
  змінюються, а новий розділ стоїть після розділу роутера і перед «# Картка», лише під роутером.
- `llm_call`: запечатаний `test_skelp_llm.py:324` перевіряє лише наявність ключів — нові ключі не заважають.
- Продакшн завжди під роутером: `workspace._read_routing` дає `()` без файлу, тож `respond` завжди кличе `converse`
  (feature critic, раунд 2, пункт 3).

## Out of scope (deliberately)
- Розгортання посилань Google у справжні адреси, `TopicView.research`, показ Search suggestions і клікабельних посилань
  у `web` — S1b.
- Дія роутера «answer» і правило фактів у роутері — S2.
- Глибоке дослідження (`deep_question`, цикл, `search_text`) — S3.
- Справжній пошук у локальному режимі (локальний двійник лише повертає заготовку «що знайдено», без мережі).
- Пошук у виклику роутера, у повторі оновлення і в навчанні — `generate_json` не шукає ніколи.

## Seam (contract)
`src/thinkhow/platform/llm.py`:
- `@dataclass(frozen=True) class Source: title: str; url: str`.
- `@dataclass(frozen=True) class Found: queries: tuple[str, ...]; sources: tuple[Source, ...];
  suggestions_html: str | None`.
- `Done(raw_json: str, usage: Usage, found: Found | None = None)` — нове поле останнім, із замовчуванням.
- `VertexLlm.__init__(client, model, timeout_s, attempts, sleep=…, clock=…, search: bool = False)`. При `search=True`
  лише `stream_json` додає в конфіг `tools=[types.Tool(enterprise_web_search=types.EnterpriseWebSearch())]` і
  збирає з **усіх чанків вдалої спроби** `grounding_metadata` у `Done.found` за одним правилом: `queries` і `sources`
  — **об'єднання по всіх чанках** без повторів (запити — за текстом, джерела — за `url`), у порядку першої появи;
  `suggestions_html` — останнє непорожнє `search_entry_point.rendered_content`. Правило дає той самий результат, чи
  Vertex повторює повні метадані в кожному чанку, чи шле їх частинами. Спроба, що впала до повтору, нічого не лишає.
  `found` = `None`, коли немає ні запитів, ні джерел. Джерело — `grounding_chunks[].web` з непорожнім `uri`; `title` —
  `web.title`, а без нього — `web.domain`, без обох — `url`.
  `generate_json` не додає інструмента ніколи. Атрибути метаданих читаються обережно (`getattr(…, None)`): чанк без
  `grounding_metadata` — це «нічого не знайдено», не помилка.
- `llm_call` отримує два ключі: `search` (bool — чи був інструмент у цьому виклику) і `queries` (int — кількість
  пошукових запитів у `found`, 0 без нього).
- `ScriptedLlm(script, chunk=7, found_script: FoundScript | None = None)`; `FoundScript = Callable[[str,
  Sequence[Turn], type[BaseModel]], Found | None]`; `stream_json` кладе `found_script(system, contents, schema)` у
  `Done.found` (без `found_script` — `None`); `generate_json` його не кличе.
- `make_llm(settings, script, search: bool = False, found_script: FoundScript | None = None)` — локально
  `ScriptedLlm(script, found_script=found_script if search else None)`, інакше `VertexLlm(..., search=search)`
  (`found_script` у Vertex не використовується).

`src/thinkhow/facilitation/types.py` (не імпортує `platform`):
- `ItemType` += `"fact"` (останнім).
- `@dataclass(frozen=True) class Source: title: str; url: str`.
- `@dataclass(frozen=True) class ResearchEvent: depth: Literal["quick", "deep"]; queries: tuple[str, ...];
  sources: tuple[Source, ...]; suggestions_html: str | None; question: str | None = None; report: str | None = None`.
- `Facilitate = Callable[[FacilitationContext], Iterator[ReplyDelta | FacilitatorUpdate | RoutingEvent |
  ResearchEvent]]`.
- `__init__.py` експортує `ResearchEvent` і `Source`.

`src/thinkhow/facilitation/research.md` (новий) — розділ інструкції «# Факти про світ», текст:
```
# Факти про світ
У тебе є пошук в інтернеті. Коли людина каже «не знаю», розрізняй, чого саме вона не знає:
- Факт про світ, який можна дізнатися (ціни, ринок, як зазвичай роблять інші, де шукають клієнтів, правила, строки,
  статистика), — не питай людину про нього: знайди сам і коротко дай знайдене в reply своїми словами, без посилань у
  тексті (джерела система допише сама). Так само, коли людина прямо питає такий факт.
- Те, що покаже лише реальність (чи відповідять клієнти, чи спрацює саме в неї), — не шукай і не вгадуй: запропонуй
  дешевий спосіб перевірити це як її крок.
- Факт про саму людину (її гроші, час, бажання, досвід) — питай її; про неї не шукай.
Знайдене — підстава для її думки, не оцінка її варіантів: рішення й вибір лишаються за людиною. Після знайденого —
як завжди, одне питання. Кожен знайдений факт, на який людина спиратиметься, коротко додай у map_updates пунктом
типу «fact» (одне речення, з числом чи назвою, без посилань).
```
`src/thinkhow/facilitation/respond.py`:
- `system_instruction(card, memory, language=None, routed=False)`: під роутером — `RULES`, «# Мова відповіді», розділ
  роутера, **тоді розділ «# Факти про світ»** (`research.md`), тоді «# Картка» і «# Пам'ять досвіду»; без роутера —
  без змін, байт у байт.
- `lead(ctx, knowledge, llm)` -> `Iterator[ReplyDelta | FacilitatorUpdate | ResearchEvent]`: як досі, а коли `Done.found`
  не `None` і має джерела — після відповіді (і після повтору `_settle`, якщо він був) віддає ще один `ReplyDelta` з
  рядком джерел, тоді `ResearchEvent(depth="quick", …)`, тоді `FacilitatorUpdate` з `reply` = відповідь + рядок
  джерел. `found` з запитами, але без джерел — `ResearchEvent` без рядка джерел. `found` = `None` — вихід `lead`
  такий самий, як до цього slice-а.
- `sources_line(sources: Sequence[facilitation.types.Source]) -> str` — `"\n\nДжерела: " + ", ".join(f"[{title}]({url})")`,
  де з `title` прибрано `[` і `]`, а в `url` `(` і `)` замінено на `%28` і `%29` (Markdown не ламається); порожній
  список → `""`. `lead` перетворює `llm.Source` на `facilitation.types.Source`. Одна функція, нею користуються S2 і S3.

`respond(...)` повертає `Iterator[ReplyDelta | FacilitatorUpdate | RoutingEvent | ResearchEvent]`.

`src/thinkhow/facilitation/converse.py`: `Lead` повертає `Iterator[ReplyDelta | FacilitatorUpdate | ResearchEvent]`;
`_lead_card` передає `ResearchEvent` далі, як і дельти (притримане оновлення й кінець картки — як досі).

`src/thinkhow/workspace/topics.py`:
- `class ResearchEntry(BaseModel, extra="forbid")`: `turn: int; depth: Literal["quick","deep"]; queries: list[str];
  sources: list[{title: str, url: str}]; suggestions_html: str | None; question: str | None; report: str | None`.
- `class ResearchFile(BaseModel, extra="forbid")`: `entries: list[ResearchEntry]`.
- `_answer` збирає `ResearchEvent` (окрема гілка, не `Delta`); після запису `conversation.md`, `map.json` і
  `routing.json` — якщо подій ≥1 — читає `research.json` (немає — порожній), **дописує** записи з `turn` = номер
  відповіді моделі і пише файл (`users/<uid>/<topic>/research.json`, JSON). Без подій файл не читається й не пишеться.
  `Failed` — нічого не пишеться (як і з `routing.json`).

`src/thinkhow/web/local.py` — заготовка локального двійника (feature Build parameters: «сценарний двійник повертає «що
знайдено» з заготовки»): `local_found(system, contents, schema) -> Found | None` — коли репліка людини в рамці
(`[Репліка людини #N]`) містить «скільки коштує» (без огляду на регістр) і схема має `reply`: `Found(queries=(текст
репліки до 80 символів,), sources=(Source("example.org", "https://example.org/local-search"),),
suggestions_html=None)`; інакше `None`. `local_script` на таку репліку додає в `map_updates` пункт типу `fact` (замість
`plan`). Жодна наявна репліка тестів і локальних розмов цієї фрази не містить (`grep -ri "скільки коштує" tests src`
— порожньо), тож локальна поведінка без неї не змінюється.

`src/thinkhow/web/app.py`: `make_llm(settings, local_script, search=True, found_script=local_found)`.

- Errors: як досі — модель не відповіла → `LlmUnavailable` → `Failed`; метаданих немає → `found=None`, звичайна
  відповідь. Нових винятків немає.
- Dependencies (injected): `client` (genai), `sleep`, `clock` — як досі; `found_script` — у двійника.
- Does NOT do: розгортання посилань, показ у `web`, «answer», глибоке; не міняє `rules.md`, `routed.md`,
  `generate_json`, `learning`.

## Decisions (with WHY)
- Q1: пошук — властивість екземпляра `VertexLlm(search=True)`, а не аргумент `stream_json` — chosen because виклик
  `lead` з чотирма аргументами і всі запечатані фейки лишаються як є (feature critic, раунд 1, #1), а в застосунку є
  лише один потоковий шлях (фасилітатор). Rejected: аргумент `search=` у `stream_json` — ламає 14 означень `stream_json` у 12 файлах тестів (`rg "def stream_json" tests`);
  окремий метод `stream_json_searched` — `lead` мусив би знати, чи вміє фейк його, або фейки мусили б мінятись.
- Q2: інструмент лише в `stream_json`, `generate_json` не шукає ніколи — chosen because `generate_json` кличуть роутер
  (дія «answer» стане потоковим викликом у S2), повтор оновлення і навчання — жоден не має давати людині фактів;
  менше пошуків — менше ціни й запитів у журналах Google. Rejected: шукати і в повторі `_settle` — повтор питає лише
  оновлення, а «знайдене» першої спроби вже є.
- Q3: джерела дописує код рядком під відповіддю, з метаданих Google, а модель посилань у текст не пише — chosen because
  адреси з метаданих справжні (модель вигадує або обрізає URL; проба 24.10 — обрізані посилання в тексті звіту), і
  рядок той самий у потоці й у `reply` (показане = записане). Rejected: просити модель вставити посилання — неперевірні
  адреси; прив'язка речень (`grounding_supports`) — feature Deferred.
- Q4: розділ «# Факти про світ» — окремий файл після розділу роутера і лише під роутером — chosen because `rules.md`,
  мовний розділ і порядок «мова → роутер → картка» запечатані, а продакшн завжди під роутером. Rejected: дописати в
  `rules.md` — ламає `test_ffm_invariants.py::test_I3…` і `test_vrl_…exact`; розділ і без роутера — у продакшні цього
  шляху немає, а запечатані тести без роутера чекають інструкцію байт у байт.
- Q5: «знайдене» лягає в карту пунктом `fact` за рішенням моделі в тому самому оновленні (не код) — chosen because
  карта йде в кожен виклик, і модель знає, на що людина спиратиметься (G2 — пам'ять між сесіями); код не знає, яке
  речення відповіді — факт. Rejected: код кладе в карту кожне джерело — шум, і `research.json` уже має їх усі.
- Q6: `research.json` дописується, старі записи не переписуються — chosen because це історія досліджень теми (як
  `routing.json`), а один файл пише лише `workspace` (A3.3). Rejected: окремий файл на репліку — більше файлів без
  потреби (P5).
- Q7: `found` без джерел (модель шукала, нічого не знайшла) — `ResearchEvent` з запитами, без рядка джерел — chosen
  because запити — факт того, що шукали (видно в `research.json`), а порожній рядок «Джерела:» — шум.
  Rejected: відкидати такий `found` — губиться слід пошуку.

- Q8: шлях `_settle` без показаного тексту (повний `generate_json` без пошуку) — рядок джерел першого виклику
  дописується до відповіді, згенерованої без результатів пошуку; джерела можуть не збігатися з текстом — прийнятий
  компроміс (рідкісний шлях: невалідний потоковий JSON без жодного показаного тексту), бо так велить контракт feature-а («рядок джерел дописується до відповіді повтору»); слід пошуку і без
  рядка зберігся б у `research.json`, тож зміна цього — поправка feature-а, кандидат на перегляд у звіті.
  Rejected: повтор з пошуком — повтор у `generate_json`, який не шукає (I4).

## Hardest seams (test-confidence points)
- **Seam 1: метадані в потоці** — `grounding_metadata` приходить не в кожному чанку, не обов'язково в останньому і,
  можливо, частинами;
  повтор потоку після падіння до першого тексту не має тягти метадані впалої спроби. Тест: фейковий клієнт genai
  (`skelp_fakes`-подібний) з планами, де метадані в середньому чанку, в останньому, розбиті (запити в одному, джерела в
  іншому), джерела частинами в кількох чанках (об'єднуються) і ті самі повні метадані в кожному чанку (без повторів), і план «впав → повтор» з метаданими лише у впалій спробі → `found is None`. Anti-pattern: тест, що кладе
  метадані в єдиний чанк.
- **Seam 2: інструмент лише там, де треба** — тест читає `config.tools` кожного виклику фейкового клієнта:
  `stream_json` екземпляра `search=True` — є `enterprise_web_search`; `generate_json` того ж екземпляра і `stream_json`
  екземпляра `search=False` — `tools` порожні/`None`. Anti-pattern: перевіряти лише, що `found` повернувся.
- **Seam 3: показане = записане** — тест через `workspace.reply` з `ScriptedLlm(found_script=…)` під роутером:
  конкатенація `Delta` з потоку `ReplyEvent` дорівнює тексту відповіді моделі в `conversation.md` (після
  `normalize`), і вона закінчується рядком джерел; те саме для шляху повтору `_settle` (невалідний потоковий JSON з
  показаним текстом). Anti-pattern: перевіряти рядок джерел лише в `update.reply`.
- **Seam 4: без «знайденого» нічого не змінилось** — `lead`/`respond` з `Done(raw, usage)` (без `found`) дає ту саму
  послідовність подій, що й до slice-а; запечатані тести — без змін (повний прогін). Anti-pattern: новий тест лише на
  щасливий шлях з пошуком.
- **Seam 5: `research.json` дописується** — три відповіді в тій самій темі — №2 з пошуком, №4 без, №6 з пошуком →
  два записи з `turn` 2 і 6 (номери відповідей моделі); відповідь №4 файл не змінює; `Failed` після `ResearchEvent` → файлу немає. Один випадок — через справжній ланцюг
  `respond` → `converse._lead_card` → `workspace._answer` з `ScriptedLlm(found_script=…)` (порядок `ResearchEvent` перед
  оновленням); `found` з запитами без джерел → запис з порожнім `sources`, у `conversation.md` рядка джерел немає (Q7).
  Anti-pattern: перевіряти лише перший запис.

## Invariants (rules that hold for every input in the stated domain)
- **I1** — Текст, який людина отримала потоком, дорівнює тексту, який записано як відповідь.
  - Domain: кожен виклик `lead` (і `respond` під роутером з обраною карткою) з будь-яким потоком `stream_json` — з
    `found` чи без, з невалідним JSON (обидва шляхи повтору `_settle`) чи валідним.
  - Source: feature, Inter-slice contracts — «той самий текст іде в потік і в `reply`, тож показане наживо = записане».
  - Broken by: рядок джерел дописано лише в `update.reply` або лише в потік; шлях повтору забуває рядок.
- **I2** — Без «знайденого» (`Done.found is None`) вихід `lead` — та сама послідовність подій, що до цього slice-а:
  жодного `ResearchEvent`, жодного рядка джерел.
  - Domain: кожен виклик `lead` з будь-яким потоком, чий `Done` не має `found`.
  - Source: feature, Inter-slice contracts — «без `found` `lead` поводиться точно як досі».
  - Broken by: порожній `ResearchEvent` на кожну відповідь; `"\n\nДжерела: "` з порожнім списком.
- **I3** — Рядок джерел містить кожну адресу з метаданих вдалої спроби (після екранування `sources_line`) рівно один раз, у порядку першої появи, хоч би
  як джерела розподілились по чанках.
  - Domain: будь-які `grounding_chunks` у будь-яких чанках вдалої спроби (зокрема повтори, частини в кількох чанках,
    без `title`, без `web`, адреси з `(` `)` і назви з `[` `]`).
  - Source: цей контракт, Seam — «без повторів за `url` (порядок першої появи)».
  - Broken by: дублікати з кількох чанків; лише останній чанк (губить ранні джерела); сортування; втрата джерела без
    `title`.
- **I4** — `generate_json` ніколи не передає моделі інструмент пошуку.
  - Domain: будь-який `VertexLlm` (з `search=True` чи `False`), будь-яка схема.
  - Source: feature, S1 — «`generate_json` не шукає ніколи (роутер, повтор оновлення, навчання)».
  - Broken by: `tools` у спільному `_config` для обох методів.
- **I5** — Запис дослідження в `research.json` не змінює і не губить попередніх записів; новий запис має `turn` =
  номер відповіді моделі, до якої він належить.
  - Domain: будь-яка послідовність відповідей теми з `ResearchEvent` і без.
  - Source: feature, Inter-slice contracts — «дописує в `research.json` з `turn` = номер відповіді моделі».
  - Broken by: перезапис файлу лише новими записами; `turn` = номер репліки людини.

## Exit criterion
- `uv run pytest -q` зелений: нові тести (Seams 1–5, I1–I5) і всі запечатані тести попередніх slice-ів без змін;
  `ruff check`, `mypy` чисті; `tests/test_a3_*` зелені (SDK Google лише в `platform`; `types.py` без `platform`).
- Smoke через composition root: `tests/smoke/test_e2e_local.py` — **нова** тестова функція (наявні не змінюються):
  `create_app(build_deps(environ, CARDS))` локально, тема → репліка «Не знаю, скільки коштує оренда офісу в Лейпцигу»
  → роутер (двійник обирає Pre-mortem) → фасилітатор з `local_found` → `conversation.md` з рядком «Джерела:
  [example.org](https://example.org/local-search)», `research.json` з одним записом (`turn` 2), `map.json` з пунктом
  `fact`.
- Live (закриває slice): `tests/live/test_research_live.py` (позначка `live`, запускається руками з ADC) — `VertexLlm`
  з `search=True` на `eu`, `gemini-4-argon`, через `workspace.reply` з локальною текою. Розмова — **репліка власника #17
  «Як це можна взнати?»** з темою `t-d824f508a729`: історія #1–#16 читається під час прогону з bucket
  `pocket-lawyer-431614-thinkhow-users` (ADC, як у пробі research-design; текст розмови в репозиторій не потрапляє),
  кладеться в локальну теку теми разом з `routing.json`, де обрано картку `weighted-matrix` (як у пробі). Прогін — один; якщо модель на #17 не шукала — це знахідка для звіту (slice не закрито, причину з'ясувати), не
  повтор до зеленого. Умови:
  відповідь з рядком «Джерела:» (≥1 посилання — тобто «з джерелом», AC2; не поріг), `research.json` з ≥1 запитом і
  ≥1 джерелом, `llm_call` з `search: true` (тест перехоплює рядки `"llm_call"` з виводу, як `tests/live/test_router_live.py:335`). Записується (не умова): пункт `fact` у `map.json`; репліка власника #25
  (людина про себе) — шукала модель чи ні (PR-17); додатково пряме питання «Скільки зараз коштує новий Škoda Octavia
  Combi у Німеччині?» під тією ж карткою. Вивід прогону — у `.engine/artifacts/spikes/research-quick-live-<час>.txt`
  (час, токени, запити, джерела; без тексту розмови власника, крім номерів реплік і відповіді моделі). Порогу часу
  немає (P4; feature Build parameters — лише записуємо).

## Deferred to later slices
- Розгортання посилань і показ у `web` — S1b (feature DAG). Revisit trigger: S1b.
- Рядки джерел із посиланнями-перенаправленнями Google, записані до S1b, у `conversation.md` і `research.json` лишаються такими; чи
  розгортати старі — **вхід S1b** (S1b вирішує явно). Модель бачить свої минулі відповіді з рядком джерел в історії — revisit trigger:
  live S1/S4 покаже, що модель почала писати посилання в текст.
- Q8 (рядок джерел до відповіді повтору `_settle`, згенерованої без пошуку) — кандидат на перегляд: revisit trigger —
  у прогонах S4 чи в журналах трапився повтор без показаного тексту на репліці з пошуком (`llm_call` з `attempts` > 1
  або два виклики на репліку).

## Open items requiring human decision (if any)
- (немає)

## Critic notes (non-blocking)
- Phase 2, раунд 1 (`CRITIC_REVISE`): одне правило збору метаданих (об'єднання запитів і джерел по чанках, suggestions —
  останнє); нотатки 2–6 враховано (число фейків, тип `respond`, Deferred про старі рядки, Q8, Seam 5).
- Phase 2, раунд 2 — `CRITIC_PASS`; нотатки: який `Source` у `sources_line`, екранування Markdown, `fact` live лише
  записується, порядок Q7/Q8 — враховано; Q8 — поведінка за контрактом feature-а, кандидат на перегляд.
- Phase 3, раунд 1 — `CRITIC_PASS`; нотатки (порядок подій через справжній ланцюг, екранування в I3, Q7 у Seam 5) — враховано.
- Phases 4–5, раунд 1 (`CRITIC_REVISE` обидві): live — репліка власника #17 (як у feature-і), Škoda — додатковий запис;
  локальна заготовка «що знайдено» в scope (feature Build parameters), Deferred про локальний пошук прибрано; Goal,
  smoke через `build_deps`, Q8 з тригером — враховано.
- Phases 4–5, раунд 2 — `CRITIC_PASS` обидві; нотатки (один smoke-пункт, один live-прогін без повтору, перехоплення
  `llm_call`, `research.json` у Deferred) — враховано.
- Cold reader — `CRITIC_PASS`. Нотатки для збирача: (1) live-вивід з відповідями моделі на розмові власника — це
  його власна тема, ризик умов Google прийняв він (PR-16, «Б»); у файлі — номери реплік і відповіді моделі, без його
  реплік; (2) S1 не розгортається до S1b (Search suggestions показує S1b) — запит Сонькові лише в кінці feature-а;
  (3) тести Seam 3 і 5 мають пройти через перетворення `llm.Source` → `facilitation.types.Source` у `lead`; (4) Seam 2 —
  ще й `generate_json` екземпляра з `make_llm(..., search=True)` на шляху роутера.
