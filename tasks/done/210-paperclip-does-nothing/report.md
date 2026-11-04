# Звіт задачі 210 — Скріпка на сервері не відкриває вибір файла

## Що змінилось для власника
- **Причину знайдено й відтворено: браузер брав старий `conversation.js` зі свого cache.** Сторінка теми вже
  нова, і скріпка на ній є. А скрипт до неї браузер узяв з образу `76e81f3`, якому кілька днів. У тому скрипті
  скріпки ще немає: функції `attachDocument` у ньому нема. Тому натискання нічого не робить. Мікрофон і
  надсилання є й у старому скрипті, тож вони працюють.
- **Чому так.** `/static` віддає `StaticFiles` без заголовка `Cache-Control`, але з `Last-Modified`. Ця дата — час
  commit-а образу. Без `Cache-Control` браузер сам вирішує, скільки файл лишається свіжим: приблизно 10 % від його
  віку. Файлу три дні, отже браузер годинами не питає сервер про новий. Адреса `/static/conversation.js` між
  образами не змінюється.
- **Виправлення.** Тепер кожна адреса `/static/...` має версію: `?v=` і перші 12 знаків sha256 від вмісту файлів
  `static/`. Так зроблено для `conversation.js`, `style.css` і `rename.js`. Якщо в новому образі ці файли змінились,
  змінюються й адреси, і старий файл з cache браузер узяти не може. Якщо файли ті самі, адреси ті самі, і cache
  працює як раніше.
- **Новий тест натискає справжню скріпку** (`tests/web/test_static_cache.py`). У тому самому профілі браузера за
  тією самою адресою спершу працює «старий образ», потім справжній застосунок. Тест натискає `#attach` і чекає
  вікна вибору файла (`expect_file_chooser`). Ще він перевіряє, що діє новий `style.css`. Без виправлення тест
  падає, з виправленням проходить. Це перевірив скрипт `bugfix.py prove` (нижче).
- **Після deploy, який принесе це виправлення, скріпка запрацює одразу.** Нова адреса скрипта браузеру ще не
  знайома, тож він завантажить скрипт з сервера. До того deploy на сервері лишається старе. Щоб скріпка запрацювала
  вже зараз, допоможе жорстке перезавантаження сторінки теми (Ctrl+Shift+R; на телефоні — очистити дані сайту).
  Нижче готовий текст запиту Сонькові. Сам я його не надсилав: без вашого слова запитів Сонькові не пишу.

## Демонстрація на хвилину
Відтворення в справжньому браузері (Playwright Chromium). Профіль браузера, порт і тека даних однакові для обох
кроків. Спершу сервер з образу `76e81f3` (`git archive`): створюю тему. Потім сервер з нового дерева: відкриваю ту
саму тему і натискаю скріпку. Скрипт лежить у
`/tmp/claude-1001/-home-lao-projects-thinkhow/0113f282-08e8-525a-a3e1-43a8f6b01ea5/scratchpad/repro/stale_cache.py`
і запускається так: `uv run python stale_cache.py <старий знімок> <новий знімок>`.

Новий образ без виправлення (`94906cf`):
```
old image: #attach on the page: 0
new image: #attach on the page: 1
new image: conversation.js has attachDocument: undefined
NO FILE CHOOSER: TimeoutError Timeout 3000ms exceeded while waiting for event "filechooser"
```
Новий образ з виправленням:
```
old image: #attach on the page: 0
new image: #attach on the page: 1
new image: conversation.js has attachDocument: function
FILE CHOOSER OPENED
```

## Перевірка
- Bug record: `.engine/bugs/001-stale-static-cache.md`. У ньому відтворення, причина, записана до виправлення,
  доказ і урок.
- `python3 .claude/hooks/bugfix.py prove …` → `PROVED: tests/web/test_static_cache.py fails on 94906cf and passes
  on the working tree; the failure shows «the paperclip opened no file chooser»`.
- `python3 .claude/hooks/complexity_budget.py check` → `within budget`: production — +6 рядків, 0 нових файлів,
  0 нових public names.
- `uv run ruff check src tests` чисто; `uv run ruff format --check src tests` → `435 files already formatted`;
  `uv run mypy src tests/web/test_static_cache.py` → `Success: no issues found in 57 source files`.
- `uv run pytest -q` → `1614 passed, 36 deselected in 1208.13s` (20 хв). Після цього прогону змінились лише тести:
  тип параметра в `_serve` (замість `type: ignore`) і другий тест (нижче); `uv run pytest -q tests/web/test_static_cache.py`
  → `2 passed`.
- Overseer: **PASS** (запит `20261104T114955Z-4006de`). Він назвав прогалину: тест не перевіряв, що версію має
  кожна адреса `/static/`, зокрема `rename.js`. Я закрив її тут же другим тестом
  `test_every_static_url_on_the_pages_carries_the_content_version`: на головній і на сторінці теми рівно три адреси
  `/static/`, і кожна закінчується `?v=` з хешем вмісту `static/`. Пропозиція `tasks/proposed/738-open-item-test-gap-a-test-that-renders-a-page-e-g.md`
  тим самим закрита, її можна видалити.

## Витрати
Одна сесія board. Додаткових сесій Claude і платних викликів моделей не було: усе працювало в local mode.
Агент один — overseer.

## Діапазон commit-ів
`94906cf` (задача в `doing/`) → `e5e5c23` (виправлення і тести) → commit закриття задачі.

## Відкладене
- Deploy на прототип — на ваше слово Сонькові. Текст запиту нижче.

## Рішення, які я ухвалив сам
- **Версія в адресі, а не заголовок `Cache-Control: no-cache`.** Задача дозволяла обидва способи. З версією браузер
  і далі тримає незмінні файли в cache і не питає про них сервер на кожній сторінці. А після deploy зі зміненими
  файлами адреса гарантовано нова, хоч би що вирішили браузер чи проміжний proxy. Зміна мала: одна змінна шаблонів
  у `server.py` і три адреси в шаблонах.
- **Версія — від вмісту файлів, а не від commit-а чи часу збирання образу.** Вона рахується при старті з того, що
  лежить у `static/`, і не потребує нових змінних середовища чи кроків збирання. Deploy, який не міняє `static/`,
  не скидає cache.
- **Три кандидати в уроки відкинуто.** Прогалину overseer-а закрито тестом. `type: ignore` прибрано: виправлено
  причину, а не обійдено gate. Урок «не було тесту, що натискає справжню скріпку» — поки один випадок, а регресійний
  тест лишається в наборі.
- **Тест моделює старий образ маленьким сервером** зі старими файлами, датованими три дні тому, як після
  `git archive`. Справжній старий знімок у тесті не потрібен: важить лише те, що стара сторінка просила адресу без
  версії.

## Готовий текст запиту Сонькові (на ваше слово)
Файл: `~/sonko/requests/2026-11-04-thinkhow-deploy-210-paperclip-cache.md`

```markdown
# ThinkHow: розгорнути задачу 210 (скріпка: свіжі /static після кожного deploy)

Що зробити: зібрати новий образ із гілки `unattended/work` (commit закриття задачі 210 або пізніший) і оновити ним
сервіс `thinkhow` і Job `thinkhow-learning`. Змінні — як у /home/lao/projects/thinkhow/docs/deploy.md, розділ 1.

    cd /home/lao/projects/thinkhow && git checkout unattended/work && git pull
    gcloud builds submit --tag $IMAGE .                                  # docs/deploy.md, розділ 5
    gcloud run services update thinkhow --region=$REGION --image=$IMAGE  # решта налаштувань сервісу не змінюється
    gcloud run jobs update thinkhow-learning --region=$REGION --image=$IMAGE

Нових змінних, прав, bucket-ів і бібліотек не треба.

Що вважати успіхом:
1. У коді сторінки теми (перегляд коду сторінки) адреси мають версію: `/static/conversation.js?v=…`,
   `/static/style.css?v=…`, `/static/rename.js?v=…`.
2. У тому самому браузері, де скріпка не працювала, без очищення cache: відкрити свою тему, натиснути скріпку —
   відкривається вікно вибору файла.
3. Вибрати невеликий файл .txt — у розмові з'являється репліка з 📎 і назвою файла.
4. У журналах Cloud Run для кроку 3 є рядок `http_request` з `route` `/topics/{uid}/{topic_id}/document` і жодного
   зі `status` 500.
Тестову тему після перевірки видалити.
```
