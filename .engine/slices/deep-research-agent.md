# Slice deep-research-agent — planning artifact

Board task `tasks/doing/314-real-deep-research.md` (the owner's words 2026-11-18, сесія Thinkhow). Standalone
/plan-slice, unattended: the frame is derived from the task, ADR-0007, the spike
`.engine/artifacts/spikes/deep-research-agent-2026-11-18/README.md` and the code; nothing was asked. Replaces the deep
cycle of the slices `research-deep`, `deep-research-confirm-first` and `deep-change-question` (own plan → 2–4
searches → report in the same request) with the real Gemini Deep Research agent running in the background.

## Goal
Глибоке дослідження в темі робить справжній агент Gemini Deep Research: план для згоди складає сам агент, після «так»
розмова йде далі, а звіт із джерелами з'являється в темі відповіддю системи, щойно готовий, і лишається там після
повернення; перезапуск Cloud Run дослідження не губить.

Вимірна ціль: (1) `uv run pytest -q` зелений — нові контрактні тести цього slice-а, запечатані тести старого циклу
замінено через tester-а (supersede); `uv run mypy src`, `uv run ruff check src tests scripts` чисті; (2) живий прогін
`scripts/live_deep_research.py` на справжньому агенті проходить усі кроки Exit criterion і пише час і ціну.

## Premise verified
Усі — spike 2026-11-18 (`.engine/artifacts/spikes/deep-research-agent-2026-11-18/README.md`, свіжість 0 днів):
- PR1. `genai.Client(api_key=…).interactions.create(agent="deep-research-preview-04-2026", input=<text>,
  agent_config={"type": "deep-research", "collaborative_planning": True}, background=True, store=True)` повертає id;
  `interactions.get(id)` за 22.6–23.0 с дає `status="completed"` і план текстом `… **Research Plan:**\n(1) …`; з рядком
  мови в input план цією мовою (run 2), без нього — англійською (run 1).
- PR2. `create(..., previous_interaction_id=<plan id>, agent_config={… "collaborative_planning": False}, background=True,
  store=True)` з input «так» запускає дослідження; `get` з іншого процесу повертає `in_progress`, потім `completed`
  (434.9 с, 18 пошуків). Звіт — текстові частини всіх кроків `model_output`, з'єднані (`output_text` — лише остання);
  джерела — Markdown-посилання `[домен](https://vertexaisearch.cloud.google.com/grounding-api-redirect/…)` у кінці
  тексту, `platform.links.resolve_link` розгортає їх у справжні адреси.
- PR3. План прив'язаний до агента: Max з `previous_interaction_id` плану стандартного агента → `400 … belongs to a
  different agent`.
- PR7. Max сам не планує: `deep-research-max-preview-04-2026` з `collaborative_planning=True` замість плану провів усе
  дослідження (458.4 с, звіт без `**Research Plan:**`; README spike, «Max does not plan»).
- PR8. Max, запущений заново (без `previous_interaction_id`) з input «розмова + `[Approved research plan]` + план +
  START», за 15 с `in_progress` (README, «Max starts fresh»). Чи звіт іде саме за планом — не перевірено до живого
  прогону (Exit criterion, крок Max).
- PR9. `get` неіснуючого id правильної форми → `NotFoundError`, `status_code == 404`; неправильної форми → 400.
- PR4. Правка: `create(previous_interaction_id=<plan id>, collaborative_planning=True, visualization="off",
  input=<правка>)` дає новий план з правкою, тією самою мовою, за 20.4 с (spike, `run2-change.*`, README §3).
- PR5. `agent_config.visualization="off"` API приймає (PR4), чи вимикає картинки на повному прогоні — не перевірено; якщо картинки все одно прийдуть, код бере лише текст (Q7) — premise не несучий.
- PR6. Vertex `global` не працює (spike §1) — тому ключ Gemini API; у Secret Manager є секрет `gemini-api-key`, у
  Cloud Run `thinkhow` його немає (крок Сонька, Deferred).

## Out of scope (deliberately)
- Підключення секрету до Cloud Run і права service account — крок Сонька (Deferred); код без ключа працює як Q10.
- Показ Markdown (заголовки, таблиці) у сторінці — текст показується як є, з посиланнями, як усі відповіді.
- Факти звіту як пункти карти (агент не дає structured output) — Deferred.
- `Llm.search_text` і його двійники в тестах — лишаються (Deferred: простота).
- Нагадування про готовий звіт — N4, не робимо ніколи.
- Скасування дослідження людиною, кілька досліджень одночасно в одній темі як окрема функція (код їх не забороняє,
  але й не показує окремо).
- PDF документів як файли для агента: текст документів теми йде в запит так, як він є в розмові (Q3).

## Seam (contract)

`src/thinkhow/platform/research.py` (новий; port + adapter + double):
- `AGENT = "deep-research-preview-04-2026"`, `AGENT_MAX = "deep-research-max-preview-04-2026"`.
- `@dataclass(frozen=True) class Planned: id: str; text: str` — `text`: частина після ОСТАННЬОГО `**Research Plan:**`
  (маркер трапляється й у луні input), обрізана; без цього маркера — увесь текст.
- `@dataclass(frozen=True) class Running`, `Ready(text: str)`, `Broken(reason: str)`; `ResearchState = Running |
  Ready | Broken`.
- `class ResearchUnavailable(Exception)`.
- `class Researcher(Protocol)`:
  - `plan(brief: str, previous: str | None) -> Planned` — створює взаємодію агента `AGENT` (завжди стандартного:
    Max не планує, PR7) з `collaborative_planning=True`, `visualization="off"`, `background=True`, `store=True`,
    `previous_interaction_id=previous` (коли не None), і чекає її кінця опитуванням `get`, поки статус `in_progress` чи `queued`; `completed` → `Planned`;
    будь-який інший статус (той самий вичерпний поділ, що в `state`), виняток SDK чи HTTP, порожній текст або понад `plan_timeout_s` → `ResearchUnavailable`.
  - `start(plan_id: str, plan: str, brief: str, deepest: bool) -> str` — не `deepest`: `AGENT` з
    `previous_interaction_id=plan_id`, input `START_INPUT`; `deepest`: `AGENT_MAX` заново, без
    `previous_interaction_id` (PR3), input `brief + "\n\n[Approved research plan]\n" + plan + "\n\n" + START_INPUT`
    (PR8). В обох (сталий рядок англійською «The plan is approved. Start the research; write the report in the
    language named in the request.»), `collaborative_planning=False`,
    `visualization="off"`, `background=True`, `store=True`; повертає її id, не чекаючи. Виняток → `ResearchUnavailable`.
  - `state(research_id: str) -> ResearchState` — один `get`. Статуси SDK (`interaction.py`: `in_progress`, `queued`,
    `completed`, `failed`, `cancelled`, `incomplete`, `budget_exceeded`, `requires_action`, будь-який інший рядок)
    класифіковано вичерпно: `in_progress`, `queued` → `Running`; `completed` → `Ready(text)`, де `text` — текстові
    частини кроків `model_output` по порядку, з'єднані, кожне посилання `grounding-api-redirect` замінене розгорнутим
    (`resolve`; `(` і `)` у розгорнутій адресі — `%28`, `%29`, щоб її ловив шаблон посилань сторінки), а порожній текст → `Broken("empty")`; КОЖЕН інший статус (зокрема `budget_exceeded`,
    `requires_action`, невідомий) → `Broken(<status>)`; «не знайдено» (виняток, чий HTTP-статус 404: `status_code` або `code`
    дорівнює 404 — обидві родини винятків SDK, PR9) → `Broken("not_found")`; інший виняток
    → `ResearchUnavailable`. Посилання розгортаються паралельно (як `llm.resolve_sources`). На кінцевому стані — рядок журналу `deep_research_finished` (id, agent, status, usage,
    created, updated).
- `class GeminiResearcher` — `__init__(client, resolve: Callable[[str], str], plan_timeout_s: float = 120.0,
  poll_s: float = 3.0, sleep=time.sleep, clock=time.monotonic)`.
- `class ScriptedResearcher` — двійник місцевого режиму і тестів: `plan` → `Planned("local-plan-<n>", "(1) <brief
  перший рядок>")`, `start` → `"local-research-<n>"`, `state` → `Ready` зі сталим текстом і одним посиланням; пише
  виклики в `calls`.
- `make_researcher(settings: Settings) -> Researcher | None`: `settings.local` → `ScriptedResearcher()`; порожній
  `settings.gemini_api_key` → `None`; інакше `GeminiResearcher(genai.Client(api_key=…), resolve_link з httpx_head)`.

`src/thinkhow/platform/config.py`: `Settings.gemini_api_key: str = ""` (`THINKHOW_GEMINI_API_KEY`).

`src/thinkhow/facilitation/types.py`:
- `PendingDeep`: `question`, `intro`, `plan: str`, `plan_id: str`, `deepest: bool = False` (запуск Max на «так»), `started: str` (усі
  непорожні рядки). Поле `questions` прибрано.
- `DeepIntro(_Frozen)` (схема виклику «Вступ», `llm_timeout_s = 60.0`): `intro: str`, `started: str`, `failed: str`
  (одне речення людині на випадок, коли запуск не вдасться: не вдалося, можна попросити пізніше), `deepest: bool`,
  `question: str | None = None`. `PendingDeep` несе й `failed: str`.
- `@dataclass(frozen=True) class DeepStarted: research_id: str; question: str; deepest: bool` — подія відповіді.
- `@dataclass(frozen=True) class DeepRunning`, `DeepReady(text: str, sources: tuple[Source, ...])`,
  `DeepBroken(reason: str)`; `Collect = Callable[[str], DeepRunning | DeepReady | DeepBroken]`.
- `DeepPlan`, `DeepReport` прибрано. `Facilitate` віддає ще й `DeepStarted`.

`src/thinkhow/facilitation/deep.py`:
- `propose(question, ctx, llm, researcher, rev, first, changed=False, previous: PendingDeep | None = None) ->
  PendingDeep` — Flow: паралельно (кожне в контексті виклику, як `_search_all` тепер) виклик «Вступ» (`generate_json`,
  `DeepIntro`, рамка з рядком першої відповіді чи правки, як тепер) і план агента: на правці —
  `researcher.plan(ctx.text, previous.plan_id)`, інакше `researcher.plan(brief(ctx, question), None)` →
  `PendingDeep` (`deepest` — з «Вступу»). Питання:
  на правці — `clean_question(intro.question) or question`, інакше `question`.
- `brief(ctx, question) -> str`: розмова (кожна репліка історії рядком «Людина:»/«Фасилітатор:» з її текстом, як
  модель її бачить, разом із текстом документів), репліка людини, `[Питання дослідження]` і рядок мови англійською «Write the research plan and the report in <ctx.language>.»
  (без мови — «in the language of the conversation»); англійською, бо агент читає його для будь-якої мови людини.
- `proposal_text(pending) = intro + "\n\n" + question + "\n" + plan`.
- `deep_agreed(pending, ctx, researcher)` → `researcher.start(pending.plan_id, pending.plan, brief(ctx,
  pending.question), pending.deepest)` → `ReplyDelta(started)`,
  `DeepStarted(id, pending.question, pending.deepest)`, `FacilitatorUpdate(reply=started, current_phase_id=фаза карти,
  phase_exit_met=False, map_updates=[])`.
- `deep_changed(pending, ctx, llm, researcher, rev)` → нова пропозиція (`propose(..., changed=True, previous=pending)`).
- `collect(researcher, research_id) -> DeepRunning | DeepReady | DeepBroken` — `state` перекладений: `Ready(text)` →
  `DeepReady(text, джерела = Markdown-посилання тексту за тим самим шаблоном, яким їх показує сторінка, кожна адреса
  раз, по порядку)`. Шаблон `LINK` переїжджає з `web/text.py` у `facilitation/types.py`; `web/text.py` бере його звідти
  (одне визначення: джерела `research.json` = посилання, які бачить людина). `ResearchUnavailable` летить далі.
- `run_deep`, `_search_all`, `_search_one`, `_findings`, `_united_*`, `_suggestions`, `_fact_items`, `DeepDone`
  прибрано; правила `deep.md` «План», «Пошук», «Звіт» замінені одним «Вступ»; «Згода» без змін.
- `consent`, `with_deep`, `deep_offer` — як тепер, з `researcher`; при `researcher is None` `with_deep` віддає
  відповідь без пропозиції, `converse` замість `deep_offer` дає `answer_fact`, а пропозиція, що чекає згоди (ключ
  прибрали після її показу), — звичайна розмова (`_converse` з `pending_deep=None`) (Q10).

`respond(ctx, knowledge, llm, researcher: Researcher | None = None)`, `converse(ctx, knowledge, llm, lead,
researcher=None)`, `lead(ctx, knowledge, llm, researcher=None)` — `researcher` тільки передається далі.

`src/thinkhow/workspace/topics.py` (+ `model.py`):
- `RunningFile` — `deep_running.json`: `researches: list[RunningResearch(id: str, turn: int, question: str, deepest:
  bool, started_at: datetime)]`; `turn` — номер відповіді, що його запустила.
- `_Facilitated` отримує поле `started: tuple[DeepStarted, ...]` (як `proposed`), `_stream` збирає `DeepStarted`, не
  віддаючи їх текстом. `_answer`: кожен `DeepStarted` дописується в `deep_running.json` у ту мить, коли `_stream` його
  отримує (ще в потоці, тож і тоді, коли потік потім кине виняток), тобто ДО будь-якого виходу `_answer` (виняток потоку, `update is None`, `EmptyReply`,
  перевірка `_still_awaiting`, запис відповіді; Q17), і тим самим кроком видаляється `deep_pending.json` (повтор «так» після
  збою запису відповіді не запустить друге платне дослідження): дослідження вже йде в Google, тож його запис не залежить від того, чи
  відповідь «запущено» потрапила в розмову; звіт доставиться і тоді, коли відповідь стала `Superseded` чи її запис упав.
- `_read_pending`: файл, що не проходить перевірку `PendingFile` (стара форма `{question, intro, questions}` від коду до
  цього slice-а), — пропозиції немає: рядок журналу `deep_pending_stale`, файл видалено, репліка отримує звичайну
  відповідь (Q13).
- `deliver_research(storage, collect: Collect, user, ref, now, broken_text: str, expired_text: str) -> Delivery(running: bool,
  delivered: int)` — Flow: `_check_now`, `_check_ref`, `_can_read` (чужий не власник → `TopicNotFound`, як
  `open_topic`) → тема іншої людини, яку читає власник (`ref.uid != user.id`) → лише читання, `Delivery(<є записи; нечитаний файл — False>, 0)`, нічого не видаляється і
  не пишеться — ця перевірка ПЕРША → `deep_running.json` (немає → `Delivery(False, 0)`; не проходить перевірку → рядок журналу `deep_running_stale`,
  файл видалено, `Delivery(False, 0)`) → репліка людини чекає відповіді
  (`_awaiting`) або пропозиція дослідження чекає згоди (`deep_pending.json` з `turn == conv.last_no()`) →
  `Delivery(True, 0)`, нічого не кличе й не пише → для кожного запису
  `collect(id)`: `DeepRunning` лишає; `DeepReady` → репліка `model` з номером `last_no()+1`, часом `now` і текстом
  звіту (у нову сесію, коли остання закрита — як `_reply_flow`; відомо й прийнято: якщо людина повернеться менш ніж за 24 год після такого звіту, питання про
  крок S6 не прийде, бо сесія зі звітом ще відкрита), запис у `research.json` (`turn` цієї репліки, `depth="deep"`, `queries=[]`, `sources`, `suggestions_html=None`,
  `question`, `report=text`); `DeepBroken` → репліка `model` з `broken_text`, а `DeepBroken("not_found")` (Google вже не тримає дослідження, Q20) — з `expired_text`; виняток `collect` → запис лишається,
  рядок журналу `deep_collect_failed` → ПІСЛЯ всього циклу `collect`, завжди (коли є що писати): `conversation.md`
  прочитано ЗНОВУ і ті самі перевірки (чекає відповіді, чекає згоди) повторено — не пройшли → нічого не пишеться,
  рядок `deep_delivery_skipped`, записи лишаються (як `_still_awaiting`, finish-answer Q5); пройшли → номери
  (`last_no()+1`, далі по одному) і сесія нових реплік — з цього другого читання → `conversation.md`, `research.json`, `deep_running.json` — ПРОЧИТАНИЙ ЗНОВУ в
  момент запису, репліку пишемо лише для id, які в ньому ще є (зниклий id доставив інший запит
  — пропустити, рядок `deep_delivery_skipped`), з нього прибрано лише id, доставлені чи невдалі в цьому проході (злиття, не перезапис списком
  першого читання: запис, доданий «так» під час `collect`, лишається); порожній список → файл видалено → `Delivery(<лишились записи>, <доставлено>)`. Рядки журналу `deep_delivered` /
  `deep_broken` (uid, topic_id, turn, research_id; у `deep_broken` ще `reason` — причина `DeepBroken`).
- `TopicView.researching: bool = False` — `open_topic` ставить `True`, коли `deep_running.json` має записи.
- `delete_topic` видаляє й `deep_running.json` (як усі файли теми — без змін коду).

`src/thinkhow/web`:
- `Deps.collect: Collect | None = None`; `app.build_deps`: `researcher = make_researcher(settings)`; `facilitate` з
  `researcher=researcher`; `collect = partial(deep.collect, researcher)` або `None`.
- `GET /topics/{uid}/{topic_id}` не доставляє (лише показує `researching`): сторінка не чекає на Google і розгортання
  посилань.
- `GET /topics/{uid}/{topic_id}/research` (один споживач — `conversation.js`; запис на GET навмисний, Q14) → JSON `{"running": bool, "delivered": int}` — тут і лише тут
  `deliver_research(..., broken_text=words["deep_broken"], expired_text=words["deep_expired"])`; без `deps.collect` → `{"running": false, "delivered": 0}`.
- `topic.html`: при `view.researching` — `<p id="researching" class="researching" role="status">{{ ui.deep_running
  }}</p>` над формою.
- `conversation.js`: `createResearchWatch({ fetch, url, idle, reload, hide, setInterval, clearInterval })` — одразу
  після завантаження сторінки і далі кожні 20 с GET `…/research`, але не новий, поки попередній ще в дорозі; `delivered > 0` і `idle()` → `reload()`; `delivered > 0` і не `idle()` — нічого (наступна
  відповідь і так перезавантажить сторінку); `running == false` і (`delivered == 0` або `idle()`) → `hide()` і зупинка; `running == false`, `delivered > 0`,
  не `idle()` → лише зупинка, «йде» лишається до перезавантаження сторінки наступною відповіддю. `idle()` — поле порожнє, немає
  запиту в дорозі, не йде запис і не ввімкнено режим розмови. Запускається, лише коли є `#researching`.
- `locales/uk.json`, `en.json`: `deep_running` («Дослідження йде — можна писати далі або піти; звіт з'явиться тут,
  щойно буде готовий.»), `deep_broken` («Глибоке дослідження не вдалося завершити. Можна попросити ще раз.»), `deep_expired` («Результат дослідження вже
  недоступний: Google зберігає його 7 днів, а тему за цей час не відкривали. Можна попросити ще раз.»); інші
  мови — фолбек на англійську (як `texts`).

`scripts/live_deep_confirm.py` (жива перевірка старого циклу, 747/754) видалено — його замінює
`scripts/live_deep_research.py` (Exit criterion); його виводи в `.engine/artifacts/747/`, `754/` лишаються.

Живий прогін збирає застосунок сам, як `scripts/live_app.py` (задача 308): `scripts/live_deep_app.py` — фабрика для
`uvicorn --factory`: `Deps` з `LocalStorage` (`THINKHOW_LOCAL_DIR`), справжньою моделлю (`make_llm` на копії
налаштувань з `local=False`, search), `GeminiResearcher` через `make_researcher` на тій самій копії (ключ із
`THINKHOW_GEMINI_API_KEY`), фіксованою особою місцевого режиму, `facilitate` з `researcher`, `collect` з ним же;
`create_app(deps)`. `scripts/live_deep_research.py` запускає її підпроцесом uvicorn, крок (5) — зупинка підпроцесу і
новий підпроцес на тій самій теці. Порядок `make_researcher` у продукті не змінюється: `local` → `ScriptedResearcher`.

Errors (Q16): `ResearchUnavailable` ніколи не доходить до `_answer` — рядок журналу `deep_unavailable` (етап, тип
винятку) і: план у `with_deep` → відповідь без пропозиції; план у `deep_offer` → `answer_fact`; план на правці →
звичайна розмова (`_converse` з `pending_deep=None`), пропозиція зникає; `start` на «так» → відповідь
`pending.failed` (речення з виклику «Вступ»), пропозиція зникає, `DeepStarted` немає. Доставка ніколи не кидає через
`collect` (лишає запис).

Dependencies (injected): `Researcher` (facilitation), `Collect` (workspace), `resolve`, `sleep`, `clock`, `client`.

Does NOT do: нагадувань; Markdown-розмітки; фактів у карту; секрету в Cloud Run; скасування; ліміту витрат.

## Decisions (with WHY)
- Q1: Шлях — Gemini API з ключем (`THINKHOW_GEMINI_API_KEY`). Чому: spike — працює; Vertex `global` упав `Internal
  error` (ADR-0007). Rejected: Vertex `global` з service account — не працює і не документований.
- Q2: Хто чекає — ніхто: id у `deep_running.json`, стан питає сервер, коли тема відкрита (перший запит `/research` сторінки й далі раз на 20 с; сама сторінка не доставляє, Q14). Чому: дослідження живе в Google (PR2), тож id досить, перезапуск нічого не губить; без запитів нічого не
  відбувається (N4). Rejected: (а) тримати запит відкритим до 60 хв — обрив губить усе; (б) фоновий потік у Cloud Run
  — найкраще в ньому: дописав би звіт, навіть коли тему ніхто не відкрив; але гине з екземпляром (Cloud Run гасить
  його без запитів), а писати без людини в темі нема для кого (N4); (в) webhook Google — сервіс за IAP, чужий запит не пройде, і потрібна ще одна точка входу.
- Q3: Контекст агента — розмова теми так, як її бачить модель (з текстом документів), питання і рядок мови. Чому:
  власник дозволив (задача 314), агент приймає текст, план має бути мовою людини (PR1). Rejected: PDF як файли —
  текст уже в розмові, а завантаження файлів у Gemini API — ще одна частина (P5).
- Q4: Вступ, рядок «запущено» і `deepest` дає наш виклик «Вступ» (`generate_json`), паралельно з планом агента.
  План завжди складає стандартний агент (Max не планує, PR7); `deepest` вирішує лише, хто досліджує після «так»: Max
  стартує заново з розмовою і погодженим планом у input (PR3 забороняє продовжити чужий план, PR8). Чому: людина
  погоджує план Deep Research, як хоче задача, і для Max теж; вступ і «запущено» — мовою людини за `language_rule`.
  Rejected: (а) Max планує сам — не планує (PR7), дослідження без згоди; (б) Max без погодження плану — суперечить
  згоді (задачі 747, 314); (в) поле `deep_max` у роутері й картках — ширша зміна схем і правил роутера.
  «Так, і якнайглибше» в репліці згоди `deepest` не змінює: згода — так / правка / ні; щоб змінити версію, людина
  робить правку («досліди якнайглибше»), і її «Вступ» ставить `deepest`.
- Q5: Правка — завжди `researcher.plan(<репліка правки>, previous=pending.plan_id)` (план стандартного агента);
  `deepest` правки — з її «Вступу» (людина могла на правці попросити якнайглибше). Чому: задача — «правка уточнює
  план агента». Rejected: свіжий план на кожну правку — губить правку як уточнення.
  Якщо PR4 провалиться на живому прогоні, правка йде свіжим планом з `brief` (розмова вже містить правку) — та сама
  сигнатура, рішення записується як нове (spike PR4 це вже показав — запасний шлях лише на випадок регресії Preview). Старт стандартного агента з плану
  правки (ланцюг план → правка → старт) spike не запускав; перший живий доказ — Exit, кроки (2)–(3); якщо впаде, Q16
  дає людині `failed`, тема не заклинює.
- Q6: Звіт — окрема репліка `model` у кінці розмови, щойно готовий; не пишеться, поки репліка людини чекає
  відповіді (тоді — наступного разу). Чому: G2 — звіт у темі як відповідь системи; формат розмови вже дозволяє дві
  репліки `model` поспіль (питання про крок, S6); не перебиває потік відповіді. Rejected: вставити звіт після
  репліки «запущено» — змінює номери вже показаних реплік. Відомо й прийнято: репліка людини, на яку відповідь не
  вдалася і яку людина не повторила, тримає доставку до закриття сесії (24 год тиші) — увесь цей час видно «йде».
- Q7: Текст звіту — як дав агент (заголовки, таблиці, `[cite: N]`, список джерел), з розгорнутими посиланнями;
  джерела `research.json` — Markdown-посилання тексту. Окремого рядка «Джерела:» не дописуємо — список уже в тексті.
  Rejected: власний переказ звіту моделлю — ще виклик і втрата деталей (P4). Відома ціна: звіт (~36 тис. знаків)
  стає частиною історії, яку кожна наступна репліка шле моделі (`_history`) — Deferred.
- Q8: Невдале дослідження (будь-який статус, крім `in_progress`, `queued`, `completed`; порожнє) — репліка з UI-словом
  `deep_broken`, запис зникає; `not_found` — так само, але зі словом `deep_expired` (Q20). Збій самого запиту стану — запис лишається, спроба наступного разу. Rejected: мовчки
  прибрати — людина чекала б вічно.
- Q9: Доставка — лише в запиті власника теми; власник, читаючи чужу тему, бачить «йде», але нічого не пише (правило
  запису `_can_write`). Rejected: доставляти будь-яким читачем — порушує «write rule: own» (M3 A3.3).
- Q10: Без ключа (`make_researcher` → `None`) глибоке дослідження не пропонується: роутерів `deep_question` → швидка
  відповідь (`answer_fact`), `deep_question` фасилітатора ігнорується. Чому: auto-deploy викладе код раніше, ніж Сонько
  додасть секрет; продукт має працювати. Rejected: падати без ключа — ламає розмову; лишити старий цикл як запасний —
  задача каже прибрати.
- Q11: Без меж витрат і без власного таймауту дослідження (рішення власника «якість понад ціну», задача 314; P4, P5 цілей). Межа лише на
  очікування плану (`plan_timeout_s = 120`: виміряно 20.4–23.0 с, у 5 разів більше), бо план тримає запит
  відкритим, а після межі відповідь іде без пропозиції (Q16).
- Q15: Поки пропозиція дослідження чекає згоди (`deep_pending.json`, `turn == conv.last_no()`), доставка чекає теж.
  Чому: `_answered` приймає згоду лише на репліці `waiting.turn + 1` (навмисно: питання про крок між ними гасить
  пропозицію, S6); звіт між пропозицією і «так» зробив би «так» звичайною реплікою, а `_write_pending` видалив би
  пропозицію — згода людини пропала б мовчки. Ціна: звіт ляже після відповіді на пропозицію (секунди–хвилини). Відомо й прийнято: якщо людина пішла, не
  відповівши на пропозицію, готовий звіт чекає її наступної репліки (межі часу немає) — revisit trigger: власник
  побачить «йде» над готовим дослідженням.
  Rejected: `_answered` пропускає доставлені звіти між пропозицією і реплікою (за `research.json`, `depth="deep"`,
  `turn > waiting.turn`) — звіт з'явився б одразу, але правило згоди стає залежним від іншого файлу, а друга
  зміна правила S6 — більше місць зламатися (P5).
- Q16: Збій агента (план, старт) — не збій відповіді: розмова йде без пропозиції або з реченням `failed`, рядок
  `deep_unavailable`. Чому: `Failed` лишає репліку без відповіді, `reply` тоді відмовляє (`PendingAnswer`), а `retry`
  знову кличе той самий агент Preview — тема заклинює, поки агент лежить (до 24 год); у `with_deep` збій викинув би
  вже показану відповідь фасилітатора. Rejected: `Failed`, як збій моделі, — «людина бачить, що щось не так, і
  повторює», але повтор упирається в ту саму недоступність, і розмова, яка від агента не залежить, стоїть.
- Q17: `deep_running.json` пишеться до відповіді «запущено». Чому: `start` уже запустив платне дослідження в Google;
  запис без репліки «запущено» нешкідливий — звіт однаково з'явиться в темі, а відповідь без запису загубила б
  дослідження (Superseded, збій запису). Rejected: писати після відповіді (як `research.json`) — «запис лише того,
  що людина бачила», але тоді `Superseded` лишає дослідження сиротою.
- Q13: Стара `deep_pending.json` (форма до цього slice-а) — пропозиції немає, файл видалено, звичайна відповідь.
  Чому: `_read_pending` кличеться поза `try` `_answer`, тож виняток заклинив би тему назавжди (репліка вже збережена,
  `retry` падає так само); auto-deploy викладе код, поки такі файли лежать. Rejected: лишити `questions` необов'язковим
  і приймати старі плани — «нічого не губиться», але старий план не має `plan_id`, з якого агент міг би стартувати;
  людина, що скаже «так», отримає звичайну відповідь і може попросити дослідження знову.
- Q14: Доставка — лише через `/research`, сторінка тільки показує «йде». Запис на GET безпечний, бо сервіс за IAP:
  передвибірка чи краулер без входу доставки не запустять. Чому: розгортання ~46 посилань і `get` у
  Google не повинні затримувати відкриття теми; сторінка питає `/research` одразу після завантаження.
  Rejected: доставка і в GET сторінки — до ~11 с послідовного розгортання в запиті сторінки (критик, нотатка 4).
- Q18 (відома ціна): поки доставка відкладена після `Ready` (друге читання не пройшло), кожне опитування повторює
  один `get` і розгортання ~46 посилань — прийнято.
- Q19: Search suggestions для звіту агента — немає: агент їх не повертає (spike §3, «No Search suggestions HTML comes
  back»), тож `suggestions_html=None`; посилання на джерела показуються розгорнутими, як у швидкому пошуку (ADR-0006).
  Умова «як для пошуку зараз» виконана тим, що показуємо все, що Google дає. Rejected: власний пошук заради
  suggestions — повертає прибраний цикл.
- Q20: Звіт, по який людина не повернулась за 7 днів, втрачено (`not_found` → `deep_expired`) — відомий ризик,
  AUTONOMOUS (`.engine/overseer/escalations.md`, 2026-11-18). Чому: втрата потребує 7 днів відсутності після 7–20 хв
  дослідження; закрити її — нічний Cloud Run Job (Scheduler уже є, `INDEX.md` F10) мав би право запису в `users` і ключ
  Gemini — обидва кроки Сонька, і slice росте; додати це пізніше можна без міграції даних (двосторонні двері).
  Rejected: доставка Job-ом зараз — ширше право Job-а (зараз лише читає `users`) заради рідкісного випадку.
  Чесне окреме речення замість «не вдалося завершити», бо дослідження завершилось.
- Q12: Опитування сторінки — 20 с. Чому: дослідження 7–20 хв; 20 с — непомітна затримка і ≤ 60 запитів `get` за
  дослідження. Rejected: 5 с — у 4 рази більше запитів без користі; SSE до кінця — тримає з'єднання хвилинами.

## Hardest seams (test-confidence points — distinct from the contract Seam above)
- **Seam 10: вичерпні статуси** — двійник клієнта повертає `budget_exceeded`, `requires_action` і невідомий рядок:
  `state` → `Broken(<status>)`, `plan` → `ResearchUnavailable` одразу (не після `plan_timeout_s`). Broken by:
  «невідоме → `Running`».
- **Seam 1: звіт із кількох частин** — `state` на двійнику клієнта, чий `completed` має три кроки `model_output` (два
  з текстом і один з картинкою між ними) і `output_text` лише останньої частини; тест вимагає обидва тексти по
  порядку. Ловить «взяли `output_text`».
- **Seam 2: план прив'язаний до агента** — двійник клієнта, що кидає `400 belongs to a different agent`, коли
  `previous_interaction_id` створено іншим агентом, і на `AGENT_MAX` з `collaborative_planning=True` повертає звіт
  без маркера (PR7): `plan` ніколи не кличе Max; `start(deepest=True)` кличе Max без previous і з планом в input.
  Ловить «Max з previous» і «Max планує».
- **Seam 3: доставка проти потоку відповіді** — тема, де остання репліка — людини без відповіді: `deliver_research`
  не кличе `collect` і не пише жодного файлу (порівняння байтів усіх файлів теми до і після).
- **Seam 4: перезапуск** — запуск через `reply` з одним `Deps`/storage, доставка новим `create_app` на тому самому
  storage (інший процес = інший об'єкт), id береться лише з `deep_running.json`. Ловить стан у пам'яті процесу.
- **Seam 5: без ключа** — `build_deps` з `THINKHOW_LOCAL` вимкненим і без ключа дає `collect is None`, а роутерів
  `deep_question` дає швидку відповідь, не пропозицію.
- **Seam 9: агент недоступний** — `Researcher`, що кидає `ResearchUnavailable` у `plan` чи `start`: на кожному з
  чотирьох шляхів (`with_deep`, `deep_offer`, правка, «так») `reply` дає `Answered`, репліка людини не лишається без
  відповіді; на «так» ще й: відповідь — `pending.failed`, `deep_pending.json` немає, `DeepStarted` немає, `deep_running.json` не створено. Broken by: `ResearchUnavailable` летить у `_answer`.
- **Seam 8: пропозиція чекає згоди** — дослідження A готове, пропозиція B показана останньою реплікою:
  `deliver_research` нічого не пише; «так» запускає B (`start` з `plan_id` B), і лише потім A доставляється.
  Broken by: доставка між пропозицією і «так».
- **Seam 7: старі файли** — `deep_running.json`, що не проходить перевірку → `deliver_research` дає `Delivery(False, 0)`,
  файл видалено, `deep_running_stale` у журналі; `deep_pending.json` у формі `{question, intro, questions}` → `reply` дає `Answered`
  звичайної відповіді, файл зник, у журналі `deep_pending_stale`. Ловить виняток поза `try` `_answer`.
- **Seam 6: JS** — `createResearchWatch` з підставними `fetch`/`setInterval`: reload лише при `delivered>0` і
  `idle()`; зупинка при `running=false` (з `hide()`, крім `delivered>0` і не `idle()` — тоді без `hide()`); `fetch`, що не повертається, — наступний тик нового запиту не шле.

- **Seam 11: запуск записано до будь-якого виходу відповіді (Q17)** — «так» з `Researcher`-двійником, чий `start`
  дає id, у чотирьох варіантах: (а) фасилітатор віддає порожню відповідь; (б) під час потоку в розмову дописано іншу
  репліку (`Superseded`); (в) запис `conversation.md` кидає виняток; (г) потік кидає виняток після `DeepStarted`. У
  кожному — `deep_running.json` має id, `deep_pending.json` немає, повтор (`retry`/ще одне «так») `start` вдруге не
  кличе. Broken by: запис у `_write_after_answer` після `_write_conversation`; `deep_pending.json` лише в `_write_pending`.
- **Seam 12: дрібні гілки адаптера** — (а) `NotFoundError` з `status_code=404` і виняток іншої родини з `code=404` →
  `Broken("not_found")`, будь-який інший виняток `get` → `ResearchUnavailable`; (б) текст плану з `**Research Plan:**`
  двічі (луна input) → `Planned.text` — після останнього; (в) двійник, що завжди `in_progress`, і підставний
  `clock` → `plan` кидає `ResearchUnavailable` після `plan_timeout_s`, не висить; (г) розгорнута адреса з `(`/`)` →
  `%28`/`%29`, і `collect` бачить її серед джерел. Broken by: лише `status_code`; поділ за першим маркером; вічне
  опитування; дужки, що обривають `LINK`.

- **Seam 13: тема змінилась під час `collect`** — двійник `Collect`, що під час виклику (а) дописує репліку людини в
  `conversation.md`, (б) пише `deep_pending.json` з `turn == last_no()`, і віддає `DeepReady`: після `deliver_research`
  `conversation.md` має лише дописане двійником, `research.json` незмінний, запис `deep_running.json` лишився, у журналі
  `deep_delivery_skipped`. Broken by: перевірка «чекає відповіді / згоди» лише на вході.
- **Seam 14: звіт, якого Google вже не тримає** — `collect` дає `DeepBroken("not_found")`: репліка — `expired_text`, не
  `broken_text`; рядок `deep_broken` має `reason=not_found`. Broken by: завжди `broken_text`.

## Invariants (rules that hold for every input in the stated domain)
- **I1** — Кожен запис `deep_running.json` (запущене дослідження, I7) або ще лежить у `deep_running.json`, або дало рівно одну репліку `model` у
  розмові (звіт чи рядок невдачі); зникнути без репліки чи дати дві не може.
  - Domain: `deep_running.json`, що проходить перевірку `RunningFile` (файл, що не проходить, — не записи, Seam 7);
    будь-яка послідовність (дві доставки одночасно — Deferred) викликів `deliver_research` на темі, зокрема
    з записами, доданими в `deep_running.json` під час `collect` (запуск «так» у цей час), з будь-якою кількістю записів, з `collect`,
    що для кожного id дає `DeepRunning`, `DeepReady`, `DeepBroken` чи кидає виняток, у будь-якому порядку.
  - Source: задача 314 «Дослідження не губиться»; Seam `deliver_research`.
  - Broken by: видалити запис до запису розмови; доставити `DeepReady` двічі при повторному виклику; переписати
    `deep_running.json` списком першого читання (стирає запис, доданий під час `collect`).
- **I2** — Поки остання репліка — людини без відповіді або пропозиція дослідження, що чекає згоди, `deliver_research` не змінює жодного файлу теми і не кличе
  `collect`.
  - Domain: будь-яка тема з `deep_running.json` і реплікою людини, що чекає (відкрита сесія), або з `deep_pending.json`,
    чий `turn` — остання репліка; і так само, коли така репліка чи пропозиція з'явилась у `conversation.md` /
    `deep_pending.json` ПІД ЧАС `collect` (друге читання після циклу) — тоді змінюється лише те, що дописав інший запит.
  - Source: Q6, Q15.
  - Broken by: доставка, що дописує звіт посеред відповіді і ламає `_still_awaiting`; доставка між пропозицією і
    «так», що гасить згоду; перевірка лише на вході, без повтору після `collect`.
- **I3** — `deliver_research` у чужій темі (`ref.uid != user.id`) не змінює жодного файлу теми.
  - Domain: власник, що читає будь-яку чужу тему за будь-якого стану `deep_running.json` — немає, з записами чи такий,
    що не проходить перевірку `RunningFile` (інший користувач чужої теми не бачить — `TopicNotFound`).
  - Source: Q9, «write rule: own» (`topics.py`, docstring).
  - Broken by: доставка без перевірки, чия тема; перевірка старого файлу (видалення + `deep_running_stale`) раніше за
    перевірку, чия тема.
- **I4** — `start` отримує рівно `plan_id`, `plan` і `deepest` погодженої пропозиції; `plan` на правці завжди
  отримує `previous=pending.plan_id`, а без правки — `previous=None`.
  - Domain: будь-яка `PendingDeep` і будь-яка відповідь «Вступ» на правці.
  - Source: PR3, Q5.
  - Broken by: запуск зі старим id чи планом після правки; правка без previous.
- **I5** — `research.json` після доставки містить усі попередні записи без змін і по одному новому на кожен
  доставлений звіт, з `turn` його репліки.
  - Domain: будь-який `research.json` (порожній, зі швидкими і глибокими записами) і будь-яка кількість звітів за раз.
  - Source: A7 (`_append_research`, I5 research-deep), G2.
  - Broken by: перезапис файлу лише новими записами; `turn` репліки «запущено».
- **I6** — У тексті `Ready` не лишається жодного посилання `grounding-api-redirect`, яке `resolve` розгорнув; решта
  тексту незмінна.
  - Domain: будь-який текст звіту з будь-якою кількістю посилань (зокрема нуль і повтори).
  - Source: Q7; умови показу джерел (ADR-0006).
  - Broken by: заміна лише першого входження; зміна тексту довкола посилань.

- **I7** — Щойно `start` повернув id, цей id лежить у `deep_running.json`, а `deep_pending.json` цієї пропозиції
  немає, хоч би чим закінчився `reply` (`Answered`, `Failed` з будь-якою причиною, виняток запису).
  - Domain: будь-яке «так» на пропозицію, де `start` повернув id, і будь-який вихід `_answer` після цього.
  - Source: Q17; задача 314 «Дослідження не губиться».
  - Broken by: запис запуску після запису відповіді; залишити `deep_pending.json` до `_write_pending` (повтор «так»
    запускає друге платне дослідження).

## Conversation delta
немає — `.engine/architecture/conversation-model.json` у проєкті немає.

## Exit criterion
- Тести контракту (tester, `tests/contract/deep_research_agent/`), по одному `test_I<n>_…` на I1–I7, і тести на
  Seam 1–14; запечатані тести `research_deep`, `deep_confirm`, `deep_change_question`, що описують старий цикл,
  замінені (supersede) — список рішенням tester-а.
- `uv run pytest -q` зелений, `uv run mypy src`, `uv run ruff check src tests scripts` чисті.
- Живий прогін `scripts/live_deep_research.py` (локальне сховище, справжня модель Vertex `eu`, справжній агент з
  `THINKHOW_GEMINI_API_KEY`, застосунок через uvicorn): (1) нова тема, репліка з проханням дослідити → відповідь
  містить план агента і питання згоди, `deep_pending.json` має `plan_id`; (2) правка → новий план, інший
  `plan_id`; (3) «так» → відповідь приходить, поки дослідження ще йде (його стан — `Running`), `deep_running.json` має id, сторінка теми має `#researching`; (4) ще
  одна репліка → звичайна відповідь, поки дослідження йде; (5) сервер зупинено і запущено знову (новий процес);
  (6) опитування `/research` до `delivered == 1`; (7) сторінка теми після перезавантаження містить репліку зі звітом
  і щонайменше одним посиланням `<a href="https://` не на `vertexaisearch`, `#researching` немає, `research.json`
  має запис `deep` з цим текстом; (8) друга тема, людина просить дослідити якнайглибше → «так» →
  `deepest: true` у записі `deep_running.json` і `agent == "deep-research-max-preview-04-2026"` у рядку
  `deep_research_finished` → звіт доставлено, як у (6)–(7) (може йти паралельно з першою темою); у виводі — пункти
  плану і заголовки звіту поруч, щоб читач бачив, чи Max ішов за планом (PR8; не перевірка коду). Мова плану в (1)
  перевіряється на тексті, який дав агент — поле `plan` у `deep_pending.json` (`Planned.text`), не на відповіді
  (вступ і питання згоди завжди мовою людини): кириличних літер у ньому більше, ніж латинських (рядок мови тепер
  англійський, PR1 перевірено з українським). Опитування в (6) і (8) обмежене 60 хв — документованим максимумом
  дослідження (задача 314, «максимум 60»); межа вичерпана — крок FAIL з останньою відповіддю `/research` у виводі.
  Кожен крок (1)–(8), крім рядка про план Max, перевіряється в коді; скрипт пише PASS/FAIL кожного кроку і виходить з
  кодом 1 на будь-якому FAIL, як `scripts/live_deep_confirm.py`. Вивід містить час кожного кроку (зокрема (1) —
  пропозиції з планом), уривок тексту кожного звіту (перші ~1 500 знаків), usage з `deep_research_finished` і ціну за
  ставками README spike §2. Вивід — `.engine/artifacts/314/live-deep-research.txt`.

## Deferred to later slices
- Секрет `gemini-api-key` у Cloud Run (`--update-secrets=THINKHOW_GEMINI_API_KEY=gemini-api-key:latest`) і роль
  `roles/secretmanager.secretAccessor` для `thinkhow-web` — крок Сонька; why later: інфраструктура не агентова —
  revisit trigger: слово власника «передай Сонькові» (текст запиту в звіті задачі 314).
- Markdown звіту (заголовки, таблиці) як HTML — why later: окрема зміна безпечного показу тексту (`web/text.py`, I3
  S1b) — revisit trigger: власник на своєму огляді скаже, що звіт важко читати.
- Факти звіту як пункти карти — why later: потрібен ще виклик моделі на звіт — revisit trigger: навчання (G3) чи
  власник побачать, що факти дослідження не враховуються далі.
- `Llm.search_text` без викликів у `src` — why later: його мають двійники ~25 запечатаних тестів — revisit trigger:
  наступний нічний прохід simplifier-а.
- Одночасні записи `conversation.md` двох запитів однієї людини: доставка і нова репліка, або дві доставки (дві
  вкладки) — після другого читання розмови і `deep_running.json` перед записом лишається вікно між цим читанням і
  записом (мілісекунди) — why later: Storage не має умовного запису за поколінням — revisit trigger: хоч один звіт, що є в `research.json`, але немає в
  розмові, або звіт двічі в одній темі.
  Те саме вікно між `reply` (читання розмови) і записом відповіді: доставка, що вклинилась, буде перезаписана
  реплікою людини — звіт є в `research.json`, але немає в розмові (той самий revisit trigger).
- Довгі звіти в історії моделі (кожна наступна репліка теми несе ~36 тис. знаків звіту) — why later: модель
  Gemini приймає такий контекст, ціна репліки росте, але P4 — revisit trigger: час чи ціна реплік у темах зі
  звітами більші, ніж у темах без звіту (тривалість і usage `llm_call` на репліку).
- Звіт людині, яка не відкрила тему понад ~7 днів після «так» — Google тримає дослідження 7 днів (ADR-0007, spike
  §3), потім `get` → 404 → `Broken("not_found")` → репліка `deep_expired` замість звіту — why later: доставка без
  відкритої сторінки потребує доставки нічним Cloud Run Job-ом (Scheduler і Job уже є, `INDEX.md` F10), але Job-у
  бракує права запису в `users` і ключа Gemini — обидва кроки Сонька (Q20) — revisit trigger: рядок журналу
  `deep_broken` з `reason=not_found`.
- Мова звіту для людини не `uk` — живий прогін перевіряє лише українську — why later: рядок мови англійський і
  однаковий для всіх мов, PR1 показав, що агент його слухає — revisit trigger: перший звіт у темі людини з мовою не `uk`
  (рядок `deep_delivered` + мова профілю), прочитаний на огляді.
- Нічний аналізатор навчання (`learning/analyze.py`) читає кожну репліку `model` як мову фасилітатора — і звіт агента
  (~36 тис. знаків, чужий автор) теж; старий цикл так само писав звіт реплікою `model` — why later: це поведінка
  навчання, не доставки — revisit trigger: спостереження навчання з якорем на репліці звіту.

## Open items requiring human decision (if any)
- немає: шлях, будова й поріг опитування — технічні; згода на глобальний API і час — слова власника (задача 314).
  Втрата звіту після 7 днів — двосторонні двері, вирішено самостійно (Q20, AUTONOMOUS у `escalations.md`).

## Critic notes (non-blocking)
- Cold-reader 3: REVISE — I3 Domain без нечитаного `deep_running.json` (порядок перевірок) → Domain розширено, Broken by
  додано; нотатки: дужки в правилі JS і випадок без `hide()` у Seam 6, I1 — лише чинні записи, Q2 проти Q14, «так, і
  якнайглибше» (Q4), старт із плану правки (Q5). Третє заперечення поспіль → `stage.py route` = park.
- Cold-reader 2: REVISE — друге читання після `collect` без тесту → Seam 13, Domain I2 розширено; нотатки: Q12
  відновлено, Q8/Deferred → `deep_expired`, Seam 14 (`expired_text`), Seam 6 (запит у дорозі).
- Cold-reader 1: ESCALATE (BLOCKER_CLASSIFICATION, двосторонні) — 7 днів: порада А взята (Q20, `deep_expired`,
  AUTONOMOUS); нотатки — точна причина Deferred (право Job-а), аналізатор навчання (Deferred), стара `deep_running.json` (Seam 7).
- Phase 5, раунд 2: CRITIC_PASS.
- Phase 5, раунд 1: REVISE — звіт після 7 днів Google → Deferred з тригером `deep_broken reason=not_found` (поле
  `reason` додано в Seam); мова не `uk` → Deferred; тригер довгих звітів названо вимірно.
- Phase 4, раунд 2: CRITIC_PASS.
- Phase 4, раунд 1: REVISE — мова плану перевіряється на `Planned.text`, кожен крок у коді з виходом 1, межа
  опитування 60 хв, крок Max за наявними спостереженнями, уривок звіту у виводі.
- Phase 3, раунд 2: CRITIC_PASS; I1 сформульовано за записами файлу; Seam 11 (в) — `reply` кидає, файли перевіряються після винятку.
- Phase 3, раунд 1: REVISE — Q17 без тесту → Seam 11 та I7; нотатки (404 обох родин, останній маркер, межа плану,
  дужки, «так» при недоступному агенті, виняток потоку після `DeepStarted`) → Seam 12, Seam 9, Seam-текст `_answer`.
- Phase 2, раунд 9 (після слова власника «А»): CRITIC_PASS. Нотатки: вікно `reply`/доставка (Deferred), порядок
  запису `started` до `update is None`/`EmptyReply` (Seam), Search suggestions (Q19), старт із плану правки (Exit, кроки 2–3).
- Phase 2 після back-edge, раунд 4: дві доставки одного звіту (запис лише для id, що лишились у файлі; один запит
  сторінки за раз), `_can_read`, дужки в адресах, S6 після звіту, номер Q18 — враховано. Після цього раунду спрацював
  запобіжник 4 раундів: фазу зупинено до слова власника (`tasks/blocked/`).
- Phase 2 після back-edge, раунд 3: як живий прогін збирає застосунок, `deep_pending.json` видаляється разом із
  записом запуску, один шаблон посилань, «йде» не ховається до показу звіту, порядок перевірок доставки — враховано.
- Phase 2 після back-edge, раунд 2: злиття `deep_running.json` при записі доставки (I1), IAP для GET, план проти
  звіту Max у виводі — враховано.
- Phase 2 після back-edge, раунд 1: вичерпні статуси, друге читання розмови завжди, `deep_running.json` до відповіді —
  враховано (Q17, Seam 10).
- Phase 2, раунд 4: back-edge PR — Max сам не планує (PR7), стартує заново з планом (PR8), 404 (PR9); архітектуру
  Max переписано (Q4, Q5, I4, Seam 2); крок Max у живому прогоні — враховано.
- Phase 2, раунд 3: повторне читання розмови перед записом доставки, ціна звіту в історії, `/research` — один
  споживач, premises перейменовано на PR1–PR6 (P1–P6 — принципи цілей) — враховано вище.
- Phase 2, раунд 2: 404 обох родин винятків, `START_INPUT` і рядок мови англійською, останній маркер плану, «йде» до
  24 год при невдалій відповіді, стара `deep_running.json` — враховано вище. Мову звіту не-української людини живий
  прогін не перевіряє (лише `uk`) — ризик названо тут.
- Phase 2, раунд 1: сесія для звіту, дві доставки, затримка сторінки, осиротіле дослідження, `_stream`, Q2(б) — враховано вище.
