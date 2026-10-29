# 729 — речення роутера про offer у запечатаному контракті fact-answer

Залежить від: —
Аудит потрібен: ні
Відкритий пункт: fact-answer-offer-sentence

## Що сталося
Задача 310 прибрала з роутера дію offer (список 2–3 способів): тепер роутер сам обирає один метод (commit 4b038d6). Але в router.md лишилось одне речення: «Якщо за питанням стоїть рішення, яке треба продумати, — не "answer", а "offer" чи "ask".» Його дослівно тримає запечатаний slice contract fact-answer (.engine/slices/fact-answer.md, рядок 52) і тест tests/contract/fact_answer/test_fa_route.py (через fa_fakes.ROUTER_ANSWER_ITEM). Заперечення tester-у дало contract_ambiguous (.engine/testing/ledger.md, request 20261028T041924Z-5adf09): змінити контракт і запечатати знову можете лише ви. Зараз це не шкодить: на наборі роутера 119 з 119 — choose, offer — 0 (.engine/artifacts/router-eval/2026-10-28T042424Z.md); але речення вказує моделі на дію, якої в правилах уже немає.

- Записано: 2026-10-28T06:26:11Z, агент

## Що зробити
Це питання до власника, не робота для агента. Коли власник відповість, задача повернеться в чергу: виконай відповідь, запиши її у звіт і закрий задачу.

## Готово, коли
Власник відповів, і відповідь виконано.

## Питання до власника
1. Змінити рядок 52 контракту fact-answer (і fa_fakes.ROUTER_ANSWER_ITEM) і запечатати знову? Варіанти: A — «… — не "answer", а "choose" чи "ask".» (раджу: ask лишився дією роутера); B — «… — не "answer", а "choose".»; C — лишити як є (offer згадано, але дії немає). Відповідь: A, B або C.
   Відповідь: A <!-- записано Claude зі слів власника 2026-10-28, сесія thinkhow-desk: «Так» — на пропозицію Claude «відповісти на всі 11 питань так, як радить runner; Сонько виконає дві команди, які заново фіксують змінені контракти» -->

2. Відповідь A виконано (commit-и — у `git log --grep "729"`): у рядку 52 контракту `.engine/slices/fact-answer.md`
   і в `src/thinkhow/facilitation/router.md` тепер «… — не "answer", а "choose" чи "ask".»; так само
   `fa_fakes.ROUTER_ANSWER_ITEM`, оракул `tests/contract/spoken_replies/sr_oracle.py` (6 рядків роутера) і тест
   `tests/contract/router/test_rt_310_leads_one_method.py` (тепер: слова "offer" у правилах роутера немає зовсім).
   Тести fact_answer, research_deep, router, spoken_replies, router_eval — 187 passed. Лишилось одне: контракт змінено
   після затвердження, і `python3 .claude/hooks/contract_fingerprint.py check .engine/slices/fact-answer.md` каже
   `CHANGED` (код 3). Старий fingerprint може видалити лише людина; без нового seal overseer не прийме жодної
   майбутньої роботи з fact-answer. Рядок 126 запечатаного контракту `.engine/slices/research-deep.md` цитує старе
   речення лише як місце вставки; його я не чіпав (тести від нього не залежать). Перепечатати контракт? Варіанти: A — так, команда (вам чи Сонькові):
   `cd /home/lao/projects/thinkhow && rm .claude/state/contracts/fact-answer.sha256 && python3 .claude/hooks/contract_fingerprint.py seal .engine/slices/fact-answer.md; echo "seal=$?"` — успіх: `seal=0` (раджу: у контракті
   змінено лише рядок 52, саме за вашою відповіддю A — `git log -p --grep 729 -- .engine/slices/fact-answer.md`); B — ні: я поверну рядок 52, router.md і тести як були (offer знову
   згадано, дії немає). Відповідь: A або B.
   Відповідь:
