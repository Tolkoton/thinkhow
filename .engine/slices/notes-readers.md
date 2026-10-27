# Slice notes-readers — planning artifact

Feature: `.engine/architecture/feature/learning-loop.md`, slice **S4** (F5 «зворотний шлях досвіду»). Board task
`tasks/doing/309-close-learning-loop.md`, unattended. Driven mode: frame from the feature's S4 entry and contract S1 → S4
(`MemoryRecord.audience`, `.engine/slices/knowledge-versions.md`); nothing asked.

## Goal
Роутер і фасилітатор читають нотатки до методів чинної ревізії: роутер — нотатки `router` біля кожної картки, яку вони
називають (коли пропонувати, з чим плутають); фасилітатор — нотатки `facilitator` лише своєї картки.

Вимірна ціль: (1) контрактні тести зелені; (2) `scripts/smoke_test_notes_readers.py` на 25 справжніх картках і двох
нотатках (`router` до `pre-mortem`, `facilitator` до `five-whys`) друкує інструкцію роутера (нотатка стоїть у розділі
`pre-mortem` і ніде більше) і фасилітатора для `five-whys` (нотатка є) і для `pre-mortem` (нотатки `five-whys` немає) →
`.engine/artifacts/notes-readers/smoke.txt`; (3) запечатані тести зелені, крім тих, що закріплюють «пам'ять фасилітатора без фільтра
за карткою», — objection-пакет `test_wrong` з посиланням на Q1 цього контракту (перелік — «Exit criterion»); (4) ruff, mypy, import-linter, швидкий набір — зелені.

## Premise verified
- Внутрішній: старі записи пам'яті без `audience` читаються як `facilitator` (S1 Seam «Схема»). Зовнішніх premise
  немає — тексти інструкцій, виклик моделі той самий. Чи нотатки не погіршують роутера — PR-28, перевіряє S5 на
  справжніх нотатках.

## Out of scope (deliberately)
- Вміст нотаток — S5 (стартові), S3 (синтезатор).
- Читання `steps.json` інших тем — відкладено фічею.
- Зміна правил роутера чи фасилітатора (`router.md`, `rules.md`) понад один рядок про те, як читати нотатки.
- Зміна `measure` (S1) — він будує ті самі інструкції і йде за цим slice-ом сам.

## Seam (contract)
- **`facilitation/route.py` `_card_text(card)`** → `_card_text(card, notes)`: після рядків «Ознаки:» — якщо є нотатки
  `router`, що називають цю картку (`card.id in record.cards`), рядок `Досвід:` і по рядку на нотатку
  `- <title>. <noticed> <do>` (у порядку `id`); немає — нічого (інструкція побайтно як до slice-а). `router_instruction`
  передає `knowledge.memory`. Docstring модуля: читає `card.router`, `card.title` і нотатки `router`.
- **Правило читання нотаток роутером** — не в `router.md` (його текст закріплено запечатаними оракулами
  spoken-replies), а одним рядком одразу після `CARDS_HEAD`, **лише коли хоча б одна картка має нотатку `router`**:
  «Рядки «Досвід:» біля картки — що помітили в розмовах інших людей: коли цей спосіб справді допомагав і з чим його
  плутають; враховуй їх, обираючи, але не називай людині.» Без нотаток `router` інструкція роутера побайтно та сама,
  що до slice-а.
- **`facilitation/respond.py` `system_instruction(card, memory, …)`**: розділ «# Пам'ять досвіду» містить лише записи з
  `audience == "facilitator"` і `card.id in record.cards`, у тому самому вигляді `_memory_text`; жодного — «(поки
  порожня)», як зараз. Сигнатура та сама.
- **`facilitation/converse.py`** docstring: «Does NOT read steps.json» (пам'ять читають `route` і `respond`).
- Errors: немає нових.
- Dependencies (injected): без змін (`knowledge` з `current()`).
- Does NOT do: не змінює карток, схем відповіді роутера чи фасилітатора, правила вибору; не показує нотаток людині.

## Decisions (with WHY)
- Q1: Фасилітатор бачить лише нотатки своєї картки — chosen because feature S4 і P4 (якість ведення): нотатки інших
  методів у кожному виклику — шум про чужі фази; бюджет S1 рахує той самий текст. Rejected: усі нотатки `facilitator`
  без фільтра — так закріпив skel-facilitation, коли пам'ять була порожня; тепер 25+ нотаток про чужі методи.
- Q2: Нотатки роутера — у розділі своєї картки, а не окремим блоком — chosen because роутер порівнює картки по одній
  («Картка за карткою — для вибору»), і досвід поруч із «Коли так / Коли ні» читається як уточнення саме цієї
  картки. Rejected: окремий розділ «# Досвід роутера» — модель мусить сама зводити нотатку з карткою.
- Q3: Без нотаток `router` — інструкція роутера побайтно та сама (і правило читання з'являється лише разом з
  нотатками) — chosen because запечатані тексти роутера (`rt_golden.py`, оракул `sr_oracle.py` ключі `route|…`) не
  змінюються, поки нотаток роутера немає, і база `router_eval` порівнюється чесно. Rejected: порожній рядок
  «Досвід: (немає)» — шум у кожній картці.

## Hardest seams (test-confidence points)
- **Seam 1: нотатка до кількох карток.** Запис `router` з `cards: [a, b]` стоїть у розділах `a` і `b`, не в `c`;
  запис `facilitator` з `cards: [a, b]` — у фасилітатора `a` і `b`, не `c`. Тест на справжній `router_instruction`,
  не на `_card_text` окремо.
- **Seam 2: аудиторія.** Записи `router` і `facilitator` з тією самою карткою `x`: роутер бачить лише перший,
  фасилітатор `x` — лише другий; запис без `audience` (старий JSON) — лише до фасилітатора.
- **Seam 3: без нотаток побайтно.** `router_instruction` з порожньою пам'яттю і з пам'яттю лише `facilitator` дорівнює
  наявним оракулам `sr_oracle.py` (`route|…`) і `rt_golden.py` — їх не змінюють.

## Invariants (rules that hold for every input of the stated domain)
- **I1** — Нотатку бачить лише її адресат і лише біля своїх карток: для будь-якого запису пам'яті його `title` є в
  розділі картки `x` інструкції роутера тоді й лише тоді, коли `audience == "router"` і `x in cards`, і є в
  інструкції фасилітатора картки `x` тоді й лише тоді, коли `audience == "facilitator"` і `x in cards`.
  - Domain: будь-яка пам'ять (0…N записів, будь-які `cards`, обидві аудиторії), будь-яка картка чинного стану.
  - Source: feature S4 «delivers»; Seam.
  - Broken by: фільтр лише за аудиторією або лише за карткою; нотатка роутера в усіх картках. («Є» — рядок нотатки
    `- <title>. <noticed> <do>` для роутера і її блок `### <id> — <title>` для фасилітатора, не лише заголовок.)
- **I2** — Картки в інструкціях ті самі: текст половини картки (для роутера — рядки до «Досвід:», для фасилітатора —
  `card_prompt(card)`) не залежить від пам'яті.
  - Domain: будь-яка пам'ять, будь-яка картка.
  - Source: feature AC1 («фази, мета й хід… ті самі»).
  - Broken by: нотатка, вставлена всередину фаз чи «Коли так».

## Exit criterion
- Контрактні тести (Seam 1–3, I1–I2) — зелені. Objection-пакет `test_wrong` (Q1 цього контракту: фасилітатор бачить
  лише нотатки своєї картки) розглянуто тестувальником:
  `tests/contract/skel_facilitation/test_skelf_respond.py::test_system_instruction_is_poc_rules_then_card_then_all_memory`
  (запис M-2 `gamma` у картці `alpha`); `tests/contract/spoken_replies/test_sr_invariants.py::
  test_I1_without_the_flag_each_instruction_is_byte_equal_to_before` і `test_sr_instructions.py::
  test_system_instruction_spoken_puts_section_after_language_rule` (оракул `sr_oracle.py` `respond|beta|…` містить
  запис M-1 `cards: [alpha]` у картці `beta`). Builder спершу проганяє повний `tests/contract` зі змінами і додає до
  пакета кожен інший тест, що впав з тієї самої причини, — і лише з неї. Решта — зелені без змін; оракули `route|…`
  не змінюються (правило лише з нотатками `router`).
- `scripts/smoke_test_notes_readers.py` — як у «Goal» (2).
- ruff, mypy, `lint-imports`, швидкий набір — зелені.

## Deferred to later slices
- Якщо запечатаний тест бюджету S1 закріпить текст фасилітатора з усією пам'яттю — він теж іде в objection-пакет —
  revisit trigger: тести S1 запечатано.
- Чи нотатки допомагають вибору — PR-28, S5 (`router_eval` з нотатками) — revisit trigger: S5.

## Open items requiring human decision (if any)
- (немає)

## Critic notes (non-blocking)
- Раунд 1: REVISE — рядок у `router.md` змінював кожну інструкцію роутера і ламав оракули spoken-replies, а пакет
  називав один тест → правило лише з нотатками `router`, повний перелік пакета з причиною, прогін `tests/contract`
  builder-ом. Notes: I1 за рядком нотатки, Seam 2 зі спільною карткою, Seam 3 на наявних оракулах, trigger для S1.
