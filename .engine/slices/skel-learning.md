# Slice skel-learning — planning artifact

Feature: `.engine/architecture/feature/walking-skeleton.md`, S6 (block: learning) — **TRACER BULLET, частина 2**.
Driven mode: frame supplied by the feature artifact, not asked. Depends on S1, S2, S4 (50382d7, f8f5fb5, a1d5218) і
на S5 лише тим, що розширює його `tests/smoke/test_e2e_local.py`.

## Goal
Найтонша частина F10 (INDEX.md, «Walking skeleton»): Cloud Run Job `analyze` з того самого образу читає закриті
сесії, на кожну без спостереження робить **один виклик Gemini** і пише одне спостереження з посиланням на якір
репліки в `system/learning/`; та сама точка входу робить `seed` (посів Знань, M3 «Посів Знань»). Вимірна ціль:
`pytest` зелений, `tests/smoke/test_e2e_local.py` проходить увесь локальний ланцюжок до файла спостереження з
якорем `#t<n>` існуючої репліки (PR-09); `pytest -m live` — один справжній виклик аналізатора на `eu`;
smoke-скрипт.

## Premise verified
- S4: `all_topics_for_learning(storage) -> Iterator[TopicRef]`; `closed_sessions(storage, ref, now) ->
  list[ClosedSession(session_no, turns: list[NumberedTurn(no, role, text, at)], closed_at)]` — лише читання, без
  правила доступу, `TopicNotFound` на зламаний `ref`.
- S1: `Llm.generate_json(system, contents, schema, rev) -> M` (`ValidationError` на невалідну відповідь;
  `LlmUnavailable` після повторів); `make_llm(settings, script)`; `Storage.write`, `read`; `load_settings`.
- S2: `knowledge.seed(storage, cards_dir) -> bool`.
- Структурований вивід зі `enum` рядків працює на `gemini-4-argon`/`eu` (фази S3: live-тест 2026-10-22). Цілі
  числа в `enum` не перевірено — тому якір у схемі — рядок `"t<n>"` (Q2).
- Контракт фічі S6 → власник: спостереження містить `uid`, `topic_id`, `session_no`, `turn`, `link` =
  `/topics/<uid>/<topic_id>#t<turn>` — маршрут S5 (`GET /topics/{uid}/{topic_id}`, якорі `id="t<no>"`).
- Domain map «Аналізатор»: спостереження — що спрацювало чи ні, де саме (посилання на репліки), чия «вина»: вибору
  моделі, ведення розмови чи обставин.

## Out of scope (deliberately)
- Синтезатор, висновки, нові версії Знань (F12, F11); повторний аналіз після результату кроку (F9).
- Сторінка спостережень для власника (повна F10) — власник бачить файл у Cloud Storage.
- Рішення роутера, оцінки, кроки як сигнали (F5, F9) — у кістяку аналізатор читає лише репліки.
- Розклад (Cloud Scheduler) і права Job — розгортання, S7 (`docs/deploy.md`).

## Seam (contract)
Пакет `src/thinkhow/learning/`:
- `analyze.py`:
  - pydantic `Observation` (файл, `ConfigDict(frozen=True, extra="forbid")`): `uid: str`, `topic_id: str`,
    `session_no: int`, `turn: int`, `link: str`, `worked: bool`, `finding: str`, `cause: Literal["method",
    "facilitation", "circumstances"]`, `closed_at: datetime`, `analyzed_at: datetime` (ревізію Знань аналізатор у кістяку
    не читає, поля для неї нема — F10).
  - `answer_schema(turn_nos: Sequence[int]) -> type[BaseModel]` — схема відповіді моделі, у цьому порядку
    полів: `finding: str` (непорожній, українською), `worked: bool`, `cause: Literal[…]`, `anchor:
    Literal["t<n>", …]` — лише номери реплік **цієї** сесії (`pydantic.create_model`, як S3 Q1); JSON-схема
    поля **завжди** `{"type": "string", "enum": [...]}`, також для одного значення (pydantic для одного
    `Literal` дає `const` — probe critic-а; `const` на Vertex не перевірено).
  - `ANALYZER` — системна інструкція українською: роль аналізатора; прочитати одну закриту сесію; одне
    спостереження: що спрацювало чи ні в веденні до ясності, без готових відповідей людині (N1), де саме —
    `anchor` на одну репліку, чия «вина» — `cause`; не цитувати людину й не переказувати подробиць у
    `finding` понад потрібне (це читає лише власник, але висновки з нього підуть у Знання — domain map,
    інваріант Знань).
  - `contents` — один `Turn("user", …)`: рядки `#<no> людина|фасилітатор: <текст>` усіх реплік сесії по
    порядку, потім `[Сесія <session_no> закрита <closed_at ISO>]`.
  - `analyze(storage: Storage, llm: Llm, now: datetime) -> AnalyzeReport` — `now` без часового поясу →
    `ValueError` одразу, до будь-якої теми (помилка програми не ховається в журнал); для кожного `ref` з
    `all_topics_for_learning` і кожної `ClosedSession` з `closed_sessions(storage, ref, now)`: якщо файл
    `observations/<uid>/<topic_id>/s<session_no>.json` у bucket-і `system` під `learning/` уже є — пропустити
    (без виклику моделі); інакше один `llm.generate_json(ANALYZER, contents, answer_schema(nos), None)` →
    `Observation(…, turn=<n з anchor>, link=f"/topics/{uid}/{topic_id}#t{n}", closed_at, analyzed_at=now)` →
    `storage.write("system", "learning/observations/<uid>/<topic_id>/s<k>.json", …, "application/json")`
    (стале ім'я — повтор перезаписує). `ValidationError` чи `LlmUnavailable` на одній сесії — рядок журналу
    `analyze_failed` (`uid`, `topic_id`, `session_no`, клас винятку; без тексту) і далі наступна; наступний
    прогін спробує знову. Будь-який виняток на рівні теми (`closed_sessions`: `TopicNotFound`, зламаний
    `conversation.md`) — `analyze_failed` без `session_no`, і далі наступна тема (Q3).
  - `@dataclass(frozen=True) AnalyzeReport(written: int, skipped: int, failed: int)`; наприкінці рядок журналу
    `analyze_done` з цими числами.
- `__init__.py` нічого не реекспортує: публічне — `thinkhow.learning.analyze.analyze` і типи модуля
  `thinkhow.learning.analyze` (реекспорт функції `analyze` затулив би однойменний модуль).
- `local.py` — `local_script(system, contents, schema) -> str` — сценарна модель локального режиму для схеми
  аналізатора: `finding` «(локальний режим) Людина назвала план; фасилітатор поставив одне питання.», `worked:
  true`, `cause: "facilitation"`, `anchor` — перший у `enum` схеми.
- `job.py` — **composition root** завдання: `run(argv: Sequence[str], environ: Mapping[str, str], cards_dir:
  Path, now: Callable[[], datetime]) -> int`: `argv[0]` — `seed` → `knowledge.seed(make_storage(settings),
  cards_dir)`, рядок журналу `seed_done` (`created: bool`), код 0; `analyze` → `analyze(make_storage(settings),
  make_llm(settings, local_script), now())`, код 0 (навіть із `failed > 0` — помилка однієї сесії не є
  помилкою Job; видно в журналі); інше → рядок у stderr з використанням і код 2. `if __name__ == "__main__":
  sys.exit(run(sys.argv[1:], os.environ, <repo>/cards, lambda: datetime.now(UTC)))` — точка входу `python -m
  thinkhow.learning.job seed|analyze` (`PYTHONPATH=src`).
- import-linter: `learning` → `workspace`, `knowledge`, `platform.storage`, `platform.llm`, `platform.config`,
  `platform.log`; ↛ `platform.identity` (контракт S1), ↛ `web`.
- Errors: `ConfigError` (налаштування) кидається з `run`; помилки однієї сесії — у журнал, не далі.
- Dependencies (injected): `analyze` — `storage`, `llm`, `now`; `run` — `argv`, `environ`, `cards_dir`, `now`
  (`storage` і `llm` `run` будує сам з налаштувань — composition root).
- Does NOT do: запис у `users` чи `system/knowledge/` поза `seed`; читання Знань під час аналізу.

## Decisions (with WHY)
- Q1: пропуск уже наявного спостереження перевіряється читанням файла, без індексу. Чому: одна задача — один файл
  (M2 S2), стан — самі файли; при ≤50 сесіях на тиждень читання дешеве. Rejected: файл-індекс «що вже
  проаналізовано» — другий файл, який мусить узгоджуватися з першими.
- Q2: якір — рядок `t<n>` в `enum` схеми, звужений до реплік сесії. Чому: модель не може вигадати неіснуючий якір
  (I1); `enum` рядків перевірено на Vertex (S3), цілих — ні. Rejected: вільне число й перевірка після — частіші
  невдалі виклики; ціле в `enum` — неперевірена поведінка Vertex.
- Q3: помилка однієї сесії не валить Job. Чому: решта сесій аналізується; наступний прогін спробує знову (файла
  ще нема). Rejected: зупинка Job на першій помилці — одна зламана сесія блокує навчання всіх.
- Q4: аналізатор не читає Знань у кістяку. Чому: P5 — найпростіша форма; спостереження з якорем доводить ланцюжок
  (PR-09), якість аналізу — наступні функції. Rejected: передавати картку в промпт — ще одна залежність без
  потреби для доказу.

## Hardest seams (test-confidence points)
- **Seam 1: які сесії аналізуються** — теми двох людей: сесія закрита кнопкою; закрита тишею (остання репліка о
  `T`, `now = T + 24h`); відкрита (`now = T + 24h - 1s`); уже з файлом спостереження; порожня сесія, закрита
  кнопкою. Двійник `Llm` рахує виклики: рівно по одному на першу і другу, нуль на решту. Відкидає «тест з одною
  закритою сесією».
- Ще в Seam 1: тема із закритою сесією 1 (репліки 1–2) і закритою сесією 2 (репліки 3–4) — `enum` схеми для
  сесії 2 рівно `["t3", "t4"]`, її `Observation.turn` ∈ {3, 4}, `link` закінчується на `#t3` чи `#t4` (відкидає
  номер у межах сесії).
- Ще в Seam 1: закрита сесія з **однією** реплікою (репліка людини без відповіді, потім тиша) — один виклик,
  схема має `enum` з одним значенням, `Observation.turn` = її номер.
- **Seam 2: зламана відповідь моделі** — `analyze` з двійником, що кидає `ValidationError` на одній сесії і
  `LlmUnavailable` на іншій: файлів для них нема, рядки `analyze_failed`, решта записана, `failed == 2`. Окремо
  `run(["analyze"], …)` у локальному режимі з темою, чий `conversation.md` зламаний (не розбирається): рядок
  `analyze_failed` без `session_no`, `analyze_done` з `failed 1`, решта тем проаналізовано, **код 0** (відкидає
  `return 1 if report.failed else 0`). Ще (I2): записне сховище-шпигун — кожен `write` прогону `analyze` — bucket
  `system`, шлях починається з `learning/observations/`.
- **Seam 3: справжня модель** — `tests/live/test_learning_live.py` (`-m live`): закрита сесія з 40 реплік
  українською (сесії PoC мали до 60 — `enum` на 40 значень) → один виклик `gemini-4-argon` на `eu` → `Observation` з `turn` ∈ номерів реплік сесії ({1…40}).
- **Seam 4: ланцюжок локально** — `tests/smoke/test_e2e_local.py`: після частини 1 (S5) `job.run(["analyze"],
  …)` у тій самій теці → `system/learning/observations/local-owner/<topic>/s1.json` з `link`
  `/topics/local-owner/<topic>#t<n>`, і `GET` цієї адреси через застосунок S5 має елемент `id="t<n>"`.

## Invariants (rules that hold for every input in the stated domain)
- **I1** — Якір кожного спостереження — номер репліки його сесії, і `link` веде на неї.
  - Domain: будь-яка закрита сесія з ≥ 1 реплікою, будь-яка валідна відповідь моделі.
  - Source: G6 (посилання на місце в сесії); контракт фічі S6 → власник; S4 → S6 (номер має кожна репліка).
  - Broken by: схема з вільним `turn`; якір із номером в межах сесії замість наскрізного.
- **I2** — `analyze` не пише нічого поза `system/learning/observations/`.
  - Domain: будь-який стан bucket-ів, будь-які відповіді й падіння моделі.
  - Source: M2 S2 (Job має право лише читати `users`; `learning/…` пише лише навчання); M3 A3.4.
  - Broken by: позначка «проаналізовано» в `conversation.md`; запис у `knowledge/`.
- **I3** — Сесія з уже наявним спостереженням не викликає модель повторно.
  - Domain: будь-яка кількість прогонів `analyze` з будь-якими `now`, що не спадають.
  - Source: feature S6 («закриті сесії … без спостереження»); Q1.
  - Broken by: перевірка за часом прогону замість наявності файла.

## Exit criterion
- `uv run pytest` зелений: контрактні тести; `tests/smoke/test_e2e_local.py` до `analyze` і якоря (Seam 4);
  попередні slices, A3; `ruff`, `mypy`, `lint-imports` без помилок.
- `uv run pytest -m live tests/live/test_learning_live.py` — зелений проти `gemini-4-argon` на `eu`.
- `uv run python scripts/smoke_test_skel_learning.py` — тимчасова тека, локальний режим: `python -m
  thinkhow.learning.job seed` (`PYTHONPATH=src`) → код 0; тема з двома репліками через `workspace` (`facilitate` —
  `build_deps` S5 у локальному режимі, як `tests/smoke/test_e2e_local.py`) і закрита сесія; `python -m thinkhow.learning.job analyze` у локальному режимі → код 0; друкує файл спостереження;
  перевіряє `link` на існуючу репліку; другий `analyze` → `written 0, skipped 1`. Справжній Job — розгортання
  власника (S7).

## Deferred to later slices
- Повторний аналіз сесії, коли прийшов результат її кроку (domain map: пакет бере сесії, де результат новіший за
  спостереження) — F9/F10 — trigger: F9 «результат кроку»; тоді «файл є» перестає бути достатнім.
- Знання (картка, пам'ять) у промпті аналізатора, `model_rev` — F10 повна — trigger: задача F10.
- Сторінка спостережень власника — F10.
- Розклад і права Job — S7 (`docs/deploy.md`).

## Open items requiring human decision (if any)
- None.

## Revisions during planning
- **Phases 2–5 (critic round 1) — challenge:** "a one-turn closed session gets `const`, not `enum`" → **revised:** `answer_schema` завжди `enum`; випадок однієї репліки в Seam 1 → **reason:** probe pydantic; `const` на Vertex не перевірено, `local_script` бере перший з `enum`.
- **Cold-reader — challenge:** "I1's «Broken by» (in-session numbering) has no test input that catches it" → **revised:** тема з сесіями 1 і 2 у Seam 1 (`enum` `["t3","t4"]`) → **reason:** у сесії 1 обидві нумерації збігаються. Нотатки: Seam 3 `{1…40}` (2), `analyze` не реекспортується (3), клас винятку в `analyze_failed` уже є (4), `facilitate` smoke-у — `build_deps` S5 (5).
- **Cold-reader 2 — challenge:** "Seam 2's `run` returns 0 with a failing fake is untestable: `run` injects no `llm`" → **revised:** `run` доводиться зламаним `conversation.md` у локальному режимі; «Dependencies» за функціями; `now` без поясу → `ValueError` одразу (нотатка 2); тест I2 (нотатка 3) → **reason:** `ScriptedLlm` локального режиму ніколи не падає; виправлено без третього прогону (escalations.md, skel-learning-cold-reader).
- Нотатки прийнято: тема з помилкою не валить Job (2), без `model_rev` (3), live-сесія на 40 реплік (4), повторний аналіз — Deferred (5). Нотатка 6 (читання файла замість `list`) — свідомо: читання дешеве при ≤50 сесіях на тиждень.

## Critic notes (non-blocking)
- Той самий `const` для одного значення стосується `answer_schema` S3 (картка з однією фазою); у кістяку картка одна, з 4 фазами — не досяжно; пропозиція у звіті.
