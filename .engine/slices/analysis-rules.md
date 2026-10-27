# Slice analysis-rules — planning artifact

Feature: `.engine/architecture/feature/learning-loop.md`, slice **S2** (F10 повна). Board task
`tasks/doing/309-close-learning-loop.md`, unattended. Driven mode: the frame is the feature artifact's S2 entry, its
contract S2 → S3 and «Build parameters»; nothing asked.

## Goal
Нічний аналізатор оцінює ведення за явними правилами аналізу і пише **кілька** спостережень на тему за прогін: де людина
просувається, де застрягла, чи підійшов метод — кожне з якорем на репліку, причиною (`router`, `method`,
`facilitation`, `circumstances`) і карткою, що вела розмову на якорі. Будь-яке спостереження (нове і старе) читає одна
функція — для синтезатора (S3).

Вимірна ціль: (1) контрактні тести поведінок і інваріантів зелені; запечатані тести інших slice-ів, що закріплюють старий
вигляд одного спостереження, змінено лише objection-пакетом (`test_wrong`, посилання на цей контракт); (2) live
`scripts/analyze_owner_conversation.py` на розмові власника `t-84d1517cb1c1` у стані «До»
(`.engine/artifacts/advice-live/2026-10-25T174143Z-t-84d1517cb1c1/conversation.md`, розділ «До») пише набір, у якому
є спостереження `kind: stuck` з якорями `t5`, `t11` і `t15` (кожен якір — хоча б одне `stuck`) і **немає** `stuck`
на `t9` («в межах місяця» — рішення) і `t13` (перелік болів — нове розуміння) — інакше аналізатор, що позначає все
«застрягла», пройшов би; і поруч — що сказав
старий аналізатор (той самий вхід, інструкція й схема до цього slice-а, з git) → `.engine/artifacts/analysis-rules/
owner-t-84d1517cb1c1.md` (acceptance AC3 фічі, слова задачі); (3) `scripts/smoke_test_skel_learning.py` і
`tests/smoke/test_e2e_local.py` зелені з новим файлом; (4) ruff, mypy, import-linter, швидкий набір — зелені.

## Premise verified
- PR-27 — `unverified`; перевіряє exit criterion (2) у цьому slice-і. Не пройде після виправлень інструкції (три
  спроби з різними правками, кожна записана) — premise `falsified`, AC3 іде до feature-architect.
- Розмова «До» йшла за карткою `opportunity-tree` (не `demand-test`: та з'явилась у `9e4025c` 2026-10-25 22:18Z,
  після «До» — bucket до 14:01Z): `tasks/done/306-unknown-leads-to-test/report.md` рядок 19 (друге — «Opportunity
  Solution Tree …»; «фаза 2 з 5» — у картки 5 фаз); текст #10 «верхню гілку», #14 дерево «Результат → Можливість».
  Три кандидати #2 відтворено з тексту і з карток, що існували тоді (`5d90360`, 2026-10-24): 1 — «в якій робочій
  ситуації… готові платити… що заважає перейти» = `jobs-to-be-done`; 2 — `opportunity-tree`; 3 — «ціль, канали, кроки
  на найближчі дні» = `goal-to-plan` (`traction-channels` теж з'явилась у `9e4025c`). Відтворення, не файл bucket-а:
  справжній `routing.json` теми — лише в розгортанні власника.
- Vertex `generate_json` зі схемою, де `anchor` — `enum`, а відповідь — список об'єктів, приймається: схема-список
  уже ходить у продукті (роутер: `candidates: list[...]` з `enum` id карток, PR-14 `verified`). Зовнішньої поведінки
  понад це немає.

## Out of scope (deliberately)
- Результати кроків (`steps.json`) у вході аналізатора і `kind: step` — S6.
- Синтезатор і стрічка — S3; сторінка спостережень для власника — S3 (`/learning`).
- Межі сесій, `_seen`, контекст аналізованих реплік (continuous-analysis Q1–Q8) — без змін.
- Переписування старих файлів спостережень — лише читаються.
- Зміна фасилітатора чи роутера (правило «застрягла» в `rules.md` — інша річ: те веде, це оцінює).

## Seam (contract)
- **Інструкція `ANALYZER`** (українською) — правила аналізу (вибір архітектора за планом у задачі):
  - **просувається** — у новій репліці людини з'явилось нове розуміння, рішення чи крок;
  - **застрягла** — людина каже, що не знає чи не може знати відповіді, і питання лишається відкритим (особливо
    кілька разів поспіль у розмові, не обов'язково в сусідніх репліках), те саме питання
    фасилітатора вдруге, людина відповідає не на питання, людина просить того, у чому система їй відмовила;
  - **чи підійшов метод** — чи метод, що вів, допоміг з тим, із чим людина прийшла;
  - **причина** — `router` (запропоновано чи обрано не той спосіб), `method` (метод сам не підійшов до ситуації),
    `facilitation` (як ставились питання, як вели), `circumstances` (обставини людини);
  - кожне спостереження — про одне місце; якір — репліка, де це видно найкраще (для «застрягла» — репліка людини, що
    це показує); кілька спостережень на тему, кожне про одне місце; без цитат і подробиць життя людини понад потрібне;
    тільки про нові репліки (рядок «Контекст» лишається, як у continuous-analysis).
- **Номери рішень.** `Decision.turn` — репліка **людини**, на яку відповідало рішення (`converse._decision` ←
  `ctx.turn_no`); відповідь ThinkHow на неї — `turn + 1`. Тож `choose`, `offer`, `ask`, `answer` з `turn = t` діють з
  репліки `t + 1`; `end` з `turn = m` — картка ще вела відповідь `m + 1` (вона й закінчила картку), тож діє з `m + 2`.
- **Вхід моделі**: як зараз (контекст + нові репліки, рядки `#<no> людина|фасилітатор: <текст>`), плюс рядки стану
  методу перед реплікою, з якої рішення діє: `[Метод: <title> (<card_id>)]` перед `#<t+1>` для `choose` з `turn = t`;
  `[Метод закінчено: <card_id> — <пройдено|не підходить>]` перед `#<m+2>` для `end` з `turn = m`; `[Роутер:
  запропоновано <id, …>]` перед `#<t+1>` для `offer`. `<title>` — заголовок картки з `knowledge.current(storage)`,
  прочитаного один раз на прогін; картки немає в чинній ревізії (чи Знань немає) — лише id, тема не падає. Рядок, що
  припадає поза показані репліки, не пишеться; рішення беруться з
  `routing.json` теми через новий читач `workspace.topic_routing(storage, ref) -> tuple[Decision, ...]` (без правила
  доступу, як `topic_sessions`; refs лише від `all_topics_for_learning`; файлу немає → `()`).
- **Схема відповіді** `answer_schema(turn_nos)` → `{observations: list[{kind: "progress"|"stuck"|"method_fit",
  finding: str ≥1, worked: bool, cause: "router"|"method"|"facilitation"|"circumstances", anchor: enum "t<n>" нових
  реплік}]}`, `min_length=1`, без верхньої межі (P5). Порядок полів кожного: `kind, finding, worked, cause, anchor`.
- **Файл** `learning/observations/<uid>/<topic>/t<a>-t<b>.json` (ім'я, `_seen`, діапазон — як зараз) =
  `ObservationSet(uid, topic_id, first_turn, last_turn, analyzed_at, observations: list[Observation])`;
  `Observation(id: "<uid>/<topic_id>/t<a>-t<b>/<k>" (k від 1 за порядком відповіді), turn: int, link:
  "/topics/<uid>/<topic_id>#t<turn>", kind, worked, finding, cause, card_id: str | None, analyzed_at: datetime)` — `analyzed_at` — той самий, що в
  набору (для сортування в S3).
  `card_id` — детерміновано, не від моделі: беруться рішення, що діють на якорі `n` (за правилом «Номери рішень»:
  `choose`/`offer`/`ask`/`answer` з `turn < n`, `end` з `turn + 1 < n`), у порядку `routing.json`; `card_id` — картка
  останнього з них, якщо це `choose`, інакше None (як `current_card`); без `routing.json` — None. Приклади: `choose`
  на `t = 3` → якір 3 — None (людина відповідала роутеру), якір 4 і 5 — картка; `end` на `m = 9` → якір 9 і 10 —
  картка, якір 11 — None. `Observation.id` (`<uid>/<topic_id>/t<a>-t<b>/<k>`) бачить споживач (S3 цитує його) — його
  формат не змінюється.
- **Читач** `learning.observations.read_all(storage) -> list[Observation]` — усі файли під `learning/observations/`
  у порядку (uid, topic, файл, k): у межах теми спершу старі `s<n>.json` за `n`, потім `t<a>-t<b>.json` за `a`: новий набір як є; старий файл діапазону (одне спостереження
  continuous-analysis: `turn, link, worked, finding, cause, first_turn, last_turn`) — набір з одного, `id` =
  `<uid>/<topic>/t<a>-t<b>/1`, `kind` = `progress` при `worked`, інакше `stuck`, `card_id` None, `analyzed_at` — з
  файлу; старий `s<n>.json` (skel-learning: `session_no`, `closed_at`, `analyzed_at`, без `first_turn`/`last_turn`) —
  так само, `id` = `<uid>/<topic>/s<n>/1`, `analyzed_at` — з файлу.
  Файл, що не читається жодним із трьох виглядів, — пропускається з логом `observation_unreadable` (шлях, без
  тексту).
- **`scripts/analyze_owner_conversation.py`** (live, exit criterion 2): вхід — розділ «До» артефакту
  `.engine/artifacts/advice-live/2026-10-25T174143Z-t-84d1517cb1c1/conversation.md`; кладе в тимчасову локальну теку
  тему з `conversation.md` (18 реплік) і `routing.json` (`offer` на 1 — `jobs-to-be-done`, `opportunity-tree`, `goal-to-plan`; `choose` `opportunity-tree` на 3), посів 25 карток;
  кличе новий `analyze` і старий (інструкція й схема з `git show c14fd9b:src/thinkhow/learning/analyze.py`) на тому
  самому вході; пише `.engine/artifacts/analysis-rules/owner-t-84d1517cb1c1.md` (commit старого, модель, регіон, дата,
  сирий JSON обох, таблиця kind/anchor/card_id/cause) і виходить з 1, якщо `stuck` на t5, t11 чи t15 немає або `stuck` є на t9 чи t13.
- `analyze()` — та сама сигнатура і `AnalyzeReport`; невдача моделі — як зараз (`failed`, нічого не записано).
- `learning/local.py` — сценарна відповідь у новій схемі (одне спостереження `progress`, якір — перший з `enum`).
- Errors: як зараз (`ValidationError`, `LlmUnavailable` → `failed`).
- Dependencies (injected): `storage`, `llm`, `now` — як зараз.
- Does NOT do: не читає `steps.json`; не пише нічого, крім `system/learning/observations/`; не змінює `_seen` чи
  контексту; не викликає моделі для `card_id`.

## Decisions (with WHY)
- Q1: Один файл на діапазон з набором спостережень — chosen because ім'я файлу вже несе «що бачено» (`_seen`,
  continuous-analysis Q2), один `write` лишає набір цілим. Rejected: (a) файл на кожне спостереження
  `t<a>-t<b>-<k>.json` — `_seen` і regex змінюються, частковий запис набору можливий; (b) старе поле + `more: [...]` —
  дві форми одного в одному файлі, а `cause: router` все одно ламає старі тести схеми.
- Q2: `card_id` з `routing.json`, детерміновано — chosen because модель не має бачити й вигадувати id карток, а
  рішення вже записані з номерами реплік. Rejected: поле `card_id` у схемі моделі — помилки моделі в id і зайвий
  `enum`; (b) без `card_id` — синтезатор (S3) не знав би, до якої картки нотатка.
- Q3: Стан методу рядками у вході — chosen because «чи підійшов метод» і причина `router` неможливі без знання, який
  метод вів і що пропонував роутер. Rejected: окремий блок «історія методів» нагорі — модель гірше прив'язує його до
  реплік; без цього — правила «метод/роутер» сліпі.
- Q4: Верхньої межі числа спостережень у схемі немає — chosen because P5 і feature critic (раунд 2, note 4).
  Rejected: `max_length=5` — межа без рядка цілей.
- Q5: Старі файли читаються як набір з одного з виведеним `kind` — chosen because у bucket-і вони вже є (сервіс з
  2026-10-23), а синтезатор має бачити все. Rejected: пропускати старі — втрачені спостереження власника.
- Q6: Запечатані тести, що закріплюють старий вигляд (одне спостереження, три причини, поля схеми `finding, worked,
  cause, anchor`) — objection-пакет `test_wrong` з посиланням на цей рядок, одним пакетом на slice-власника; решта
  їхніх перевірок (якір у межах нових реплік, `_seen`, контекст, лог невдачі, лише `system/learning/`) — не
  слабшає. Rejected: залишити старий формат поруч — дві правди.

## Hardest seams (test-confidence points)
- **Seam 1: `card_id` на межах.** Якір = `choose.turn` → None; `choose.turn + 1` → картка; `end.turn` і `end.turn + 1`
  → картка; `end.turn + 2` → None; тема без `routing.json`; `offer` без `choose` → None. Тест з `routing.json`, записаним через `workspace` фікстури, а не з
  мокнутого `topic_routing`.
- **Seam 2: вхід моделі.** Сценарний `llm` ловить `contents`: рядки `[Метод: …]` стоять перед реплікою з номером
  рішення, у контексті й у нових; без `routing.json` — жодного такого рядка.
- **Seam 3: читач трьох виглядів.** Байти старих файлів — буквальний JSON за моделлю `Observation` з `669a07e`
  (`s<n>.json`) і з `c14fd9b` (`t<a>-t<b>.json`), не створені новим кодом.
- **Seam 4: live на справжній розмові.** Вхід — розділ «До» артефакту (18 реплік, #1–#18), розібраний у
  `conversation.md` теми в локальній теці; скрипт відтворює `routing.json` з тексту: `offer` на #1 (`jobs-to-be-done`,
  `opportunity-tree`, `goal-to-plan`), `choose` на #3 картки `opportunity-tree` (друга з трьох у #2).
  Перевірка — по `kind`, `anchor` і `card_id` (для t5, t11, t15 — `opportunity-tree`), не по тексту. Артефакт пише модель,
  регіон, дату і сирий JSON кожного прогону; «три спроби» PR-27 — три різні правки інструкції, не повтори тієї самої; жодна правка не
  додає слів чи прикладів з розмови `t-84d1517cb1c1` (інакше перевірка міряє підгонку, а не правило). Один прогін на
  кожну версію інструкції; номер спроби — в артефакті.

## Invariants (rules that hold for every input of the stated domain)
- **I1** — Кожен якір — нова репліка: для кожного спостереження файлу `first_turn ≤ turn ≤ last_turn` і `link`
  закінчується `#t<turn>`.
  - Domain: файли, які пише цей аналізатор: будь-яка тема з новими репліками, будь-яка валідна відповідь моделі (старі
    `s<n>.json` без `first_turn`/`last_turn` — поза доменом; їх лише читає `read_all`).
  - Source: Seam «Схема відповіді» (`enum` нових); G6.
  - Broken by: якір з контексту або номер, перерахований з індексу списку.
- **I2** — `id` спостережень унікальні серед усіх, що повертає `read_all`, і стабільні: два виклики `read_all` на тих
  самих файлах дають ті самі `id` у тому самому порядку.
  - Domain: будь-яка суміш нових, старих діапазонних і `s<n>.json` файлів.
  - Source: Seam «Читач»; S3 цитує спостереження за `id`.
  - Broken by: `id` з лічильника прогону, з часу чи з позиції файлу в переліку; `k`, рахований через усю тему, а не
    в межах файлу.
- **I4** — `card_id` — картка, що вела репліку якоря: для кожного спостереження `card_id` дорівнює картці за правилом
  «Номери рішень» для `turn`, незалежно від відповіді моделі.
  - Domain: будь-який `routing.json` (будь-яка послідовність рішень, `end` і `choose` підряд), будь-який якір з нових.
  - Source: Seam «`card_id`»; Goal «картка, що вела розмову на якорі».
  - Broken by: `turn ≤ якоря` для `choose` (картка на репліці, що відповідала роутеру) або `card_id` від моделі.
- **I3** — Набір цілий: кількість спостережень у файлі дорівнює кількості в відповіді моделі, у її порядку (`k` = 1…N).
  - Domain: будь-яка відповідь з N ≥ 1.
  - Source: Seam «Файл».
  - Broken by: запис лише першого спостереження або сортування.

## Exit criterion
- Контрактні тести (поведінки Seam, I1–I4) — зелені; objection-пакет до запечатаних тестів skel-learning,
  continuous-analysis, walking-skeleton-block розглянуто тестувальником (`test_wrong` → змінено), решта — зелені.
- `scripts/analyze_owner_conversation.py` (live, `gemini-4-argon`/`eu`): новий аналізатор на розмові `t-84d1517cb1c1`
  «До» → набір з `stuck` на `t5`, `t11`, `t15` і без `stuck` на `t9`, `t13`; старий аналізатор (з `git show c14fd9b:src/thinkhow/learning/analyze.py`
  — інструкція й схема) на тому самому вході — для порівняння; обидва — у `.engine/artifacts/analysis-rules/
  owner-t-84d1517cb1c1.md`. Умова — так/ні з AC3 фічі (слова задачі), без порогу.
- `scripts/smoke_test_skel_learning.py` і `tests/smoke/test_e2e_local.py` (оновлені до набору) — зелені.
- ruff, mypy, `lint-imports`, швидкий набір — зелені.

## Deferred to later slices
- `kind: step` і результати кроків — S6 — revisit trigger: S6 починається. Тип `Observation.kind` у цьому slice-і —
  `progress|stuck|method_fit|step` (читач приймає `step` уже зараз, щоб S3 не закріпив вужчого); схема моделі — без
  `step`, його додає S6.
- Сторінка спостережень для власника — S3 — revisit trigger: S3.
- `kind` старих файлів виведено з `worked` (наближення: старе `worked: false` могло бути й `method_fit`) — revisit
  trigger: власник побачить старі спостереження в `/learning` (S3).

## Open items requiring human decision (if any)
- (немає)

## Critic notes (non-blocking)
- Раунд 1 (фази 2–5 разом): REVISE — `card_id` на `choose.turn` хибно давав нову картку → правило «Номери рішень»,
  приклади, рядки стану перед `#t+1`/`#m+2`, I4. Notes внесено: 18 реплік і `card_id` у live, джерело `<title>`,
  базовий commit `c14fd9b`, сирий JSON у артефакті, без числа «одне–п'ять», домен I1, `Observation.id` — контракт,
  наближення `kind` старих файлів у «Deferred». Cold reader: REVISE — `Observation` без `analyzed_at`, а S3 сортує за
  ним → поле додано для всіх трьох виглядів; notes: Seam-рядок скрипта live, сильніший «Broken by» I2. Cold reader 2:
  REVISE — відтворений `routing.json` називав `demand-test`, якої тоді не було → `opportunity-tree` і три кандидати з
  джерелом у «Premise verified»; notes: порядок старих `s<n>.json`. Третій cold reader — AUTONOMOUS (escalations.md):
  виправлення фактичне, не розвилка. Cold reader 3: REVISE — перевірка live проходила б для аналізатора, що все
  позначає «застрягла», а правило «застрягла» мало слова з самої розмови → загальне правило, заборона слів розмови в
  правках, перевірка «немає `stuck` на t9, t13»; notes: `kind` приймає `step`, байти старих файлів з commit-ів, один
  прогін на версію. Запечатано без четвертого читача — AUTONOMOUS (escalations.md).
