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
   Відповідь:
