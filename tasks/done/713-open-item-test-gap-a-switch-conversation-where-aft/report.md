# Звіт — 713: брак тесту, рядок index-у після «Давай інакше» судив не ту картку

## Що змінилось для власника
- Overseer при PASS юніта 3 `router-eval` (запит `20261024T185333Z-f91702`) знайшов брак тесту: позначка
  «після «давай інакше»: end — …, нове offer без картки — …» в `index.md` живих розмов шукала `end` картки `c.led`,
  тобто останнього `choose`. Новий тест
  `test_switch_then_another_card_chosen_and_unfinished_the_row_judges_the_card_switched_from`
  (`tests/contract/router_eval/test_rev_switch_row.py:13`) показав, що це справжня вада: коли після перемикання
  роутер обирає іншу картку і вона не доходить до `end`, рядок казав «end — ні», хоча картку, з якої перемкнулись,
  закінчено `not_fit`.
- Виправлено в `scripts/card_conversations.py:340` (`_marks`): позначку тепер судять за карткою, з якої перемкнулись, —
  карткою першого `choose` (driver шле «Давай інакше» лише раз, через два ходи після першого `choose`). За цією
  карткою перевіряють і `end`, і те, що нове `offer` її не містить. Код продукту в `src/` не змінено.

## Демонстрація на хвилину
- Сценарій тесту (fake product model): offer → «Давай перше.» → `choose weighted-matrix` → два ходи → «Давай інакше» →
  `end weighted-matrix not_fit` → наступний хід роутер `choose five-whys` → five-whys не закінчується до межі в 8 ходів.
- Червоний прогін, старий `scripts/card_conversations.py` (`git stash`) + новий тест:
  `uv run pytest tests/contract/router_eval/test_rev_switch_row.py -q` → `1 failed`,
  `AssertionError: assert 'після «давай інакше»: end — так, нове offer без картки — ні' in '…обрано іншу картку (five-whys); після «давай інакше»: end — ні, нове offer без картки — ні |…'`.
- Зелений прогін на виправленому коді: той самий тест → `1 passed`; увесь `tests/contract/router_eval` → `50 passed`
  (до появи нового файлу, з тестом у ньому теж зелений).
- `python3 .claude/hooks/testing.py check router-eval` → `match: 6 sealed test file(s) of router-eval`: sealed tests
  tester-а не змінено.
- `uv run ruff check` і `ruff format --check` обох файлів — чисто; `uv run mypy scripts/card_conversations.py` → `Success`.
- Повний набір: `uv run pytest -q -p no:cacheprovider` → `26 failed, 1494 passed, 36 deselected`. Це ті самі 26 червоних, що й у задачі 712 (`394ea75`: «the same 26 red as before»): `skel_learning` 19, `skel_facilitation` 2, `walking_skeleton_block` 2, `one_conversation_block` 1, `voice_synthesis` 1, `voice_conversation_mode_block` 1. Жодного з `router_eval`.

## Витрати
Лише ця сесія; додаткових сесій Claude не запускав.

## Діапазон commit-ів
`0fc3879` (задача → doing) … `e765f45` (код і тест; помилково захопив ще три файли, нижче) … `c1057cb` (повертає ці
три файли) … commit, яким задачу перенесено в `done/`.

## Відкладене
Нічого.

## Рішення, які я ухвалив сам
- Задача каже «код не міняти, якщо тест не знайде справжньої вади». Тест її знайшов, тому я виправив `_marks`.
  Це скрипт evals, не код продукту.
- Тест не дописано в `tests/contract/router_eval/test_rev_conversations.py`, як сказано в задачі, а покладено поруч, в
  окремий файл `test_rev_switch_row.py`. Перший файл sealed для slice-у `router-eval` (`testing.py check` на
  дописаний файл відповів `CHANGED`), а builder файлів tester-а не редагує. Окремий файл seal не ламає.
- Картку, з якої перемкнулись, визначаю як картку першого `choose`. Це так, бо driver шле «Давай інакше» рівно раз,
  через два ходи після першого `choose`. Окремого поля в `Conversation` не додавав.
- Моя помилка і її виправлення: я запустив `commit_checkpoint.sh --help`, а скрипт прочитав `--help` як назву
  вузла і закомітив усе через `git add -u` (`e765f45`). Так у commit потрапили ваша незакомічена зміна
  `.claude/unattended/board-runner.sh` і два файли `.engine/artifacts/conversation-loop/smoke.txt`,
  `.engine/artifacts/conversation-resilience/smoke.txt`, які видалив прогін тестів. Історію я не переписував.
  Натомість commit `c1057cb` повертає ці три файли в git до попереднього стану. Ваша зміна в `board-runner.sh`
  лишилась у робочому дереві незакоміченою, як і була. Та сама помилка (без `--help`) уже була в задачі 703. Тому я
  поклав урок у чергу (`lesson_queue.py add`, `#dec79025`): аргументи `commit_checkpoint.sh` читати з його заголовка, а не через `--help`, і давати `--staged`, коли в дереві є чужі зміни.
