# Premise log — what we assume is true, and what depends on it

Governed by **Constitution Article 1** (verify before you commit) and **Article 8**
(a falsified premise re-opens whatever depended on it). Every level records its
load-bearing assumptions here — not only inside its own plan — so that when one turns
out false, the system can trace *everything it affects* instead of hoping someone
remembers.

(Markdown for now because every agent reads it natively and a human can scan it. If a
tool ever needs to query it programmatically, graduate it to JSON with the same
fields.)

## How to use — four operations

1. **RECORD.** When a plan states a load-bearing assumption about an external system
   or a chosen technology, add a row with status `unverified` and list what depends
   on it.
2. **VERIFY.** Attach evidence (a spike, a PoC, or docs + a captured runtime check)
   and set the status and the date checked. External-system checks go **stale after
   ~7 days**.
3. **FALSIFY & PROPAGATE.** If a check refutes the assumption, set status
   `falsified`, then mark every item in *depended-on-by* for review and route each to
   its level's human gate (Article 8).
4. **QUERY.** Before committing a plan: does it rely on any `unverified` or stale
   premise? Before deleting or changing something: what depends on it?

**Status:** `unverified` · `verified` · `accepted-as-risk` · `falsified`
**Level:** `slice` · `feature` · `architecture`

## Premises

| id | statement (one falsifiable sentence) | level | status | evidence | checked | depended-on-by |
|----|----|----|----|----|----|----|
| PR-01 | Vertex AI в `europe-west3` (або на `eu` multi-region endpoint) надає модель Gemini класу Pro з reasoning/thinking (не Flash — рішення власника), придатну для фасилітації: стрімінг відповіді + structured output за JSON Schema, без потреби в `global` endpoint | architecture | `unverified` | none — goals C1, P4; рішення власника 2026-10-18 (Flash уже тестували — замало); `docs/infra.md` (проєкт, регіон) | | `project:system-design`, `project:llm-gateway` |
| PR-02 | Один виклик Gemini на репліку (картка + карта проблеми + історія сесії в контексті) дає і відповідь людині з одним питанням без готової відповіді, і валідне структуроване оновлення (фаза, зміни карти) — у ≥95% реплік, укр. і англ. мовами; якість ведення оцінює власник, час лише записується (P4, запит 005) | architecture | `unverified` | none — research 01 L1200 (single prompt достатньо для ≤8 реплік), не перевірено на Gemini | | `project:system-design`, `feature:facilitation`, `feature:problem-map` |
| PR-03 | Довга сесія (до 60 реплік — оцінка архітектора; P2) разом із карткою, картою проблеми і пам'яттю досвіду в межах бюджету розміру (S6: вміщується у вікно контексту моделі із запасом; перевірка версії не дає Знанням його перевищити) вміщується в контекст моделі, а сумарні витрати — в межах кредитів Google (Q2; ціну сесії лише записуємо — P4) (≤10 людей, ≤50 сесій/тиждень) | architecture | `unverified` | none — goals P2, Q2 | | `project:system-design` |
| PR-04 | IAP перед Cloud Run пускає лише запрошені звичайні Gmail-акаунти (власний OAuth-клієнт «External», проєкт без організації), застосунок отримує перевірений email із підписаного заголовка, і потік відповіді (SSE) проходить крізь IAP без буферизації, а репліка, відправлена після закінчення сесії входу IAP, не губиться | architecture | `unverified` | none — goals C3, N2; docs.cloud.google.com/iap/docs/oauth-client-creation (managed client — лише для користувачів організації) | | `project:system-design`, `feature:access` |
| PR-05 | Люди повертаються до своєї проблеми в застосунку (листів немає) достатньо часто, щоб з'являлись відповіді «як вийшов крок?» і «чи врахував це розбір?» (D1 v2) | architecture | `accepted-as-risk` | власник обрав «без листів», знаючи, що людина, яка не повернулась, запиту не побачить: `.engine/goals/requests/002.md`, «Рішення власника» (2026-10-18); research 03 L117 | 2026-10-18 | `feature:steps-outcomes`, `project:D1` |
| PR-07 | Файли в Cloud Storage, які застосунок у Cloud Run і завдання навчання пишуть за правилом «кожен файл пише одна задача», зберігаються між перезапусками і читаються з Cloud Run з прийнятною затримкою | architecture | `unverified` | none — рішення власника «одна папка, свої файли» (2026-10-18); збереження об'єктів — основна задокументована властивість Cloud Storage; перевіряє walking skeleton | | `project:system-design` |
| PR-08 | Speech-to-Text Chirp 3 у регіоні `eu` з закріпленою мовою людини розпізнає надиктовані репліки (від 30 с до 5+ хв, у форматах браузерів) достатньо точно, щоб людина лише трохи правила текст, хоча б одним зі способів S8 з часом очікування, який власник вважає прийнятним після задачі 104 | feature | `unverified` | docs.cloud.google.com/speech-to-text/docs/models/chirp-3 (eu GA, uk-UA GA, language_codes; Recognize — до ~1 хв); квота v2 Streaming — подача в реальному часі, до 5 хв | 2026-10-18 | `feature:F13-voice` |

*(Add a new row whenever a plan states a new load-bearing assumption. Ensure the statement is a single falsifiable sentence. If an assumption is falsified, immediately flag all items in the 'depended-on-by' column for review.)*