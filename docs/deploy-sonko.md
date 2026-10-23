# Розгортання walking skeleton ThinkHow — інструкція для Сонька

Ти розгортаєш прототип ThinkHow у Google Cloud замість власника. Основна інструкція — `docs/deploy.md`, кроки 1–9 і
чекліст розділу 10. Цей файл каже, як її виконати безпечно і що принести назад. Де вони розходяться, діє цей файл.

## Що ти отримуєш і що віддаєш

- **Вхід:** репозиторій `git@github.com:Tolkoton/thinkhow.git`, гілка `unattended/work`, commit `c3dcc00` або новіший
  (запиши, який саме розгорнув: `git rev-parse --short HEAD`).
- **Вихід:** файл `~/engine-ops/thinkhow/deploy-report-105.md` за формою з розділу «Звіт» нижче (дороблення —
  дописуй у той самий файл новим розділом з датою). Claude Code проєкту прочитає його сам. У репозиторій нічого не
  commit-ь і не push-ай.

## Перед стартом

1. `gcloud auth list` — активний акаунт `leskivmr@gmail.com` (роль Owner у проєкті). `gcloud config get project` —
   `pocket-lawyer-431614`. Якщо ні — зупинись і спитай власника.
2. Спитай у власника перелік Gmail-ів, яких запросити (Test users у кроці 6 і доступ IAP у кроці 8). Без переліку
   розгортай лише з `leskivmr@gmail.com`.
3. **Інвентаризація.** Проєкт `pocket-lawyer-431614` міг уже мати інші сервіси. До будь-якої зміни збери й запиши у
   звіт:
   ```bash
   gcloud run services list --region=europe-west3
   gcloud run jobs list --region=europe-west3
   gcloud storage buckets list --format='value(name)'
   gcloud logging sinks describe _Default
   gcloud logging buckets list --location=europe-west3
   gcloud iap settings get --project=pocket-lawyer-431614 2>&1 | head -40
   ```
   Окремо в консолі: чи є вже OAuth consent screen, якого він типу (Internal/External) і статусу (Testing/In production).

## Правила

- **Нічого існуючого не видаляй і не перезаписуй.** Якщо команда відповідає `already exists`, не видаляй і не
  створюй заново: перевір, що наявне відповідає інструкції, запиши «вже було» і йди далі. Якщо не відповідає —
  зупинись на цьому кроці і спитай власника.
- **Крок 2 (журнали) — лише якщо в проєкті нема інших сервісів.** `gcloud logging sinks update _Default` переводить
  журнали **всього проєкту**. Якщо інвентаризація показала будь-що, крім ThinkHow, `_Default` не чіпай. Замість цього:
  ```bash
  FILTER='resource.labels.service_name="thinkhow" OR resource.labels.job_name="thinkhow-learning"'
  gcloud logging buckets create thinkhow-eu --location=$REGION --retention-days=30
  gcloud logging sinks create thinkhow-eu \
    logging.googleapis.com/projects/$PROJECT/locations/$REGION/buckets/thinkhow-eu --log-filter="$FILTER"
  gcloud logging sinks update _Default --add-exclusion=name=thinkhow,filter="$FILTER"
  ```
  Тоді журнали ThinkHow лежать у `thinkhow-eu`, а решта проєкту — як було.
- **Крок 6 (OAuth, IAP).** Якщо consent screen уже є і він Internal або In production — не міняй його тип і статус,
  зупинись і спитай власника. Якщо IAP у проєкті вже має свій OAuth-клієнт — не заміняй, спитай. Client secret
  вводь лише в консоль; не пиши його у звіт, у файли чи в чат.
- **Права** — рівно ті, що в кроках 4, 8 і 9. Жодних ролей понад це і жодних змін IAM на ресурсах, яких інструкція
  не називає.
- **Код не міняй.** Якщо образ не збирається або сервіс не стартує — це результат: запиши помилку дослівно у звіт.
- **Команда не спрацювала:** прочитай помилку і спробуй ще раз один раз. Якщо прапорець не існує у твоїй версії
  `gcloud` (наприклад, `--iap` у `gcloud run deploy` може вимагати `gcloud beta run deploy`), можна взяти
  задокументований еквівалент — запиши у звіт, що саме замінив. Друга невдача — зупинись на цьому кроці, звіт.
- **Порядок важливий:** `seed` (крок 7) — до розгортання сервісу (крок 8).

## Дороблення після першого розгортання (2026-10-23)

Перший прогін зупинився на кроці 6. Сервіс віддає `502 Empty Google Account OAuth client ID(s)/secret(s)`, бо в IAP
сервісу `thinkhow` немає OAuth-клієнта. Проєкт без організації, тож API це не налаштує; роби це в консолі, у
своєму браузері під `leskivmr@gmail.com`. Решту кроків не повторюй.

1. **Google Auth Platform → Branding / Audience** (старе «OAuth consent screen»). Якщо екрана немає — створи:
   User type **External**, статус **Testing**. Якщо є — тип і статус не міняй. У **Test users** додай
   `leskivmr@gmail.com` і Gmail-и, які назвав власник.
2. **APIs & Services → Credentials → Create credentials → OAuth client ID → Web application**, назва `thinkhow-iap`.
   Після створення відкрий клієнт і додай Authorized redirect URI
   `https://iap.googleapis.com/v1/oauth/clientIds/<CLIENT_ID>:handleRedirect`.
3. **Security → Identity-Aware Proxy** → рядок Cloud Run `thinkhow` → ⋮ → **Settings** → **Custom OAuth** → встав
   Client ID і Secret, збережи. Secret нікуди не записуй.
4. Перевір: `curl -s https://thinkhow-1017046526541.europe-west3.run.app/` більше не дає `Empty Google Account OAuth…`,
   а `gcloud iap settings get --resource-type=cloud-run --service=thinkhow --region=europe-west3` показує
   `oauth_settings` (secret у звіт не копіюй).

Якщо в консолі будь-який з цих пунктів неможливий — зупинись і опиши у звіті, що саме бачиш на екрані.

## Чекліст (розділ 10 `docs/deploy.md`)

«так» ставиться лише за **перевіреним результатом** пункту, як він написаний у `docs/deploy.md`. Пункт, який ти не
виконав або виконав інакше (немає тем, не було повторного розгортання, Job запускали лише як `seed`, переглянуто
лише налаштування замість рядків журналу), — «не зроблено» з поясненням. Крок, що чекає дії, — це зупинка, не
«зроблено».

Пройди пункти 1–9. Пункт 2 потребує браузера з Gmail-ом, якого **не** запрошено; пункт 4 — браузера, де можна
видалити cookie. Якщо чогось із цього нема — постав «потрібна людина» і поясни чому; власник пройде ці пункти сам.
Пункт 6 (повторне розгортання) роби, коли ніхто не пише.

Пункти 5–9 мають сенс лише після того, як людина в пунктах 1–4 створила тему, написала репліку й натиснула
«Завершити сесію». До того вони — «не зроблено», а не «так»: порожній bucket, Job, запущений лише як `seed`, файли
`knowledge/` замість `learning/observations/s1.json`, наявний sink без рядків журналу результату пункту не дають.

## Звіт

`deploy-report-105.md`:

```markdown
# Розгортання 105 — звіт Сонька
Commit: <hash>   Дата: <YYYY-MM-DD>   gcloud: <версія>
URL сервісу: <url>

## Інвентаризація
<що вже було в проєкті; висновок: крок 2 за docs/deploy.md чи окремий sink>

## Кроки
| Крок | Результат: зроблено / вже було / помилка | Відхилення від інструкції |
|---|---|---|
| 1 … 9 | | |

## Чекліст
| Пункт | так / ні / потрібна людина | Що побачив |
|---|---|---|
| 1 … 9 | | |

## Помилки дослівно
<вивід команд, що впали; без client secret і без тексту розмов>
```

Власник перенесе підсумок у відповідь на питання 2 задачі `tasks/blocked/105-walking-skeleton.md`: «так», якщо всі
9 пунктів вийшли, або номери пунктів, що не вийшли, і що ти бачив.
