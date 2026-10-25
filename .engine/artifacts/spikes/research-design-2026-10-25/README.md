# Проба задачі 303 перед архітектурою: де вирішувати «шукати чи ні» (2026-10-25)

Після відповіді власника (пошук дозволено, варіант обираю сам) — три питання до вибору будови. Модель `gemini-4-argon`,
Vertex `eu`, проєкт `pocket-lawyer-431614`. Розмова — тема власника `t-d824f508a729` (bucket users
`104839836105981044615/`), репліки до #17, #19, #21, #23, #25, #29 дослівно.

## 1. Окремий класифікатор перед фасилітатором (`classify.py`, `classify.out`)
Окремий виклик «чи це факт про світ, швидко чи глибоко»: `gemini-3.5-flash` — 4.4–8.6 с, `gemini-4-argon` — 5.5–9.3 с
на **кожну** репліку. Обидві моделі назвали #17, #19, #21 «world_fact», #25 — «none»; але глибину «deep» ставили
щоразу, а #23 (людина каже «чи це дасть ефект — невідомо», тобто це перевіряє реальність) — теж «world_fact».
Висновок: +5–9 с на кожну репліку і грубе рішення про глибину.

## 2. Пошук як інструмент у виклику фасилітатора (`inline.py`, `inline.out`)
Той самий виклик фасилітатора продукту (`system_instruction` картки `weighted-matrix` під роутером, `answer_schema`,
потік JSON) з `enterprise_web_search` і розділом «Факти про світ» в інструкції, проти того самого без інструмента:

| репліка | без пошуку: перший текст / разом | з пошуком: перший текст / разом | пошукові запити, джерела |
|---|---|---|---|
| #17 «Як це можна взнати?» | 12.1 / 16.3 с | 21.6 / 25.7 с | 2 запити, 2 джерела |
| #19 «мені треба якусь логіку» | 6.9 / 9.9 с | 24.0 / 28.2 с | 2, 3 |
| #21 «якби я знав… чи треба мені фасилітатор?» | 18.0 / 20.7 с | 36.3 / 43.8 с | 2, 4 |
| #25 (людина розповідає про себе) | 6.0 / 9.2 с | 5.7 / 8.9 с | не шукала |

Без пошуку фасилітатор на #17–#21 знову просить людину відібрати варіанти й оцінити самій. З пошуком — дає ринкові
строки (Mittelstand: цикл 3–9 місяців; біржі фрілансу, зокрема Malt, — 1–4 тижні; продаж мікростартапів через
Acquire.com чи Flippa — 1–3 місяці) і далі питає оцінку людини. На #25 модель не шукала і часу не додала. Потік JSON
разом з інструментом працює.
Висновок: рішення «шукати чи ні» ухвалює сама модель у своєму виклику; на репліках без пошуку це нічого не коштує.

## 3. Що приходить разом із відповіддю з пошуком (`entry.py`, `entry.out`)
- І Web Grounding for Enterprise, і Grounding with Google Search повертають `search_entry_point.rendered_content` —
  HTML ~5 КБ (стилі й «чипи» з пошуковими запитами). Сторінка WGE: «When you use Web Grounding for Enterprise, and
  you receive Search suggestions in your response, you must display the Search suggestions in production»; показувати
  «exactly as provided», поки видно відповідь, тієї самої ширини
  (https://docs.cloud.google.com/vertex-ai/generative-ai/docs/grounding/web-grounding-enterprise).
- Джерела (`grounding_chunks[].web`) — назва (домен) і посилання `vertexaisearch.cloud.google.com/grounding-api-redirect/…`;
  HEAD на нього дає 302 на справжню сторінку (meinauto.de, carwow.de…). Тож справжню адресу можна записати в тему, і
  вона не залежить від того, скільки живе посилання Google.
- `grounding_supports` є (4–7) — прив'язка речень до джерел; для показу джерел списком не потрібна.

## 4. Умови Google для відповідей з пошуком (перевірено 2026-10-25, master-critic і я дослівно)
Service Specific Terms (https://cloud.google.com/terms/service-terms) §20(k)(i) «Use Restrictions for Grounding with
Google Search»; §20(l): «Section 20(k) (Grounding with Google Search) also applies to Web Grounding for Enterprise»
(крім назви, індексу і пункту про 3 дні журналів). «Grounded Results» — уся відповідь, яку модель згенерувала з
пошуком. Дослівно:
- (1) «Customer will only display the Grounded Results with the associated Search Suggestion(s) to the End User who
  submitted the prompt; provided, however, that Customer may elect not to display Search Suggestions subject to the
  conditions set forth on the Pricing page.»
- (2) «Will not … cache, frame, syndicate, resell, analyze, train on, or otherwise learn from Grounded Results or Search
  Suggestions. … it is a violation of these terms … using programmatic or automated means to collect Links».
- (3) «Will not … copy, store … except that: (3.1) Customer may copy and store, for up to two (2) years, the Grounded
  Results: (3.1.1) that were displayed by Customer only to evaluate and optimize the display …; (3.1.2) in the chat
  history of an End User of the Customer Application only for the purpose of allowing that End User to view their chat
  history.»
- (4.1) «will not modify, or intersperse any other content with, the Grounded Results or Search Suggestions».

Що це означає для ThinkHow: відповідь із пошуком можна зберігати лише в історії розмови самої людини і показувати лише
їй. Нічне навчання (G3) не може її аналізувати; власник не може читати її в чужих темах (G4, P3); карта («факт»),
`research.json`, розгортання посилань і власний цикл глибокого дослідження (він переписує знайдене у звіт) — поза
дозволеним. Відповідь власника «обмежень немає» стосувалася ЄС, а не цих умов.

## 5. Пошук не від Google — що відомо без ключа (2026-10-25, з сайтів, не виміряно)
- **Tavily** (https://www.tavily.com/terms, /pricing): обмежень на зберігання результатів в умовах немає; «1,000 API
  credits / month» безплатно, далі «$0.008» за кредит; але §6.5 — Tavily і його постачальники можуть використовувати
  запити й результати «for purposes of training, improving, developing, and enhancing artificial intelligence models»;
  де обробляються дані — не сказано.
- **Brave Search API** (https://brave.com/search/api/): $5 за 1 000 запитів, $5 безплатних кредитів щомісяця; на
  питання «Can I store results or use them to train models?» — «Yes, with a [plan] that includes storage rights»
  (який план — на сторінці не сказано).
- Обидва потребують ключа API (реєстрація власником). Якість на німецькому й українському ринку не виміряна.
