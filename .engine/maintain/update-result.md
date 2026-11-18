# Оновлення залежностей: що вийшло

Перелік: `.engine/maintain/updates.json` (8c6977f48f6fb5eaf89c3c977ed5364472b976bfd923b7cc2c99e8b6728150d3). Написав `owner_action.py update-deps` — runner за відповіддю власника «так».

Оновлено 8 з 9.

- `google-auth[requests]` 2.62.0 → 2.62.2, `httpx2` 2.16.0 → 2.16.2, `mypy` 2.4.0 → 2.4.1, `pydantic` 2.14.1 → 2.14.3, `pydantic-settings` 2.16.1 → 2.16.3, `ruff` 0.17.1 → 0.17.5 — оновлено, перевірки зелені, commit `7433ca3`.
- `import-linter` 2.15 → 2.16 — оновлено, перевірки зелені, commit `fb9d8b9`.
- `playwright` 1.64.1 → 1.65.2 — СКАСОВАНО: команда оновлення завершилась з кодом 1; файли повернуто з git; `uv sync --frozen` — код завершення 0. Вивід:
  ```
  × No solution found when resolving dependencies for split (markers:
    │ python_full_version >= '3.15'):
    ╰─▶ Because thinkhow:dev depends on playwright==1.64.1 and
        playwright==1.65.2, we can conclude that thinkhow:dev's requirements
        are unsatisfiable.
        And because your project requires thinkhow:dev, we can conclude that
        your project's requirements are unsatisfiable.
  
        hint: While the active Python version is 3.13, the resolution failed for
        other Python versions supported by your project. Consider limiting your
        project's supported Python versions using `requires-python`.
  ```
- `pytest` 9.1.1 → 9.2.0 — оновлено, перевірки зелені, commit `e34ddc0`.
