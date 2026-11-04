# Bug <number-name>

type: bugfix
status: fixed
<!-- status: recorded → reproduced → fixed; or parked (not reproduced in three attempts);
     or question for the owner (the expected behaviour is written nowhere); or became a slice.
     This file is the contract of the fix and its report at once: the overseer audits against it.
     Sections 1–4 are written before the fix exists. -->

## 1. Record
- Symptom: власник (2026-11-04, після розгортання образу `5a4af72`, ревізія `thinkhow-00015-kll`): «кнопка додати файл не працює, вона не натискається, нічого не відбувається».
- Expected: натискання скріпки `#attach` відкриває вибір файла; після кожного розгортання браузер виконує `/static` файли нового образу.
- Where the expected is written: `.engine/slices/document-upload.md` (скріпка → вибір файла → файл іде в тему; task 311), `src/thinkhow/web/static/conversation.js:286` (`attachDocument`: `clip.addEventListener("click", () => pick.click())`); слова власника в `tasks/doing/210-paperclip-does-nothing.md` («Що зробити»: «щоб після кожного розгортання браузер брав нові `/static` файли»).
- Actual: після переходу зі старого образу на новий за тією самою адресою сторінка нова (кнопка `#attach` є), а `conversation.js` — старий із кешу браузера, у ньому немає `attachDocument`; натискання нічого не робить.
- Where it was seen: сервер Cloud Run за IAP, образ `5a4af72`, браузер власника (пристрій невідомий); відтворено локально, Chromium Playwright.

## 2. Reproduction
Three attempts, each a different way. Reproduced — stop at that attempt. Not reproduced after
the third — the status becomes `parked`, nothing below is filled in and no code is changed.

### Attempt 1
- Command: `uv run python /tmp/claude-1001/-home-lao-projects-thinkhow/0113f282-08e8-525a-a3e1-43a8f6b01ea5/scratchpad/repro/stale_cache.py /tmp/claude-1001/-home-lao-projects-thinkhow/0113f282-08e8-525a-a3e1-43a8f6b01ea5/scratchpad/repro/old /tmp/claude-1001/-home-lao-projects-thinkhow/0113f282-08e8-525a-a3e1-43a8f6b01ea5/scratchpad/repro/new` (old = `git archive 76e81f3`, new = `git archive HEAD` = `94906cf`; той самий persistent профіль Chromium, той самий порт і тека даних; спершу сервер зі старого знімка — створити тему, потім сервер із нового — відкрити ту саму тему навігацією, натиснути `#attach`, чекати `filechooser`)
- Output:
  ```
  old image: #attach on the page: 0
  new image: #attach on the page: 1
  new image: conversation.js has attachDocument: undefined
  NO FILE CHOOSER: TimeoutError Timeout 3000ms exceeded while waiting for event "filechooser"
  ```
- Result: reproduced

### Attempt 2
Не потрібна: відтворено з першої спроби.

### Attempt 3
Не потрібна: відтворено з першої спроби.

## 3. Failing test
- Test: `tests/web/test_static_cache.py::test_after_a_deploy_the_paperclip_opens_the_file_chooser` — у справжньому браузері (Playwright Chromium, persistent профіль): спершу «старий образ» за адресою (сторінка просить `/static/conversation.js` і `/static/style.css` без версії, файли датовані три дні тому, як після `git archive`), потім справжній застосунок цього дерева на тому самому порту; людина відкриває свою тему, натискає справжню `#attach` і чекає `filechooser`; ще — що діє новий `style.css` (у старому є `--stale`).
- Command that runs it: `uv run pytest -q tests/web/test_static_cache.py`
- It fails with: `AssertionError: the paperclip opened no file chooser: the old conversation.js came from the browser's cache` (у журналі запитів того прогону `/static/rename.js` іде на сервер, а `conversation.js` і `style.css` — ні: їх узято з кешу)
- Tests written first to pin the present behaviour around the code (only when no test could reach it): none

## 4. Cause
Written before the fix.
- Where it showed: `src/thinkhow/web/templates/topic.html:57` — `<script src="/static/conversation.js">`: сторінка нового образу просить ту саму адресу, що й старий образ, і браузер бере старий скрипт без `attachDocument`.
- Why it happened: `/static` віддає `StaticFiles` (`src/thinkhow/web/server.py:68`) без `Cache-Control`, але з `Last-Modified` — часом commit-а знімка (`git archive` ставить усім файлам час commit-а: старий `conversation.js` — 2026-11-01 12:48). Без `Cache-Control` браузер рахує свіжість евристично (≈10 % від віку файла — години), тож адреса без версії після розгортання годинами лишається старою. Адреси `/static/...` не змінюються між образами.
- Same places: `grep -rn "/static/" src` → `src/thinkhow/web/templates/base.html:8` (`style.css`), `base.html:15` (`rename.js`), `topic.html:57` (`conversation.js`) — та сама причина в усіх трьох; виправляються тут усі три. Інших посилань на `/static` у `src` немає (`style.css` не імпортує інших файлів: `grep -n "url(\|@import" src/thinkhow/web/static/style.css` — порожньо).

## 5. Fix
- What changed: `src/thinkhow/web/server.py` — глобальна змінна шаблонів `static_v`: перші 12 знаків sha256 від вмісту файлів `static/`, обчислена при імпорті; `src/thinkhow/web/templates/base.html` і `topic.html` — три адреси `/static/...` дістали `?v={{ static_v }}`. Образ зі зміненими файлами дає нові адреси, і браузер не може взяти старий файл із кешу; образ без змін у `static/` лишає адреси, і кеш працює як раніше.
- Nothing else: no tidying on the way, no renaming, no new helper for later.

The budget below is the ready small budget of a bug fix. The 40 is a signal, not a ceiling —
going over any line calls the simplifier; when it does not find the excess justified, this
stops being a bug fix and becomes a slice through `/plan-slice`. The numbers are not edited.

## Complexity budget
base_commit: 94906cfa37ca961c6f52202653ea859bb57dfda1
max_new_files: 0
max_net_new_lines: 40
max_new_public_symbols: 0
max_new_abstractions: 0
max_new_dependencies: 0
justification: none

## 6. Proof
The command and the whole output of `python3 .claude/hooks/bugfix.py prove …`, pasted. `REFUSED` is not a proof.

Command: `python3 .claude/hooks/bugfix.py prove --record .engine/bugs/001-stale-static-cache.md --test tests/web/test_static_cache.py --cmd "uv run pytest -q tests/web/test_static_cache.py" --expect "the paperclip opened no file chooser"`

```
PROVED: tests/web/test_static_cache.py fails on 94906cf and passes on the working tree; the failure shows «the paperclip opened no file chooser»
  command: uv run pytest -q tests/web/test_static_cache.py
  the fix: .engine/PROGRESS.md, .engine/bugs/001-stale-static-cache.md, src/thinkhow/web/server.py, src/thinkhow/web/templates/base.html, src/thinkhow/web/templates/topic.html
  before the fix: exit 1
    |         )
    | E       AssertionError: the paperclip opened no file chooser: the old conversation.js came from the browser's cache
    | E       assert False
    | 
    | tests/web/test_static_cache.py:96: AssertionError
    | ----------------------------- Captured stdout call -----------------------------
    | {"severity": "INFO", "method": "GET", "route": "/language", "status": 200, "latency_ms": 16, "event": "http_request", "request_id": "8fc04efc546e4bda8d8f9d3e5c7c863b"}
    | {"severity": "INFO", "method": "GET", "route": "/static/rename.js", "status": 200, "latency_ms": 1, "event": "http_request", "request_id": "1cd12a38123d47c4be2604190d29f4d9"}
    | {"severity": "INFO", "method": "POST", "route": "/language", "status": 303, "latency_ms": 1, "event": "http_request", "request_id": "4af4912296a743979ae2f8cb308ae8c2"}
    | {"severity": "INFO", "method": "GET", "route": "/", "status": 200, "latency_ms": 5, "event": "http_request", "request_id": "156acad10b2f4be5867c715d4095ca55"}
    | {"severity": "INFO", "method": "POST", "route": "/topics", "status": 303, "latency_ms": 1, "event": "http_request", "request_id": "d90cad04c2bf47c2980613bd0af03211"}
    | {"severity": "INFO", "method": "GET", "route": "/topics/{uid}/{topic_id}", "status": 200, "latency_ms": 16, "event": "http_request", "request_id": "392d5ce66fe34c0fa519daf50d5ed32c"}
    | =========================== short test summary info ============================
    | FAILED tests/web/test_static_cache.py::test_after_a_deploy_the_paperclip_opens_the_file_chooser
    | 1 failed in 6.74s
  with the fix: exit 0
    | Using CPython 3.13.12
    | Creating virtual environment at: .venv
    | Installed 92 packages in 47ms
    | .                                                                        [100%]
    | 1 passed in 3.55s
```

Додатково — та сама репродукція, що в Attempt 1, проти дерева з виправленням (`cp -r src cards` у `…/repro/fixed`): `old image: #attach on the page: 0` / `new image: #attach on the page: 1` / `new image: conversation.js has attachDocument: function` / `FILE CHOOSER OPENED`.

## 7. Gate and overseer
- Gate: `uv run pytest -q` → `1614 passed, 36 deselected in 1208.13s` (було 1613 у задачі 209, +1 — цей тест); `uv run ruff check src tests` чисто; `uv run mypy src tests/web/test_static_cache.py` → `Success: no issues found in 57 source files`
- Overseer: PASS, запит `20261104T114955Z-4006de`. Його test gap (кожна адреса `/static/` на сторінках має `?v=` = хешу вмісту, і `rename.js` теж) закрито тут же: `tests/web/test_static_cache.py::test_every_static_url_on_the_pages_carries_the_content_version`
- The regression test stays in the suite: `tests/web/test_static_cache.py::test_after_a_deploy_the_paperclip_opens_the_file_chooser`, `tests/web/test_static_cache.py::test_every_static_url_on_the_pages_carries_the_content_version`

## 8. Lesson
Why was this not caught earlier — one of: a test was missing | the contract was wrong | a rule was missing | external.
- Answer: a test was missing — жоден тест не натискав справжню `#attach` (smoke і контрактні тести task 311 кладуть файл прямо в `#document`) і жоден не відкривав сторінку після «розгортання» в тому самому браузері, тож кеш `/static` старого образу не потрапляв під перевірку.
- Queued: `#c86ff9ac added`; під час розбору черги — `discard`: один випадок, регресійний тест лишається в наборі (для пам'яті потрібні два записи журналу)
