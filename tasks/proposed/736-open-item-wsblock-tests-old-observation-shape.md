# 736 — Два тести walking-skeleton-block читають старий вигляд спостереження

Залежить від: —
Аудит потрібен: ні
Відкритий пункт: wsblock-tests-old-observation-shape

## Що сталося
Повний прогін у задачі 720 (4 failed, 1521 passed) показав два червоні тести: tests/contract/walking_skeleton_block/test_wsblock_connections.py::test_s4_learning_reads_every_topic_and_topic_sessions_numbered_across_the_topic і ::test_s6_observation_link_of_a_persons_topic_opens_the_turn_for_the_owner. Обидва падають з KeyError: 'turn'. Вони читають файл спостереження як одне спостереження, а з analysis-rules це набір (ObservationSet). Без змін задачі 720 вони теж червоні (перевірено на bd68d21). Exit criterion analysis-rules називає objection-пакет і до walking-skeleton-block.

- Записано: 2026-10-28T23:52:36Z, агент задачі 720
- Це пропозиція, а не задача в черзі: runner із `tasks/proposed/` нічого не бере. У роботу її ставить власник — файлом із цим номером в inbox.

## Що зробити
Objection-пакет на ці два тести під slice-ом, що має вільні кола (або після зміни двигуна про кола, .engine/engine-feedback.md, «a parked slice has no way back»). Перевірки ті самі, але по кожному спостереженню набору: turn, link на #t<turn>, сторінка відкривається.

## Готово, коли
Описане вище зроблено і перевірено, або на нього є відповідь власника.

## Питання до власника
