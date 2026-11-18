# 758 — Межа 60 с для згоди на глибоке дослідження (DeepConsent) — звіт

## Що змінилось для власника
Поки пропозиція глибокого дослідження чекає на згоду, кожна відповідь людині починається з виклику DeepConsent. Тепер завислий виклик DeepConsent обривається через 60 с, а не через 300 с. Двічі завислий виклик раніше тримав людину ≈ 606 с, тепер ≈ 127 с. Межа та сама, що вже стоїть у router-а, плану і StepOutcome. Виміряні виклики тривали 2.6–9.7 с (`.engine/artifacts/752/measurements.txt`), тож 60 с у шість разів більше за найдовший.

Виконано за вашою відповіддю «так» у картці (дозвіл змінити запечатаний тест).

## Демонстрація на хвилину
`uv run pytest -q tests/platform/test_measured_limits.py -k deep_consent`: тест імітує виклик, що завис двічі, а потім відповів. До зміни він був червоний: «the person waited 606 s». Тепер він зелений.

## Що зроблено
- `src/thinkhow/facilitation/types.py`: у `DeepConsent` додано `llm_timeout_s: ClassVar[float] = 60.0`.
- `tests/contract/deep_confirm/test_dc_types.py`: тест змінено рівно як у `.engine/artifacts/752/deep-consent.diff`. Тепер він називається `test_deep_consent_answer_is_one_of_four_words_and_has_its_own_minute_limit` і перевіряє `consent.llm_timeout_s == 60.0`. Файл запечатано заново командою `python3 .claude/hooks/testing.py reseal deep-research-confirm-first --owner-answer 758-open-item-deep-consent-minute-limit`, рядок про це є в `.engine/testing/ledger.md`.
- `tests/platform/test_measured_limits.py`: доданий тест `test_a_deep_consent_that_hangs_twice_is_given_up_within_a_minute_each_time`.
- Перевірки: повний набір тестів — 1717 passed. ruff: All checks passed. mypy: немає помилок у 453 файлах. Overseer: PASS (20261118T111928Z-267563).

## Витрати
Додаткових сесій Claude не було. Overseer — звичайний subagent цієї сесії.

## Діапазон commit-ів
Один commit після e808025 (board: 758 → doing).

## Відкладене
Рядок 53 контракту `.engine/slices/deep-research-confirm-first.md` (розділ Seam) досі каже, що DeepConsent не має власної межі. Контракт запечатаний, тому я його не змінював. Розділ «Deferred» того ж контракту відкладав цю межу саме до вимірів 752. Overseer визнав, що це виконання відкладеного пункту, а не нове рішення.

## Рішення, які я ухвалив сам
- Два кандидати з черги уроків (test-gap-update-only-retry-keeps-300, playwright-pin-1-65) відкинув. Вони вже лежать на task board як пропозиції 759 і 760, тож окремого уроку не несуть.
