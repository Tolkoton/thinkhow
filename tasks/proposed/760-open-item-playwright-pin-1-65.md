# 760 — Playwright 1.64.1 → 1.65.2: зняти жорстку фіксацію

Залежить від: —
Аудит потрібен: ні
Відкритий пункт: playwright-pin-1-65

## Що сталося
Догляд 2026-11-18: runner скасував оновлення playwright 1.64.1 → 1.65.2 — pyproject.toml:23 фіксує playwright==1.64.1, тож 'uv sync --upgrade-package' не може вийти за цю межу (.engine/maintain/update-result.md). Ту саму версію named ще три sealed contract tests: tests/contract/conversation_resilience/cres_catchup_run.py:433, tests/contract/conversation_loop/cloop_catchup_run.py:369, tests/contract/minimal_design/mdesign_catchup_run.py:131 ('uv run --with playwright==1.64.1').

- Записано: 2026-11-18T11:10:54Z, агент
- Це пропозиція, а не задача в черзі: runner із `tasks/proposed/` нічого не бере. У роботу її ставить власник — файлом із цим номером в inbox.

## Що зробити
Змінити фіксацію в pyproject.toml на 1.65.2 (uv.lock — у тому ж commit-і), встановити відповідний Chromium (uv run playwright install chromium), прогнати smoke-скрипти голосу й розмови; три sealed тести, що називають 1.64.1, міняти лише через передбачений шлях для sealed тестів (re-seal).

## Готово, коли
Описане вище зроблено і перевірено, або на нього є відповідь власника.

## Питання до власника
