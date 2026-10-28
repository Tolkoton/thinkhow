# 735 — Live-тест skel-learning досі читає старий вигляд спостереження

Залежить від: —
Аудит потрібен: ні
Відкритий пункт: skel-learning-live-test-old-shape

## Що сталося
Задача 720 перенесла 20 sealed tests skel-learning на набір спостережень (ObservationSet). Live-тест tests/contract/skel_learning/test_skell_live.py::test_seam3_real_model_anchors_the_observation_to_a_turn_of_a_40_turn_topic не був у пакеті: він live і без ключа deselected. Він досі імпортує Observation з thinkhow.learning.analyze і читає obs.first_turn та obs.last_turn. mypy: «Observation has no attribute first_turn» (рядок 65). Справжній прогін цього тесту впаде. Обидва slice-и, під якими його можна виправити (skel-learning і synthesizer), уже не мають кіл суперечки: synthesizer використав свої два в задачі 720.

- Записано: 2026-10-28T23:36:39Z, агент задачі 720
- Це пропозиція, а не задача в черзі: runner із `tasks/proposed/` нічого не бере. У роботу її ставить власник — файлом із цим номером в inbox.

## Що зробити
Коли двигун уміє знімати park або рахує кола за контрактом, що вимагає зміни (.engine/engine-feedback.md, «a parked slice has no way back»): objection-пакет на test_skell_live.py. Перевірки ті самі, але по ObservationSet: файл t1-t40.json, (first_turn, last_turn) == (1, 40) на наборі, у кожного спостереження turn у 1..40, link на #t<turn>, finding не порожній.

## Готово, коли
Описане вище зроблено і перевірено, або на нього є відповідь власника.

## Питання до власника
