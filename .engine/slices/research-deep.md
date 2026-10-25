# Slice research-deep — planning artifact

Feature: `.engine/architecture/feature/research-in-conversation.md`, S3 (block deep). Driven mode, unattended: frame
supplied by the feature artifact, not asked. Depends on S1 `research-quick`, S1b `research-display`, S2 `fact-answer`
(all DONE).

## Goal
Коли питання багатогранне (ринок, кілька шляхів), фасилітатор пропонує глибоке дослідження і каже, що це близько двох
хвилин; коли людина погодилась чи сама попросила, система в **тій самій** відповіді проводить власний цикл: план
підпитань → пошуки паралельно → звіт з джерелами, що закінчується одним питанням до людини; поки йде цикл, людина бачить,
що саме шукають (feature S3, AC3; власник: «деякі питання потребують глибокої аналізу… по потребі»). Звіт, джерела і
пункти `fact` лягають у тему (`conversation.md`, `research.json` з `depth: "deep"`, `map.json`) — G2. Вимірна ціль:
pytest зелений (запечатані тести — без змін); live на справжньому Google (`eu`, WGE) через `workspace.reply`: людина під
карткою погоджується на глибоке → звіт з рядком джерел і питанням, `research.json` з записом `deep` (питання, звіт,
запити, джерела), час і ціна записані (AC3).

## Premise verified
- PR-19 — власний цикл (план → 4 пошукові виклики з WGE паралельно → звіт) на Vertex `eu`: 128.7 с, звіт з місцевими
  джерелами (`.engine/artifacts/spikes/research-google-eu-2026-10-24/deep_wge.out`, 2026-10-24; ціна ≈ $0.31–0.38 за
  прайсом `.engine/sketches/gemini-eu.md`: $2.2 вхід / $11 вихід за 1M до 30.11.2026, пошук $14 за 1 000 понад
  5 000 безплатних на місяць). У продукті — `unverified` до live цього slice-а.
- Пошуковий виклик без JSON (`generate_content` з `tools=[enterprise_web_search]`) повертає текст і
  `grounding_metadata` (там само, `deep_wge.py`).
- Запечатані тести, що обмежують форму: `test_skelf_respond.py:150-155` — схема потоку **без роутера** має рівно
  `reply, current_phase_id, phase_exit_met, map_updates`; `test_fa_converse.py:150` — схема потоку `answer_fact` —
  саме `FactAnswer`, `:163`, `:178` — схеми повторів `answer` — рівно `{map_updates}` і `{reply, map_updates}`;
  `test_fa_route.py:63-67` — `RESEARCH_SECTION` починається «# Факти про світ» і закінчується рядком «Пункт «fact»…»;
  `test_rq_respond.py:111` — текст розділу S1 стоїть у ньому суцільно. Тому `FacilitatorUpdate`, `FactAnswer`,
  `answer_schema(card)`, `update_schema(card)` **не змінюються**, а нове правило вставлено всередину `research.md` між
  текстом S1 і останнім рядком S2.
- Під роутером фасилітатор отримує схему з картки (`answer_schema(card)`); жоден запечатаний тест не перелічує полів
  схеми **під роутером** (перевірено `grep model_fields tests/contract`).
- Cloud Run `--timeout 3600` (`docs/deploy.md`): запит SSE на ~2 хв уміщується.

## Out of scope (deliberately)
- Фонове завдання, черга, Gemini Deep Research (ADR-0006).
- Кнопка «досліди глибоко» — глибину визначає розмова (feature).
- Живий показ кроків окремими подіями SSE — кроки йдуть текстом у тому самому потоці дельт.
- Повтор окремого пошукового виклику, що впав (його просто немає у звіті).
- Окрема сторінка звіту (feature Deferred).

## Seam (contract)
`src/thinkhow/platform/llm.py`:
- `Llm.search_text(self, system: str, prompt: str, rev: KnowledgeRev | None) -> tuple[str, Found | None]` — новий метод
  протоколу. `VertexLlm.search_text`: `generate_content` з `system_instruction`, **без** JSON-схеми, з
  `tools=[enterprise_web_search]` (завжди — це пошуковий виклик), ті самі повтори й межа часу, що в `generate_json`;
  `Found` — тим самим правилом S1 (запити й джерела без повторів, останні suggestions), розгорнуті `resolve` (S1b);
  один `llm_call` з `search: true`. Модель не відповіла → `LlmUnavailable`. `resolve` є лише в екземпляра з
  `search=True` — саме його бере застосунок (`web/app.py`).
- `ScriptedLlm(script, chunk=7, found_script=None, search_script: SearchScript | None = None)`;
  `SearchScript = Callable[[str, str], tuple[str, Found | None]]`; без `search_script` — `("", None)`.

`src/thinkhow/facilitation/types.py`:
- `class DeepPlan(_Frozen)`: `intro: str (min_length=1)`, `questions: list[str] (2–4 елементи, кожен непорожній)`.
- `class DeepReport(_Frozen)`: `report: str (min_length=1)`, `facts: list[str]` — лише тексти нових фактів (без `op`,
  `id`, `turn`); пункти карти з них будує код (Q9).
- `RouterAnswer.deep_question: str | None = None` (у `route.py`; правило `_fits_its_action`: `deep_question` — лише при
  `answer`; `reply` роутера при `deep_question` ігнорується, як і при `answer`). Скрізь (роутер і фасилітатор) порожній чи пробільний `deep_question` — те саме, що `None` (рядок
  обрізається; порожній → `None`).

`src/thinkhow/facilitation/deep.py` (новий):
- `def deep_research(question: str, ctx: FacilitationContext, llm: model.Llm, rev: model.KnowledgeRev, taken:
  frozenset[str] = frozenset()) -> Iterator[ReplyDelta | DeepDone]` — `taken` — `id` з `map_updates` першої відповіді
  (передає `with_deep`; на шляху роутера порожній) — Flow:
  1. план: `llm.generate_json(PLAN_RULES + мова, contents, DeepPlan, rev)`, де `contents` = `frame(ctx)` (історія сесії,
     карта, репліка людини), а до останнього повідомлення дописано `"\n\n[Питання дослідження]\n" + question` (одна
     повторна спроба невалідного, далі `FacilitationError`);
  2. дельта кроків: `intro` + `"\n"` + рядки `- <підпитання>` (мовою людини — її дає план);
  3. пошуки паралельно (`ThreadPoolExecutor`, по одному на підпитання; результати збираються **в порядку підпитань** — за
     поданими `submit` по порядку): `llm.search_text(SEARCH_RULES + мова, підпитання, rev)`; виклик, що кинув `LlmUnavailable`,
     пропускається; усі впали → `LlmUnavailable`. Кожен пошук іде в контексті того, хто кличе: `executor.submit(contextvars.copy_context().run,
     search, q)` на підпитання, результати — у порядку підпитань; так `request_id` (`ContextVar`, `platform/log.py`)
     є в кожному рядку `llm_call` пошуків (без копії контексту потоки його не бачать — проба critic-а 2026-10-25).
     Клієнт genai і `httpx.head` з кількох потоків безпечні (PR-19: `deep_wge.py` — один клієнт під
     `ThreadPoolExecutor(4)`); `search_text` усередині розгортає посилання своїм пулом (S1b) — вкладені пули безпечні;
  4. звіт: `llm.generate_json(REPORT_RULES + мова, [Turn("user", питання + знахідки кожного підпитання)], DeepReport,
     rev)` без пошуку (одна повторна спроба, далі `FacilitationError`); дельта: `"\n\n" + report`;
  5. дельта рядка джерел — `sources_line` (S1) над об'єднанням джерел усіх пошуків (без повторів за `url`, у порядку
     підпитань);
  6. пункти карти: на кожен факт звіту — `MapUpdate(op="add", type="fact", text=факт, turn=f"t{ctx.turn_no}",
     id=f"d{ctx.turn_no}-{k}")`, де `k` — найменше ціле від 1, з яким `id` ще немає ні в карті, ні в `taken`, ні
     серед уже доданих звітом (ні `update`, ні `remove` звіт не робить);
  7. `DeepDone(text, map_updates, event)` — `text` = усе, що пішло дельтами в кроках 2, 4, 5: кроки, `"\n\n"`, звіт,
     тоді рядок джерел зі своїм початком `"\n\nДжерела: "` (порожній, коли джерел немає), `event` = `ResearchEvent(depth="deep", queries=усі запити пошуків, sources=об'єднання, suggestions_html=
     останні непорожні, question=question, report=report)`.
- `@dataclass(frozen=True) class DeepDone: text: str; map_updates: tuple[MapUpdate, ...]; event: ResearchEvent`.
- `def with_deep(items, deep_question: Callable[[], str | None], ctx, llm, rev) -> Iterator[...]` — `deep_question`
  читається, **коли з `items` прийшло оновлення** (у `lead` це значення, яке `fill` зняв під час `settle`; ледачий
  генератор інакше дав би `None`) — притримує оновлення з `items`;
  без `deep_question` — нічого не змінює; з ним — передає далі дельти й події `items`, тоді дельти `deep_research`
  (перша з `"\n\n"` попереду, коли до неї вже був текст), тоді `ResearchEvent(deep)`, тоді оновлення з `reply` =
  попередній `reply` + `"\n\n"` + `DeepDone.text` і `map_updates` = попередні + звітові.
- `deep.md` — три правила (план, пошук, звіт), кожне — розділ `## План`, `## Пошук`, `## Звіт`:
  - План: «Розклади питання на 2–4 підпитання для пошуку в інтернеті, кожне — коротке речення мовою людини. intro —
    одне речення людині, що ти досліджуєш і що це займе близько двох хвилин.»
  - Пошук: «Знайди факти з джерелами на це підпитання. Коротко, з числами, назвами й датами.»
  - Звіт: «Склади стислий звіт людині на її питання з цих знахідок: що відомо, з числами; де джерела розходяться — скажи
    так. Без посилань у тексті (джерела система допише сама). Не радь, що їй робити, і не оцінюй її варіантів.
    Закінчи одним питанням до людини: що з цього для неї важливо далі. У facts — кожен факт, на який вона
    спиратиметься, одним реченням, з числом чи назвою, без посилань.»

`src/thinkhow/facilitation/research.md` — **між** текстом S1 і останнім рядком S2 вставлено одне речення (без
заголовка; воно вірне на обох шляхах — і фасилітатора, і `answer_fact`, бо згоду людини там ловить роутер):
```
Коли питання багатогранне (ринок, кілька шляхів, порівняння) і швидкого пошуку замало, запропонуй людині глибоке
дослідження: скажи, що це займе близько двох хвилин, і спитай, чи шукати.
```
`src/thinkhow/facilitation/deep_field.md` (новий) — розділ лише для фасилітатора під роутером (`system_instruction(...,
routed=True)` додає його **після** `RESEARCH_SECTION`, перед «# Картка»):
```
# Глибоке дослідження
Коли людина погодилась на глибоке дослідження або сама просить дослідити глибоко — постав питання дослідження в
deep_question (одне речення: що саме з'ясувати), а в reply коротко скажи, що починаєш. Інакше deep_question — null.
```
`answer_fact` цього розділу не отримує: його схема `FactAnswer` поля не має (Q8).

Фасилітатор під роутером (`respond.py`):
- `lead` під роутером стрімить схему `routed_answer_schema(card)` = `answer_schema(card)` + `deep_question: str | None =
  None` (останнім полем), повтор лише оновлення — `update_schema(card)` + те саме поле; `fill` знімає `deep_question` з
  полів (у `FacilitatorUpdate` його немає) і запам'ятовує; далі `with_deep(with_research(settled, found), deep_question,
  …)` — `with_deep` працює **всередині** `lead`, тож `converse._lead_card` бачить оновлення вже після глибоких подій, і
  `RoutingEvent` кінця картки (якщо є) іде після `ResearchEvent(deep)`, перед оновленням. Без роутера — схеми й вихід
  `lead` байт у байт як досі.

Шлях роутера (`converse.py`, `route.py`, `router.md`):
- `router.md`, пункт `"answer"` доповнено **після** його останнього речення («…не "answer", а "offer" чи "ask".»; текст
  пункту S2 лишається суцільним): «Так само "answer" — коли людина погоджується на глибоке дослідження, яке
  щойно запропоновано, або сама просить дослідити глибоко, а картки не обрано: тоді deep_question — одне речення, що
  саме з'ясувати.»
- `converse` на `answer` з `deep_question`: замість `answer_fact` — `deep_research` одразу (без першого виклику),
  тоді `ResearchEvent(deep)` і `FacilitatorUpdate(reply=DeepDone.text, current_phase_id=None, phase_exit_met=False,
  map_updates=звітові)`. На `answer` без `deep_question` — `answer_fact`, як у S2.

`src/thinkhow/web/local.py`: `local_search(system, prompt)` — заготовка: текст «(локально) знайдено: <prompt>», `Found` з
`example.org`. `platform/llm.py`: `make_llm(..., search_script: SearchScript | None = None)` — локально
`ScriptedLlm(..., search_script=search_script)`; `web/app.py` передає `search_script=local_search`.

- Errors: план чи звіт невалідні двічі → `FacilitationError` → `Failed`; усі пошуки впали → `LlmUnavailable` →
  `Failed`; один пошук впав — звіт з решти. На `Failed` нічого не пишеться (як досі) — показані дельти губляться, людина
  тисне «Спробуйте ще раз».
- Dependencies (injected): `llm` (і `search_text`), `rev`.
- Does NOT do: фонові завдання, повтор окремого пошуку, кнопку, окрему сторінку.

## Decisions (with WHY)
- Q1: `deep_question` — у схемі фасилітатора **під роутером** і в `RouterAnswer`, а не в `FacilitatorUpdate`/
  `FactAnswer`, як писав контракт feature-а — chosen because запечатані тести фіксують поля схеми без роутера, саму
  `FactAnswer` і її повтори (Premise verified); роутер уже бачить, що людина погоджується, коли картки немає. Rejected:
  поле в `FacilitatorUpdate` — ламає `test_skelf_respond.py:155`; поле в `FactAnswer` — ламає `test_fa_converse.py:178`.
  Відхилення від контракту feature-а — у місці поля, не в поведінці: обидва шляхи (картка і «answer») досяжні.
- Q2: цикл у тому самому запиті, поки оновлення притримане — chosen because `workspace` і `converse._lead_card` читають
  до першого оновлення, а `conversation.md` пишеться з `reply` (feature critic раунд 1 #2); ~2 хв уміщуються в
  `--timeout 3600`. Rejected: фонове завдання (найсильніше: людина не прив'язана до відкритого потоку на ~2 хв, і обрив з'єднання нічого
  не губить) — черга і другий записувач розмови заради 2 хв (ADR-0006).
- Q3: звіт — `generate_json` без пошуку, лише зведення знайденого — chosen because знахідки вже є, а ще один пошук
  додав би час і ціну; модель лишається тією самою (P4 — якість ведення важливіша за швидкість, і тут вона не
  страждає). Rejected: звіт з пошуком — повторні пошуки того самого.
- Q4: кроки й `intro` пише план мовою людини, без фіксованого «Шукаю:» — chosen because C4 (відповідь мовою людини), а
  фіксований український рядок порушив би його для польської чи англійської. Rejected: фіксований текст кроків.
- Q5: 2–4 підпитання (`DeepPlan.questions` 2–4, як і правило плану) — chosen because саме так перевірено PR-19 (129–137 с); це межа схеми,
  не поріг для людини (feature Build parameters, `PROVISIONAL`, ціна розвороту — число в схемі). Rejected: без межі —
  модель може дати 10 підпитань і 5 хв.
- Q6: один пошук, що впав, — пропуск, усі впали — `LlmUnavailable` — chosen because звіт з трьох знахідок кращий за
  жоден, а без знахідок звіту немає з чого скласти. Rejected: повтор окремого пошуку — довше, і `VertexLlm` уже
  повторює виклик сам.
- Q7: на шляху роутера глибоке — одразу, без першого виклику `answer_fact` — chosen because людина вже погодилась, і
  ще одна коротка відповідь перед циклом лише додала б час; `intro` плану каже, що почалося. Рішення лишається
  `Decision(kind="answer")`, і на наступних репліках роутер читає його як «answer (відповідь фактом)» — прийнято
  свідомо: глибоке на шляху роутера — теж відповідь фактами, без способу думати. Rejected: спершу
  `answer_fact` з полем — неможливо без зміни `FactAnswer` (Q1).

- Q8: правило поля `deep_question` — окремим розділом лише в інструкції фасилітатора під роутером, а в спільному
  `research.md` — лише речення «запропонуй глибоке» — chosen because `research.md` іде і в `answer_fact`, чия схема
  `FactAnswer` поля не має: там модель обіцяла б «починаю», а цикл не запускався б. Згоду на шляху `answer` ловить
  роутер (`router.md`). Rejected: усе правило в `research.md` — обіцянка без дії на шляху S2; правило в `routed.md` —
  той файл про кінець картки, і змішав би дві причини змін.
- Q9: звіт повертає лише тексти фактів, а `id` і `turn` пунктів дає код — chosen because виклик звіту не бачить карти й
  номерів, а `add` з чужим `id` мовчки замінює пункт людини (`workspace._apply_one`); код знає карту і номер репліки.
  Rejected: дати звіту карту й правило `id` (як фасилітатору) — модель усе одно може влучити в наявний `id` чи
  зробити `update`/`remove` пунктів людини.
## Hardest seams (test-confidence points)
- **Seam 1: глибоке під карткою, весь шлях** — через `workspace.reply` з `ScriptedLlm`, де потік фасилітатора дає
  `deep_question`, план — 3 підпитання, пошуки — свої `Found`, звіт — з фактами. Що видно на рівні `workspace`:
  послідовність текстів `Delta` (відповідь → рядок джерел першого виклику, якщо він шукав → кроки → звіт → рядок
  джерел циклу); `conversation.md` = з'єднані дельти (після тієї самої `normalize`, що в S1); `research.json` — запис
  `deep` з `question`, `report`, запитами й джерелами всіх пошуків (після запису `quick`, коли перший виклик шукав);
  `map.json` — факти звіту; `routing.json` — рішення кінця картки, коли фаза остання (доказ, що `RoutingEvent` не
  загубився за оновленням). На рівні генератора `respond` (під роутером): кожна подія глибокого (`ResearchEvent`) і
  `RoutingEvent` кінця картки — **перед** `FacilitatorUpdate`; порядку між ними тест не перевіряє (його дає `_lead_card`). Карта з пунктом
  `d<N>-1`, звіт з двома фактами → `d<N>-2` і `d<N>-3`, обидва в `map.json`, наявний пункт лишається (I4).
  Інструкція `answer_fact` не містить `deep_question`; інструкція фасилітатора під роутером містить розділ
  «# Глибоке дослідження» після «# Факти про світ». Anti-pattern: тест `deep_research` окремо від `lead`.
- **Seam 2: глибоке на шляху роутера** — роутер дає `answer` з `deep_question` → `answer_fact` не кликано, перший потоковий
  виклик відсутній; на рівні `converse`: `RoutingEvent(answer)` першим, `ResearchEvent(deep)` перед оновленням з
  `current_phase_id=None`; через `workspace`: дельти кроків, звіту, джерел, `routing.json` з `answer`, `research.json`
  з `deep`. Роутер з `deep_question` при дії, іншій за `answer`, → помилка валідації (одна повторна
  спроба, як для інших правил дій). Anti-pattern: перевірити лише, що цикл почався.
- **Seam 3: паралельні пошуки і їхні невдачі** — фейковий `search_text`, де всі пошуки чекають на спільному
  `threading.Barrier(n, timeout=…)` (у пулі не менше потоків, ніж підпитань — `max_workers >= len(questions)`) (послідовна реалізація падає на `BrokenBarrierError`, тест червоний), а перший
  підпитання ще й чекає на подію, яку ставлять інші (закінчується останнім), → результат і джерела — у порядку
  підпитань, не завершення (I2); один кидає `LlmUnavailable` (спершу дійшовши до
  бар'єра, щоб решта не чекала до межі часу) → звіт з решти, у звіті
  немає його знахідок; усі кидають → `Failed`, жодного файлу не змінено, крім репліки людини. Кожен рядок `llm_call` пошуків
  має `request_id` запиту (тест ставить `log.request_id` перед тим, як читати потік відповіді). Anti-pattern: послідовна реалізація.
- **Seam 4: нічого не змінилось без `deep_question`** — `lead` без роутера — схеми й події байт у байт як до slice-а
  (запечатані тести); `lead` під роутером з `deep_question: null` — ті самі події, що в S1; `answer` без
  `deep_question` — `answer_fact` (запечатані тести S2). Anti-pattern: лише новий шлях.
- **Seam 5: `VertexLlm.search_text`** — фейковий клієнт genai: конфіг з `enterprise_web_search` і без
  `response_json_schema`; `Found` з метаданих; `resolve` застосовано; `llm_call` з `search: true`; повтор після
  тимчасової помилки; спроби вичерпано → `LlmUnavailable` (не `("", None)`). Anti-pattern: перевіряти лише текст.

## Invariants (rules that hold for every input in the stated domain)
- **I1** — Текст, показаний людині потоком, дорівнює записаній відповіді — і з глибоким дослідженням.
  - Domain: кожна відповідь з `deep_question` (під карткою і на шляху роутера), з першим `found` і без, з будь-якою
    кількістю підпитань 2–4 і будь-якою частиною пошуків, що впали (не всіма).
  - Source: feature, Inter-slice contracts, S3 — «`reply` = перша відповідь + рядки … + звіт + рядок джерел (показане
    наживо = записане)».
  - Broken by: звіт лише в `reply`, без дельти; кроки лише в потоці; роздільники різні в потоці і в `reply`.
- **I2** — Джерела глибокого запису — об'єднання джерел пошуків, що вдалися: кожна адреса рівно раз, у порядку
  підпитань, і жодного джерела пошуку, що впав.
  - Domain: будь-які `Found` пошуків (з повторами між підпитаннями, порожні, `None`), будь-яка частина впалих пошуків.
  - Source: цей контракт, Seam крок 5; S1 I3 — «кожну адресу … рівно один раз, у порядку першої появи».
  - Broken by: джерела лише першого пошуку; порядок завершення потоків; повтори між підпитаннями.
- **I3** — Без `deep_question` жоден виклик плану, пошуку чи звіту не робиться.
  - Domain: будь-яка відповідь фасилітатора (з роутером і без) і будь-яка відповідь `answer` з `deep_question` —
    `null`, порожнім чи пробільним рядком.
  - Source: feature — «ставити питання лише коли людина погодилась чи сама попросила»; Seam `with_deep` — «без
    `deep_question` — нічого не змінює».
  - Broken by: цикл на порожньому рядку `deep_question: ""`; цикл на кожній відповіді з `found`.

- **I4** — Зміни карти від звіту — лише `add` пунктів `fact`, кожен з `id`, унікальним серед карти, `map_updates`
  першої відповіді цієї ж репліки і решти `add` звіту; жоден наявний пункт ними не замінюється, і кожен факт звіту — окремий
  пункт у `map.json` (два однакові тексти — два пункти).
  - Domain: будь-яка карта (зокрема з `id` виду `d<N>-<k>`), будь-які `map_updates` першої відповіді і будь-які `facts`
    звіту (порожні, з повторами).
  - Source: Q9; `workspace._apply_one` — `add` з наявним `id` замінює пункт.
  - Broken by: `id` за лічильником без перевірки карти; той самий `k` для кожного факту (рахується один раз);
    `map_updates` звіту від моделі.

## Exit criterion
- `uv run pytest -q` зелений: нові тести (Seams 1–5, I1–I4) і всі запечатані тести без змін; `uv run ruff check src
  scripts tests` і `uv run mypy` — кожен окремою командою, чисті.
- Live (закриває slice, AC3): `tests/live/test_research_deep_live.py` (`live`, ADC, `make_llm(..., search=True)`,
  локальна тека, через `workspace.reply`): тема з обраною карткою `weighted-matrix`, історія — репліки власника #1–#16
  з bucket (як `test_research_live.py`), де відповідь моделі на #16 **замінено** пропозицією глибокого дослідження,
  записаною в тест («Можу глибше дослідити, як Mittelstand купує консалтинг і де швидше перші гроші — це близько двох
  хвилин. Шукати?»; так немає двох реплік моделі поспіль); репліка людини «Так, досліди.». Умови (усі — тест):
  - відповідь має кроки (`intro` і щонайменше два рядки `- <підпитання>` перед звітом), звіт і рядок «Джерела:»;
  - `research.json` має запис `deep` з непорожніми `question`, `report`, `queries`, `sources`;
  - вивід `.engine/artifacts/spikes/research-deep-live-<час>.txt` містить загальний час відповіді, `latency_ms` і токени
    кожного `llm_call` (пошукові теж), кількість пошукових запитів і ціну за прайсом PR-19 — модель і пошук окремо ($14 за 1 000 понад 5 000
    безплатних, і без них), лише значення, без порогу (P4).
  Записується (не умова): який шлях пройшов (останнє рішення `routing.json`), скільки підпитань дав план, чи текст
  перед «Джерела:» закінчується питанням; пункти `fact` у `map.json`; чи остання
  відповідь у `conversation.md` = з'єднані дельти (I1 на справжній моделі). Червоний live (будь-яка умова вище) —
  slice **не закрито**, AC3 не виконано: причину — у вивід, правило (`deep_field.md` / `research.md` / `router.md`) чи
  код виправити і зробити рівно один новий прогін після виправлення; прогін без змін ще раз — заборонено; не
  виправляється — пункт на дошку.

## Deferred to later slices
- Інші реалізації `Llm` без `search_text` (`scripts/router_eval.py`, запечатані фейки) — до глибокого шляху вони не
  доходять (немає `deep_question`) — revisit trigger: сценарій `router_eval` чи тест, що дає `deep_question`.
- Збереження часткового результату, коли цикл впав посередині — why later: людина тисне «Спробуйте ще раз», і цикл іде
  знову — revisit trigger: `Failed` після показаних дельт у live S4, або власник про це каже.
- Живий показ кроків окремими подіями (а не текстом) — why later: текст кроків уже показує, що шукають — revisit
  trigger: власник хоче бачити прогрес інакше.
- Глибоке через розгорнутий сервіс (тиша в потоці ~100 с між кроками і звітом; ризик — простій з'єднання за Cloud
  Run, не `--timeout`) — why later: це S4 і розгортання (контракт feature-а S3 → S4) — revisit trigger: S4.
- Глибоке на шляху роутера live — why later: AC3 вимагає хоч одне наскрізне; шлях роутера перевіряють контрактні тести
  — revisit trigger: S4 (живий прогін розмови власника) чи власник.

## Open items requiring human decision (if any)
- (немає)

## Critic notes (non-blocking)
- Phase 2, раунд 1 (`CRITIC_REVISE`): правило поля — окремий розділ лише під роутером (Q8); нотатки: порожній
  `deep_question` = `None`, відхилення від контракту feature-а записано в feature-артефакті, `with_deep` усередині `lead`.
- Phase 2, раунд 2 (`CRITIC_REVISE`): звіт повертає лише тексти фактів, пункти карти будує код (Q9, I4); нотатки: що
  йде в план (`frame` + питання), порядок результатів, потоки, `reply` роутера — враховано.
- Phase 2, раунд 3 (`CRITIC_REVISE`): `request_id` у потоках — копія контексту на кожен пошук (проба critic-а);
  нотатки: `deep_question` читається з `fill` після `settle`, `make_llm`/`app.py` для `search_script`, Q7 свідомо,
  steelman фонового завдання, порядок Q — враховано.
- Phase 2, раунд 4 — `CRITIC_PASS`; нотатки («передає далі», вкладені пули, інші `Llm` без `search_text`) — враховано.
- Phase 3, раунд 1 (`CRITIC_REVISE`): Seam 3 — спільний `Barrier` і перший пошук останнім; I4 — про зміни звіту; Exit — I1–I4.
- Phase 3, раунд 2 (`CRITIC_REVISE`): I4 — унікальність серед `add` звіту, кожен факт окремо; нотатки (порожній `deep_question`
  в I3, `deep_question` при іншій дії, бар'єр перед винятком) — враховано.
- Phase 3, раунд 3 (`CRITIC_REVISE`): Seam 1 — що видно на рівні `workspace` і генератора `respond`; нотатки (потоків не
  менше, ніж підпитань; два записи quick+deep; `normalize`) — враховано.
- Phase 3, раунд 4 — `CRITIC_PASS`; нотатки (порядок не перевіряється, вичерпані спроби, `request_id` перед читанням) — враховано.
- Phases 4–5, раунд 1: Phase 4 `CRITIC_REVISE` — червоний live = не закрито, одне виправлення і один прогін; Phase 5
  `CRITIC_PASS`; нотатки (заміна #16, тригер, розгорнутий сервіс у S4, записи fact/I1) — враховано.
- Phase 4, раунд 2 (`CRITIC_REVISE`): час і ціна у виводі — умова (AC3); нотатки (непорожні `queries`, кроки визначено,
  питання наприкінці — запис) — враховано.
- Phase 4, раунд 3 — `CRITIC_PASS`; нотатки (шлях і число підпитань у виводі, ціна пошуку окремо) — враховано.
- Cold reader (`CRITIC_REVISE`): `taken` у підписі `deep_research`; нотатки (роздільники тексту, 2–4 підпитання, місце речення
  в `router.md`, `resolve` лише з пошуком) — враховано.
- Cold reader, раунд 2 — `CRITIC_PASS`; нотатки (дельта звіту з `\n\n`, `submit` замість `map`) — враховано. Фази 2 і 3
  дійшли до 4-го раунду: кожен раунд — нова вада, жодного коливання між двома позиціями.
