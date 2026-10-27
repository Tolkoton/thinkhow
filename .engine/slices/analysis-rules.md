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
є спостереження `kind: stuck` з якорями `t5`, `t11` і `t15` (кожен якір — хоча б одне `stuck`), і поруч — що сказав
старий аналізатор (той самий вхід, інструкція й схема до цього slice-а, з git) → `.engine/artifacts/analysis-rules/
owner-t-84d1517cb1c1.md` (acceptance AC3 фічі, слова задачі); (3) `scripts/smoke_test_skel_learning.py` і
`tests/smoke/test_e2e_local.py` зелені з новим файлом; (4) ruff, mypy, import-linter, швидкий набір — зелені.

## Premise verified
- PR-27 — `unverified`; перевіряє exit criterion (2) у цьому slice-і. Не пройде після виправлень інструкції (три
  спроби з різними правками, кожна записана) — premise `falsified`, AC3 іде до feature-architect.
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
  - **застрягла** — кілька «не знаю» поспіль (або «звідки мені знати», «то якраз треба вияснити»), те саме питання
    фасилітатора вдруге, людина відповідає не на питання, людина просить того, у чому система їй відмовила;
  - **чи підійшов метод** — чи метод, що вів, допоміг з тим, із чим людина прийшла;
  - **причина** — `router` (запропоновано чи обрано не той спосіб), `method` (метод сам не підійшов до ситуації),
    `facilitation` (як ставились питання, як вели), `circumstances` (обставини людини);
  - кожне спостереження — про одне місце; якір — репліка, де це видно найкраще (для «застрягла» — репліка людини, що
    це показує); кілька спостережень на тему (порадою: одне–п'ять); без цитат і подробиць життя людини понад потрібне;
    тільки про нові репліки (рядок «Контекст» лишається, як у continuous-analysis).
- **Вхід моделі**: як зараз (контекст + нові репліки, рядки `#<no> людина|фасилітатор: <текст>`), плюс рядки стану
  методу перед реплікою, з якої він діє: `[Метод: <title> (<card_id>) — з #<n>]` для `choose`, `[Метод закінчено:
  <card_id> — <пройдено|не підходить>]` для `end`, `[Роутер: запропоновано <id, …>]` для `offer`; рішення беруться з
  `routing.json` теми через новий читач `workspace.topic_routing(storage, ref) -> tuple[Decision, ...]` (без правила
  доступу, як `topic_sessions`; refs лише від `all_topics_for_learning`; файлу немає → `()`).
- **Схема відповіді** `answer_schema(turn_nos)` → `{observations: list[{kind: "progress"|"stuck"|"method_fit",
  finding: str ≥1, worked: bool, cause: "router"|"method"|"facilitation"|"circumstances", anchor: enum "t<n>" нових
  реплік}]}`, `min_length=1`, без верхньої межі (P5). Порядок полів кожного: `kind, finding, worked, cause, anchor`.
- **Файл** `learning/observations/<uid>/<topic>/t<a>-t<b>.json` (ім'я, `_seen`, діапазон — як зараз) =
  `ObservationSet(uid, topic_id, first_turn, last_turn, analyzed_at, observations: list[Observation])`;
  `Observation(id: "<uid>/<topic_id>/t<a>-t<b>/<k>" (k від 1 за порядком відповіді), turn: int, link:
  "/topics/<uid>/<topic_id>#t<turn>", kind, worked, finding, cause, card_id: str | None)`.
  `card_id` — детерміновано, не від моделі: картка останнього `choose` з `turn` ≤ якоря, якщо між ним і якорем (`turn` <
  якоря) немає `end`; інакше (і без `routing.json`) None.
- **Читач** `learning.observations.read_all(storage) -> list[Observation]` — усі файли під `learning/observations/`
  у порядку (uid, topic, first_turn, k): новий набір як є; старий файл діапазону (одне спостереження
  continuous-analysis: `turn, link, worked, finding, cause, first_turn, last_turn`) — набір з одного, `id` =
  `<uid>/<topic>/t<a>-t<b>/1`, `kind` = `progress` при `worked`, інакше `stuck`, `card_id` None; старий `s<n>.json`
  (skel-learning: `session_no`, `closed_at`, без `first_turn`/`last_turn`) — так само, `id` = `<uid>/<topic>/s<n>/1`.
  Файл, що не читається жодним із трьох виглядів, — пропускається з логом `observation_unreadable` (шлях, без
  тексту).
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
- **Seam 1: `card_id` на межах.** Якір на репліці, де щойно `choose` (той самий `turn`), після `end` (якір > `end`),
  тема без `routing.json`, `offer` без `choose`. Тест з `routing.json`, записаним через `workspace` фікстури, а не з
  мокнутого `topic_routing`.
- **Seam 2: вхід моделі.** Сценарний `llm` ловить `contents`: рядки `[Метод: …]` стоять перед реплікою з номером
  рішення, у контексті й у нових; без `routing.json` — жодного такого рядка.
- **Seam 3: читач трьох виглядів.** Справжні байти старих файлів (як їх писали skel-learning і continuous-analysis —
  з їхніх фікстур), не створені новим кодом.
- **Seam 4: live на справжній розмові.** Вхід — розділ «До» артефакту, розібраний у `conversation.md` теми в
  локальній теці (17 реплік, без `routing.json` власника не було? — є: #3 «почати з другого» = `choose`; скрипт
  відтворює `routing.json` з тексту: `offer` на #1, `choose` на #3 картки `demand-test` (друга з трьох у #2), щоб
  `card_id` був справжнім). Перевірка — по `kind` і `anchor`, не по тексту.

## Invariants (rules that hold for every input of the stated domain)
- **I1** — Кожен якір — нова репліка: для кожного спостереження файлу `first_turn ≤ turn ≤ last_turn` і `link`
  закінчується `#t<turn>`.
  - Domain: будь-яка тема з новими репліками, будь-яка валідна відповідь моделі.
  - Source: Seam «Схема відповіді» (`enum` нових); G6.
  - Broken by: якір з контексту або номер, перерахований з індексу списку.
- **I2** — `id` спостережень унікальні серед усіх, що повертає `read_all`, і стабільні: два виклики `read_all` на тих
  самих файлах дають ті самі `id` у тому самому порядку.
  - Domain: будь-яка суміш нових, старих діапазонних і `s<n>.json` файлів.
  - Source: Seam «Читач»; S3 цитує спостереження за `id`.
  - Broken by: `id` з лічильника прогону чи з часу; однакові `id` для старого `s1.json` і `t1-t2.json`.
- **I3** — Набір цілий: кількість спостережень у файлі дорівнює кількості в відповіді моделі, у її порядку (`k` = 1…N).
  - Domain: будь-яка відповідь з N ≥ 1.
  - Source: Seam «Файл».
  - Broken by: запис лише першого спостереження або сортування.

## Exit criterion
- Контрактні тести (поведінки Seam, I1–I3) — зелені; objection-пакет до запечатаних тестів skel-learning,
  continuous-analysis, walking-skeleton-block розглянуто тестувальником (`test_wrong` → змінено), решта — зелені.
- `scripts/analyze_owner_conversation.py` (live, `gemini-4-argon`/`eu`): новий аналізатор на розмові `t-84d1517cb1c1`
  «До» → набір з `stuck` на `t5`, `t11`, `t15`; старий аналізатор (з `git show <base>:src/thinkhow/learning/analyze.py`
  — інструкція й схема) на тому самому вході — для порівняння; обидва — у `.engine/artifacts/analysis-rules/
  owner-t-84d1517cb1c1.md`. Умова — так/ні з AC3 фічі (слова задачі), без порогу.
- `scripts/smoke_test_skel_learning.py` і `tests/smoke/test_e2e_local.py` (оновлені до набору) — зелені.
- ruff, mypy, `lint-imports`, швидкий набір — зелені.

## Deferred to later slices
- `kind: step` і результати кроків — S6 — revisit trigger: S6 починається.
- Сторінка спостережень для власника — S3 — revisit trigger: S3.

## Open items requiring human decision (if any)
- (немає)

## Critic notes (non-blocking)
- (заповнюється)
