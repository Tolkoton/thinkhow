# 720 — slice skel-learning: третя суперечка про contract tests

Залежить від: —
Аудит потрібен: ні
Відкритий пункт: testing-parked-skel-learning

## Що сталося
Два кола суперечки між builder-ом і tester-ом не розв'язали slice skel-learning: round 1: tests/contract/skel_learning/test_skell_chain.py::test_seam4_local_chain_ends_in_an_observation_whose_link_opens_an_existing_turn — test_wrong | round 2: tests/contract/skel_learning/test_skell_analyze.py — test_wrong; tests/contract/skel_learning/test_skell_invariants.py — test_wrong; tests/contract/skel_learning/test_skell_job.py — test_wrong; tests/contract/skel_learning/test_skell_chain.py — test_wrong; tests/contract/skel_learning/test_skell_catchup_smoke.py — test_wrong; tests/contract/skel_learning/test_skell_live.py — test_wrong; tests/contract/skel_learning/test_skell_disputed_q2_exception_message.py — test_wrong. Третє коло не проводиться: slice відкладено, робота йде далі з наступним. Обидва кола стоять у .engine/testing/ledger.md.

- Записано: 2026-10-27T17:39:36Z, hook testing.py

## Що зробити
Це питання до власника, не робота для агента. Коли власник відповість, задача повернеться в чергу: виконай відповідь, запиши її у звіт і закрий задачу.

## Готово, коли
Власник відповів, і відповідь виконано.

## Питання до власника
1. Хто правий у суперечці про тести slice-а skel-learning — тест, код чи slice contract слід уточнити?
   Контекст (дописав агент задачі 309, 2026-10-27): третя суперечка — не про помилку. 20 запечатаних тестів
   skel-learning (перший аналізатор, walking skeleton) перевіряють старий вигляд результату аналізатора: одне
   спостереження на файл, відповідь моделі `finding, worked, cause, anchor`, три причини. Задача 309 («кілька
   спостережень на тему за ніч», причина «роутер» — ваш план «1Б») свідомо це змінює запечатаним контрактом
   `.engine/slices/analysis-rules.md`: файл — набір спостережень, у кожного `kind` (просувається / застрягла / чи
   підійшов метод) і картка, що вела розмову. Два кола суперечки skel-learning уже пішли на інше (задача 202,
   прибрана кнопка «Завершити сесію»), тож на це кола не лишилось. Перелік тестів — `.engine/testing/objections/
   skel-learning-309-analysis-rules.md`.
   Варіанти: А — тести застаріли: свіжий tester переносить ці 20 тестів на новий вигляд (набір, `kind`, чотири
   причини), решту їхніх перевірок лишає такими ж суворими. Б — лишити старий вигляд: аналізатор знову пише одне
   спостереження на ніч, без «застрягла» і без причини «роутер» — тоді не виконується пункт задачі 309 про правила
   аналізу і перевірку на вашій розмові `t-84d1517cb1c1`. Порада: А — це і є ваше «кілька спостережень» і
   «застрягання на #5, #11, #15»; усе, що ці тести ще бережуть (якір у межах нових реплік, курсор з назв файлів,
   контекст, невдача нічого не пише), лишається.
   Відповідь:
