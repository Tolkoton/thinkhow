# 721 — slice skel-guards-deploy: третя суперечка про contract tests

Залежить від: —
Аудит потрібен: ні
Відкритий пункт: testing-parked-skel-guards-deploy

## Що сталося
Два кола суперечки між builder-ом і tester-ом не розв'язали slice skel-guards-deploy: round 1: tests/contract/walking_skeleton_block/test_wsblock_connections.py (helpers drain, chain_facilitate, client_as, never: lines 56, 60, 64, 141) — test_wrong; tests/contract/walking_skeleton_block/wsblock_fakes.py:72 and the dependent errors at test_wsblock_connections.py:78, 85, 111, 115, 209, 216, 285, 287, 289, 304, 397, 400 — test_wrong | round 2: tests/contract/walking_skeleton_block/test_wsblock_connections.py::test_s1_storage_protocol_is_the_one_door_of_knowledge_workspace_and_learning — test_wrong; tests/contract/walking_skeleton_block/test_wsblock_connections.py::test_s1_llm_protocol_serves_facilitation_and_learning_and_unavailable_reaches_workspace_as_failed — test_wrong; tests/contract/walking_skeleton_block/test_wsblock_connections.py::test_s4_workspace_signatures_and_its_flow_through_the_routes — test_wrong; tests/contract/walking_skeleton_block/test_wsblock_connections.py::test_s4_learning_reads_every_topic_and_closed_sessions_numbered_across_the_topic — test_wrong; tests/contract/walking_skeleton_block/test_wsblock_connections.py::test_s6_observation_link_of_a_persons_topic_opens_the_turn_for_the_owner — test_wrong; tests/contract/walking_skeleton_block/test_wsblock_connections.py::test_ac4_foreign_topic_hidden_owner_sees_all_knowledge_untouched_by_the_chain — test_wrong. Третє коло не проводиться: slice відкладено, робота йде далі з наступним. Обидва кола стоять у .engine/testing/ledger.md.

- Записано: 2026-10-27T17:44:50Z, hook testing.py

## Що зробити
Це питання до власника, не робота для агента. Коли власник відповість, задача повернеться в чергу: виконай відповідь, запиши її у звіт і закрий задачу.

## Готово, коли
Власник відповів, і відповідь виконано.

## Питання до власника
1. Хто правий у суперечці про тести slice-а skel-guards-deploy — тест, код чи slice contract слід уточнити?
   Контекст (дописав агент задачі 309, 2026-10-27): та сама причина, що в 720. Два запечатані блокові тести
   walking skeleton (`tests/contract/walking_skeleton_block/test_wsblock_connections.py::test_s4_…` і `::test_s6_…`)
   читають файл спостереження як одне спостереження; задача 309 (`.engine/slices/analysis-rules.md`) робить його
   набором спостережень. Кола суперечки цього slice-а вже пішли на інше (гігієна типів). Перелік —
   `.engine/testing/objections/skel-guards-deploy-309-analysis-rules.md`.
   Варіанти: А — тести застаріли: свіжий tester переносить два тести на набір (посилання кожного спостереження
   відкриває репліку для власника), решту перевірок лишає. Б — лишити старий вигляд файлу (і тоді — так само, як Б у
   720). Порада: А — разом з відповіддю на 720.
   Відповідь: А <!-- записано Claude зі слів власника 2026-10-28, сесія thinkhow-desk: «Так» — на пропозицію Claude «відповісти на всі 11 питань так, як радить runner; Сонько виконає дві команди, які заново фіксують змінені контракти» -->
