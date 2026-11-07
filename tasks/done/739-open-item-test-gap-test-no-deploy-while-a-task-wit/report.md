# Звіт: тест «немає deploy, поки в doing/ задача з незакоміченим кодом» тепер справді будує образ

## Що змінилось для власника
Для вас нічого не змінилося: код автоматичного розгортання (`scripts/auto_deploy.py`) той самий, змінився лише тест.
Раніше тест `test_no_deploy_while_a_task_with_uncommitted_code_is_in_doing` ставив сервісу ту саму версію, що й
останній commit `→ done`, тож скрипт відповідав «up to date» ще до build. Реалізація, яка будує образ із робочої
теки (разом із незакоміченим кодом), цей тест проходила. Тепер сервіс працює на старішому commit-і, build справді
відбувається, і тест перевіряє, що в build context лежить `src/app.py` із commit-а `→ done` (`v2`), а не
незакомічений `v3-uncommitted`.

Справжньої вади тест не знайшов: на коді як він є тести зелені.

## Що зроблено
`tests/test_auto_deploy.py`, тест `test_no_deploy_while_a_task_with_uncommitted_code_is_in_doing`:
- `Gcloud(running=older)`, де `older` — короткий sha початкового commit-а фікстури (до `→ done`);
- очікується `deployed <done>`, `gcloud.built["src/app.py"] == "v2\n"` і що `tasks/doing/101-b.md` у build context немає.

Назву тесту не змінено: він і далі про те, що незакомічений код задачі з `doing/` не потрапляє в deploy.

## Демонстрація на хвилину
Червоний прогін. У `scripts/auto_deploy.py` функцію `unpack` тимчасово замінено на копію робочої теки
(`shutil.copytree(repo, into, …)` замість `git archive <sha>`):

```
uv run pytest -q tests/test_auto_deploy.py -k "uncommitted_code or snapshot_of_the_done"
>       assert gcloud.built["src/app.py"] == "v2\n"
E       AssertionError: assert 'v3-uncommitted\n' == 'v2\n'
2 failed, 14 deselected
```

На тій самій зміні стара версія тесту (з `HEAD`) зелена — `1 passed, 15 deselected`. Отже, брак, про який писав
overseer, справжній, а новий тест його закриває.

Зміну скасовано (`git status` показує лише `tests/test_auto_deploy.py`). Зелений прогін на коді як він є:

```
uv run pytest -q tests/test_auto_deploy.py
16 passed
```

`uv run ruff check tests/test_auto_deploy.py` — `All checks passed!`; `uv run mypy tests/test_auto_deploy.py` —
`Success: no issues found in 1 source file`.

Повний набір: `uv run pytest -q` → `1629 passed, 36 deselected in 1208.38s`. Прогін переписав
`.engine/artifacts/step-results/smoke.txt`; цю зміну скасовано, у commit вона не йде.

## Витрати
Одна сесія runner-а. Додаткових сесій Claude не було.

## Діапазон commit-ів
Від `485b208` (задача в `doing/`) до commit-а, що переносить задачу в `done/`.

## Відкладене
Нічого.

## Рішення, які я ухвалив сам
- Змінив наявний тест, а не дописав новий поруч: випадок «сервіс уже на цій версії» окремо покриває
  `test_no_deploy_when_the_image_is_already_this_version`, тож стара перевірка «up to date» дублювала його.
- Червоний прогін — на заміні `unpack` копією робочої теки: саме таку реалізацію описав overseer.
