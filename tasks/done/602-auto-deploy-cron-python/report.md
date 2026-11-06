# 602 — Рядок cron автоматичного розгортання — з Python 3.12: звіт

## Що змінилось для власника
- Автоматичне розгортання працює на сервері тим рядком cron, який Сонько справді встановив:
  `python3` з `PATH=/home/lao/engine-ops/bin:…`, тобто Python 3.12. `docs/deploy.md`, розділ 11, тепер дає саме цей
  рядок (раніше — `/usr/bin/python3`, тобто 3.10, на якому скрипт падав). Рядок у документі збігається з `crontab -l`
  символ у символ.
- Щоб помилка не повторилась, є тест: він бере рядок cron з `docs/deploy.md`, знаходить `python3` за його `PATH`,
  запускає його і перевіряє, що версія задовольняє `requires-python` з `pyproject.toml` (`>=3.12`).

## Демонстрація на хвилину
- `uv run pytest -q tests/test_auto_deploy.py` → `16 passed`.
- Увесь набір: `uv run pytest -q` → `1628 passed, 36 deselected` (22 хв; `live` відібрано, як завжди).
- Новий тест ловить саме цю помилку: зі старим рядком у документі він падає з `assert (3, 10) >= (3, 12)`.
- `diff <(grep -o "\*/5 [^']*" docs/deploy.md) <(crontab -l | grep auto_deploy)` → без різниці.
- Сухий прогін з `PATH` рядка cron (лише читання):
  `PATH=/home/lao/engine-ops/bin:/snap/bin:/usr/bin:/bin THINKHOW_DEPLOY_STATE=/tmp/thinkhow-deploy-dry python3 scripts/auto_deploy.py --dry-run -v`
  → `up to date: nothing for the image changed since 8014eaf`, exit 0; `python3 --version` з цим `PATH` → `Python 3.12.13`.
- Живий cron: `~/.local/state/thinkhow-deploy/cron.log` порожній з 21:00 (жодного `ImportError`), файл `lock`
  оновлено о 21:35 — скрипт запускається.

## Витрати
Одна сесія board runner-а; додаткових сесій не було.

## Діапазон commit-ів
Від `93ee1ba` (задача → doing) до commit-а, яким задача переходить у `done/`.

## Відкладене
Нічого.

## Рішення, які я ухвалив сам
- Перевірку зроблено тестом у `tests/test_auto_deploy.py`, а не перевіркою версії всередині `scripts/auto_deploy.py`:
  скрипт на 3.10 падає ще на імпорті, тож власна перевірка в ньому дала б лише гарніше повідомлення в `cron.log`,
  а тест ловить неправильний рядок у документі до того, як його встановлять.
- Тест запускає справжній інтерпретатор з `PATH` рядка, тому він має сенс на цьому сервері; на машині без
  `/home/lao/engine-ops/bin` і без 3.12 у `/snap/bin`, `/usr/bin`, `/bin` він упаде — і це правильно: там рядок не працював би.
- `board_question` не змінено: він запускає `python3` з `PATH`, а `PATH` рядка cron дає 3.12. Це записано в docstring
  скрипта і в `docs/deploy.md`.
