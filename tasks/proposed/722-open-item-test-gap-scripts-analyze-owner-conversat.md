# 722 — Брак тесту (overseer): scripts/analyze_owner_conversation.py keeps the raw JSON of every attempt in the artifact (attempt 1 included), as Seam 4 requires ('сирий JSON кожного прогону')

Залежить від: —
Аудит потрібен: ні
Відкритий пункт: test-gap-scripts-analyze-owner-conversation-py-keeps-the-raw-json-of-3a76c7f3

## Що сталося
Overseer повернув юніт `analysis-rules|309-close-learning-loop|unit 2` (BLOCK, запит `20261027T174608Z-f15f28`) і назвав ще й брак тесту: the artifact now holds only attempt 2's raw JSON; attempt 1 is a prose summary, and its old-analyzer anchor (t18, per premise-log PR-27) disagrees with the t15 the artifact shows — nothing checks that each run's record survives Де: `scripts/analyze_owner_conversation.py`. Вердикт — у ledger: `python3 .claude/hooks/journal.py show ledger`.

- Записано: 2026-10-27T18:38:18Z, overseer (overseer_verdict.py)
- Це пропозиція, а не задача в черзі: runner із `tasks/proposed/` нічого не бере. У роботу її ставить власник — файлом із цим номером в inbox.

## Що зробити
Дописати перевірку «scripts/analyze_owner_conversation.py keeps the raw JSON of every attempt in the artifact (attempt 1 included), as Seam 4 requires ('сирий JSON кожного прогону')»: тест червоніє на тому, що описано вище (the artifact now holds only attempt 2's raw JSON; attempt 1 is a prose summary, and its old-analyzer anchor (t18, per premise-log PR-27) disagrees with the t15 the artifact shows — nothing checks that each run's record survives), і зелений на коді, як він є (покажи обидва прогони); код не міняти, якщо тест не знайде справжньої вади; швидкий набір тестів зелений.

## Готово, коли
Описане вище зроблено і перевірено, або на нього є відповідь власника.

## Питання до власника
