# Розгортання walking skeleton ThinkHow (для власника)

Інструкція до задачі 105. Агент збудував код, образ і цю інструкцію, але нічого не розгортав: розгортання — ваша дія.
Наприкінці є **чекліст**. Він перевіряє PR-04, PR-07 і AC1, а відповідь на нього закриває задачу.

Порядок кроків важливий. Сервіс у хмарі читає Знання вже при старті, тому `seed` (крок 7) має пройти **до**
розгортання сервісу (крок 8). Інакше сервіс не стартує: `KnowledgeMissing: the Knowledge has no change record`.

## 1. Змінні

Проєкт `pocket-lawyer-431614`, регіон `europe-west3`, модель на endpoint Vertex `eu` (`gemini-4-argon`, ADR-0002).
Ці команди виконуються в одній сесії терміналу, бо всі наступні кроки користуються змінними.

```bash
export PROJECT=pocket-lawyer-431614
export REGION=europe-west3
export PROJECT_NUMBER=$(gcloud projects describe $PROJECT --format='value(projectNumber)')
export USERS_BUCKET=$PROJECT-thinkhow-users
export SYSTEM_BUCKET=$PROJECT-thinkhow-system
export OWNER_EMAIL=leskivmr@gmail.com
export IMAGE=$REGION-docker.pkg.dev/$PROJECT/thinkhow/thinkhow:skeleton
gcloud config set project $PROJECT
gcloud services enable run.googleapis.com iap.googleapis.com aiplatform.googleapis.com \
  cloudbuild.googleapis.com artifactregistry.googleapis.com cloudscheduler.googleapis.com
```

## 2. Журнали в ЄС

Журнали застосунку пишуться в bucket журналів у `europe-west3`, і маршрут `_Default` веде туди.

```bash
gcloud logging buckets create thinkhow-eu --location=$REGION --retention-days=30
gcloud logging sinks update _Default \
  logging.googleapis.com/projects/$PROJECT/locations/$REGION/buckets/thinkhow-eu
```

- Команда `gcloud logging settings update --storage-location` діє лише для організації чи теки. До проєкту без
  організації вона не застосовна.
- Bucket `_Required` (журнали аудиту самого Google) лишається глобальним, і змінити це не можна.

## 3. Bucket-и даних

Імена bucket-ів у Cloud Storage глобально унікальні. Тому код знає лише логічні `users` і `system`, а справжні
імена передаються змінними `THINKHOW_USERS_BUCKET` і `THINKHOW_SYSTEM_BUCKET`.

Для обох bucket-ів увімкнено uniform access і object versioning (старі версії файлів — M2 S2).

```bash
for b in $USERS_BUCKET $SYSTEM_BUCKET; do
  gcloud storage buckets create gs://$b --location=$REGION --uniform-bucket-level-access
  gcloud storage buckets update gs://$b --versioning
done
```

## 4. Service accounts і права

- `thinkhow-web`: пише теки людей і лише читає Знання.
- `thinkhow-job`: лише читає `users` і пише `system`, тобто Знання при `seed` і спостереження (M2 S2).

```bash
gcloud iam service-accounts create thinkhow-web --display-name="ThinkHow web"
gcloud iam service-accounts create thinkhow-job --display-name="ThinkHow learning job"
WEB=thinkhow-web@$PROJECT.iam.gserviceaccount.com
JOB=thinkhow-job@$PROJECT.iam.gserviceaccount.com
gcloud storage buckets add-iam-policy-binding gs://$USERS_BUCKET --member=serviceAccount:$WEB --role=roles/storage.objectAdmin
gcloud storage buckets add-iam-policy-binding gs://$SYSTEM_BUCKET --member=serviceAccount:$WEB --role=roles/storage.objectViewer
gcloud storage buckets add-iam-policy-binding gs://$USERS_BUCKET --member=serviceAccount:$JOB --role=roles/storage.objectViewer
gcloud storage buckets add-iam-policy-binding gs://$SYSTEM_BUCKET --member=serviceAccount:$JOB --role=roles/storage.objectAdmin
for sa in $WEB $JOB; do
  gcloud projects add-iam-policy-binding $PROJECT --member=serviceAccount:$sa --role=roles/aiplatform.user
done
```

## 5. Образ

Образ збирає Cloud Build у хмарі. Агент його не збирав, бо Docker на машині агента працює без доступу до демона.

```bash
gcloud artifacts repositories create thinkhow --repository-format=docker --location=$REGION
gcloud builds submit --tag $IMAGE .
```

За бажанням образ можна перевірити локально, до хмари.

```bash
docker build -t thinkhow:skeleton .
docker run --rm -p 127.0.0.1:8080:8080 -e THINKHOW_LOCAL=true -e THINKHOW_LOCAL_DIR=/tmp/data \
  -e THINKHOW_OWNER_EMAIL=owner@localhost thinkhow:skeleton
```

Після цього відкрийте `http://127.0.0.1:8080/`: має бути видно «Мої теми» і «Усі теми».

Друга перевірка — рядок використання з кодом 2:

```bash
docker run --rm thinkhow:skeleton python -m thinkhow.learning.job
```

## 6. OAuth-клієнт «External» для IAP

Ці кроки робляться в консолі. Звичайні Gmail-акаунти не пускає клієнт, яким керує Google: він лише для користувачів
організації (PR-04).

1. APIs & Services → OAuth consent screen: User type **External**, статус **Testing**. У Test users додайте кожен
   запрошений Gmail і свій.
2. APIs & Services → Credentials → Create credentials → OAuth client ID → Web application. Authorized redirect URI:
   `https://iap.googleapis.com/v1/oauth/clientIds/<CLIENT_ID>:handleRedirect`.
3. Security → Identity-Aware Proxy → Settings: вкажіть цей OAuth-клієнт (client ID і secret) для проєкту.
   Якщо проєкт не належить організації, API налаштувань IAP для всього проєкту відповідає `Project must belong to an
   organization`. Тоді клієнт задається на самому сервісі, після кроку 8: рядок Cloud Run `thinkhow` → ⋮ → Settings →
   Custom OAuth. Ознака, що клієнта немає: сервіс відповідає `502 Empty Google Account OAuth client ID(s)/secret(s)`.
   Ознака, що він є: `gcloud iap settings get --resource-type=cloud-run --service=thinkhow --region=$REGION`
   показує `oauthSettings`, а запит без входу отримує `302` на `accounts.google.com`.

## 7. Cloud Run Job `thinkhow-learning` і посів Знань

Job працює з того самого образу. За замовчуванням він запускає `analyze`, бо Scheduler кличе `:run` без змін.
`--task-timeout 3600s` — технічне значення агента: десятки сесій по кілька секунд на виклик моделі, із запасом.

```bash
gcloud run jobs deploy thinkhow-learning --image=$IMAGE --region=$REGION \
  --service-account=thinkhow-job@$PROJECT.iam.gserviceaccount.com \
  --set-env-vars=THINKHOW_USERS_BUCKET=$USERS_BUCKET,THINKHOW_SYSTEM_BUCKET=$SYSTEM_BUCKET,THINKHOW_OWNER_EMAIL=$OWNER_EMAIL \
  --command=python --args=-m,thinkhow.learning.job,analyze \
  --task-timeout=3600s --max-retries=0
```

Посів Знань робиться один раз. `--args` замінює весь збережений перелік аргументів, тому його треба писати повністю.
Цей запуск потребує права `run.jobs.runWithOverrides`, а воно є в ролі власника.

```bash
gcloud run jobs execute thinkhow-learning --region=$REGION --wait --args=-m,thinkhow.learning.job,seed
```

У журналі має з'явитися рядок `seed_done` з `"created": true`. Повторний запуск дає `false` і нічого не змінює.

Нова ревізія карток. Коли в образі змінилась тека `cards/` (наприклад, задача 302 додала 17 карток до Pre-mortem), а
Знання вже засіяно, запустіть Job з командою `cards` — він пише нову ревізію Знань з теки `cards/` образу:

```bash
gcloud run jobs update thinkhow-learning --region=$REGION --image=$IMAGE
gcloud run jobs execute thinkhow-learning --region=$REGION --wait --args=-m,thinkhow.learning.job,cards
```

У журналі має з'явитися рядок `cards_published` з номером нової ревізії (`"rev": 2` для першої такої). Повторний
запуск дає `"rev": null` і нічого не змінює. Сервіс читає Знання лише на старті, тому **після** `cards` розгорніть
сервіс (розділ 8) або перезапустіть його новою ревізією — інакше він і далі працює зі старою ревізією.

## 8. Cloud Run service `thinkhow`

Сервіс має рівно один екземпляр (`--max-instances 1`, рішення M2 «кожен файл пише одна задача»). Під час викладки
нової ревізії стара й нова можуть недовго працювати разом. Тому нову версію краще розгортати не посеред чиєїсь
сесії (прийнятий ризик M2).

`--timeout 3600` потрібен для довгого потоку відповіді.

```bash
gcloud run deploy thinkhow --image=$IMAGE --region=$REGION \
  --service-account=thinkhow-web@$PROJECT.iam.gserviceaccount.com \
  --set-env-vars=THINKHOW_USERS_BUCKET=$USERS_BUCKET,THINKHOW_SYSTEM_BUCKET=$SYSTEM_BUCKET,THINKHOW_OWNER_EMAIL=$OWNER_EMAIL,THINKHOW_IAP_AUDIENCE=/projects/$PROJECT_NUMBER/locations/europe-west3/services/thinkhow \
  --max-instances 1 --min-instances 0 --timeout 3600 \
  --iap --no-allow-unauthenticated
```

Аудиторія IAP для Cloud Run має форму `/projects/<PROJECT_NUMBER>/locations/europe-west3/services/thinkhow`. Цю
форму агент узяв із документації і не перевіряв. Якщо вхід працює, аудиторія правильна.

Сервісний агент IAP має право викликати сервіс. Цей крок агент теж не перевіряв:

```bash
gcloud run services add-iam-policy-binding thinkhow --region=$REGION \
  --member=serviceAccount:service-$PROJECT_NUMBER@gcp-sa-iap.iam.gserviceaccount.com --role=roles/run.invoker
```

Доступ через IAP треба дати кожній запрошеній людині і собі:

```bash
gcloud iap web add-iam-policy-binding --resource-type=cloud-run --service=thinkhow --region=$REGION \
  --member=user:<GMAIL> --role=roles/iap.httpsResourceAccessor
```

## 9. Cloud Scheduler: щоночі `analyze`

```bash
gcloud iam service-accounts create thinkhow-scheduler --display-name="ThinkHow scheduler"
SCHED=thinkhow-scheduler@$PROJECT.iam.gserviceaccount.com
gcloud run jobs add-iam-policy-binding thinkhow-learning --region=$REGION \
  --member=serviceAccount:$SCHED --role=roles/run.invoker
gcloud scheduler jobs create http thinkhow-analyze-nightly --location=$REGION \
  --schedule="0 3 * * *" --time-zone="Europe/Kyiv" --http-method=POST \
  --uri="https://run.googleapis.com/v2/projects/$PROJECT/locations/europe-west3/jobs/thinkhow-learning:run" \
  --oauth-service-account-email=$SCHED
```

## 10. Чекліст власника

Кожен пункт має три частини: що зробити, що має вийти, і що записати у відповідь у задачі
`tasks/blocked/105-walking-skeleton.md`.

**PR-04 — вхід і потік крізь IAP**
1. Відкрийте URL сервісу (`gcloud run services describe thinkhow --region=$REGION --format='value(status.url)'`) під
   запрошеним Gmail. Має відкритися Google-вхід, а після нього — при першому вході — сторінка «Мова» (задача 106):
   оберіть свою мову й натисніть «Зберегти». Далі — сторінка «Мої теми». Під вашим email видно ще й «Усі теми».
2. Спробуйте зайти Gmail-акаунтом, якого не запрошено. IAP має його не пустити.
3. Створіть тему і напишіть репліку. Відповідь має з'являтися потоком: текст росте, а не приходить цілим наприкінці.
   Кнопка «Надіслати» вимкнена, доки відповідь не закінчиться.
4. Перевірте, що репліка не губиться після кінця сесії IAP:
   - напишіть текст у поле, але не надсилайте;
   - видаліть cookie `GCP_IAP_AUTH_TOKEN…` цього сайту (або вийдіть з Google);
   - натисніть «Надіслати». Має з'явитися повідомлення «Потрібно увійти через Google», а текст лишитися в полі;
   - оновіть сторінку й увійдіть знову. Текст має бути в полі, і тепер його можна надіслати.

**PR-07 — файли в Cloud Storage**
5. Виконайте `gcloud storage ls -r gs://$USERS_BUCKET`. Мають бути `<uid>/profile.json`,
   `<uid>/<topic>/conversation.md` і `map.json`.
6. Розгорніть сервіс ще раз (повторіть команду кроку 8), коли ніхто не пише. Тема й розмова мають бути на місці.

**AC1 — увесь ланцюжок**
7. Нічого не завершуйте: кнопки «Завершити сесію» немає (задача 202). Запустіть
   `gcloud run jobs execute thinkhow-learning --region=$REGION --wait` — він бере всі репліки, яких ще не аналізував.
8. Виконайте `gcloud storage ls -r gs://$SYSTEM_BUCKET/learning/observations/`. Має бути файл `t<a>-t<b>.json` (діапазон
   нових реплік, наприклад `t1-t2.json`). У ньому поле `link` відкриває вашу репліку: `<URL сервісу><link>` веде на
   сторінку теми з потрібним `#t<n>`. Повторний запуск Job без нових реплік нового файлу не додає.
9. Подивіться журнали: Logs Explorer, bucket `thinkhow-eu`. Мають бути рядки `http_request`, `llm_call` (модель
   `gemini-4-argon`) і `analyze_done` без тексту розмов.

**F13 — мова і голос (задача 106)**
10. Відкрийте сторінку «Мова» (посилання вгорі). Російської в переліку немає. Оберіть іншу мову, збережіть — на
    головній видно «Мова: <назва>». Поверніть свою.
11. У своїй темі натисніть «🎤 Говорити». Браузер спитає доступ до мікрофона — дозвольте. Скажіть дві-три фрази
    своєю мовою, натисніть кнопку ще раз. Через кілька секунд текст має з'явитися в полі (дописатися до того, що
    там уже було). Виправте, якщо треба, і натисніть «Надіслати». Фасилітатор відповідає мовою з профілю.
12. Надиктуйте одну довгу репліку — кілька хвилин. Текст має з'явитися (зазвичай за 3–15 с). Так перевіряється, що
    запис на кілька мегабайтів проходить крізь IAP.
13. Те саме — з iPhone чи Mac у Safari (інший формат запису, mp4/AAC).
14. У журналах мають бути рядки `speech_call` (модель `gemini-3.5-transcribe`, `language`, `latency_ms`,
    `outcome`) — без тексту й без звуку.
Нових API і прав голос не потребує: розпізнавання йде через той самий Vertex AI (`aiplatform.googleapis.com`,
`roles/aiplatform.user`, ADR-0005). Якщо текст не з'являється, натисніть «Розпізнати ще раз» — запис лишається на
сторінці, доки не з'явиться текст.

**Що відповісти.** Якщо все так, відповідайте «так», і агент запише `SKELETON_VERIFIED`, PR-04 і PR-07 — `verified`.
Якщо щось не так, назвіть номер пункту і що побачили. Тоді premise стає `falsified`, і задача повертається до M2/M3
(Art. 8).
