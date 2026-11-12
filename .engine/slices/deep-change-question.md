# Slice deep-change-question — planning artifact

Board task `tasks/doing/754-open-item-deep-change-question-line.md` (the owner's «Так», 2026-11-12, сесія Thinkhow).
Standalone /plan-slice, unattended: the frame is derived from the task, the sealed slice `deep-research-confirm-first`
(its decision Q6) and the code; nothing was asked. Changes one thing of that slice: after a change to the proposal the
research question is the plan's refined one, not the first.

## Goal
Після правки плану глибокого дослідження людина бачить уточнене питання дослідження, а звіт пишеться на нього.
Зараз (`src/thinkhow/facilitation/deep.py`, `deep_changed`) новий план складається для того самого
`pending.question`, і рядок питання лишається першим: у живій перевірці 747 після «Не треба про оренду, додай, які
кав'ярні там найпопулярніші» рядок питання й далі згадував оренду (`.engine/artifacts/747/live-deep-confirm.txt`,
тема «б: правка», рядок 75), а `run_deep` після згоди пише звіт і `ResearchEvent.question` саме на `pending.question`.

Вимірна ціль: план на шляху правки повертає уточнене питання (нове необов'язкове поле `DeepPlan.question`), і
`deep_changed` кладе його в `PendingDeep.question`; без нього (немає, `null`, порожнє) — лишається попереднє.
`uv run pytest -q` зелений (нові контрактні тести цього slice-а; запечатані тести не змінюються — Q5); `uv run mypy
src`, `uv run ruff check src tests scripts` чисті; жива перевірка правки на справжній моделі (Exit criterion).

## Premise verified
- Gemini на Vertex приймає в `response_json_schema` необов'язкове поле `str | None = None` (pydantic дає
  `anyOf: [string, null]`, поле не в `required`) і повертає валідну відповідь: так уже працює
  `RouterAnswer.deep_question` (`src/thinkhow/facilitation/route.py:46`), схема якого йде тим самим
  `VertexLlm._config` (`src/thinkhow/platform/llm.py:240`, `schema.model_json_schema()`); жива перевірка 747
  (`.engine/artifacts/747/live-deep-confirm.txt`, 2026-11-11) пройшла саме через роутер із `deep_question`. Свіжість:
  1 день. Чи модель справді заповнить `question` на правці — не premise, а ціль, яку перевіряє жива перевірка.
- Зовнішніх систем, яких продукт ще не кличе, slice не додає.

## Out of scope (deliberately)
- Перша пропозиція (`deep_offer`, `with_deep`): питання дослідження лишається тим, яке дав роутер чи фасилітатор (Q2).
- Зміна `PendingDeep`, `DeepProposed`, `deep_pending.json`, `run_deep`, `proposal_text` — вони вже несуть
  `pending.question` далі; уточнене питання доходить до звіту через них без змін (Q6).
- Межі часу викликів, `DeepConsent` (пропозиція 752).
- Правка без «change» (розпізнавання згоди) — як у deep-research-confirm-first.

## Seam (contract)

`src/thinkhow/facilitation/types.py`:
- `class DeepPlan(_Frozen)` отримує в кінці поле `question: str | None = None` — питання дослідження, переписане
  з правкою людини (лише на правці); `intro`, `questions`, `llm_timeout_s` не змінюються. Порожній чи пробільний
  рядок валідний (не помилка схеми) і означає «немає».

`src/thinkhow/facilitation/deep.py`:
- `def propose(question: str, ctx: FacilitationContext, llm: model.Llm, rev: model.KnowledgeRev, first: bool,
  changed: bool = False) -> PendingDeep` — як і було, один виклик плану (`_twice`), рамка та сама; результат
  `PendingDeep(question=Q, intro=plan.intro, questions=list(plan.questions))`, де `Q = clean_question(plan.question)
  or question`, коли `changed`, і `Q = question`, коли ні. Коли `changed`, у рамку плану перед реплікою людини йде
  рядок стану `CHANGE_LINE + "\n\n"` — тим самим механізмом `state`, що й `FIRST_REPLY_LINE` (`deep.py:67`,
  `settle.frame`); коли ні — цього рядка в рамці немає. `first` і `changed` разом не кличуться (правка — не перша
  відповідь теми).
- `CHANGE_LINE: str` — нова константа модуля `deep.py`, що починається з `"[Стан] Людина змінює попередній план"`
  (далі — що зробити: скласти новий план з її правкою і заповнити `question`).
- `deep_changed(pending, ctx, llm, rev)` — та сама сигнатура: `propose(pending.question, ctx, llm, rev, first=False,
  changed=True)` → дельта тексту, `DeepProposed`, оновлення з фазою картки — як було.
- `deep_offer`, `with_deep` кличуть `propose` без `changed` (типово `False`).

`src/thinkhow/facilitation/deep.md`, розділ `## План` — речення «Якщо людина просить змінити попередній план —
склади новий з її правкою.» замінюється на: якщо вище є рядок «[Стан] Людина змінює попередній план» — склади новий
план з її правкою і заповни `question`: питання дослідження заново, одним реченням, з правкою (те, що людина
прибрала, не згадуй); без цього рядка `question` не заповнюй. Перше речення розділу не змінюється (його тримає
`tests/contract/research_deep/rdp_fakes.py:13`).

- Errors: як було — невалідна відповідь плану двічі → `FacilitationError`; `question` нічого нового не додає.
- Dependencies (injected): `llm`, `rev`, `ctx` — як було.
- Does NOT do: не кличе модель ще раз, щоб переписати питання; не змінює питання першої пропозиції; не змінює
  збережену форму пропозиції.

## Decisions (with WHY)
- Q1: Уточнене питання повертає сам план — нове необов'язкове поле `DeepPlan.question`. Чому: один виклик, як і
  було (7.7–16.4 с), і план уже бачить правку в рамці та старе питання після `QUESTION_HEAD`. Відкинуто: (а) окремий
  виклик «перепиши питання» — ще один виклик на правку, ще 7–16 с очікування; (б) окрема схема `DeepChangePlan` з
  обов'язковим `question` — друга схема з тими самими межами `intro`/`questions` і другий тип у фейках; обов'язкове
  поле не потрібне, бо є запасний варіант (Q3). Це той самий шлях, що відкинуло рішення Q6 slice-а
  deep-research-confirm-first; власник поставив задачу 754 саме на нього («Так», 2026-11-12).
- Q2: Питання бере з плану лише `deep_changed`; перша пропозиція лишає питання роутера/фасилітатора. Чому: задача
  каже «брати його в deep_changed замість pending.question»; питання першої пропозиції сформульоване тим, хто
  вирішив дослідити. Тримає це новий тест Seam 3 / I2 (фейки запечатаних тестів `question` не дають, тож вони цього не
  стережуть). Якщо модель на першій пропозиції все ж заповнить `question`, код його ігнорує — так задумано, не дефект.
  Відкинуто: брати `plan.question` завжди, коли воно є, — модель могла б переписати питання й без правки, і перша
  пропозиція розійшлася б з рішенням роутера.
- Q3: Немає, `null`, порожнє чи пробільне `plan.question` на правці → лишається `pending.question` (через наявний
  `clean_question`, обрізане). Чому: поле необов'язкове, модель може його не дати; правка тоді працює як до 754.
  Відкинуто: вважати відповідь без `question` невалідною і повторювати — повторний виклик заради рядка, якого вимагає
  лише ця правка.
- Q4: Про те, що це правка, план дізнається з рядка стану `CHANGE_LINE` у рамці (код знає це напевно: `changed`), а
  правило «План» у `deep.md` каже: з цим рядком — заповни `question`, без нього — ні. Чому: «коли» вирішує код, а не
  здогад моделі з історії; механізм уже є (`FIRST_REPLY_LINE`), це один умовний префікс; без нього провал живої
  перевірки (Exit criterion 2) лишив би builder-а без плану (рецензія Phase 5). Відкинуто: лише речення правила без
  рядка стану — модель має сама розпізнати правку з історії. Також відкинуто: окремий розділ правил для правки — `deep.RULES` має рівно чотири розділи, і це тримає запечатаний
  `test_deep_md_has_the_three_sections_and_the_new_fourth_one_consent`.
- Q5: Запечатані тести не переглядаються (`supersede` не потрібен). Чому: перевірено `rg`: фейки плану
  (`tests/contract/deep_confirm/dc_fakes.py:197`, `tests/contract/research_deep/rdp_fakes.py:145`) не дають
  `question`, тож на правці лишається `pending.question` — `test_deep_changed_proposes_again_for_the_same_question_…`
  (`tests/contract/deep_confirm/test_dc_deep.py:272`) і далі правдивий; тест полів `DeepPlan`
  (`test_rdp_deep.py:106`) перевіряє лише межі `intro`/`questions`; знімок правила «План» у
  `tests/contract/spoken_replies/sr_oracle.py:24` читає `RULES["План"]`, а не дослівний текст. Задача пропонувала
  supersede «тестів, що перелічують поля DeepPlan» — таких немає. Якщо тестувальник знайде інакше — supersede.
- Q6: Уточнене питання доходить до звіту без змін `run_deep`: він уже бере `pending.question` для `[Питання людини]`
  і `ResearchEvent.question`, а `deep_pending.json` зберігає `PendingDeep` цілим. Чому: найменша зміна. Відкинуто:
  окреме поле «показане питання» в `PendingDeep` — дві правди про одне питання.

## Hardest seams (test-confidence points — distinct from the contract Seam above)
- **Seam 1: уточнене питання доходить до звіту через збережену пропозицію** — тест рівня `workspace.reply` (як у
  `tests/contract/deep_confirm/`; новий файл тестів поруч із ними): відповідь 1 — пропозиція з DQ; відповідь 2 —
  правка, фейк плану повертає `question=DQ2` (DQ2 не містить DQ як підрядка, а intro — ні DQ, ні DQ2); другий варіант
  ланцюжка — ще одна правка, план без `question` (питання лишається DQ2, не DQ); відповідь 3 — «так»: рамка виклику звіту містить `[Питання людини]\nDQ2`, `ResearchEvent.question
  == DQ2`, а показаний текст відповіді 2 містить DQ2 і не містить DQ. Виключає підробку, що змінює лише показаний
  текст, а в `deep_pending.json` кладе старе питання.
- **Seam 2: запасний варіант** — на правці фейк плану без `question`, з `"question": null`, з `""`, з `"   "` →
  `PendingDeep.question == pending.question`; з `"  DQ2  "` → `"DQ2"`. Виключає `plan.question or question` без
  обрізання (пробільне питання пройшло б у рядок).
- **Seam 3: перша пропозиція не чіпає `question` плану** — фейк плану повертає `question=DQ2` на шляху роутера
  (`deep_offer`) і під карткою (`with_deep`) → `PendingDeep.question == DQ`. Виключає `propose`, що бере
  `plan.question` завжди.
- **Seam 4: схема і рядок стану йдуть до моделі** — `DeepPlan.model_json_schema()` має `question` у `properties` і
  не має в `required`; правило «План» з `deep.md` згадує `question` і «[Стан] Людина змінює попередній план»; рамка
  виклику плану на правці містить `CHANGE_LINE`, а на `deep_offer` і `with_deep` — ні. Модель дізнається про поле і
  про правку лише так.

## Invariants (rules that hold for every input in the stated domain)
- **I1** — На правці питання нової пропозиції — обрізане `plan.question`, якщо воно непорожнє, інакше питання
  попередньої пропозиції.
  - Domain: будь-яка валідна відповідь `DeepPlan` на шляху `deep_changed`: `question` відсутнє, `null`, `""`,
    пробільне, текст із пробілами довкола, текст, рівний попередньому питанню; будь-яке `pending.question`.
  - Source: «Seam» (`propose` з `changed=True`), Q3; задача 754, «Що зробити».
  - Broken by: `deep_changed`, що лишає `pending.question` (як до 754); `plan.question or question` без
    `clean_question` (пробільне питання показане людині).
- **I2** — Питання першої пропозиції — те, що дали роутер чи фасилітатор, що б не повернув план у `question`.
  - Domain: будь-яка валідна відповідь `DeepPlan` (з `question` чи без) на шляхах `deep_offer` і `with_deep`.
  - Source: «Seam» (`propose` без `changed`), Q2.
  - Broken by: `propose`, що бере `plan.question` завжди, коли воно є.
- **I3** — Після згоди звіт і `ResearchEvent.question` пишуться на те питання, яке було показане в останній
  пропозиції.
  - Domain: будь-який ланцюжок пропозиція → 0..n правок (кожна з `question` чи без) → «так» через `workspace.reply`.
  - Source: Goal («звіт пишеться на нього»); задача 754, «Що сталося».
  - Broken by: показ уточненого питання без запису його в `PendingDeep`/`deep_pending.json`; `run_deep`, що бере
    питання не з `pending`.

## Exit criterion
1. Нові контрактні тести цього slice-а (Seams 1–4, по одному тесту `test_I<n>_…` на кожне правило) зелені;
   `uv run pytest -q` (повний набір) зелений; `uv run mypy src` і `uv run ruff check src tests scripts` чисті.
2. Жива перевірка на справжній моделі (Vertex `eu`, модель застосунку): `scripts/live_deep_confirm.py`, тема
   «б: правка», доповнена кодовими перевірками (exit 1 при порушенні): після правки «Не треба про оренду, додай, які
   кав'ярні там найпопулярніші» `deep_pending.json` має `question`, відмінне від питання першої пропозиції; рядок
   питання в тексті відповіді на правку дорівнює цьому `question`; у `question.lower()` немає кореня «оренд». Вивід —
   `.engine/artifacts/754/live-deep-confirm.txt` (вивід 747 лишається як доказ того slice-а; докстрінг і `OUT`
   скрипта називають 754). Теми «а» і «в» лишаються, як були, і проходять. Один прогін стохастичної моделі — це
   «спостережено раз», не частота. Якщо прогін не проходить, builder у межах цього slice-а може лише уточнити
   формулювання `CHANGE_LINE` і правила «План» (тексти промптів); зміна Seam — новий план.

## Deferred to later slices
- Уточнення питання на першій пропозиції — why later: ніхто не просив, роутер уже формулює його; цей slice через
  це нічого не втрачає, наступний заплатить один умовний шлях у `propose` — revisit trigger: задача чи пропозиція на
  task board, або вивід живої перевірки, де питання першої пропозиції розходиться з проханням людини.

- Як часто модель заповнює `question` на правці (жива перевірка — один прогін; без поля правка тихо працює як до
  754, Q3) — why later: частота — поріг власника, а прецедент 747 — один прогін — revisit trigger: жива розмова чи
  прогін, де рядок питання після правки ще несе прибране людиною.

## Open items requiring human decision (if any)
- Немає.

## Critic notes (non-blocking)
- Phase 5 (REVISE, прийнято варіант (а) рецензента): рядок стану правки перенесено з Deferred у цей slice.
- Phase 3: тестові дані Seam 1 — DQ2 не містить DQ. Cold reader: на сьогоднішньому коді фейк плану з `question`
  не проходить схему (`extra="forbid"`), тож червоні спершу і тести Seam 3, не лише Seam 1.
- Cold reader: якщо жива перевірка не проходить і після трьох різних уточнень текстів промптів — park, не нові прогони.
- Phase 4: прогін — «спостережено раз»; перевірка «популяр» (чи правку враховано) необов'язкова, не входить у критерій.
- Phase 2: Q2 не приписує запечатаним тестам захист I2; Q4 назвав альтернативу «рядок стану на правці», яку Phase 5 прийняла.
