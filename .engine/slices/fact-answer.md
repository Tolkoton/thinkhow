# Slice fact-answer — planning artifact

Feature: `.engine/architecture/feature/research-in-conversation.md`, S2 (block quick). Driven mode, unattended: frame
supplied by the feature artifact, not asked. Depends on S1 `research-quick` (DONE: `Found`, `with_research`,
`sources_line`, `ResearchEvent`, `research.md`) and S1b `research-display` (DONE).

## Goal
Пряме фактичне питання людини, коли способу думати ще не обрано («Скільки коштує новий Škoda Octavia Combi у
Німеччині?»), отримує відповідь фактом з джерелом, без ведення моделлю мислення (N1 v5, приклад власника: «можна
просто загуглити… і сказати мені. То не треба мене ганяти по мисленевих моделях»; feature AC2). Роутер ставить нову
дію `answer`, і один потоковий виклик з пошуком відповідає коротко, з рядком джерел, одним питанням і пунктом `fact` у
карті. Заодно — правило «`fact` лише для знайденого» (знахідка live S1: на #25 модель поклала факт про людину в `fact`).
Вимірна ціль: pytest зелений (запечатані тести — без змін); live на `eu`: нова тема, перша репліка — пряме питання про
ціну → `routing.json` з `kind: "answer"`, відповідь з рядком «Джерела:», `research.json`, пункт `fact`; ситуація, яку
треба продумати («Не можу вирішити, чи переходити на нову роботу»), → не `answer` (записується, рішення моделі — PR-18).

## Premise verified
- Роутер — `generate_json` без інструмента (S1, I4); `route` повертає `RouterAnswer` з `action ∈ {offer, ask, choose}`;
  `converse` на `offer`/`ask` віддає `RoutingEvent`, текст роутера і `FacilitatorUpdate` з `current_phase_id=None`
  (`facilitation/converse.py`). Запечатані тести роутера читають `ROUTER_RULES` з коду (`test_rt_route.py:26`,
  `:142`), тож текст `router.md` можна доповнити; жоден запечатаний тест не перелічує дій поіменно.
- `current_card(routing)` — картка лише після останнього `choose` (`types.py`); `web.method` реагує лише на `choose` і
  `end` (`web/method.py:34-36`) — `answer` без позначки методу, підпис «вільна розмова».
- `scripts/router_eval.py` міряє будь-яку дію як рядок (`action: str`) — нова дія його не ламає.
- Запечатаний `tests/contract/research_quick/rq_fakes.py` містить текст `research.md` і перевіряє `RESEARCH_SECTION in
  routed` та `lines.count("# Факти про світ") == 1` (`test_rq_respond.py:109-121`) — рядок, дописаний **після**
  останнього рядка розділу, ці перевірки не ламає.
- Live S1 і S1b (`research-quick-live-…084129Z.txt`, `research-display-live-…091556Z.txt`): той самий пряме питання
  про ціну під карткою дав відповідь з 4 джерелами і пунктом `fact` — потоковий виклик з пошуком на нього відповідає.
- PR-18 (роутер ставить `answer` влучно) — `unverified`; перевіряє live цього slice-а (лише записується).

## Out of scope (deliberately)
- Глибоке дослідження (`deep_question`, цикл, «погодився на глибоке → answer») — S3.
- Пошук у виклику роутера — роутер лишається без інструмента (S1, I4).
- Відповідь фактом посеред обраної картки — це шлях фасилітатора з правилом «Факти про світ» (S1); `answer` — лише
  коли картки немає (останнє рішення не `choose`).
- Нова позначка методу на сторінці для `answer`.
- Поріг влучності роутера на `answer` (власник порогів не ставив).

## Seam (contract)
`src/thinkhow/facilitation/types.py`:
- `Decision.kind: Literal["offer", "ask", "choose", "end", "answer"]` (додано останнім).

`src/thinkhow/facilitation/route.py`:
- `RouterAnswer.action: Literal["offer", "ask", "choose", "answer"]`; правило `_fits_its_action`: `answer` — `card_id`
  має бути `None` (кандидати — будь-які 0–3, як ранжування; `reply` ігнорується).
- `_decision_line`: `answer` → `- репліка #N: answer (відповідь фактом)`.
- `router.md` доповнено (після рядка про `ask`, перед «why відповіді») пунктом:
  ```
    - "answer" — коли людина прямо питає факт про світ, який можна знайти (ціна, строк, правило, як це зазвичай
      роблять), а способу думати ще не обрано, і сама відповідь фактом — те, чого вона хоче. reply — null; card_id —
      null. Якщо за питанням стоїть рішення, яке треба продумати, — не "answer", а "offer" чи "ask".
  ```
  і в «Правила» рядком: `- В "ask" не питай людину фактів про світ, які можна знайти: для них є "answer".`

`src/thinkhow/facilitation/answer.py` (новий):
- `def answer_fact(ctx: FacilitationContext, knowledge: CurrentKnowledge, llm: model.Llm) -> Iterator[ReplyDelta |
  FacilitatorUpdate | ResearchEvent]` — Flow: інструкція → один `llm.stream_json(system, contents, FactAnswer, rev)` →
  дельти далі → settle (як у `lead`, той самий повтор: невалідний JSON з показаним текстом → `generate_json` лише
  `map_updates`; без показаного — повний `generate_json`) → `with_research(…, found)` (S1).
- `class FactAnswer(_Frozen)` і `class FactUpdate(_Frozen)` (`map_updates` лише) — обидва в `types.py`, поруч із `FacilitatorUpdate`; `answer.py`
  їх імпортує. `FactAnswer`: `reply: str (min_length=1)` першим, `map_updates: list[MapUpdate]`. Оновлення, яке
  віддається: `FacilitatorUpdate(reply=…, current_phase_id=None, phase_exit_met=False, map_updates=…)`.
- `system` = `ANSWER_RULES` (`answer.md`) + `"\n\n# Мова відповіді\n" + language_rule(ctx.language) + "\n\n" +
  RESEARCH_SECTION + "\n"`. `contents` — історія сесії, тоді рамка `[Карта проблеми зараз]` + карта і `[Репліка людини #N]` + текст — без
  рядка вільного режиму (`FREE_MODE_LINE`) і без стану роутера.
- `answer.md`:
  ```
  Ти — ThinkHow. Людина прямо питає факт про світ. Знайди його в інтернеті й відповідай коротко, фактом: два-чотири
  речення своїми словами, з числами чи назвами, без посилань у тексті (джерела система допише сама). Не радь, що їй
  робити, і не оцінюй її варіантів: рішення лишається за нею. Наприкінці — одне питання: що з цим фактом для неї
  важливо далі. Знайдений факт коротко додай у map_updates пунктом типу «fact» (id нового пункту — новий, напр. «i3»;
  turn — «t<номер з рамки репліки>»).
  ```

`src/thinkhow/facilitation/settle.py` (новий; не імпортує ні `respond`, ні `converse`, ні `answer` — залежності йдуть
в один бік: `converse` → `answer` → `settle`, `respond` → `settle`):
- сюди переїжджають з `respond.py` без зміни поведінки: `settle` (колишній `_settle`, узагальнений), `with_research`,
  `sources_line` (з `_title`, `_url`), `_research`, `SOURCES_HEAD`, `RESEARCH_SECTION`, `_parse`, `_retry`, `_plain`.
- `settle(llm, system, contents, rev, shown, raw, full: type[BaseModel], update_only: type[BaseModel], retry_ask: str,
  fill: Callable[[dict[str, Any]], dict[str, Any]])` — повна схема, схема «лише оновлення», текст прохання повтору і
  функція, що доповнює поля до `FacilitatorUpdate`. `lead` передає схеми картки, `RETRY_ASK` і тотожну `fill` —
  поведінка `lead` байт у байт як досі; `answer_fact` — `FactAnswer`, `FactUpdate(map_updates)`, `FACT_RETRY_ASK`
  («Поверни лише зміни карти до своєї відповіді вище.») і `fill`, що додає `current_phase_id=None`,
  `phase_exit_met=False`.
- `respond.py` імпортує їх із `settle.py` і далі експортує `sources_line`, `lead`, `RESEARCH_SECTION` явно (`from
  … import sources_line as sources_line`, бо mypy `strict` вимикає неявний реекспорт; запечатані тести імпортують
  `lead` і `sources_line` з `respond`).
- `frame(ctx, state: str = "")` — рамка останньої репліки (`[Карта проблеми зараз]` + карта, `state`, `[Репліка людини
  #N]` + текст) теж переїжджає в `settle.py`: `respond` передає свій рядок вільного режиму, `answer_fact` — нічого; `_state` і `FREE_MODE_LINE` лишаються в
  `respond`.
- `scripts/card_conversations.py:228` — `answer` позначається як «роутер», не «фасилітатор».

`src/thinkhow/facilitation/converse.py`:
- на `answer`: `RoutingEvent(Decision(kind="answer", card_id=None, …))`, тоді потік `answer_fact(ctx, knowledge, llm)`
  (дельти, `ResearchEvent`, оновлення). Рішення `answer` не змінює `current_card` — на наступній репліці знову роутер.

`src/thinkhow/facilitation/research.md`: дописано **останнім рядком**:
`Пункт «fact» — лише для знайденого пошуком; що людина розповіла про себе — не «fact».`

- Errors: як у `lead` — модель не відповіла → `LlmUnavailable` → `Failed`; невалідна двічі → `FacilitationError`.
- Dependencies (injected): `llm`, `knowledge` — як досі.
- Does NOT do: глибоке, пошук у роутері, «answer» під обраною карткою, позначка методу.

## Decisions (with WHY)
- Q1: роутер лише позначає `answer`, а відповідає окремий потоковий виклик з пошуком — chosen because роутер — це
  `generate_json` без інструмента (I4, feature critic раунд 1 #3), а відповідь людині має йти потоком з джерелами тим
  самим шляхом, що в S1 (`with_research`). Rejected: роутер з інструментом відповідає сам у `reply` — немає потоку,
  джерел і пошуку на кожному виклику роутера (ціна й час на кожну першу репліку).
- Q2: окрема коротка інструкція `answer.md`, а не картка — chosen because відповідь фактом не веде фазами, і власник
  прямо сказав «не треба мене ганяти по мисленевих моделях»; правила фасилітатора («без готових відповідей», фази) тут
  суперечили б N1 v5. Rejected: фасилітатор з `pre-mortem` — веде моделлю мислення; вільний режим (найсильніше: без
  нового файлу інструкції, код уже під тестами) — `rules.md` каже «Без готових відповідей… не давай порад» і веде
  загальними кроками до вибору, тобто знову «ганяє», а саме проти цього слова власника.
- Q3: `answer` не обирає картки, наступна репліка — знову роутер — chosen because після факту людина може захотіти
  подумати (тоді роутер запропонує спосіб) або спитати ще факт; P6 — людина не мусить обирати. Rejected: після `answer`
  одразу пропонувати способи — нав'язує модель мислення тому, хто лише питав факт.
- Q4: `_settle` узагальнено, а не скопійовано — chosen because повтор невалідної відповіді має бути той самий
  (показане = записане, I1 S1), і дві копії розійшлися б. Rejected: копія в `answer.py` — дублювання шляху, який уже
  має запечатані тести.
- Q8: модель на `answer` не шукала (`found` порожній) — відповідь без рядка джерел, як дала модель; пункт `fact` у
  карті лишається, як вирішила модель — прийнятий ризик поруч із PR-18, live це записує. Rejected: код викидає `fact`,
  коли `found` порожній — код вирішував би за модель, що вона знає без пошуку; і повтор з примусовим пошуком — у
  Gemini немає «обов'язково шукати» для `enterprise_web_search`.
- Q7: спільні помічники — в окремому `settle.py` — chosen because підпис `converse(ctx, knowledge, llm, lead)`
  запечатаний (5+ викликів у тестах), тож `converse` мусить імпортувати `answer_fact`, а `respond.py` імпортує
  `converse` під час завантаження: `converse` → `answer` → `respond` → `converse` — коло. Rejected: імпорт усередині
  функції `converse` — ховає коло, а не прибирає; передати `answer_fact` параметром — ламає запечатаний підпис.
- Q5: рядок «`fact` — лише для знайденого» дописано в кінець `research.md` — chosen because live S1 показав помилку
  моделі, а текст розділу запечатаний вмістом, не кінцем (`RESEARCH_SECTION in routed`). Rejected: переписати розділ —
  ламає запечатаний `rq_fakes.RESEARCH_SECTION`.
- Q6: `answer` дозволяє 0–3 кандидатів як ранжування — chosen because `router_eval` міряє «першу» з кандидатів
  (`scripts/router_eval.py:124-131`: `first` — `card_id` при `choose`, інакше перший кандидат), і
  модель може назвати способи, які підійшли б, якщо людина захоче думати далі. Rejected: заборонити кандидатів — ще
  одна причина невалідної відповіді без користі.

## Hardest seams (test-confidence points)
- **Seam 1: шлях `answer` повністю** — `converse` з фейковим `llm` (роутер дає `answer` з **непорожнім** `reply`, якого
  немає ніде в потоці й у `conversation.md`; потік — `FactAnswer` з `found`) → порядок подій: `RoutingEvent(answer)`, дельти відповіді, дельта рядка джерел, `ResearchEvent`,
  `FacilitatorUpdate(current_phase_id=None, map_updates з fact)`; через `workspace.reply` — `routing.json` з `answer`,
  `research.json`, `map.json` з `fact`, `conversation.md` = показане. Також `found` порожній чи `None`: без рядка джерел, без `ResearchEvent`, без запису в
  `research.json`, пункт `fact` лишається, `reply` = показане (Q8). Anti-pattern: тест `answer_fact` без `converse`.
- **Seam 2: після `answer` — знову роутер** — дві репліки через `workspace.reply`: перша `answer`, друга кличе роутер
  (не фасилітатора), бо `current_card` — `None`; рамка другого виклику роутера містить рядок стану `- репліка #1: answer
  (відповідь фактом)` і не містить `ask (уточнювальне питання)` (`_decision_line` мовчки малює невідоме як `ask`).
  Anti-pattern: перевіряти лише першу репліку або лише те, що роутер викликано.
- **Seam 3: інструкція відповіді фактом** — системна інструкція виклику `answer_fact` містить `answer.md`, мовне
  правило людини і розділ «# Факти про світ», і **не** містить `rules.md` фасилітатора й жодної картки. Anti-pattern:
  перевіряти лише наявність `answer.md`.
- **Seam 4: повтор невалідної відповіді** — невалідний потоковий JSON з показаним текстом → один `generate_json` зі
  схемою лише `map_updates`; без показаного — повний `generate_json`; в обох `reply` = показане (і рядок джерел); повтор лише оновлення несе `FACT_RETRY_ASK` і схему без
  `reply` і без фази (не `RETRY_ASK` і не `update_schema` картки), а
  оновлення після нього — з `current_phase_id=None`, `phase_exit_met=False`.
  Anti-pattern: лише валідний шлях.
- **Seam 5: валідність `answer`** — `RouterAnswer(action="answer", card_id="x")` → помилка валідації (одна повторна
  спроба роутера, як для інших дій); `card_id=None` з кандидатами чи без, з `reply` чи без → валідно; `ROUTER_RULES` містить пункт `"answer"` і рядок `- В "ask" не питай людину фактів про світ, які можна знайти:
  для них є "answer".`; `RESEARCH_SECTION` (з `research.md`) закінчується рядком `Пункт «fact» — лише для знайденого
  пошуком; що людина розповіла про себе — не «fact».`, а запечатані перевірки `rq_fakes` лишаються зеленими.
  Anti-pattern: лише щасливий шлях.

## Invariants (rules that hold for every input in the stated domain)
- **I1** — Після рішення `answer` чинної картки немає: `current_card` повертає `None`, і наступну репліку веде роутер.
  - Domain: будь-яка послідовність рішень теми, що закінчується `answer` (після `choose`, `end`, `offer` чи порожня).
  - Source: цей контракт, Q3; Seam — «Рішення `answer` не змінює `current_card` — на наступній репліці знову роутер».
  - Broken by: `answer` записано як `choose`; `current_card` шукає останній `choose`, а не дивиться на останнє рішення.
- **I2** — На шляху `answer` текст, показаний людині потоком, дорівнює записаній відповіді (з рядком джерел).
  - Domain: кожен виклик `answer_fact` з будь-яким потоком — валідним, невалідним з показаним текстом і без, з `found`
    чи без.
  - Source: feature, Inter-slice contracts — «показане наживо = записане»; S1 I1.
  - Broken by: рядок джерел лише в `reply`; повтор, що бере текст повторної відповіді замість показаного.
- **I3** — Інструкція виклику `answer_fact` не містить правил фасилітатора (`rules.md`) і тексту жодної картки.
  - Domain: будь-яка ревізія Знань, будь-яка мова людини, будь-яка карта.
  - Source: Q2 — «не треба мене ганяти по мисленевих моделях» (N1 v5).
  - Broken by: `answer_fact` збирає інструкцію через `system_instruction(card, …)`.

## Exit criterion
- `uv run pytest -q` зелений: нові тести (Seams 1–5, I1–I3) і всі запечатані тести без змін; `uv run ruff check src
  tests` і `uv run mypy` — кожен окремою командою, чисті.
- Live (закриває slice): `tests/live/test_fact_answer_live.py` (`live`, з ADC, `make_llm(..., search=True)`, локальна
  тека, через `workspace.reply`): нова тема, перша репліка «Скільки зараз коштує новий Škoda Octavia Combi у
  Німеччині?» → `routing.json` має рішення `answer`, відповідь з рядком «Джерела:», `research.json` з ≥1 джерелом,
  `map.json` з пунктом `fact`. Записується (не умова): друга тема, перша репліка «Не можу вирішити, чи переходити на
  нову роботу, бо там більше платять, але далеко їздити» — яку дію поставив роутер (не `answer` очікувано, PR-18).
  Обидві теми — один прогін, без повтору до зеленого: якщо на питання про ціну роутер поставив не `answer`, PR-18
  `falsified` — записати, slice не закрито, знахідка (не правка «до зеленого»); якщо `answer` без пошуку (порожній
  `found`) — теж знахідка (Q8, Deferred). Зміст відповіді (без порад, одне питання) судить власник з артефакту (P4). Вивід — `.engine/artifacts/spikes/fact-answer-live-<час>.txt` з відповідями,
  рішеннями роутера і рядками `llm_call`. Порогу часу немає (P4).

## Deferred to later slices
- «Погодився на глибоке → answer» і поле `deep_question` у `FactAnswer` — S3 (feature). Revisit trigger: S3.
- Влучність `answer` на наборі ситуацій `router_eval` — why later: нових очікуваних випадків власник не ставив —
  revisit trigger: S4 чи розмова власника покаже `answer` не там. Ціна потім: випадки `answer` у `cases.yaml` і рядок
  у звіті `router_eval`.
- Код не викидає пункт `fact`, коли `found` порожній (Q8) — gain: рішення за моделлю, без шляху примусового пошуку;
  ціна потім — один фільтр у `answer_fact` чи `with_research` — revisit trigger: будь-який live-артефакт (S2 друга тема,
  S4) показує `answer` з порожнім `found` і пунктом `fact`, або власник бачить у карті `fact` без джерела.

## Open items requiring human decision (if any)
- (немає)

## Critic notes (non-blocking)
- Phase 2, раунд 1 (`CRITIC_REVISE`): коло імпортів → `settle.py` (Q7); нотатки: свій текст повтору для `answer`, Q2
  steelman вільного режиму, рамка без рядка вільного режиму, посилання на `router_eval.py` — враховано.
- Phase 2, раунд 2 — `CRITIC_PASS`; нотатки враховано: Q8 (відповідь без пошуку), `card_conversations` знає `answer`, явний
  реекспорт, `FactAnswer` у `types.py`, одна `frame` у `settle.py`.
- Phase 3, раунд 1 (`CRITIC_REVISE`): Seam 2 перевіряє рядок стану `answer` у рамці роутера; нотатки (непорожній `reply`
  роутера, порожній `found`, текст повтору, `reply` при `answer`) — враховано.
- Phase 3, раунд 2 — `CRITIC_PASS`; нотатка: `ROUTER_RULES` містить `answer` (Seam 5) — враховано; збіг id пункту `fact` з
  наявним — ризик, що вже є у фасилітатора, не новий.
- Phases 4–5, раунд 1 (`CRITIC_REVISE` обидві): перевірка обох нових рядків правил (Seam 5); червоний live — PR-18
  falsified, знахідка; Q8 — у Deferred з тригером; ціна відкладеного `router_eval`.
- Cold reader — `CRITIC_PASS`; нотатки (місце `FactUpdate`, `_state` у `respond`, поля після повтору) — враховано.
