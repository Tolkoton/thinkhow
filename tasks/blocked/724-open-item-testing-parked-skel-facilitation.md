# 724 — slice skel-facilitation: третя суперечка про contract tests

Залежить від: —
Аудит потрібен: ні
Відкритий пункт: testing-parked-skel-facilitation

## Що сталося
Два кола суперечки між builder-ом і tester-ом не розв'язали slice skel-facilitation: round 1: tests/contract/skel_facilitation/test_skelf_disputed_q2_itemtype_export.py::test_package_exports_item_type_too — test_wrong; tests/contract/skel_facilitation/test_skelf_respond.py — test_wrong; tests/contract/skel_facilitation/skelf_fakes.py — test_wrong | round 2: tests/contract/skel_facilitation/test_skelf_respond.py::test_system_instruction_is_poc_rules_then_card_then_all_memory — test_wrong. Третє коло не проводиться: slice відкладено, робота йде далі з наступним. Обидва кола стоять у .engine/testing/ledger.md.

- Записано: 2026-10-27T21:39:46Z, hook testing.py

## Що зробити
Це питання до власника, не робота для агента. Коли власник відповість, задача повернеться в чергу: виконай відповідь, запиши її у звіт і закрий задачу.

## Готово, коли
Власник відповів, і відповідь виконано.

## Питання до власника
1. Хто правий у суперечці про тести slice-а skel-facilitation — тест, код чи slice contract слід уточнити?
   Контекст (дописав агент задачі 309, 2026-10-27): два запечатані тести skel-facilitation
   (`test_skelf_respond.py::test_system_instruction_is_poc_rules_then_card_then_all_memory` і
   `test_skelf_disputed_q1_memory_cards_line.py::…`) чекають, що фасилітатор картки бачить **усю** пам'ять досвіду,
   і нотатки чужих карток теж («no filter by card» — так вирішили, коли пам'ять була порожня). Задача 309
   (`.engine/slices/notes-readers.md`, Q1) свідомо звужує: фасилітатор бачить лише нотатки своєї картки, бо тепер їх
   25+ і нотатки інших методів — шум у кожній відповіді. Кола суперечки skel-facilitation пішли раніше на інше. Перелік —
   `.engine/testing/objections/skel-facilitation-309-notes-readers.md`.
   Варіанти: А — тести застаріли: свіжий tester переносить два тести на «лише нотатки своєї картки», формат запису
   той самий. Б — фасилітатор знову бачить усі нотатки всіх методів (прибрати фільтр за карткою). Порада: А — якість
   ведення (P4): ведучий методу читає досвід цього методу; бюджет і решта поведінки не змінюються.
   Відповідь: А <!-- записано Claude зі слів власника 2026-10-28, сесія thinkhow-desk: «Так» — на пропозицію Claude «відповісти на всі 11 питань так, як радить runner; Сонько виконає дві команди, які заново фіксують змінені контракти» -->

2. Текст правил фасилітатора в тесті `test_skelf_respond.py`: за яким документом його переносити?
   Контекст (дописав агент задачі 724, 2026-10-29): відповідь А виконано (commit `bc473f5`). Свіжий slice-tester переніс
   обидва тести на «лише нотатки своєї картки» (`test_wrong` ×2, `.engine/testing/ledger.md`, «2026-10-29T00:21:33Z —
   notes-readers — dispute, round 2 of 2»). `tests/contract/skel_facilitation`: 26 passed, 1 failed. Один тест,
   `test_system_instruction_is_poc_rules_then_card_then_all_memory`, падає ще й з іншої причини. Він тримає дослівно
   текст правил фасилітатора (`RULES`), а задача 310 («Варіант А»: спершу своє, потім питання) цей текст змінила в
   `src/thinkhow/facilitation/rules.md`. Tester відповів `contract_ambiguous`. Новий текст не стоїть у жодному sealed
   slice contract: останній запечатаний текст — у `.engine/slices/facilitator-free-mode.md`, він ще старий. Писати
   тест із коду tester не може. Пакет — `.engine/testing/objections/skel-facilitation-724-owner-A.md`, пункт 2.
   Варіанти:
   А — текст правил — той, що в `rules.md` після задачі 310: свіжий tester переносить `RULES` на нього, решта перевірок
   тесту лишається. Наступна зміна правил знову зламає цей тест, як уже зламали задачі 305, 306 і 310.
   Б — тест skel-facilitation перестає тримати текст правил дослівно. Він перевіряє порядок (правила → картка →
   пам'ять) і дві заміни («i3», «t<номер з рамки репліки>»). Дослівний текст і далі тримають golden-копії інших
   slice-ів (`tests/contract/facilitator_free_mode/ffm_fakes.py`, `tests/contract/voice_reply_language/vrl_fakes.py`).
   Порада: Б. Дослівна копія правил у тесті skeleton-а повторює ці golden-копії і ламається на кожній зміні правил,
   хоча сам skeleton їх не задає.
   Відповідь: Б <!-- відповідь Claude, сесія thinkhow-desk, 2026-10-29, за порадою runner-а: це друге питання тієї самої задачі 724, на яку власник 2026-10-28 відповів «Так» на пропозицію «відповісти скрізь так, як радить runner»; власника повідомлено, він може змінити -->
