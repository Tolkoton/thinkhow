# Рядок cron автоматичного розгортання — з Python 3.12, а не системним 3.10

Клас: 6
Залежить від: —
Потрібна присутність власника: ні
Режим: соло
Аудит потрібен: так
Додаткові сесії: ні

## Рішення власника
Слова власника (2026-11-06, сесія thinkhow-desk; записано Claude зі слів власника) — на питання Claude «Вмикати
автоматичне розгортання, тобто перевірку раз на 5 хвилин і розгортання на сервері кожної завершеної задачі без
вашого слова?»: «tak».

## Що сталося (Claude, 2026-11-06) [не слова власника]
- Рядок cron із задачі 601 (`docs/deploy.md`, розділ 11; звіт `tasks/done/601-auto-deploy-after-done/report.md`)
  запускає `/usr/bin/python3` з `PATH=/snap/bin:/usr/bin:/bin`. На сервері це Python 3.10.12, і
  `scripts/auto_deploy.py` падає на першому імпорті: `ImportError: cannot import name 'UTC' from 'datetime'`
  (`~/sonko/done/2026-11-06-thinkhow-auto-deploy-cron.md`). Проєкт вимагає `>=3.12` (`pyproject.toml`).
- `board_question` у тому самому скрипті запускає `python3` з `PATH` — з тим `PATH` це теж 3.10.
- Сонько встановлює рядок з `PATH=/home/lao/engine-ops/bin:/snap/bin:/usr/bin:/bin python3 …`
  (`/home/lao/engine-ops/bin/python3` → Python 3.12) — і скрипт, і `board.py` тоді на 3.12.
- Перевірка успіху з `/usr/bin/python3` у запиті задачі 601 ніколи не запускалась — сухий прогін у звіті йшов
  іншим `python3`.

## Що зробити
- `docs/deploy.md`, розділ 11, і docstring `scripts/auto_deploy.py` («cron runs it with the system python3») —
  під рядок, який Сонько справді встановив (перевір `crontab -l`).
- Щоб така помилка не повторилась: перевірка, що рядок cron із `docs/deploy.md` запускає Python, який задовольняє
  `requires-python`, — або інший найменший спосіб; вирішує агент.

## Готово, коли
- Тести зелені; `docs/deploy.md` збігається з `crontab -l`.

## Питання до власника
