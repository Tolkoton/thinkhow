# 759 — Test gap: повтор «лише зміни карти» має лишити межу 300 с

Залежить від: —
Аудит потрібен: ні
Відкритий пункт: test-gap-update-only-retry-keeps-300

## Що сталося
Перший overseer задачі 752 назвав test gap. Межу 180 с поставлено в FacilitatorUpdate і FactAnswer. Повтор settle.py «лише зміни карти» (update_schema / RoutedFacilitatorUpdateOnly / FactUpdate) не успадковує цієї межі й лишається з 300 с. Жоден тест цього не тримає: якщо дати update_schema __base__=FacilitatorUpdate, повтор тихо отримає 180 с.

- Записано: 2026-11-18T08:24:05Z, агент
- Це пропозиція, а не задача в черзі: runner із `tasks/proposed/` нічого не бере. У роботу її ставить власник — файлом із цим номером в inbox.

## Що зробити
Тест у tests/platform/test_measured_limits.py: getattr(update_schema(card), 'llm_timeout_s', None) is None і так само для _routed(card)[1] і FactUpdate; або прогін SlowGemini, де повтор на 250 с не обривається.

## Готово, коли
Описане вище зроблено і перевірено, або на нього є відповідь власника.

## Питання до власника
