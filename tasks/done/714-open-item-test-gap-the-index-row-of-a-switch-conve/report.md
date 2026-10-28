# Звіт — 714: брак тесту, рядок index-у --switch розмови казав «обрано іншу картку», хоча роутер обрав цільову

## Що змінилось для власника
- Overseer при PASS юніта 3 `router-eval` (запит `20261024T185333Z-f91702`) знайшов брак тесту: позначку
  «обрано іншу картку (<id>)» в `index.md` живих розмов ставили за останнім `choose`. У --switch розмові останній
  `choose` іде після «Давай інакше», тож розмова, де роутер обрав цільову картку й вів її, все одно отримувала цю позначку.
- Новий тест `test_switch_conversation_that_led_the_target_first_is_not_marked_another_card`
  (`tests/contract/router_eval/test_rev_switch_row.py:43`) показав, що вада справжня.
- Виправлено в `scripts/card_conversations.py:275-278` (`_judge`): позначку тепер ставлять за першим `choose` роутера після
  його `offer` (`turn > 0`, тобто без засіяного вибору стенду); коли такого немає — за `conv.led`, як і раніше. Фази, `end` і `done` і далі
  судять за карткою, яку вели останньою. Код продукту в `src/` не змінено.

## Демонстрація на хвилину
- Сценарій тесту (fake product model): offer weighted-matrix/issue-tree → «Давай перше.» → `choose weighted-matrix` →
  два ходи → «Давай інакше» → `end weighted-matrix not_fit` → `choose five-whys`; target — weighted-matrix.
- Червоний прогін, тест на старому `_judge`: `uv run pytest tests/contract/router_eval/test_rev_switch_row.py -q` →
  `1 failed, 1 passed`, `'обрано іншу картку' is contained here: … | 8 | обрано іншу картку (five-whys); після «давай інакше»: end — так, нове offer без картки — ні |`.
- Зелений прогін після виправлення: `uv run pytest tests/contract/router_eval tests/contract/product_router_eval -q` →
  `75 passed` (сюди входять обидва тести цього файлу і `test_another_card_chosen_index_names_it_and_the_card_led_is_judged`, де позначка має лишитись).
- `python3 .claude/hooks/testing.py check router-eval` → `match: 6 sealed test file(s) of router-eval`.
- `uv run ruff check`, `ruff format --check` обох файлів — чисто; `uv run mypy scripts/card_conversations.py` → `Success`.
- Повний набір: `uv run pytest -q -p no:cacheprovider` → `26 failed, 1495 passed, 36 deselected`. Це ті самі 26 червоних, що й у задачі 713 (там `26 failed, 1494 passed`; плюс один — новий тест): `skel_learning` 19, `skel_facilitation` 2, `walking_skeleton_block` 2, `one_conversation_block` 1, `voice_synthesis` 1, `voice_conversation_mode_block` 1. Жодного з `router_eval`. Прогін переписав `.engine/artifacts/step-results/smoke.txt`, я повернув його до стану з git.

## Витрати
Лише ця сесія; додаткових сесій Claude не запускав.

## Діапазон commit-ів
`5b4c51a` (задача → doing) … `f820703` (код і тест) … commit, яким задачу перенесено в `done/`.

## Відкладене
Нічого.

## Рішення, які я ухвалив сам
- Тест знайшов справжню ваду, тож я виправив `_judge`. Це скрипт evals, не код продукту.
- Тест додано не в sealed `test_rev_conversations.py`, як сказано в задачі, а в `test_rev_switch_row.py` — файл builder-а
  із задачі 713. Причина та сама, що в 713: builder не редагує файлів tester-а.
- «Перший `choose` після offer» означає `turn > 0`. Так засіяний `choose` стенду (turn 0) не рахується за вибір роутера.
  Це та сама межа, якою вже користується `conv.offered`.
- Ваша незакомічена зміна `.claude/unattended/board-runner.sh` лишилась у робочому дереві: усі commit-и зроблено з `--staged`.
