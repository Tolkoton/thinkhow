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
`.engine/artifacts/notes-readers/smoke.txt`; (3) запечатані тести роутера й фасилітатора зелені, крім того, що
закріплює «пам'ять без фільтра за карткою» (skel-facilitation), — objection-пакет `test_wrong` з посиланням на цей
контракт; (4) ruff, mypy, import-linter, швидкий набір — зелені.

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
- **`ROUTER_RULES`** (`router.md`): один рядок у «Правила»: «Рядки «Досвід:» біля картки — що помітили в розмовах
  інших людей: коли цей спосіб справді допомагав і з чим його плутають; враховуй їх, обираючи, але не називай людині.»
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
- Q3: Без нотаток — інструкція побайтно та сама — chosen because запечатані golden-тексти роутера (`rt_golden.py`)
  не змінюються, поки пам'ять порожня, і набір `router_eval` бази порівнюється чесно. Rejected: порожній рядок
  «Досвід: (немає)» — шум у кожній картці.

## Hardest seams (test-confidence points)
- **Seam 1: нотатка до кількох карток.** Запис `router` з `cards: [a, b]` стоїть у розділах `a` і `b`, не в `c`;
  запис `facilitator` з `cards: [a, b]` — у фасилітатора `a` і `b`, не `c`. Тест на справжній `router_instruction`,
  не на `_card_text` окремо.
- **Seam 2: аудиторія.** Запис `facilitator` не потрапляє до роутера, запис `router` — до фасилітатора; запис без
  `audience` (старий JSON) — лише до фасилітатора.
- **Seam 3: без нотаток побайтно.** `router_instruction` з порожньою пам'яттю і з пам'яттю лише `facilitator` дорівнює
  тексту до slice-а (golden із `git show c14fd9b`).

## Invariants (rules that hold for every input of the stated domain)
- **I1** — Нотатку бачить лише її адресат і лише біля своїх карток: для будь-якого запису пам'яті його `title` є в
  розділі картки `x` інструкції роутера тоді й лише тоді, коли `audience == "router"` і `x in cards`, і є в
  інструкції фасилітатора картки `x` тоді й лише тоді, коли `audience == "facilitator"` і `x in cards`.
  - Domain: будь-яка пам'ять (0…N записів, будь-які `cards`, обидві аудиторії), будь-яка картка чинного стану.
  - Source: feature S4 «delivers»; Seam.
  - Broken by: фільтр лише за аудиторією або лише за карткою; нотатка роутера в усіх картках.
- **I2** — Картки в інструкціях ті самі: текст половини картки (для роутера — рядки до «Досвід:», для фасилітатора —
  `card_prompt(card)`) не залежить від пам'яті.
  - Domain: будь-яка пам'ять, будь-яка картка.
  - Source: feature AC1 («фази, мета й хід… ті самі»).
  - Broken by: нотатка, вставлена всередину фаз чи «Коли так».

## Exit criterion
- Контрактні тести (Seam 1–3, I1–I2) — зелені; objection-пакет до `tests/contract/skel_facilitation/
  test_skelf_respond.py::test_system_instruction_is_poc_rules_then_card_then_all_memory` (`test_wrong`, Q1 цього
  контракту) розглянуто тестувальником; решта запечатаних тестів роутера й фасилітатора — зелені без змін.
- `scripts/smoke_test_notes_readers.py` — як у «Goal» (2).
- ruff, mypy, `lint-imports`, швидкий набір — зелені.

## Deferred to later slices
- Чи нотатки допомагають вибору — PR-28, S5 (`router_eval` з нотатками) — revisit trigger: S5.

## Open items requiring human decision (if any)
- (немає)

## Critic notes (non-blocking)
- (заповнюється)
