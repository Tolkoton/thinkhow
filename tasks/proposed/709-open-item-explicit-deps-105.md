# 709 — Explicit dependencies: google-auth, PyYAML, httpx, httpx2, types-PyYAML

Залежить від: —
Аудит потрібен: ні
Відкритий пункт: explicit-deps-105

## Що сталося
Task 105, question 5: the owner allowed it and said dependencies are the agent's call («мене про таке не питати»). Unattended, the hook park-ask-gated.py refuses `uv add google-auth pyyaml httpx httpx2` (2026-10-24). The code imports them; today they come in only as dependencies of fastapi[standard], google-genai and google-cloud-storage.

- Записано: 2026-10-24T07:42:45Z, hook park-ask-gated.py
- Це пропозиція, а не задача в черзі: runner із `tasks/proposed/` нічого не бере. У роботу її ставить власник — файлом із цим номером в inbox.

## Що зробити
In a session the hook lets through (attended, or after the engine lets the agent add packages — engine task agent-decides-packages): `uv add google-auth pyyaml httpx httpx2` and `uv add --dev types-PyYAML`, then remove the mypy override for `yaml` in pyproject.toml; run ruff, mypy, pytest. Do not ask the owner.

## Готово, коли
Описане вище зроблено і перевірено, або на нього є відповідь власника.

## Питання до власника
