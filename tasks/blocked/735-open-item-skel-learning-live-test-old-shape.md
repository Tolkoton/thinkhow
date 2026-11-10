# 735 — Live-тест skel-learning досі читає старий вигляд спостереження

Залежить від: —
Потрібна присутність власника: ні
Режим: соло
Аудит потрібен: так
Додаткові сесії: ні
Відкритий пункт: skel-learning-live-test-old-shape

## Рішення власника
Слова власника (2026-11-10, сесія Thinkhow; записано Claude зі слів власника): «Добре, став ті задачі і попередні
всі задачі теж став. Давай докінчимо це.» — «попередні всі задачі» — усі пропозиції з `tasks/proposed/`.

## Що сталося
Задача 720 перенесла 20 sealed tests skel-learning на набір спостережень (ObservationSet). Live-тест tests/contract/skel_learning/test_skell_live.py::test_seam3_real_model_anchors_the_observation_to_a_turn_of_a_40_turn_topic не був у пакеті: він live і без ключа deselected. Він досі імпортує Observation з thinkhow.learning.analyze і читає obs.first_turn та obs.last_turn. mypy: «Observation has no attribute first_turn» (рядок 65). Справжній прогін цього тесту впаде. Обидва slice-и, під якими його можна виправити (skel-learning і synthesizer), уже не мають кіл суперечки: synthesizer використав свої два в задачі 720.

- Записано: 2026-10-28T23:36:39Z, агент задачі 720
- Це пропозиція, а не задача в черзі: runner із `tasks/proposed/` нічого не бере. У роботу її ставить власник — файлом із цим номером в inbox.

## Що зробити
Коли двигун уміє знімати park або рахує кола за контрактом, що вимагає зміни (.engine/engine-feedback.md, «a parked slice has no way back»): objection-пакет на test_skell_live.py. Перевірки ті самі, але по ObservationSet: файл t1-t40.json, (first_turn, last_turn) == (1, 40) на наборі, у кожного спостереження turn у 1..40, link на #t<turn>, finding не порожній.

## Готово, коли
Описане вище зроблено і перевірено, або на нього є відповідь власника.

## Питання до власника

Перевірено (2026-11-10, Claude): справжній прогін `uv run pytest -m live tests/contract/skel_learning/test_skell_live.py`
на gemini-4-argon падає: модель відповіла, `analyze` записав файл (`written=1`), але тест читає його як старе
`Observation` і отримує `ValidationError` (рядок 64). `uv run mypy` на цьому файлі — 3 помилки. Готова правка лежить
у `.engine/artifacts/735/test_skell_live.diff` (повний файл — `.engine/artifacts/735/test_skell_live.proposed.py`).
Вона читає `ObservationSet` і робить ті самі перевірки по набору, як у «Що зробити»: файл `t1-t40.json`,
`(first_turn, last_turn) == (1, 40)`, набір не порожній, у кожного спостереження turn у 1..40, link на `#t<turn>`,
finding не порожній. Копія з цією правкою на тій самій живій моделі — `1 passed`; mypy по ній чистий. Вивід обох прогонів:
`.engine/artifacts/735/live-sealed.txt` (`1 failed`) і `.engine/artifacts/735/live-proposed.txt` (`1 passed`).
Сам sealed файл я не змінював. Обидва slice-и вже використали свої два objection rounds (skel-learning: `rounds 2`
у `testing.py status`; synthesizer — у задачі 720). Тому третій objection лише запаркує slice, а supersede не
підходить: жоден новіший контракт не каже нічого про цей тест.

1. Дозволити правку sealed тесту skel-learning `tests/contract/skel_learning/test_skell_live.py` рівно так, як у
   `.engine/artifacts/735/test_skell_live.diff`?
   - **А. Так.** Наступна сесія кладе цю правку і запечатує файл знову командою
     `python3 .claude/hooks/testing.py reseal skel-learning --owner-answer 735-open-item-skel-learning-live-test-old-shape`.
     Скрипт приймає лише ваше одне слово «так» під цим питанням. Після цього живий тест skel-learning зелений, а mypy
     по `tests` червоний лише на файлі notes-readers (задача 733).
   - **Б. Ні, objection.** Третій round запаркує skel-learning, а тест лишиться неправленим. Сенсу немає.
   - **В. Ні, лишити як є.** Без ключа тест deselected і нікому не заважає. Але будь-який справжній прогін `-m live`
     на ньому впаде, а mypy по `tests` лишається червоним.

   Порада: **А**. Перевірки ті самі, лише по набору замість одного спостереження, і правка вже пройшла на живій моделі.

   Застереження: reseal запечатує заново всі змінені файли skel-learning. У `testing.py status` їх зараз ще шість
   (`tests/contract/skel_learning/test_skell_analyze.py`, `tests/contract/skel_learning/test_skell_chain.py`, `tests/contract/skel_learning/test_skell_invariants.py`, `tests/contract/skel_learning/test_skell_job.py`, `tests/contract/skel_learning/test_skell_schema.py`, `tests/contract/skel_learning/test_skell_catchup_smoke.py`), тому що задача 720 змінила їх через objection до
   synthesizer. Скрипт вимагає, щоб ця картка називала кожен з них. Тож «так» тут означає дозвіл запечатати заново й ці
   шість у теперішньому вигляді, а не тільки live-тест.

Відповідь:
