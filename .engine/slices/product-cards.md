# Slice product-cards — planning artifact

Task: `tasks/doing/307-product-thinking-pack.md` (клас 3, конвеєр, без нагляду). Driven mode: slice S1 (tracer
bullet) feature-а `.engine/architecture/feature/product-thinking-pack.md`; рамку взято звідти, не спитано.

## Goal
У Знаннях — сім нових карток продуктового мислення з research 04 (`docs/research/04-product-pack.md` §1, §3):
`customer-interviews`, `demand-test`, `positioning`, `offer-design`, `value-pricing`, `traction-channels`,
`unit-economics` — українською, за схемою F6 без змін, з назвою методу в `method` (задача 205). Набір ситуацій
роутера має випадки кожної з них. Роутер без зміни коду бачить 25 карток і на першу репліку розмови власника
`t-84d1517cb1c1` («… як це продати?») відповідає валідною пропозицією на `eu`.

Вимірна ціль:
1. `cards/` — рівно 25 файлів: 18 id задачі 302 і 7 id вище; кожен приймає `Card.model_validate`, `card_prompt`
   рендерить; `pre-mortem.yaml` — той самий blob `8f52b66a795076cbe4e49965f8fb9b0b4009dd03`.
2. `tests/fixtures/routing/cases.yaml`: 85 старих випадків без змін тексту, `expect` і `not_first`; на кожну нову
   картку ≥3 позитивні (третій, `<префікс>-3`, — відкладена частина) і ≥1 hard negative; `also_ok` старих випадків
   доповнено лише там, де нова картка — справжня нічия, з причиною в коментарі.
3. Повний набір тестів зелений (`uv run pytest`), `ruff`, `mypy`, `lint-imports` чисті; змінено лише запечатані
   тести, названі в Q4, — через заперечення slice-tester-у.
4. Smoke `scripts/smoke_test_product_cards.py` на справжній моделі (`gemini-4-argon`, Vertex `eu`) — код 0.

## Premise verified
- P1 (які тести ламає 25 карток): прогін повного набору в копії дерева (`git worktree /tmp/th307` на `6091f88`, 7
  заглушок — копії `five-whys.yaml` з новими id, 2026-10-25): `20 failed, 870 passed`. Падають:
  cards-library — `test_cl_content.py::test_seam5_cards_holds_exactly_the_18_ids_of_the_goal`,
  `test_cl_job.py::test_goal2_…_18_cards…`, `test_cl_catchup_smoke.py` (3), `test_cl_catchup_disputed_q1_smoke_checks.py`,
  `test_cl_catchup_disputed_q2_smoke_output.py` (п'ять останніх — через `scripts/smoke_test_cards_library.py:60`
  `len(state.cards) == 18`); router-eval — `test_rev_cases.py` (4: кількість `== 18` у рядках 35, 90 і відсутні
  випадки нових карток), `test_rev_conversations.py::test_person_instruction_names_no_method_for_the_situation_of_every_card`
  (немає позитивного випадку нової картки), `test_tmr_block.py` (5: `s1_to_s2`, `s1_to_s3`, `ac4`, `ac5`, `ac6`);
  skel-knowledge — `test_skelk_real_card.py::test_seeding_the_repository_cards_gives_revision_1_with_pre_mortem`;
  незапечатані — `test_ntm_methods.py::test_every_card_names_its_method_pre_mortem_by_its_sealed_title`,
  `tests/live/test_router_live.py::test_the_detector_knows_every_card_by_id_and_by_name`.
- P2 (роутер без зміни коду бере всі картки ревізії): `tests/contract/thinking_models_router_block/tmr_fakes.py:42`
  і `src/thinkhow/facilitation/route.py` будують інструкцію з `knowledge.cards` — `test_tmr_block.py::test_s1_to_s2…`
  у копії з 25 картками падає лише на `len(CARD_IDS) == 18`, тобто роутер бачить усі 25. Живу перевірку дає smoke
  (PR-20 у `.engine/premises/premise-log.md`).
- Vertex `eu` і `gemini-4-argon` — PR-01 `verified`; ADC на сервері працює (прогін 180821Z задачі 306, 2026-10-25).

## Out of scope (deliberately)
- Прогони набору ситуацій, правки карток за плутаниною, живі розмови, звіт «старі / нові» — S2.
- Зміни коду `src/` (роутер, фасилітатор, схема F6, `card_prompt`) — feature, P5.
- Зміна `cards/pre-mortem.yaml` і текстів, `expect`, `not_first` старих випадків.
- Розгортання (Job `cards` на сервері) — крок закриття задачі (запит Сонькові).
- SPIN, Lean Canvas та інші відкладені методи — research 04 §5.

## Seam (contract)
- Content (7 файлів `cards/<id>.yaml`): поля F6 (`id`, `title`, `method`, `router` з `needs`/`when_yes`/`when_no`/
  `signals`, `facilitator` з `purpose`/`stance`/`needs`/`phases`/`ending`/`traps`/`pairs_well`), як 18 наявних;
  коментар нагорі називає розділ research 04. Для кожної:
  - `purpose` чесно називає доказовість за research 04 (Tier B для `demand-test` — про підхід «гіпотеза → тест»,
    Tier D для `offer-design` — «практика без досліджень»);
  - фази ведуть питаннями (N1): картка не пише за людину офер, позиціонування, ціну; рахує фасилітатор лише з чисел
    людини; фаза закінчується тим, що людина назвала сама;
  - `offer-design` має запобіжники research 04 §3.4: офер — гіпотеза, наприкінці — як перевірити; без штучного
    дефіциту, вигаданих бонусів і тиску; гарантія — лише та, яку людина виконає;
  - `customer-interviews`, `value-pricing`, `demand-test` спираються на те, що гіпотетичні «купив би» і «заплатив би»
    завищені (research 04 §3.1), і ведуть до перевірки діями чи грошима;
  - `method`: `The Mom Test (Fitzpatrick)`; `Pretotyping і гіпотеза XYZ (Savoia)`; `Positioning (Dunford)`;
    `Value Equation (Hormozi)`; `Economic Value to the Customer (EVC)`; `Bullseye (Traction)`;
    `Unit economics (LTV і CAC)` — кожна частина до дужки стоїть у research 04;
  - останній trap — «Не той випадок» з межами `when_no`.
- `pairs_well` нових карток — за шляхом research 04 §6.
- Межі (research 04 §4; пару `traction-channels` ↔ `demand-test` бере з §3.6, `value-pricing` ↔ `positioning` — з
  §2, де позиціонування стоїть перед ціною; `unit-economics` межі `when_no` не має — research 04 §4 не називає їй близької
  картки (сусіди в `pairs_well` — за §6), межа з `weighted-matrix` — лише hard negative `ue-neg-1`): `when_no` нових карток і старих `jobs-to-be-done`, `opportunity-tree` називають сусіда
  (`customer-interviews` ↔ JTBD; `demand-test` ↔ `opportunity-tree`; `offer-design` ↔ `value-pricing` ↔
  `positioning`; `traction-channels` ↔ `demand-test`); `pairs_well` старих JTBD і `opportunity-tree` — нові сусіди.
  Інші старі картки не змінюються.
- Cases (`tests/fixtures/routing/cases.yaml`), написані з research 04 §2–§4 **до** половин `router` нових карток:
  префікси `ci-`, `dt-`, `pos-`, `of-`, `vp-`, `tc-`, `ue-`; `<префікс>-1..3` — `kind: positive`, `-3` — відкладена
  частина; `<префікс>-neg-N`, N ≤ 2 (жоден негативний id не закінчується на `-3`) — `kind: negative` з `not_first: [<нова картка>]` (зокрема на пари меж вище, і хоча б
  один hard negative, де нова картка — `expect`, а стара в `not_first`); 2–3 нічиї між новими (`tie-…`, ім'я не
  закінчується на `-3`); старі випадки — лише `also_ok`, блоковим списком (один запис на рядок), і кожен доданий запис — з коментарем
  `# 307: <чому нічия>` у своєму рядку.
- Tests and scripts (не код продукту):
  - запечатані — лише через заперечення (Q4);
  - `tests/contract/name_the_methods/test_ntm_methods.py`: кількість — з `cards/` (25); назва методу — у research 01
    **або** research 04; заборона торговельних марок — і `SPIN`, `Blue Ocean`, `Value Proposition Canvas`;
  - `tests/live/test_router_live.py`: детектор назв знає 7 нових карток (`OWN_NAMES` з характерною основою або
    `NO_OWN_NAME` — Q3); рядок «Знання — 18 карток» (`:211`) → `len(cards)`;
  - `scripts/smoke_test_cards_library.py:60` → `len(state.cards) == 25` (літерал: запечатаний
    `test_cl_catchup_disputed_q1_smoke_checks.py` видаляє чи додає картку в копії й чекає, що smoke впаде);
  - `scripts/router_eval.py:255` «Знання — 18 карток» → кількість з Знань; docstring `scripts/card_conversations.py:55`.
- Smoke `scripts/smoke_test_product_cards.py`: тимчасове `LocalStorage` → `seed` з `cards/` → `current` має 25 карток,
  серед них 7 нових → `facilitation.route` на справжній моделі з першою реплікою власника (`#1` з
  `.engine/artifacts/advice-live/2026-10-25T174143Z-t-84d1517cb1c1/conversation.md`, дослівно; у скрипті — константою
  з посиланням) → відповідь валідна за схемою роутера; друкує дію, кандидатів з `why`, текст і рядок «нові картки серед
  кандидатів: […]» (не умова успіху — зміст пропозиції міряє S2); код 0 лише тоді, коли дія `offer` з 2–3 кандидатами
  і кожен id кандидата є в `cards/`; інша дія, порожній список чи невідомий id — код 1. Один повтор після не-`offer`
  дозволено лише з записом першої відповіді в артефакті (Q7).
  Вивід — `.engine/artifacts/spikes/product-cards-router-live-<час>.txt`.
- Does NOT do: не змінює `src/`; не запускає набір ситуацій і живих розмов; не змінює `pre-mortem.yaml` і старі
  випадки, крім `also_ok`.

## Decisions (with WHY)
- Q1: сім карток, по одній на питання ланцюжка «кому → що → скільки → де → чи сходиться → як перевірити» — research
  04 §1, §4. Rejected: одна картка «продаж» з підрежимами — роутер не міг би запропонувати потрібний крок, а
  фасилітатор губився б (як `opportunity-tree`, рішення задачі 302 тримати розбиття під тригером); Rejected: 10+
  карток (SPIN, Lean Canvas…) — дублікати чи анкети (research 04 §5), «семантична тіснота» (research 01 §7(ґ).2).
- Q2: випадки — у цьому slice-і, перед половинами `router`: запечатані `test_rev_cases.py` і `test_tmr_block.py`
  пов'язують картки й випадки, тож окремо вони не можуть бути зеленими (feature critic, раунд 1). Ризик «набір з
  текстів карток» закриває порядок (випадки першими) і запечатаний тест 6 слів поспіль. Rejected: випадки в S2 —
  S1 не мав би зеленого виходу.
- Q3: детектор назв `tests/live/test_router_live.py` — `OWN_NAMES` лише для власних назв методу з основою, що не
  трапляється в звичайній мові роутера (`mom test`, `pretotyp`, `xyz`, `dunford`, `value equation`, `hormozi`,
  `evc`, `bullseye`, `ltv`, `cac`; короткі — з межами слова `\b…\b`, як наявні `\brice\b`, `\bost\b`); англійський
  id у відповіді (`_id_pattern`: `positioning`, `demand test`, `unit economics`) — теж назва методу, і це прийнято;
  загальні слова «ціна», «офер», «канал», «позиціонування» не ловляться — бо
  детектор має ловити назву методу, а не тему розмови. Решта — `NO_OWN_NAME`. Rejected: ловити «позиціонуван» —
  звичайна відповідь роутера про позиціонування стала б «назвою методу».
- Q4: запечатані тести «18 карток» — їхню передумову скасовує задача власника 307. Три пакети заперечень
  (`testing.py request <slug> --tester objection --package <файл>`), суть кожного тесту лишається:
  - cards-library: `test_cl_content.py` — `GOAL_IDS` = 18 id задачі 302 + 7 id задачі 307; заборони торговельних
    марок, «час змінити метод», кризового тексту — на всі картки, крім `pre-mortem` (24); `test_cl_job.py` — ревізія 2
    з усіма 25 (`test_cl_disputed_q1_case_insensitive.py` з 25 картками не падає — P1 — і не змінюється: I4 і
    `test_cl_content.py` вже тримають заборони на всіх 24, регістронезалежно);
  - router-eval: `test_rev_cases.py` — `len(known) == 18` і `len(held) == 18` → 25; `test_tmr_block.py` — `s1_to_s2`,
    `s1_to_s3`, `ac6`: 25 замість 18; `ac4` і `ac5` (AC feature-а задачі 302: звіт і живі розмови для кожної з її 18
    карток) — обмежити 18 id задачі 302, бо AC тих самих перевірок для 7 нових — у S2 (новий тест там);
  - skel-knowledge: `test_skelk_real_card.py` — `REPOSITORY_CARD_IDS` = 25 id.
  Rejected: тримати нові картки в іншій теці — ламає посів і роутер.
- Q5: smoke — `route` прямо, без `converse` і `workspace`: tracer перевіряє Знання з 25 карток → роутер → модель;
  `converse`/`workspace` не змінюються і мають свої запечатані тести. Rejected: повна розмова — це S2.
- Q7: smoke успішний лише на `offer` з 2–3 кандидатами з `cards/` — як «Integration exit criterion» feature-а; прогін
  задачі 305 на тій самій репліці дав `offer` з трьох способів, тож це очікувана поведінка. Rejected: код 0 і на
  `ask`/`choose` — tracer тоді не ловив би роутер, що нічого не пропонує на «як це продати?» (slice critic, фаза 2).
- Q6: `also_ok` старих випадків — лише до прогону 1 (S2), з причиною; бо інакше «не гірше» підганяється
  (feature, «Не гірше»).

## Hardest seams (test-confidence points — distinct from the contract Seam above)
- **Seam 1: картка пройшла схему, але порушує правила бібліотеки** (копію з чужим вмістом ловить Seam 6) — тести на справжній `cards/`: 25 id; кожна
  валідна, id = ім'я файлу, `card_prompt` рендерить; остання пастка «Не той випадок»; `method` не порожній (крім
  `pre-mortem`) і його назви — у research 01 або 04; торговельні марки й заборонені фрази — ні в одній, крім
  `pre-mortem`. Відкидає картку без назви методу чи «Не той випадок».
- **Seam 6: картка-копія з чужим вмістом** — тест з таблицею в самому тесті, рядок на кожну з 7 нових карток:
  `method` дорівнює рядку з Seam дослівно; перший коментар файлу називає свій розділ research 04 (`§3.1`…`§3.7`);
  `facilitator.purpose` має позначку доказовості (`demand-test` — «рандомізован»; `offer-design` — «без досліджень»;
  `unit-economics` — «арифметик»; решта — «практик»); `customer-interviews`, `value-pricing`, `demand-test` — у текстах фасилітатора є «гіпотетичн»
  або «купив би» / «заплатив би»; `offer-design` — «гіпотез» і «перевір» в останній фазі чи `ending`, «дефіцит» і
  «гаранті» в текстах. Відкидає копію `five-whys.yaml` під новим id (P1: така копія проходить схему, I1–I4 і Seam 3).
  Чого механічно не перевірити — що картка веде питаннями і не пише за людину (N1), без тиску на клієнта, — перевіряють
  живі розмови S2 і читач звіту (`reader`).
- **Seam 2: набір ситуацій, написаний з карток** — запечатаний 6-грамний тест на всіх 25; плюс порядок у Seam
  (випадки комітяться окремим commit-ом до половин `router` — видно в git log). Відкидає підгонку набору.
- **Seam 3: межі між сусідами** — тест з таблицею в самому тесті. Пари: `customer-interviews` ↔ `jobs-to-be-done`,
  `demand-test` ↔ `opportunity-tree`, `offer-design` ↔ `value-pricing`, `offer-design` ↔ `positioning`, `value-pricing`
  ↔ `positioning`, `traction-channels` ↔ `demand-test` (обидві сторони кожної). Кожного сусіда називає його фраза —
  так, як бібліотека вже називає сусідів у `when_no` (JTBD: «Дерево питань»): `jobs-to-be-done` — «наймають»;
  `opportunity-tree` — «дерево можливостей»; `customer-interviews` — «розмови з клієнтами»; `demand-test` —
  «перевірка попиту»; `offer-design` — «офер»; `value-pricing` — «ціна від цінності»; `positioning` —
  «позиціонування»; `traction-channels` — «канали». Хоча б один пункт `router.when_no` сторони містить фразу сусіда
  (регістронезалежно, після тієї самої нормалізації лапок і апострофів, що в детекторі). Тест має рядок-перевірку
  самого правила: `when_no` без фрази сусіда — падає. Фрази обрано так, що в `when_no` старих `jobs-to-be-done` і
  `opportunity-tree` до slice-а їх немає (`git show 6091f88:cards/…`), тож зелений тест означає дописану межу. І в
  `cases.yaml` для кожної пари є випадок `kind: negative`, де одна сторона — `expect`, інша — в `not_first`.
  Відкидає межу, записану лише з одного боку, і пару без hard negative.
- **Seam 4: запечатані тести** — повний набір після змін; кожен змінений запечатаний тест — лише в пакеті
  заперечення з причиною; суть (що тест ловить) — та сама: перевірка, що копія з 24 чи 26 картками валить smoke,
  лишається.
- **Seam 5: smoke на справжній моделі** — не підробка `llm`: справжній `gemini-4-argon`, рядок `llm_call` у виводі
  друкує журнал продуктового порту моделі (`src/thinkhow/platform/llm.py`), а не скрипт, з моделлю; регіон
  (`settings.location`) smoke друкує окремим рядком.

## Invariants (rules that hold for every input in the stated domain)
- **I1** — кожна картка в `cards/` валідна за F6, її id = ім'я файлу, остання пастка — «Не той випадок», і (крім
  `pre-mortem`) `method` не порожній, а кожна назва в ньому стоїть у research 01 або research 04.
  - Domain: усі файли `cards/*.yaml` (25 після slice-а; і будь-яка майбутня картка).
  - Source: feature «Build parameters» (policies про картки); задача 205 (назва методу).
  - Broken by: нова картка без `method`, з назвою, якої немає в дослідженнях, або без «Не той випадок».
- **I2** — для кожної картки в `cards/` у `cases.yaml` є ≥3 позитивні випадки з нею як `expect`, рівно один з них —
  `-3`, і ≥1 негативний з нею в `not_first`.
  - Domain: усі картки `cards/`.
  - Source: задача 307 «Роутер» (позитивні, hard negatives, відкладена частина); запечатані `test_rev_cases.py`.
  - Broken by: нова картка без випадків або без відкладеної частини; негативний випадок з id на `-3`.
- **I3** — жодні 6 слів поспіль з тексту будь-якого випадку не стоять в одному пункті `router` будь-якої картки.
  - Domain: усі випадки `cases.yaml` × усі картки `cards/`.
  - Source: задача 302 (набір не з текстів карток); запечатаний `test_rev_cases.py::test_no_six_words…`.
  - Broken by: половина `router`, списана з випадку.
- **I4** — у жодній картці `cards/`, крім `pre-mortem`, немає торговельних марок research 01 §3.6 і research 04 §5
  (`Kepner`, `Cynefin`, `WOOP`, `GROW™`, `Outcome-Driven`, `\bODI\b`, `Six Thinking Hats`, `\bSPIN\b`, `Blue Ocean`,
  `Value Proposition Canvas`) і фраз «час змінити метод», кризового тексту — регістронезалежно.
  - Domain: усі рядки всіх картки `cards/`, крім `pre-mortem.yaml`.
  - Source: research 01 §3.6, research 04 §5; заборони задачі 302 (Seam 5 `cards-library`); N3.
  - Broken by: нова картка, що називає SPIN чи пише кризовий текст.

- **I5** — кожен з 85 старих випадків (ids у `6091f88:tests/fixtures/routing/cases.yaml`) має ті самі `kind`, `text`,
  `expect`, `not_first` (і `history`, `offered`, `absent`, `ended`, де є), а його `also_ok` лише доповнено; кожен
  доданий запис стоїть у рядку з коментарем `# 307:`.
  - Domain: усі випадки `cases.yaml` з ids, що були в commit `6091f88`.
  - Source: «Goal» 2; feature «Не гірше» (старі випадки не змінюються, крім `also_ok` до прогону 1).
  - Broken by: правка `expect` чи `not_first` старого випадку, коли нова картка «забирає» його.

## Exit criterion
- Тести: `uv run pytest` (повний набір) зелений; серед них `tests/contract/cards_library/*` і
  `tests/contract/router_eval/test_rev_cases.py` після заперечень, `test_ntm_methods.py`, детектор
  `test_router_live.py` (офлайн-частина), нові тести slice-а на I1–I5 (I5 — порівняння з
  `git show 6091f88:tests/fixtures/routing/cases.yaml`), Seam 3 і Seam 6. `uv run ruff check`, `uv run mypy`,
  `uv run lint-imports` — чисто.
- Заперечення: три вердикти slice-tester-а (`objection`) у `.engine/testing/ledger.md` для cards-library, router-eval,
  skel-knowledge — `test_wrong` на кожен змінений запечатаний тест; `testing.py check` кожного з трьох — `match`.
- Порядок: commit з випадками нових карток стоїть у `git log` раніше за commit з їхніми картками.
- Smoke: `PYTHONPATH=src uv run python scripts/smoke_test_product_cards.py` на сервері з ADC — код 0, вивід у
  `.engine/artifacts/spikes/product-cards-router-live-<час>.txt` (шлях — у `.engine/PROGRESS.md`) з рядком `llm_call`,
  моделлю і регіоном (`gemini-4-argon`, `eu`), числом карток `current` (25) і переліком 7 нових ids, дією `offer` і 2–3 кандидатами з `cards/`. Код 0 не
  означає, що запропоновано нову картку: зміст пропозиції міряє S2.
- Порогів немає.

## Deferred to later slices
- Прогони 1 і 2 набору, правки за плутаниною, 7 живих розмов, звіт «старі / нові», тест AC4/AC5 для 7 нових — S2
  `product-router-eval` — why later: S1 отримує зелений tracer без недетермінізму живої моделі у виході; S2 платить
  AC4/AC5 для 7 нових карток і новий тест — revisit trigger: S1 закрито. S2 не додає `also_ok` старим випадкам (I5:
  набір заморожено до прогону 1).
- SPIN Selling — research 04 §5 — revisit trigger: у розмовах людей (живі розмови S2, плутанини прогону, сигнал G7
  «бракує способу думати») з'являється підготовка до продажної розмови, яку `customer-interviews` не покриває.

## Open items requiring human decision (if any)
- Немає.

## Critic notes (non-blocking)
- Cold reader (PASS): регіон не входить у `llm_call` — smoke друкує `settings.location` сам (внесено); Seam 3 —
  перевірка по парах, не «будь-яка фраза»; порядок Q6/Q7 — косметика.
- Фаза 2, раунд 1 (BLOCKING → Q7): smoke був слабший за контракт feature-а; нотатки — §-посилання пар, `\b` для
  коротких основ, рядок «нові картки серед кандидатів», `test_cl_disputed_q1…` прибрано з пакета.
- Фаза 3, раунд 1 (BLOCKING → Seam 6): копія `five-whys.yaml` під новим id проходила все; нотатки — `-neg-N` ≤ 2,
  корені замість відмінків, `unit-economics` без пари свідомо, порожній список кандидатів — код 1.
- Фаза 4, раунд 1 (BLOCKING → I5): нічого не ловило правку старих випадків; нотатки — вердикти заперечень і порядок
  commit-ів у виході, перелік 25 карток у виводі smoke.
- Фаза 3, раунд 3 (PASS); нотатки — фразу сусіда писати в лапках у називному відмінку, як «Дерево питань» у JTBD;
  `also_ok` блоковим списком; `\bSPIN\b` — внесено.
- Фаза 3, раунд 2 (BLOCKING → Seam 3): основи «цін», «дерев», «клієнт» уже стоять у `when_no` старих карток —
  тест проходив без межі; тепер — фраза-назва сусіда, якої до slice-а там немає, і рядок, що правило падає без неї.
  Нотатки: `unit-economics` — «арифметик»; хто друкує `llm_call`.
- Фаза 4, раунд 2 (PASS); нотатки — повтор smoke, модель і регіон, `testing.py status`, blob pre-mortem — внесено.
- Фаза 2, раунд 2 (PASS); нотатки — `pairs_well` нових карток за research 04 §6; `unit-economics` без межі `when_no`
  (§4), але з сусідами в `pairs_well` (§6).
- Фаза 5, раунд 2 (PASS); нотатки — PR-21 перевіряють живі розмови S2; запис про брак способу думати — рядок звіту S2.
- Фаза 5, раунд 1 (BLOCKING): вимогу `offer` тихо переносило в S2 — знято: smoke знову вимагає `offer` (Q7); нотатки —
  чому S2 пізніше, тригер SPIN, S2 не додає `also_ok`.
