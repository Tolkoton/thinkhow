# 705 — Refuse to start in the cloud without THINKHOW_IAP_AUDIENCE

Залежить від: —
Аудит потрібен: ні
Відкритий пункт: iap-audience-required

## Що сталося
load_settings refuses cloud mode without the two buckets and owner_email, but not without iap_audience (src/thinkhow/platform/config.py). With it empty the service starts and every IAP login fails at verification, which looks like an IAP problem.

- Записано: 2026-10-22T19:08:40Z, агент
- Це пропозиція, а не задача в черзі: runner із `tasks/proposed/` нічого не бере. У роботу її ставить власник — файлом із цим номером в inbox.

## Що зробити
Add iap_audience to the required cloud settings in platform/config.py (only for the web service: the Job reads no identity — e.g. a separate check in web/app.py build_deps), with a test.

## Готово, коли
Описане вище зроблено і перевірено, або на нього є відповідь власника.

## Питання до власника
