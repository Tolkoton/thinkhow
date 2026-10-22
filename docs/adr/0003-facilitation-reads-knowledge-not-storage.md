# ADR-0003: Фасилітація доходить до сховища лише через Знання — один названий виняток у запобіжнику імпортів

## Status

ACCEPTED — рішення агента (двосторонні двері, engine-rules «Verdict routing»), 2026-10-22, задача 105,
slice skel-facilitation; overseer ADR_REQUIRED (запит 20261022T164551Z-90467c). Власник бачить у звіті задачі.

Date: 2026-10-22

## Context and Problem Statement

Запобіжник A3 (M3) з slice skel-platform (Q5) — контракт import-linter «facilitation stores nothing and
knows no person»: `thinkhow.facilitation` не імпортує `thinkhow.access` і `thinkhow.platform.storage`.
import-linter за замовчуванням забороняє й непрямі ланцюжки. У slice skel-facilitation фасилітація
читає Знання (стрілка M3 facilitation → knowledge), а Знання читають сховище (стрілка M3 knowledge →
storage, slice skel-knowledge). Ланцюжок `facilitation → knowledge → knowledge.store →
platform.storage` зламав контракт, хоча кожна його стрілка дозволена M3.

Спершу агент поставив на контракт `allow_indirect_imports = true` і записав це лише рядком AUTONOMOUS у
`.engine/overseer/escalations.md` (facilitation-indirect-storage). Це розходиться з рішенням Q6 запечатаного
контракту skel-facilitation: там `allow_indirect_imports = true` відкинуто для контракту `workspace`, бо
воно послаблює запобіжник для всіх посередників. Overseer вимагав ADR.

## Decision Drivers

- G4 і M3 A3: запобіжник має ловити шлях до сховища, якого архітектура не дозволяла.
- Обидві стрілки ланцюжка — у M3; фасилітація справді нічого не зберігає сама.
- Узгодженість із Q6 skel-facilitation (не послаблювати запобіжник для всіх посередників).

## Considered Options

- A. `allow_indirect_imports = true` на контракті фасилітації — лише прямі імпорти заборонені.
- B. Непряма перевірка лишається, `ignore_imports = ["thinkhow.knowledge.store -> thinkhow.platform.storage"]`
  — виняток лише для одного ребра, яке дозволяє M3.
- C. Прибрати `platform.storage` з контракту фасилітації.

## Decision Outcome

Обрано **B**. Новий посередник, через який фасилітація дійшла б до сховища чи до `access`, і далі ламає
контракт; виняток — одне назване ребро. A відкинуто: перетворює запобіжник на перевірку лише прямих
імпортів (той самий аргумент, що в Q6). C відкинуто: втрачає перевірку прямого запису з фасилітації.

### Consequences

- Кожен новий законний ланцюжок до сховища через фасилітацію потребує ще одного рядка `ignore_imports`
  і нового рішення; незаконний — видно одразу.
- Зміст контракту S1: «жодного шляху, крім названих винятків». skel-platform Q5 і skel-facilitation Q6
  читаються разом із цим ADR.
- Двосторонні двері: один рядок у `pyproject.toml`. Запис AUTONOMOUS facilitation-indirect-storage
  у `escalations.md` замінено цим ADR.

## Amendment 1 — 2026-10-22, slice skel-learning

Контракт «learning needs no identity» (S1) зламався ланцюжком `learning.analyze → workspace → access →
access.user → platform.identity`: `access.user` імпортує лише тип `Identity` (параметр `current_user`), а
завдання навчання особи не перевіряє і `current_user` не кличе. За правилом цього ADR — один названий виняток:
`ignore_imports = ["thinkhow.access.user -> thinkhow.platform.identity"]` у контракті навчання; будь-який інший
шлях від навчання до `platform.identity` і далі ламає контракт. Відкинуто: `allow_indirect_imports` (те саме, що
варіант A вище); перенести `Identity` з `platform` в `access` — `platform.identity` повертає його, і `platform` не
імпортує частини (M3 A4).
