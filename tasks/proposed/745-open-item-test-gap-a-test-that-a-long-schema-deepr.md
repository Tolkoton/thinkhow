# 745 — Брак тесту (overseer): a test that a long schema (DeepReport, or any schema without llm_timeout_s) still gets HttpOptions.timeout == Settings.llm_timeout_s * 1000 (300000 ms) from VertexLlm._config

Залежить від: —
Аудит потрібен: ні
Відкритий пункт: test-gap-a-test-that-a-long-schema-deepreport-or-any-schema-without-l-7e6393a7

## Що сталося
Overseer прийняв юніт `-|313-reply-hangs-when-gemini-hangs|unit 1` (PASS, запит `20261110T085437Z-717ea4`) і знайшов брак тесту: an implementation that shortens the instance limit for everything (e.g. Settings.llm_timeout_s = 60, or getattr falling back to 60) passes both hung-call tests while it cuts the legitimate 194 s research report and searches, which breaks P4 Де: `tests/platform/test_hung_call.py`. Вердикт — у ledger: `python3 .claude/hooks/journal.py show ledger`.

- Записано: 2026-11-10T09:04:04Z, overseer (overseer_verdict.py)
- Це пропозиція, а не задача в черзі: runner із `tasks/proposed/` нічого не бере. У роботу її ставить власник — файлом із цим номером в inbox.

## Що зробити
Дописати перевірку «a test that a long schema (DeepReport, or any schema without llm_timeout_s) still gets HttpOptions.timeout == Settings.llm_timeout_s * 1000 (300000 ms) from VertexLlm._config»: тест червоніє на тому, що описано вище (an implementation that shortens the instance limit for everything (e.g. Settings.llm_timeout_s = 60, or getattr falling back to 60) passes both hung-call tests while it cuts the legitimate 194 s research report and searches, which breaks P4), і зелений на коді, як він є (покажи обидва прогони); код не міняти, якщо тест не знайде справжньої вади; швидкий набір тестів зелений.

## Готово, коли
Описане вище зроблено і перевірено, або на нього є відповідь власника.

## Питання до власника
