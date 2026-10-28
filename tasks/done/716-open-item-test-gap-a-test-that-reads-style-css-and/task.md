# 716 — Брак тесту (overseer): a test that reads style.css and asserts that #mic[data-state="recording"] hides .i-mic and shows .i-stop (or changes the background), and that #mic[data-state="recognizing"] shows .spinner

Залежить від: —
Аудит потрібен: ні
Відкритий пункт: test-gap-a-test-that-reads-style-css-and-asserts-that-mic-data-state-fb2dfa71

## Що сталося
Overseer прийняв юніт `-|207-icon-buttons|unit 1` (PASS, запит `20261025T212050Z-fb0bbb`) і знайшов брак тесту: Delete or break the CSS state rules and every test in the suite still passes, because the node tests only check mic.dataset.state. The person would then see no sign that recording is running, which the task requires («має бути видно й без тексту»). Only the Playwright script, which is not in the suite, would catch it. Де: `tests/web/test_icon_buttons.py`. Вердикт — у ledger: `python3 .claude/hooks/journal.py show ledger`.

- Записано: 2026-10-25T21:25:28Z, overseer (overseer_verdict.py)
- Це пропозиція, а не задача в черзі: runner із `tasks/proposed/` нічого не бере. У роботу її ставить власник — файлом із цим номером в inbox.

## Що зробити
Дописати перевірку «a test that reads style.css and asserts that #mic[data-state="recording"] hides .i-mic and shows .i-stop (or changes the background), and that #mic[data-state="recognizing"] shows .spinner»: тест червоніє на тому, що описано вище (Delete or break the CSS state rules and every test in the suite still passes, because the node tests only check mic.dataset.state. The person would then see no sign that recording is running, which the task requires («має бути видно й без тексту»). Only the Playwright script, which is not in the suite, would catch it.), і зелений на коді, як він є (покажи обидва прогони); код не міняти, якщо тест не знайде справжньої вади; швидкий набір тестів зелений.

## Готово, коли
Описане вище зроблено і перевірено, або на нього є відповідь власника.

## Питання до власника
