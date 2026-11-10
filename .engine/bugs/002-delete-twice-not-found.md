# Bug 002-delete-twice-not-found

type: bugfix
status: fixed
<!-- status: recorded → reproduced → fixed; or parked (not reproduced in three attempts);
     or question for the owner (the expected behaviour is written nowhere); or became a slice.
     This file is the contract of the fix and its report at once: the overseer audits against it.
     Sections 1–4 are written before the fix exists. -->

## 1. Record
- Symptom: власник (2026-11-10, сесія Thinkhow): «коли тема видаляється, показується помилка, що тема не знайдена, а мало би просто вийти на основне меню з темами.»
- Expected: друге (повторне) видалення своєї теми, якої вже немає, веде до списку «Мої теми» (303 → `/`) без помилки; видалення чужої теми — як і досі, 404 «Тему не знайдено.» (G4).
- Where the expected is written: слова власника в `tasks/doing/212-delete-twice-not-found.md` («Рішення власника» і «Що зробити»: «видалення своєї теми, якої вже немає, веде просто до списку «Мої теми», без помилки. Чужа тема — як і досі, відмова (G4)»); 303 → `/` для видалення — `tests/web/test_delete_topic.py::test_post_delete_removes_the_topic_and_goes_home`; відмова чужому — `test_post_delete_of_a_foreign_topic_is_404_and_deletes_nothing`.
- Actual: перше `POST /topics/<uid>/<id>/delete` → 303 (тему видалено), друге таке саме → 404 зі сторінкою «Тему не знайдено.».
- Where it was seen: Cloud Run, журнали 2026-11-10: 07:10:22 `POST …/t-2c5db02daa1e/delete` → 303, 07:10:24.9 той самий → 404; 07:10:53 `…/t-d17ae6d68adb/delete` → 303, 07:10:54.2 → 404 (task 212, «Що з'ясовано»). Друге натискання — людське: `GET /` після 303 іде 1.2–3.5 с, і людина тисне ще раз.

## 2. Reproduction
Three attempts, each a different way. Reproduced — stop at that attempt. Not reproduced after
the third — the status becomes `parked`, nothing below is filled in and no code is changed.

### Attempt 1
- Command: `PYTHONPATH=src uv run python /tmp/repro212.py` — справжній застосунок (`create_app`) через `TestClient`, LocalStorage, людина Аліса створює тему і двічі поспіль шле той самий `POST /topics/alice-1/<id>/delete` (так приходять два натискання кнопки підтвердження: форма без JS, `delete.html`).
- Output:
  ```
  {"severity": "INFO", "method": "POST", "route": "/topics/{uid}/{topic_id}/delete", "status": 303, ...}
  click 1: 303 / False
  {"severity": "INFO", "method": "POST", "route": "/topics/{uid}/{topic_id}/delete", "status": 404, ...}
  click 2: 404 None True
  ```
  (третє поле — чи є на сторінці «Тему не знайдено.»)
- Result: reproduced

### Attempt 2
Не потрібна: відтворено з першої спроби (і збігається з журналами Cloud Run у розділі 1).

### Attempt 3
Не потрібна: відтворено з першої спроби.

## 3. Failing test
- Test: `tests/web/test_delete_topic.py::test_a_second_delete_of_the_own_topic_goes_home_without_an_error` — на рівні endpoint-а, де людина бачить помилку: два однакові `POST …/delete` від власниці теми; друге має дати 303 → `/`.
- Command that runs it: `uv run pytest -q tests/web/test_delete_topic.py -k second_delete`
- It fails with: `AssertionError: assert (404, None) == (303, '/')`
- Tests written first to pin the present behaviour around the code (only when no test could reach it): none

## 4. Cause
Written before the fix.
- Where it showed: `src/thinkhow/web/server.py:68` — помилка `TopicNotFound` перетворюється на 404 «Тему не знайдено.», і її отримує другий `POST …/delete`.
- Why it happened: маршрут `delete` (`src/thinkhow/web/server.py:168`) пропускає назовні кожне `TopicNotFound` з `workspace.delete_topic`, а та кидає його в двох різних випадках: тема чужа (`_can_write`, `src/thinkhow/workspace/topics.py:564`) і своя тема, якої вже немає (`topics.py:256`). Повторне видалення — звичайний випадок (повторне натискання, поки `GET /` іде секунди), а маршрут не відрізняє «вже видалено» від «не твоє».
- Same places: `grep -n "TopicNotFound" src/thinkhow/workspace/topics.py` і маршрути `server.py`, що змінюють тему за посиланням: `rename` (`server.py:174`) — повторне перейменування своєї теми, якої вже немає, теж дало б 404, але повтор перейменування існуючої теми — 303 (журнали: 07:10:43 і 07:10:44, обидва 303), тож у звіті власника цей випадок не виникає; він не той самий шлях (перейменування видаленої теми — інша ситуація, де помилка доречна). `reply`/`retry`/`document`/`voice` до видаленої теми — помилка там правильна (не повтор тієї самої дії, яка вже вдалася). Виправляється тут лише `delete`.

## 5. Fix
- What changed: `src/thinkhow/web/server.py` (маршрут `delete`) — `TopicNotFound` від `workspace.delete_topic` для своєї теми (`uid == user.id`) більше не виходить назовні: маршрут веде на `/` (303), як після вдалого видалення; для чужої теми помилка йде далі — 404, як і досі (G4). `tests/web/test_delete_topic.py` — тест регресії. `workspace.delete_topic` не змінено: його контракт (тема, якої немає → `TopicNotFound`, `test_an_unknown_or_malformed_topic_is_not_found_and_touches_nothing`) лишається.
- Кнопку після першого натискання не вимикаю: з виправленням друге натискання нешкідливе (видалення — 303 → список; перейменування й так 303), а вимкнення — нова поведінка JS на сторінці, поза найменшим виправленням.
- Nothing else: no tidying on the way, no renaming, no new helper for later.

The budget below is the ready small budget of a bug fix. The 40 is a signal, not a ceiling —
going over any line calls the simplifier; when it does not find the excess justified, this
stops being a bug fix and becomes a slice through `/plan-slice`. The numbers are not edited.

## Complexity budget
base_commit: cfb7b5b8e87b04c2dbabf36a5573d900f2dfcd31
max_new_files: 0
max_net_new_lines: 40
max_new_public_symbols: 0
max_new_abstractions: 0
max_new_dependencies: 0
justification: none

## 6. Proof
The command and the whole output of `python3 .claude/hooks/bugfix.py prove …`, pasted. `REFUSED` is not a proof.

Command: `python3 .claude/hooks/bugfix.py prove --record .engine/bugs/002-delete-twice-not-found.md --test tests/web/test_delete_topic.py --cmd "uv run pytest -q tests/web/test_delete_topic.py -k second_delete" --expect "assert (404, None) == (303, '/')"`

```
PROVED: tests/web/test_delete_topic.py fails on cfb7b5b and passes on the working tree; the failure shows «assert (404, None) == (303, '/')»
  command: uv run pytest -q tests/web/test_delete_topic.py -k second_delete
  the fix: .engine/PROGRESS.md, .engine/bugs/002-delete-twice-not-found.md, src/thinkhow/web/server.py
  before the fix: exit 1
    |         client.post(_url(ref) + "/delete", headers=H_ALICE, follow_redirects=False)
    |         r = client.post(_url(ref) + "/delete", headers=H_ALICE, follow_redirects=False)
    | >       assert (r.status_code, r.headers.get("location")) == (303, "/")
    | E       AssertionError: assert (404, None) == (303, '/')
    | E         
    | E         At index 0 diff: 404 != 303
    | E         Use -v to get more diff
    | 
    | tests/web/test_delete_topic.py:248: AssertionError
    | ----------------------------- Captured stdout call -----------------------------
    | {"severity": "INFO", "method": "POST", "route": "/topics/{uid}/{topic_id}/delete", "status": 303, "latency_ms": 2, "event": "http_request", "request_id": "4462c5b56b7e4c0eaed825cbe5d148be"}
    | {"severity": "INFO", "method": "POST", "route": "/topics/{uid}/{topic_id}/delete", "status": 404, "latency_ms": 1, "event": "http_request", "request_id": "6695c6aa1ab744e6a0e114a75b5640b7"}
    | =========================== short test summary info ============================
    | FAILED tests/web/test_delete_topic.py::test_a_second_delete_of_the_own_topic_goes_home_without_an_error
    | 1 failed, 14 deselected in 2.42s
  with the fix: exit 0
    | Using CPython 3.13.12
    | Creating virtual environment at: .venv
    | Installed 92 packages in 48ms
    | .                                                                        [100%]
    | 1 passed, 14 deselected in 2.05s
```

Budget: `python3 .claude/hooks/complexity_budget.py check` → `within budget`: production 0 new files, +6 lines, 0 new public symbols, 0 new abstractions, 0 new dependencies; tests +11 lines.

## 7. Gate and overseer
- Gate: `uv run ruff check src tests` — All checks passed; `uv run ruff format --check` (2 змінені файли) — already formatted; `uv run mypy src tests/web/test_delete_topic.py` — no issues in 57 source files; повний прогін `uv run pytest -q -p no:cacheprovider` — `1632 passed, 36 deselected in 1198.94s`.
- Overseer: PASS, `20261110T081732Z-23d207` (re-ran `bugfix.py prove` → PROVED).
- The regression test stays in the suite: tests/web/test_delete_topic.py::test_a_second_delete_of_the_own_topic_goes_home_without_an_error

## 8. Lesson
Why was this not caught earlier — one of: a test was missing | the contract was wrong | a rule was missing | external.
- Answer: a test was missing — жоден тест не слав той самий `POST`, що змінює стан, двічі поспіль, хоча людина тисне вдруге, поки наступна сторінка вантажиться; друге натискання вже вдалої дії має вести туди ж, куди перше.
- Queued: `#27fd1745 added`
