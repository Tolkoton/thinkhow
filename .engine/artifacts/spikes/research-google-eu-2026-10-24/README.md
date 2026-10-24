# Перевірка premise задачі 303: що з досліджень Google працює в межах C1 (2026-10-24)

Проєкт `pocket-lawyer-431614`, модель `gemini-4-argon`, `google-genai` через ADC. Жодних даних людей у пробах:
питання про ціни авто, ринок електромобілів і оренду у Львові. Скрипти поруч.

## Що працює технічно (живі виклики)

| Проба | Endpoint | Результат |
|---|---|---|
| `ground.py`: Grounding with Google Search, «Скільки коштує Skoda Octavia Combi в Німеччині?» | `eu` | OK: ціна від 32 840 € з 4 джерелами (skoda-auto, carwow.de, meinauto.de, дилер); 2 пошукові запити німецькою, які модель склала сама |
| `ground_json.py`: те саме + `response_json_schema` (як у фасилітатора) | `eu` | OK за 17.8 с: валідний JSON, `grounding_metadata` з 2 запитами і 4 джерелами |
| `wge.py`: Web Grounding for Enterprise (`enterprise_web_search`) | `eu` | OK за 20.5 с, 12 джерел (skoda, mobile.de) |
| `wge.py` | `europe-west4` | 404: `gemini-4-argon` у цьому регіоні немає (як і в PR-01) |
| `models.py`: моделі з «research»/«deep» у назві | `eu`, `europe-west4`, `global` | жодної: Deep Research на Vertex немає |
| `deep.py`: власний цикл «план → 4 grounded-пошуки паралельно → синтез», Google Search | `eu` | 137.3 с; 13 пошукових запитів; 39 джерел; вхід 9 128 / вихід 10 242 токени (`deep_google_search.out`) |
| `deep_wge.py`: той самий цикл через WGE, український ринок (оренда у Львові) | `eu` | 128.7 с; 20 пошукових запитів; 30 джерел (ЛУН, DIM.RIA, OLX, ZAXID.NET, Радіо Свобода); вхід 6 317 / вихід 7 740 токенів (`deep_wge.out`) |

Ціна власного циклу (прайс Vertex, `.engine/sketches/gemini-eu.md`, крок 3: $2.2 вхід / $11 вихід за 1M до 30.11.2026):
модель ≈ $0.02 + $0.11 = $0.13; пошук — 13 запитів × $14 / 1 000 = $0.18 понад безплатні 5 000 запитів на місяць
(до них — $0). Разом ≈ $0.31 за глибоке дослідження, з 01.12.2026 ≈ $0.45. Цикл через WGE: модель ≈ $0.10, пошук 20 × $0.014 = $0.28,
разом ≈ $0.38. Швидкий пошук (один grounded-виклик) — 18–21 с, ≈ $0.01 моделі плюс 2 запити пошуку ($0.03 понад безплатні).
Найдовший підпошук обох циклів — 98–107 с: глибоке дослідження займає ~2 хв, тож людину треба попередити, що чекати.

## Що каже документація Google про ЄС (перевірено 2026-10-24, сторінки від 2026-10-22)

- **Grounding with Google Search:** у таблиці «Supported capabilities» Vertex рядок позначено «Not supported» для
  локальної обробки в усіх стовпцях, включно з `eu` multi-region; «If a capability or feature is not explicitly listed
  as supported, localized ML processing is not guaranteed»
  (https://docs.cloud.google.com/gemini-enterprise-agent-platform/resources/supported-capabilities). Service Specific
  Terms §20(k)(ii): Google збирає і зберігає в журналах «queries derived from End User prompts and contextual
  information … for up to three (3) days» (https://cloud.google.com/terms/service-terms). Тобто пошукові запити,
  складені з розмови людини, обробляються без гарантії ЄС і до 3 днів лежать у журналах Google.
- **Web Grounding for Enterprise:** terms §20(l) — ті самі умови, але індекс «GCP's web index» і пункт про 3 дні
  журналів видалено; сторінка WGE: «The service doesn't log customer data», «doesn't store customer data»
  (https://docs.cloud.google.com/vertex-ai/generative-ai/docs/grounding/web-grounding-enterprise). Таблиця локацій
  Gemini Enterprise: «Web Grounding for Enterprise — US/EU multi-regions: At-rest DRZ supported. MLP supported»
  (https://docs.cloud.google.com/gemini/enterprise/docs/locations). Але в таблиці Vertex рядка WGE немає, тож для
  Vertex `eu` локальну обробку явно не гарантовано.
- **Ціна обох:** для Gemini 3 і 4 — 5 000 запитів на місяць безплатно, далі $14 за 1 000 пошукових запитів; платиться
  лише відповідь, що повернула хоч одне джерело (https://cloud.google.com/vertex-ai/generative-ai/pricing).
- **Gemini Deep Research (агент Google):** лише Gemini Developer API (Interactions API,
  `generativelanguage.googleapis.com`), Preview; ~80 запитів, ~$1–3 за задачу (Max: до ~160, ~$3–7), більшість задач —
  до 20 хв (https://ai.google.dev/gemini-api/docs/deep-research). Умови Gemini API: дані «may be stored transiently or
  cached in any country in which Google or its agents maintain facilities» (https://ai.google.dev/gemini-api/terms) —
  ЄС не гарантовано. На Vertex його немає. У Gemini Enterprise є «deep_research» через `locations/global`, за
  allowlist, без підтвердженої резидентності ЄС.
- Інше: Custom Search JSON API закритий для нових клієнтів; Vertex AI Search шукає лише у власних даних, а не у
  відкритому інтернеті.

## Висновок для задачі
Технічно все потрібне є на `eu`: швидкий пошук з джерелами (обидва види grounding) і глибоке дослідження як власний
цикл із grounded-викликів, ~2 хв. Але **жоден спосіб шукати в інтернеті не має явної гарантії обробки в ЄС на Vertex**, а
запити до пошуку складаються з розмови людини. За задачею і C1 це питання власникові, не рішення агента.
