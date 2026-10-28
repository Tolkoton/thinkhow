# 711 — One continuous conversation per topic, no sessions

Залежить від: —
Аудит потрібен: ні
Відкритий пункт: ca-one-conversation

## Що сталося
Task 202 kept sessions (24 h of silence) only for display and the facilitator's history (continuous-analysis Q1). After a break of more than a day the facilitator does not see the earlier part of the topic.

- Записано: 2026-10-24T08:07:26Z, агент
- Це пропозиція, а не задача в черзі: runner із `tasks/proposed/` нічого не бере. У роботу її ставить власник — файлом із цим номером в inbox.

## Що зробити
If the owner wants the facilitator to see the whole topic: drop the session boundary for the facilitator's history and revise the analyzer's context limit (continuous-analysis Q8) together. Trigger: the owner says sessions are not needed, or sees the facilitator 'forget' a topic after a break.

## Готово, коли
Описане вище зроблено і перевірено, або на нього є відповідь власника.

## Питання до власника

1. **Код готовий (commit `3535650`), але Stop gate його не пропускає — через речі, яких ця задача не робила.** Фасилітатор
   тепер бачить усю тему, аналізатор — теж (контракт `.engine/slices/one-conversation.md`, 232 тести зелені, smoke
   `uv run python scripts/smoke_test_one_conversation.py` → `OK`). Gate блокує з двох причин:
   - `mypy` на змінених файлах: запечатані тести continuous-analysis, які довелося оновити, мали помилки ще до задачі
     (`FakeLlm` без `search_text`). На commit-і `5249680` `uv run mypy src tests` уже дає 208 помилок; у `src` — жодної.
     Ще 25 contract-тестів інших slice-ів червоні на тому самому commit-і.
   - `# noqa: E402` у файлах tester-а (`tests/contract/one_conversation/oc_fakes.py`, `…_block/test_ocb_block.py`) —
     той самий прийом, що в наявному `research_in_conversation_block/ric_fakes.py`; bypass guard просить
     `gate-allow`. Запечатані тести я правити не можу, а обидва раунди objection уже використано.
   Крім того, рядок контракту «`uv run mypy src tests` … зелені» був хибним від початку: tester запечатав тест
   `test_acceptance_4_…`, що його перевіряє, і той червоний.
   Варіанти:
   (A) Ви дозволяєте мені переписати контракт: «не гірше, ніж було, і файли цього slice-а чисті» плюс
       `gate-allow: noqa — sealed helpers reused via sys.path, as in ric_fakes`. Ви видаляєте старий fingerprint
       (`rm .claude/state/contracts/one-conversation.sha256`), tester звужує тест, overseer перевіряє, задача
       закривається. Борг із 208 помилок — окремо, пропозиція 733.
   (B) Спершу задача 733 (виправити 208 помилок mypy і 25 червоних тестів через tester-ів їхніх slice-ів), потім ця
       задача продовжиться без зміни контракту. Довше, і 733 сама може впертися в той самий gate.
   (C) Відкотити зміну (`git revert 3535650`) і лишити сесії, як було.
   Раджу (A): зміна продукту вже зроблена й перевірена, а заважає лише старий борг, який (A) не ховає, а виносить в
   окрему задачу.
   Відповідь:
