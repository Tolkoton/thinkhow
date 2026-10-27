# 717 — Брак тесту (overseer): A cl_talk test where, with the mode on, /reply answers non-200 with an <p class="error"> fragment (e.g. 409) and asserts #error shows that fragment's text, the mode goes to data-state="" with no reloa

Залежить від: —
Аудит потрібен: ні
Відкритий пункт: test-gap-a-cl-talk-test-where-with-the-mode-on-reply-answers-non-200-7e29cd87

## Що сталося
Overseer прийняв юніт `conversation-loop|308-voice-conversation-mode|unit 1` (PASS, запит `20261027T101838Z-1d20fb`) і знайшов брак тесту: attach's modeUi.showError could drop its text and call talk.failed() with no argument, or route to the page ui and reload; the tester left Q7 untested, so today's suite would let both through Де: `tests/contract/conversation_loop/cl_talk.test.mjs`. Вердикт — у ledger: `python3 .claude/hooks/journal.py show ledger`.

- Записано: 2026-10-27T10:31:28Z, overseer (overseer_verdict.py)
- Це пропозиція, а не задача в черзі: runner із `tasks/proposed/` нічого не бере. У роботу її ставить власник — файлом із цим номером в inbox.

## Що зробити
Дописати перевірку «A cl_talk test where, with the mode on, /reply answers non-200 with an <p class="error"> fragment (e.g. 409) and asserts #error shows that fragment's text, the mode goes to data-state="" with no reload, and #mic/#send are enabled again»: тест червоніє на тому, що описано вище (attach's modeUi.showError could drop its text and call talk.failed() with no argument, or route to the page ui and reload; the tester left Q7 untested, so today's suite would let both through), і зелений на коді, як він є (покажи обидва прогони); код не міняти, якщо тест не знайде справжньої вади; швидкий набір тестів зелений.

## Готово, коли
Описане вище зроблено і перевірено, або на нього є відповідь власника.

## Питання до власника
