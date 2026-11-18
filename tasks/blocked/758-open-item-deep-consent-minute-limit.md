# 758 — Межа 60 с для згоди на глибоке дослідження (DeepConsent) — правка запечатаного тесту

Залежить від: —
Аудит потрібен: ні
Відкритий пункт: deep-consent-minute-limit

## Що сталося
Задача 752 поставила межі за вимірами. Для DeepConsent вони такі: у журналі 3.3 с (1 виклик), 6 живих викликів 2.6–9.7 с (.engine/artifacts/752/measurements.txt). Тому межу варто поставити 60 с, як у роутера, плану і StepOutcome. Тоді двічі завислий виклик тримає людину ≈ 125 с, а не ≈ 605 с; поки пропозиція дослідження чекає згоди, з цього виклику починається кожна відповідь. Але запечатаний тест slice-а deep-research-confirm-first, tests/contract/deep_confirm/test_dc_types.py::test_deep_consent_answer_is_one_of_four_words_and_has_no_own_time_limit, вимагає, щоб DeepConsent не мав власної межі. Так каже рядок 53 його контракту (.engine/slices/deep-research-confirm-first.md), а розділ «Deferred» того ж контракту відкладає цю межу саме до 752. Objection тут не допоможе: тест відповідає своєму контракту, тож tester, найімовірніше, скаже test_right. Supersede потребує нового запечатаного контракту, а в 752 його немає. Тому в 752 я DeepConsent не змінив, і набір лишився зеленим. Готова правка: .engine/artifacts/752/deep-consent.diff (ClassVar у types.py, рядок тесту стає assert consent.llm_timeout_s == 60.0, плюс тест завислого виклику в tests/platform/test_measured_limits.py).

- Записано: 2026-11-18T08:20:19Z, агент

## Що зробити
Це питання до власника, не робота для агента. Коли власник відповість, задача повернеться в чергу: виконай відповідь, запиши її у звіт і закрий задачу.

## Готово, коли
Власник відповів, і відповідь виконано.

## Питання до власника
1. Дозволити правку запечатаного тесту slice-а deep-research-confirm-first, файл tests/contract/deep_confirm/test_dc_types.py, рівно як у .engine/artifacts/752/deep-consent.diff? А. Так: наступна сесія кладе правку, ставить DeepConsent межу 60 с і запечатує файл заново командою python3 .claude/hooks/testing.py reseal deep-research-confirm-first --owner-answer <ця картка>; скрипт приймає лише одне слово «так». Б. Ні, лишити 300 с: двічі завислий виклик згоди й далі триматиме людину ≈ 605 с. Порада: А — виміри 2.6–9.7 с, 60 с у 6 разів більше за найдовший.
   Відповідь:
