# 105 — Walking skeleton: найтонший наскрізний ланцюжок ThinkHow

Залежить від: 101
Потрібна присутність власника: ні
Режим: конвеєр
Аудит потрібен: так
Додаткові сесії: ні

Джерело: `/master-architect`, M4 → M5 (`.engine/architecture/INDEX.md`, розділ «Walking skeleton»).
Архітектура: `.engine/architecture/domain-map.md`, `.engine/architecture/architecture-map.md` (M2, M3),
`docs/adr/0001-files-in-cloud-storage.md`, `docs/adr/0002-gemini-pro-in-eu.md`. Проєкт і регіон —
`docs/infra.md`.

## Що зробити
- Побудувати через `/feature-architect` найтонші частини F1, F2, F6, F4, F3, F10 точно за таблицею
  «Walking skeleton» в `INDEX.md`: вхід IAP → тема → одна репліка з відповіддю Gemini Pro потоком за
  однією карткою (Pre-mortem, українською) → `conversation.md` і `map.json` у Cloud Storage → нічне
  завдання навчання читає закриту розмову й одним викликом Gemini пише спостереження з посиланням на
  якір репліки.
- Будова коду — M3 (папки за частинами, `platform` — єдиний, хто знає про Google, чотири автоматичні
  запобіжники A3). Додавання пакетів (`uv add …`) — з дозволу власника.
- Розгортання робить власник за інструкцією, яку skeleton пише в `docs/deploy.md`: bucket-и `users` і
  `system` (`europe-west3`, старі версії), Cloud Run service (1 екземпляр) з IAP і OAuth-клієнтом
  «External», Cloud Run Job (`seed`, `analyze`) з правом лише читати `users`, Cloud Scheduler, регіон
  журналів — ЄС.

## Готово, коли
- Наскрізний ланцюжок працює на розгортанні власника; premises PR-04 (вхід Gmail, email, потік SSE
  крізь IAP, репліка після закінчення сесії IAP не губиться) і PR-07 (файли пишуться й читаються з
  Cloud Run) — `verified` з посиланнями на докази; у журналі — `SKELETON_VERIFIED`.
- Тести A3 зелені: без циклів; лише `platform` імпортує SDK Google; теки людей пише лише `workspace`,
  чужа тема недоступна, власник бачить усе; Знання змінюються лише через `knowledge`.
- Не пройшло → premise `falsified`, повернення до M2/M3 (Art. 8).

## Питання до власника
1. Умова старту: PoC 101 пройдено — або ви письмово приймаєте ризик і стартуєте без нього?
   Відповідь:
