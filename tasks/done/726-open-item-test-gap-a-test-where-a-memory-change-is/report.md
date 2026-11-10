# Звіт: зміна пам'яті посеред відповіді не змішує дві revision в одній відповіді — тепер це перевірено

## Що змінилось для власника
Код не змінився. Додано один тест:
`tests/web/test_live_knowledge_gap_one_revision_a_reply.py`, функція
`test_a_change_published_inside_a_reply_reaches_neither_call_of_that_reply` (рядок 78).

Як працює тест:
- Він проганяє одну повну відповідь `respond` над `LiveKnowledge` (`src/thinkhow/web/app.py:52`). Router обирає
  `pre-mortem`, далі відповідає facilitator цієї картки.
- Модель — `PublishingLlm` (рядок 43): обгортка над `ScriptedLlm(local_script)`, яка записує `rev` кожного виклику.
- Під час першого виклику, тобто виклику router-а, обгортка публікує нову revision N+1 з нотатками `late-router` і
  `late-fac`.
- Одразу після публікації обгортка робить `live.now()` (рядок 75). Так поводиться відповідь іншої людини: web app
  ділить один `LiveKnowledge` між усіма запитами.

Тест перевіряє:
- обидва виклики моделі отримали `rev` revision N, з якої почалася відповідь (рядок 94);
- в instruction router-а є нотатка `early-router` revision N і немає `late-router`;
- в instruction facilitator-а є `early-fac` і немає `late-fac`;
- наступна відповідь (`live.now()`) уже бере N+1 цілою.

Справжньої вади тест не знайшов: на коді, як він є, тест зелений. Відповідь бере знімок один раз
(`src/thinkhow/facilitation/respond.py:46`) і далі читає тільки його.

Як стоїть брак, який назвав overseer (2026-10-27T21:45Z, запит `20261027T214157Z-023d21`, «rev_pair read from revision
N while memory is read from revision N+1 passes every current test»):
- Ваду per-field refresh прибрав commit `043f651`, ще до цієї задачі. Тести, які рахують `latest_pair`
  (`tests/web/test_live_knowledge.py` і тест задачі 725), уже ловлять кожен варіант, що бере Knowledge вдруге
  посеред відповіді, бо такий варіант робить другий `latest_pair`.
- Жоден тест не ловив інший варіант: відповідь викликає `now()`, але далі читає спільний об'єкт `LiveKnowledge`, а не
  свій знімок. Тоді `now()` іншої відповіді посеред цієї підміняє поля, і facilitator бачить N+1, а router вирішував на
  N. Новий тест — єдиний червоний на цьому варіанті (прогін M4 нижче).

## Демонстрація на хвилину
Червоні прогони. Я тимчасово міняв код, а після кожної заміни повертав файл з копії (наприкінці `git status` показує
лише новий файл задачі). «Нові» — `uv run pytest -q tests/web/test_live_knowledge_gap_one_revision_a_reply.py`;
«старі» — `uv run pytest -q tests/web/test_live_knowledge.py tests/web/test_live_knowledge_gap_one_pair_a_reply.py`.

| Варіант | Що змінено | Новий тест | Старі тести |
|---|---|---|---|
| M1 | клас `LiveKnowledge` з `cd1d07e` (refresh на кожному читанні поля), `now()` повертає `self` | 1 failed: `[…rev=3…] == […rev=2…]` | 5 failed, 2 passed |
| M2 | facilitator бере `live.now()` удруге посеред відповіді | 1 failed: те саме | 4 failed, 3 passed |
| M3 | `rev` facilitator-а з нового `now()`, його пам'ять зі знімка відповіді (rev однієї revision біля memory іншої) | 1 failed: те саме | 4 failed, 3 passed |
| M4 | `respond` викликає `now()`, але читає спільний об'єкт, а не знімок | 1 failed: те саме | 7 passed |

Що означає `rev=3` проти `rev=2`: у тесті revision N — це 2 (seed і одна зміна пам'яті), а N+1 — 3. У кожному
варіанті facilitator отримав 3, хоча router вирішував на 2.

Зелений прогін на коді, як він є:
```
uv run pytest -q tests/web/test_live_knowledge_gap_one_revision_a_reply.py  → 1 passed
uv run pytest -q tests/web  → 87 passed
```
Перевірки нового файлу: `uv run ruff check` → `All checks passed!`; `uv run ruff format --check` → `1 file already
formatted`; `uv run mypy` → `Success: no issues found in 1 source file`.

Повний набір: `uv run pytest -q -p no:cacheprovider` → `1642 passed, 36 deselected in 1234.54s` (1641 у задачі 725 плюс новий тест); після прогону дерево чисте, крім нових файлів задачі.

## Витрати
Одна сесія runner-а. Додаткових сесій Claude не було, live-прогонів моделі теж: модель у тесті —
`ScriptedLlm(local_script)`.

## Діапазон commit-ів
Від `1c130b8` (задача в `doing/`) до commit-а, що переносить задачу в `done/`.

## Відкладене
Нічого.

## Рішення, які я ухвалив сам
- Нова revision публікується під час виклику моделі router-а. Це єдина точка посеред відповіді, де між читанням полів
  для router-а і для facilitator-а минає час. Тому саме тут розходяться «rev рішення router-а» і «пам'ять в
  instruction».
- До публікації додано `now()` іншої відповіді. Без нього варіант M4 проходив би й новий тест: поля спільного об'єкта
  міняє лише `now()`. А web app справді ділить один `LiveKnowledge` між запитами (`build_deps`).
- Тест лежить в окремому файлі, як і тест задачі 725. Так його видно як закриття цього браку, а старі тести лишаються,
  як є.
