# 712 — Finish the facilitator's answer after the window is closed

Залежить від: —
Аудит потрібен: ні
Відкритий пункт: ca-finish-answer-after-close

## Що сталося
When the person closes the window during the stream, their turn is saved but the answer is not (continuous-analysis Q6); the page then offers «Спробуйте ще раз».

- Записано: 2026-10-24T08:07:26Z, агент
- Це пропозиція, а не задача в черзі: runner із `tasks/proposed/` нічого не бере. У роботу її ставить власник — файлом із цим номером в inbox.

## Що зробити
Run the facilitator call to the end on the server even with no one watching, and write the answer. Trigger: a person's turn with no answer followed by another person's turn in conversation.md, or the owner asks for it.

## Готово, коли
Описане вище зроблено і перевірено, або на нього є відповідь власника.

## Питання до власника

1. **Код готовий і перевірений (commit `9ba9ac4`), але audit overseer-а не запускається — через ваду двигуна, не коду.**
   Сервер тепер дописує відповідь фасилітатора, коли вікно закрили; пізня відповідь не стирає того, що записано тим
   часом. 10 контрактних тестів tester-а зелені, smoke `uv run python scripts/smoke_test_finish_answer.py` → `OK`
   (на старому коді — `exit 1`), повний набір — ті самі 26 червоних, що до задачі. Вада: tester перейменував свої
   файли `test_fa_*` → `test_fin_*` (вони збігались іменем із тестами `fact_answer`, і повний прогін падав), а
   `testing.py` не вміє перенести печатку на нові імена. Він і далі пам'ятає старі шляхи, каже `CHANGED` і не дає
   overseer-у почати. Сам стан печатки (`.claude/state/`) агентові писати не можна. engine-27 вже підтвердив ваду і
   передав задачу на виправлення Сонькові (`~/sonko/requests/2026-10-28-engine-task-stale-seal.md`).
   Варіанти:
   (A) Чекати релізу двигуна з виправленням. Тоді один раунд objection з `renamed` перенесе печатку, overseer
       перевірить, задача закриється. Нічого робити не треба.
   (B) Перенести печатку зараз у вашому терміналі:
       `cd ~/projects/thinkhow && python3 -c "import hashlib,json,pathlib as p; f=p.Path('.claude/state/testing/seals/finish-answer.json'); s=json.loads(f.read_text()); d='tests/contract/finish_answer/'; s['files']={d+n:hashlib.sha256(p.Path(d+n).read_bytes()).hexdigest() for n in ('test_fin_behaviour.py','test_fin_invariants.py','test_fin_disputed_q1_superseded_turn.py')}; f.write_text(json.dumps(s,indent=2))"`
       і відповісти «B». Тоді я продовжу з audit.
   (C) Закрити без audit. Не раджу: overseer — єдина незалежна перевірка коду.
   Раджу (A): виправлення вже в дорозі, а (B) — ручний запис у стан hook-ів, який двигун потім однаково виправить
   по-своєму. Якщо поспішаєте — (B), він безпечний: міняє лише список запечатаних файлів цього slice-а.
   (`testing.py` порівнює саме SHA-256 файлу: `digest`, `.claude/hooks/testing.py`:1130.)
   Відповідь: (A) — чекати релізу двигуна з виправленням <!-- записано Claude зі слів власника 2026-10-28, сесія thinkhow-desk: «Так» — на пропозицію Claude «відповісти на всі 11 питань так, як радить runner; Сонько виконає дві команди, які заново фіксують змінені контракти» -->
