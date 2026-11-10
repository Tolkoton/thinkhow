# Bug 003-hung-router-call

type: bugfix
status: fixed
<!-- status: recorded → reproduced → fixed; or parked (not reproduced in three attempts);
     or question for the owner (the expected behaviour is written nowhere); or became a slice.
     This file is the contract of the fix and its report at once: the overseer audits against it.
     Sections 1–4 are written before the fix exists. -->

## 1. Record
- Symptom: власник (2026-11-10, сесія Thinkhow): «Так, останні апдейти поламали SynHub в корі. Він навіть не відповідає.»
- Expected: завислий виклик Gemini розпізнається швидко — за секунди-хвилину для роутера, а не через 300 с на кожну з трьох спроб; виклик, що справді працює і видає відповідь, не обривається (P4).
- Where the expected is written: слова власника в `tasks/doing/313-reply-hangs-when-gemini-hangs.md`, «Що зробити»: «Виправити так, щоб завислий виклик розпізнавався швидко, а не через 300 с: наприклад, окремі межі для різних викликів за їхніми виміряними часами (роутер і структуровані виклики — секунди; …)» і «P4 («якість ведення понад швидкість»): не обривати виклик, що справді працює і видає відповідь, — лише завислий.»
- Actual: межа кожного виклику одна — `llm_timeout_s = 300.0`, спроб `llm_attempts = 3` (`src/thinkhow/platform/config.py:30-31`); виклик роутера, що двічі завис, тримає людину 604 с.
- Where it was seen: Cloud Run, ревізія `…7-nsm`, 2026-11-10 07:12:18 UTC `POST /topics/{uid}/{topic_id}/reply` — 645 с; рядок `llm_call` 07:22:23: `search: false`, `latency_ms: 604431`, `attempts: 3`, `prompt_tokens: 21762`, `output_tokens: 188`, `outcome: ok`.

### Виміряні часи (Cloud Logging, `gcloud logging read 'resource.type="cloud_run_revision" AND jsonPayload.request_id:*' --freshness=30d`, 668 рядків, 125 `llm_call`, згруповані за `request_id` з рядком `http_request`)
Вид виклику — за `search` і порядком у запиті: `search: false` — `generate_json`; `true` — `stream_json` екземпляра з пошуком або `search_text`.
- Роутер (`generate_json`, перший виклик `POST …/reply`), 23.10–10.11, ~55 викликів з однією спробою: 3.5–16 с типово; рідше 24.9, 45.0 с; один 177.5 с (27.10 11:49, `attempts: 1`). Завислий: 604.4 с, `attempts: 3`.
- План дослідження (`generate_json`, 2-й із 7 викликів): 7.7, 7.7, 16.4 с.
- Звіт дослідження (`generate_json`, 7-й із 7): 43.6, 47.6, 193.6 с.
- Пошуки дослідження (`search_text`, 3–6-й із 7): 25.7–180.6 с; один 347.5 с з `attempts: 2` (06.11 08:52 — перша спроба висіла до 300 с).
- Потік фасилітатора (`stream_json`): 4.1–119.3 с загалом; сьогодні 40.4, 62.5, 109.4 с.

## 2. Reproduction
Three attempts, each a different way. Reproduced — stop at that attempt. Not reproduced after
the third — the status becomes `parked`, nothing below is filled in and no code is changed.

### Attempt 1
- Command: `PYTHONPATH=src uv run python /tmp/r313/repro.py` — справжній `route()` і справжній `VertexLlm` з межами `Settings` (300 с, 3 спроби); підставний клієнт Gemini двічі «висить» (годинник іде на всю межу читання з `http_options.timeout`, тоді `httpx.ReadTimeout` — так httpx здається, коли сервер не шле жодного байта), третій раз відповідає за 4 с.
- Output:
  ```
  {"severity": "INFO", "model": "gemini-4-argon", "prompt_tokens": 0, "output_tokens": 0, "thought_tokens": 0, "latency_ms": 605739, "attempts": 3, "rev": 3, "n": 7, "outcome": "ok", "search": false, "queries": 0, "event": "llm_call", "request_id": null}
  router action=answer; the person waited 606 s
  ```
  Те саме, що в журналі Cloud Run: `latency_ms: 604431`, `attempts: 3`, `outcome: ok`.
- Result: reproduced

### Attempt 2
Не потрібна: відтворено з першої спроби (і збігається з журналом Cloud Run у розділі 1).

### Attempt 3
Не потрібна: відтворено з першої спроби.

## 3. Failing test
- Test: `tests/platform/test_hung_call.py::test_a_router_call_that_hangs_twice_is_given_up_within_a_minute_each_time` — `route()` над справжнім `VertexLlm` з межами `Settings` і клієнтом Gemini, що двічі висить; людина чекає не більше 2 × 60 с + backoff (≤ 3 с) + відповідь (4 с).
- Сусід із тією самою причиною, власний тест: `tests/platform/test_hung_call.py::test_a_deep_plan_call_that_hangs_twice_is_given_up_within_a_minute_each_time` — `deep_research()`, перший кроки плану людині показано не пізніше тієї ж межі.
- Command that runs it: `uv run pytest tests/platform/test_hung_call.py -q`
- It fails with: `E       AssertionError: the person waited 606 s` (обидва тести; 600 с двох межок по 300 с + backoff + 4 с відповіді)
- Tests written first to pin the present behaviour around the code (only when no test could reach it): none

## 4. Cause
Written before the fix.
- Where it showed: `src/thinkhow/facilitation/route.py:73` — `llm.generate_json(...)` роутера повертається лише через 604 с.
- Why it happened: `VertexLlm` дає кожному виклику ту саму межу `self.timeout_s` (`src/thinkhow/platform/llm.py` `_config`: `http_options=types.HttpOptions(timeout=int(self.timeout_s * 1000))`), а вона з `Settings.llm_timeout_s = 300.0` — розміром під найдовший законний виклик (пошук дослідження до ~181 с, звіт до ~194 с). Виклик без потоку (`generate_content`) не шле жодного байта до кінця, тож httpx-межа читання — це межа всього виклику; завислий короткий виклик чекає ту саму довгу межу, і так до трьох разів.
- Same places: `grep -rn "generate_json\|stream_json\|search_text" src` — кожен виклик живе під тією самою межею 300 с:
  - `facilitation/deep.py:68` план дослідження — короткий структурований (7.7–16.4 с) → та сама причина, виправляється тут з власним тестом.
  - `facilitation/steps.py:24` розпізнавання кроку — короткий структурований, але в журналах його не відрізнити (нема вимірів) → пропозиція задачі.
  - `facilitation/deep.py:74` звіт дослідження (43.6–193.6 с), `learning/*` (пакетне завдання, не перед людиною), `settle.py:50,53` (рідкий запасний шлях, пише всю відповідь) — законно довгі, межу 300 с лишаю.
  - `facilitation/respond.py:64`, `answer.py:34` потік фасилітатора — межа httpx тут між фрагментами; до першого фрагмента йде мислення (сьогодні до ~100 с), виміру «час до першого фрагмента» в журналі нема → пропозиція задачі (спершу логувати цей час).
  - `facilitation/deep.py:183` пошук дослідження (`search_text`) — законно до ~181 с, 06.11 висів 300 с → межа між ними потребує більше вимірів → у ту саму пропозицію.

## 5. Fix
- What changed:
  - `src/thinkhow/platform/llm.py` `_config`: межа виклику — `llm_timeout_s` схеми, якщо схема її має, інакше межа екземпляра (300 с); так короткий структурований виклик здається за своєю межею, а довгі лишаються як були.
  - `src/thinkhow/facilitation/route.py` `RouterAnswer.llm_timeout_s = 60.0` (ClassVar; схема `router_schema` її успадковує; у JSON-схему для моделі не йде — перевірено: `'llm_timeout_s' in RouterAnswer.model_json_schema()['properties']` → `False`).
  - `src/thinkhow/facilitation/types.py` `DeepPlan.llm_timeout_s = 60.0` — сусід із тією самою причиною.
  - Межа 60 с: роутер законно 3.5–45 с (один раз 177.5 с), план 7.7–16.4 с; 60 с ≥ 1.3 × найдовшого звичайного і ≈ 4 × типової верхньої межі 16 с. Завислий двічі виклик тепер тримає людину ≈ 125 с замість 604 с (найгірше — три завислі спроби: ≈ 183 с замість ≈ 903 с).
  - Чому не параметр `generate_json(..., timeout_s=)`: протокол `Llm` реалізують 33 підставні класи в тестах (`grep -rn "def generate_json" tests src | wc -l` → 33), більшість — запечатані контрактні тести; межа на схемі не міняє протоколу.
  - Бюджет: `complexity_budget.py check` → `within budget … production: 0 new files, +8 lines, 0 new public symbols, 0 new abstractions, 0 new dependencies; tests: +75 lines`.
- Nothing else: no tidying on the way, no renaming, no new helper for later.

The budget below is the ready small budget of a bug fix. The 40 is a signal, not a ceiling —
going over any line calls the simplifier; when it does not find the excess justified, this
stops being a bug fix and becomes a slice through `/plan-slice`. The numbers are not edited.

## Complexity budget
base_commit: 54919d209ffd167a8f9cf7eb4c8d889a493de2c3
max_new_files: 0
max_net_new_lines: 40
max_new_public_symbols: 0
max_new_abstractions: 0
max_new_dependencies: 0
justification: none

## 6. Proof
The command and the whole output of `python3 .claude/hooks/bugfix.py prove …`, pasted. `REFUSED` is not a proof.

Command: `python3 .claude/hooks/bugfix.py prove --record .engine/bugs/003-hung-router-call.md --test tests/platform/test_hung_call.py --cmd "uv run pytest tests/platform/test_hung_call.py -q" --expect "AssertionError: the person waited 60"` (`--expect` без останньої цифри: backoff випадковий, 605–607 с)

```
PROVED: tests/platform/test_hung_call.py fails on 54919d2 and passes on the working tree; the failure shows «AssertionError: the person waited 60»
  command: uv run pytest tests/platform/test_hung_call.py -q
  the fix: .engine/PROGRESS.md, .engine/bugs/003-hung-router-call.md, src/thinkhow/facilitation/route.py, src/thinkhow/facilitation/types.py, src/thinkhow/platform/llm.py
  before the fix: exit 1
    |         client = HangingGemini(hangs=2, raw=plan)
    |         steps = next(deep_research("питання", fa.context(()), production_llm(client), KnowledgeRev(3, 7)))
    |         assert isinstance(steps, ReplyDelta) and steps.text.startswith("Шукаю.")
    | >       assert client.now <= 2 * 60 + BACKOFF_S + ANSWER_S, f"the person waited {client.now:.0f} s"
    | E       AssertionError: the person waited 606 s
    | E       assert 606.0712102346853 <= (((2 * 60) + 3.0) + 4.0)
    | E        +  where 606.0712102346853 = <test_hung_call.HangingGemini object at 0x7882e0430e10>.now
    | 
    | tests/platform/test_hung_call.py:75: AssertionError
    | ----------------------------- Captured stdout call -----------------------------
    | {"severity": "INFO", "model": "gemini-4-argon", "prompt_tokens": 0, "output_tokens": 0, "thought_tokens": 0, "latency_ms": 606071, "attempts": 3, "rev": 3, "n": 7, "outcome": "ok", "search": false, "queries": 0, "event": "llm_call", "request_id": null}
    | =========================== short test summary info ============================
    | FAILED tests/platform/test_hung_call.py::test_a_router_call_that_hangs_twice_is_given_up_within_a_minute_each_time
    | FAILED tests/platform/test_hung_call.py::test_a_deep_plan_call_that_hangs_twice_is_given_up_within_a_minute_each_time
    | 2 failed in 1.54s
  with the fix: exit 0
    | Using CPython 3.13.12
    | Creating virtual environment at: .venv
    | Installed 92 packages in 49ms
    | ..                                                                       [100%]
    | 2 passed in 1.49s
```

## 7. Gate and overseer
- Gate: `uv run pytest -q` → `1634 passed, 36 deselected in 1207.22s` (до: 1632 passed, задача 212); `uv run ruff check .` → `All checks passed!`; `uv run mypy` → `Success: no issues found in 59 source files`; import-linter → `Contracts: 7 kept, 0 broken.`
- Overseer: PASS, `20261110T085437Z-717ea4` (re-ran `bugfix.py prove` → PROVED). Test gap it named — a test that a schema without `llm_timeout_s` (e.g. `DeepReport`) still gets 300 000 ms — became `tasks/proposed/745-open-item-test-gap-a-test-that-a-long-schema-deepr.md`.
- The regression test stays in the suite: `tests/platform/test_hung_call.py::test_a_router_call_that_hangs_twice_is_given_up_within_a_minute_each_time`, `…::test_a_deep_plan_call_that_hangs_twice_is_given_up_within_a_minute_each_time`

## 8. Lesson
Why was this not caught earlier — one of: a test was missing | the contract was wrong | a rule was missing | external.
- Answer: the contract was wrong — skel-platform поставив одну межу на всі виклики Gemini (`Settings.llm_timeout_s = 300.0`) під найдовший, і жоден тест не питав, скільки чекає людина, коли короткий виклик висить.
- Queued: `#7097cdec added`; triaged → discard (the lesson lives in this record; one case is not a rule yet).
